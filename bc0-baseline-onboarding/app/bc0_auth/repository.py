# -*- coding: utf-8 -*-
"""
Persistenz der Benutzerverwaltung — der einzige Ort mit SQL für Benutzer und Sitzungen.

Warum eine eigene Schicht
-------------------------
Die Anwendung läuft gegen zwei Datenbanken: PostgreSQL im Betrieb, SQLite in der
Entwicklung (siehe ``app.py``). Die Unterschiede — UUID gegen Text, ``BOOLEAN``
gegen ``INTEGER``, ``TIMESTAMPTZ`` gegen ISO-Zeichenkette — sind hier gebündelt.
Oberhalb dieser Schicht kommt keine dieser Eigenheiten mehr vor.

Verbindungsfabrik
-----------------
Das Repository öffnet keine Verbindung selbst, sondern bekommt im Konstruktor eine
Funktion übergeben, die eine liefert (``verbindung_erzeugen``). Erwartet wird die
in ``app.py`` definierte Schnittstelle: ``execute(sql, params)`` mit ``?`` als
Platzhalter, ``commit()``, ``close()``, Zeilen als Mapping.

Zwei Gründe für diese Bauform: Es entsteht kein Import-Zyklus zwischen ``app.py``
und diesem Paket, und die Tests können eine eigene, flüchtige SQLite-Datenbank
übergeben, ohne die Anwendung zu starten.

Sitzungsschlüssel
-----------------
In ``app_sitzungen`` steht **nicht** der Sitzungsschlüssel, sondern nur sein
SHA-256-Abdruck. Wer die Datenbank lesen kann — etwa über ein Backup — kann damit
keine fremde Sitzung übernehmen.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Callable, Iterable, List, Optional, Tuple

from .modelle import Benutzer, Rolle, Sitzung

# Typ der Verbindungsfabrik: eine parameterlose Funktion, die ein Verbindungsobjekt liefert.
VerbindungsFabrik = Callable[[], object]


# --------------------------------------------------------------------------- #
# DDL
# --------------------------------------------------------------------------- #
# Namensregel: Tabellen der Anwendungsschicht tragen das Präfix `app_`. Damit ist
# auf einen Blick unterscheidbar, was Fachdaten sind (companies, ref_prozesse,
# bitkom_bewertungen) und was nur dem Betrieb der Oberfläche dient. Die Rollen der
# Bounded Contexts (bc1_role …) lesen die Fachdaten, nicht diese Tabellen.

# Die DDL steht als Folge einzelner Anweisungen und nicht als ein Skript-Text:
# SQLite führt über `execute` genau eine Anweisung aus. Einzelanweisungen laufen
# über beide Backends und über die Testverbindung gleichermaßen.

DDL_POSTGRES = (
    """
    CREATE TABLE IF NOT EXISTS app_benutzer (
      benutzer_id       TEXT PRIMARY KEY,
      email             TEXT NOT NULL UNIQUE,
      name              TEXT NOT NULL,
      passwort_hash     TEXT NOT NULL,
      rolle             TEXT NOT NULL CHECK (rolle IN ('benutzer','admin')),
      aktiv             BOOLEAN NOT NULL DEFAULT TRUE,
      angelegt_am       TIMESTAMPTZ NOT NULL DEFAULT now(),
      letzte_anmeldung  TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_benutzer_mandanten (
      benutzer_id  TEXT NOT NULL REFERENCES app_benutzer(benutzer_id) ON DELETE CASCADE,
      company_id   UUID NOT NULL REFERENCES companies(company_id)     ON DELETE CASCADE,
      PRIMARY KEY (benutzer_id, company_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_sitzungen (
      sitzung_id         TEXT PRIMARY KEY,
      benutzer_id        TEXT NOT NULL REFERENCES app_benutzer(benutzer_id) ON DELETE CASCADE,
      schluessel_abdruck TEXT NOT NULL UNIQUE,
      angelegt_am        TIMESTAMPTZ NOT NULL DEFAULT now(),
      laeuft_ab          TIMESTAMPTZ NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sitzung_benutzer ON app_sitzungen(benutzer_id)",
    """
    CREATE TABLE IF NOT EXISTS app_anmeldeversuche (
      abdruck       TEXT PRIMARY KEY,
      art           TEXT NOT NULL CHECK (art IN ('email','ip')),
      fehlversuche  INTEGER NOT NULL DEFAULT 0,
      letzter_am    TIMESTAMPTZ NOT NULL,
      gesperrt_bis  TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_anmeldeversuch_alt ON app_anmeldeversuche(letzter_am)",
)

DDL_SQLITE = (
    """
    CREATE TABLE IF NOT EXISTS app_benutzer (
      benutzer_id       TEXT PRIMARY KEY,
      email             TEXT NOT NULL UNIQUE,
      name              TEXT NOT NULL,
      passwort_hash     TEXT NOT NULL,
      rolle             TEXT NOT NULL CHECK (rolle IN ('benutzer','admin')),
      aktiv             INTEGER NOT NULL DEFAULT 1,
      angelegt_am       TEXT NOT NULL,
      letzte_anmeldung  TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_benutzer_mandanten (
      benutzer_id  TEXT NOT NULL,
      company_id   TEXT NOT NULL,
      PRIMARY KEY (benutzer_id, company_id),
      FOREIGN KEY (benutzer_id) REFERENCES app_benutzer(benutzer_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_sitzungen (
      sitzung_id         TEXT PRIMARY KEY,
      benutzer_id        TEXT NOT NULL,
      schluessel_abdruck TEXT NOT NULL UNIQUE,
      angelegt_am        TEXT NOT NULL,
      laeuft_ab          TEXT NOT NULL,
      FOREIGN KEY (benutzer_id) REFERENCES app_benutzer(benutzer_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sitzung_benutzer ON app_sitzungen(benutzer_id)",
    """
    CREATE TABLE IF NOT EXISTS app_anmeldeversuche (
      abdruck       TEXT PRIMARY KEY,
      art           TEXT NOT NULL CHECK (art IN ('email','ip')),
      fehlversuche  INTEGER NOT NULL DEFAULT 0,
      letzter_am    TEXT NOT NULL,
      gesperrt_bis  TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_anmeldeversuch_alt ON app_anmeldeversuche(letzter_am)",
)


# --------------------------------------------------------------------------- #
# Hilfsfunktionen für die Unterschiede zwischen den Backends
# --------------------------------------------------------------------------- #
def _jetzt() -> _dt.datetime:
    """Aktueller Zeitpunkt in UTC — bewusst zeitzonenbehaftet."""
    return _dt.datetime.now(_dt.timezone.utc)


def _als_zeitpunkt(wert) -> _dt.datetime:
    """Normalisiert einen Zeitstempel aus der Datenbank auf ``datetime`` in UTC.

    PostgreSQL liefert bereits ein ``datetime``; SQLite eine ISO-Zeichenkette.
    Ein Wert ohne Zeitzone wird als UTC gelesen — die Anwendung schreibt
    ausschließlich UTC.
    """
    if isinstance(wert, _dt.datetime):
        zeitpunkt = wert
    else:
        zeitpunkt = _dt.datetime.fromisoformat(str(wert))
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=_dt.timezone.utc)
    return zeitpunkt


def _als_wahrheitswert(wert) -> bool:
    """Normalisiert ``BOOLEAN`` (PostgreSQL) und ``INTEGER`` (SQLite)."""
    if isinstance(wert, bool):
        return wert
    return str(wert) not in ("0", "False", "false", "None", "")


class _Basis:
    """Gemeinsames Verhalten beider Repositories."""

    def __init__(self, verbindung_erzeugen: VerbindungsFabrik, ist_postgres: bool):
        """Merkt sich die Verbindungsfabrik und den Dialektschalter.

        Es wird eine **Fabrik** hinterlegt, keine offene Verbindung. Jede
        Methode öffnet und schliesst ihre eigene; das Paket hält keinen
        Verbindungspool und keinen Zustand ueber Anfragen hinweg. Bei der
        Nutzungsgröße dieser Anwendung ist das der einfachere Weg, und er
        verhindert die häufigste Fehlerklasse an dieser Stelle: eine
        Verbindung, die nach einer Ausnahme in einer offenen Transaktion
        hängenbleibt.
        """
        self._verbindung_erzeugen = verbindung_erzeugen
        self._pg = bool(ist_postgres)

    # Kleine Helfer, damit die Methoden unten lesbar bleiben.
    def _oeffnen(self):
        """Öffnet eine frische Verbindung.

        Jede aufrufende Methode ist verpflichtet, sie in ``try/finally`` wieder
        zu schliessen — das ist im ganzen Modul durchgehalten.
        """
        return self._verbindung_erzeugen()

    @property
    def _wahr(self):
        """Literal für „wahr" im jeweiligen Backend."""
        return True if self._pg else 1

    @property
    def _uuid_param(self) -> str:
        """Platzhalter für eine ``company_id``.

        In PostgreSQL ist die Spalte vom Typ ``UUID``; der Parameter muss darum
        ausdrücklich gecastet werden. In SQLite ist sie Text.
        """
        return "?::uuid" if self._pg else "?"

    @property
    def _uuid_lesen(self) -> str:
        """Ausdruck, der eine ``company_id`` als Text liefert."""
        return "company_id::text AS company_id" if self._pg else "company_id"


class BenutzerRepository(_Basis):
    """Lesen und Schreiben von Benutzern samt ihrer Mandantenzuordnung."""

    def tabellen_anlegen(self) -> None:
        """Legt die Tabellen an, falls sie fehlen (idempotent).

        Wird beim Start der Anwendung aufgerufen. Bewusst ``IF NOT EXISTS`` und
        kein Migrationswerkzeug: Der Umfang rechtfertigt keines, und der
        Vollstand ist in ``schema_v1.2.sql`` dokumentiert.
        """
        verbindung = self._oeffnen()
        try:
            for anweisung in DDL_POSTGRES if self._pg else DDL_SQLITE:
                verbindung.execute(anweisung)
            verbindung.commit()
        finally:
            verbindung.close()

    # ---------------- Lesen ----------------

    def _mandanten_lesen(self, verbindung, benutzer_id: str) -> frozenset:
        """Liest die Mandantenzuordnung eines Benutzers.

        Nimmt die Verbindung als Parameter statt selbst eine zu öffnen: Die
        Methode wird aus :meth:`_zu_benutzer` heraus je Zeile gerufen. Beim
        Auflisten von zwanzig Konten wären das sonst zwanzig zusätzliche
        Verbindungen.

        Das Ergebnis ist ein ``frozenset`` von Zeichenketten. Unveränderlich,
        weil es in :class:`~bc0_auth.modelle.Benutzer` landet und dort die
        Grundlage der Mandantentrennung ist — ein Aufrufer soll seine eigenen
        Rechte nicht nachträglich erweitern können. Die ausdrückliche
        ``str``-Umwandlung ist nötig, weil PostgreSQL ein ``UUID``-Objekt
        liefert und SQLite eine Zeichenkette; ohne sie schlüge der Vergleich
        in ``darf_mandanten_sehen`` nur im Betrieb fehl.
        """
        zeilen = verbindung.execute(
            "SELECT " + self._uuid_lesen + " FROM app_benutzer_mandanten WHERE benutzer_id=?",
            (benutzer_id,),
        ).fetchall()
        return frozenset(str(z["company_id"]) for z in zeilen)

    def _zu_benutzer(self, verbindung, zeile) -> Benutzer:
        """Formt eine Datenbankzeile in die Datenklasse :class:`Benutzer` um.

        Die einzige Stelle, an der das geschieht — deshalb ist hier auch
        sichergestellt, dass ``passwort_hash`` **nicht** mitwandert. Die
        Datenklasse hat kein Feld dafür; wer den Hash braucht (nur
        :meth:`finde_per_email`), bekommt ihn getrennt.

        ``Rolle.aus_text`` weist einen unbekannten Rollennamen ab, statt still
        auf ``benutzer`` zurückzufallen. Eine unlesbare Rolle ist ein Fehler
        im Datenbestand und soll als solcher auffallen.
        """
        return Benutzer(
            benutzer_id=zeile["benutzer_id"],
            email=zeile["email"],
            name=zeile["name"],
            rolle=Rolle.aus_text(zeile["rolle"]),
            mandanten=self._mandanten_lesen(verbindung, zeile["benutzer_id"]),
            aktiv=_als_wahrheitswert(zeile["aktiv"]),
        )

    def finde_per_email(self, email: str) -> Optional[Tuple[Benutzer, str]]:
        """Sucht einen Benutzer für die Anmeldung.

        Returns:
            Ein Paar aus Benutzer und gespeichertem Passwort-Hash, oder ``None``.
            Der Hash wird bewusst getrennt zurückgegeben und nicht in
            :class:`Benutzer` geführt — so kann er nicht versehentlich in einer
            API-Antwort landen.
        """
        verbindung = self._oeffnen()
        try:
            zeile = verbindung.execute(
                "SELECT * FROM app_benutzer WHERE email=?",
                ((email or "").strip().lower(),),
            ).fetchone()
            if not zeile:
                return None
            return self._zu_benutzer(verbindung, zeile), zeile["passwort_hash"]
        finally:
            verbindung.close()

    def finde_per_id(self, benutzer_id: str) -> Optional[Benutzer]:
        """Lädt einen Benutzer ueber seine ID.

        Der Weg, ueber den die Middleware bei **jeder** Anfrage den Benutzer
        neu lädt. Genau daher wirken Sperre, Rollenwechsel und entzogene
        Mandanten sofort und ohne Neuanmeldung (Tests ``test_auth.py`` Nr. 27
        und ``test_mandantenfilter.py`` Nr. 11).
        """
        verbindung = self._oeffnen()
        try:
            zeile = verbindung.execute(
                "SELECT * FROM app_benutzer WHERE benutzer_id=?", (benutzer_id,)
            ).fetchone()
            return self._zu_benutzer(verbindung, zeile) if zeile else None
        finally:
            verbindung.close()

    def alle(self) -> List[Benutzer]:
        """Liefert alle Konten, nach E-Mail sortiert.

        Ohne Seitenteilung — bei einer zweistelligen Zahl von Konten
        angemessen. Würde die Anwendung auf Hunderte Konten wachsen, waere
        dies die Stelle, an der es zuerst weh täte: :meth:`_zu_benutzer` ruft
        je Zeile :meth:`_mandanten_lesen`, also N+1 Abfragen auf **einer**
        Verbindung.
        """
        verbindung = self._oeffnen()
        try:
            zeilen = verbindung.execute(
                "SELECT * FROM app_benutzer ORDER BY email"
            ).fetchall()
            return [self._zu_benutzer(verbindung, z) for z in zeilen]
        finally:
            verbindung.close()

    def anzahl(self) -> int:
        """Anzahl angelegter Benutzer — Grundlage für den Erststart-Hinweis."""
        verbindung = self._oeffnen()
        try:
            return int(
                verbindung.execute("SELECT COUNT(*) AS n FROM app_benutzer").fetchone()["n"]
            )
        finally:
            verbindung.close()

    # ---------------- Schreiben ----------------

    def anlegen(
        self,
        email: str,
        name: str,
        passwort_hash: str,
        rolle: Rolle,
        mandanten: Iterable[str] = (),
    ) -> Benutzer:
        """Legt einen Benutzer an und verknüpft ihn mit seinen Mandanten.

        Raises:
            ValueError: wenn die E-Mail bereits vergeben ist.
        """
        email = (email or "").strip().lower()
        if not email:
            raise ValueError("Eine E-Mail-Adresse ist erforderlich.")
        benutzer_id = str(uuid.uuid4())
        verbindung = self._oeffnen()
        try:
            if verbindung.execute(
                "SELECT 1 AS x FROM app_benutzer WHERE email=?", (email,)
            ).fetchone():
                raise ValueError("Diese E-Mail-Adresse ist bereits vergeben: %s" % email)
            verbindung.execute(
                "INSERT INTO app_benutzer(benutzer_id,email,name,passwort_hash,rolle,aktiv,angelegt_am) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    benutzer_id,
                    email,
                    (name or email).strip(),
                    passwort_hash,
                    rolle.value,
                    self._wahr,
                    _jetzt() if self._pg else _jetzt().isoformat(),
                ),
            )
            self._mandanten_schreiben(verbindung, benutzer_id, mandanten)
            verbindung.commit()
            zeile = verbindung.execute(
                "SELECT * FROM app_benutzer WHERE benutzer_id=?", (benutzer_id,)
            ).fetchone()
            return self._zu_benutzer(verbindung, zeile)
        finally:
            verbindung.close()

    def _mandanten_schreiben(self, verbindung, benutzer_id: str, mandanten: Iterable[str]) -> None:
        """Ersetzt die Mandantenzuordnung — löschen, dann neu einfuegen.

        Ersetzen statt Abgleichen, weil die Zuordnung keine eigenen Attribute
        trägt: Es gibt nichts, was beim Löschen verlorenginge.

        Zwei Dinge sind hier bewusst:

        * Die Menge wird ueber ein ``set`` geführt und von Leereinträgen
          befreit. Eine doppelt geschickte ID würde sonst am
          Primärschlüssel scheitern und die ganze Zuordnung zerreißen.
        * Es wird **nicht** committet. Der Aufrufer entscheidet, ob dies Teil
          einer größeren Transaktion ist — beim Anlegen eines Benutzers
          gehören Konto und Zuordnung in einen Commit.
        """
        verbindung.execute(
            "DELETE FROM app_benutzer_mandanten WHERE benutzer_id=?", (benutzer_id,)
        )
        for mandant_id in {str(m).strip() for m in (mandanten or ()) if str(m).strip()}:
            verbindung.execute(
                "INSERT INTO app_benutzer_mandanten(benutzer_id,company_id) VALUES(?,"
                + self._uuid_param
                + ")",
                (benutzer_id, mandant_id),
            )

    def mandanten_setzen(self, benutzer_id: str, mandanten: Iterable[str]) -> None:
        """Ersetzt die Mandantenzuordnung eines Benutzers vollständig."""
        verbindung = self._oeffnen()
        try:
            self._mandanten_schreiben(verbindung, benutzer_id, mandanten)
            verbindung.commit()
        finally:
            verbindung.close()

    def passwort_setzen(self, benutzer_id: str, passwort_hash: str) -> None:
        """Schreibt einen **bereits abgeleiteten** Hash.

        Der Parameter heisst ``passwort_hash`` und nicht ``passwort``: Diese
        Schicht sieht nie einen Klartext. Die Ableitung geschieht im
        :class:`~bc0_auth.dienst.AuthDienst`, die Längenprüfung in
        :mod:`bc0_auth.passwoerter`. Wer hier einen Klartext hereinreicht,
        speichert ihn im Klartext — deshalb steht der Hinweis hier.

        Das Beenden der laufenden Sitzungen gehört **nicht** hierher, sondern
        in den Dienst (``AuthDienst.passwort_aendern``), der beides zusammen
        auslöst. Diese Methode allein ist kein vollständiger
        Passwortwechsel.
        """
        verbindung = self._oeffnen()
        try:
            verbindung.execute(
                "UPDATE app_benutzer SET passwort_hash=? WHERE benutzer_id=?",
                (passwort_hash, benutzer_id),
            )
            verbindung.commit()
        finally:
            verbindung.close()

    def name_setzen(self, benutzer_id: str, name: str) -> None:
        """Ändert den Anzeigenamen.

        Der Name erscheint in ``freigegeben_durch``. Er wird deshalb geändert und
        nicht historisiert: Wer eine Freigabe erteilt hat, steht über die
        ``benutzer_id`` fest, unabhängig davon, wie die Person heute heißt.
        """
        verbindung = self._oeffnen()
        try:
            verbindung.execute(
                "UPDATE app_benutzer SET name=? WHERE benutzer_id=?",
                ((name or "").strip(), benutzer_id),
            )
            verbindung.commit()
        finally:
            verbindung.close()

    def rolle_setzen(self, benutzer_id: str, rolle: Rolle) -> None:
        """Setzt die Rolle.

        Der Parameter ist die Aufzählung :class:`Rolle`, keine Zeichenkette —
        ein Tippfehler fällt damit beim Aufruf auf und nicht erst als
        unlesbare Zeile beim naechsten Laden.

        Die Änderung wirkt ohne Neuanmeldung; die Middleware lädt den
        Benutzer je Anfrage neu. Dass ein Admin sich nicht selbst herabstufen
        kann, wird eine Schicht höher geprüft (``routen.py``), nicht hier —
        das Repository kennt den Handelnden nicht.
        """
        verbindung = self._oeffnen()
        try:
            verbindung.execute(
                "UPDATE app_benutzer SET rolle=? WHERE benutzer_id=?",
                (rolle.value, benutzer_id),
            )
            verbindung.commit()
        finally:
            verbindung.close()

    def aktiv_setzen(self, benutzer_id: str, aktiv: bool) -> None:
        """Aktiviert oder sperrt ein Konto.

        Eine Sperre wirkt sofort für neue Anmeldungen. Bestehende Sitzungen
        werden vom :class:`~bc0_auth.dienst.AuthDienst` beim nächsten Auflösen
        verworfen, weil dieser den Benutzer jedes Mal frisch lädt.
        """
        wert = bool(aktiv) if self._pg else (1 if aktiv else 0)
        verbindung = self._oeffnen()
        try:
            verbindung.execute(
                "UPDATE app_benutzer SET aktiv=? WHERE benutzer_id=?", (wert, benutzer_id)
            )
            verbindung.commit()
        finally:
            verbindung.close()

    def anmeldung_vermerken(self, benutzer_id: str) -> None:
        """Hält den Zeitpunkt der letzten erfolgreichen Anmeldung fest.

        Rein informativ — die Spalte steuert nichts. Sie ist derzeit der
        einzige Anhaltspunkt dafür, ob ein Konto ueberhaupt genutzt wird, und
        damit ein schwacher Ersatz für das fehlende Änderungsprotokoll.

        Der Zeitstempel geht für PostgreSQL als ``datetime`` und für SQLite
        als ISO-Zeichenkette hinaus; SQLite kennt keinen Zeitstempeltyp.
        """
        verbindung = self._oeffnen()
        try:
            verbindung.execute(
                "UPDATE app_benutzer SET letzte_anmeldung=? WHERE benutzer_id=?",
                (_jetzt() if self._pg else _jetzt().isoformat(), benutzer_id),
            )
            verbindung.commit()
        finally:
            verbindung.close()


class SitzungsRepository(_Basis):
    """Anlegen, Auflösen und Beenden von Sitzungen."""

    def anlegen(self, benutzer_id: str, schluessel_abdruck: str, dauer: _dt.timedelta) -> Sitzung:
        """Legt eine Sitzung an und gibt sie zurück.

        Der Parameter ist der **Abdruck** des Sitzungsschlüssels, nicht der
        Schlüssel. Der Schlüssel selbst erreicht diese Schicht nie und steht
        nirgends in der Datenbank — wer ``app_sitzungen`` liest, kann keine
        Sitzung übernehmen (Test ``test_auth.py`` Nr. 22).

        Der Ablauf wird beim Anlegen **ausgerechnet und gespeichert**, statt
        ihn später aus ``angelegt_am`` plus der aktuellen Konfiguration
        abzuleiten. Sonst würde eine Änderung der Sitzungsdauer rückwirkend
        alle bestehenden Sitzungen verlängern oder beenden.

        Args:
            benutzer_id: Konto, zu dem die Sitzung gehört.
            schluessel_abdruck: SHA-256-Abdruck aus
                :func:`bc0_auth.passwoerter.schluessel_abdruck`.
            dauer: Gültigkeit ab jetzt.
        """
        sitzung_id = str(uuid.uuid4())
        angelegt = _jetzt()
        ablauf = angelegt + dauer
        verbindung = self._oeffnen()
        try:
            verbindung.execute(
                "INSERT INTO app_sitzungen(sitzung_id,benutzer_id,schluessel_abdruck,angelegt_am,laeuft_ab) "
                "VALUES(?,?,?,?,?)",
                (
                    sitzung_id,
                    benutzer_id,
                    schluessel_abdruck,
                    angelegt if self._pg else angelegt.isoformat(),
                    ablauf if self._pg else ablauf.isoformat(),
                ),
            )
            verbindung.commit()
        finally:
            verbindung.close()
        return Sitzung(sitzung_id, benutzer_id, angelegt, ablauf)

    def finde_per_abdruck(self, schluessel_abdruck: str) -> Optional[Sitzung]:
        """Sucht eine Sitzung ueber den Abdruck ihres Schlüssels.

        Der Weg, den jede angemeldete Anfrage nimmt. Die Suche läuft über die
        indizierte Spalte ``schluessel_abdruck``; ein Abgleich ueber alle
        Zeilen findet nicht statt.

        Gibt die Sitzung **auch dann** zurück, wenn sie abgelaufen ist. Die
        Ablaufprüfung liegt in :meth:`Sitzung.ist_abgelaufen` und wird vom
        Dienst ausgewertet — hier wird gelesen, nicht entschieden.
        """
        verbindung = self._oeffnen()
        try:
            zeile = verbindung.execute(
                "SELECT * FROM app_sitzungen WHERE schluessel_abdruck=?", (schluessel_abdruck,)
            ).fetchone()
            if not zeile:
                return None
            return Sitzung(
                sitzung_id=zeile["sitzung_id"],
                benutzer_id=zeile["benutzer_id"],
                angelegt_am=_als_zeitpunkt(zeile["angelegt_am"]),
                laeuft_ab=_als_zeitpunkt(zeile["laeuft_ab"]),
            )
        finally:
            verbindung.close()

    def beenden(self, schluessel_abdruck: str) -> None:
        """Beendet genau eine Sitzung — die Abmeldung."""
        verbindung = self._oeffnen()
        try:
            verbindung.execute(
                "DELETE FROM app_sitzungen WHERE schluessel_abdruck=?", (schluessel_abdruck,)
            )
            verbindung.commit()
        finally:
            verbindung.close()

    def alle_beenden(self, benutzer_id: str) -> None:
        """Beendet alle Sitzungen eines Benutzers — etwa nach einem Passwortwechsel."""
        verbindung = self._oeffnen()
        try:
            verbindung.execute("DELETE FROM app_sitzungen WHERE benutzer_id=?", (benutzer_id,))
            verbindung.commit()
        finally:
            verbindung.close()

    def abgelaufene_entfernen(self) -> int:
        """Räumt abgelaufene Sitzungen ab.

        Wird beim Anmelden mitausgeführt. So bleibt die Tabelle klein, ohne dass
        ein eigener Hintergrundlauf nötig wäre.
        """
        verbindung = self._oeffnen()
        try:
            jetzt = _jetzt() if self._pg else _jetzt().isoformat()
            zeiger = verbindung.execute("DELETE FROM app_sitzungen WHERE laeuft_ab<=?", (jetzt,))
            verbindung.commit()
            return getattr(zeiger, "rowcount", 0) or 0
        finally:
            verbindung.close()


class AnmeldeversuchRepository(_Basis):
    """Zaehlt Fehlversuche und haelt die Sperre — je E-Mail und je IP.

    WARUM DIE TABELLE NUR ABDRUECKE FUEHRT
      Gespeichert wird der SHA-256-Abdruck des Schluessels (``email:<adresse>``
      oder ``ip:<adresse>``), nicht der Schluessel selbst — dieselbe Regel wie
      bei ``app_sitzungen``, und hier aus einem zusaetzlichen Grund: Der Zaehler
      entsteht **auch fuer Adressen, die es nicht gibt**. Wer die Anmeldemaske
      mit fremden E-Mail-Adressen befuellt, wuerde sonst dafuer sorgen, dass BC0
      genau diese Adressen dauerhaft ablegt — personenbezogene Daten von
      Menschen, die mit dem Projekt nichts zu tun haben.

      **Die Tabelle zaehlt, das Protokoll erzaehlt.** Wer wissen will, WER es
      versucht hat, liest das Serverprotokoll; dort steht die Adresse im
      Klartext, und dort ist sie nach dem Rotieren wieder weg. Wer zu einer
      bekannten Adresse nachsehen will, ob sie gerade gesperrt ist, bildet
      ihren Abdruck und fragt danach.

    WARUM ZWEI ZAEHLER UND NICHT EINER
      Nur je E-Mail zu zaehlen liesse jemanden EIN Passwort gegen alle zwoelf
      Konten durchprobieren — kein Zaehler erreicht dabei seine Schwelle. Nur
      je IP zu zaehlen liesse sich mit wechselnden Adressen umgehen. Beide
      Zaehler laufen deshalb nebeneinander, und **der strengere entscheidet**.
    """

    @staticmethod
    def abdruck(art: str, wert: str) -> str:
        """Bildet den Ablageschluessel aus Art und Wert.

        E-Mail-Adressen werden vorher kleingeschrieben und beschnitten: Sonst
        waeren ``A@b.de`` und ``a@b.de`` zwei Zaehler, und die Anmeldung sucht
        den Benutzer ohnehin unabhaengig von der Schreibweise.
        """
        import hashlib

        roh = (wert or "").strip()
        if art == "email":
            roh = roh.lower()
        return hashlib.sha256(("%s:%s" % (art, roh)).encode("utf-8")).hexdigest()

    def stand(self, abdruck: str) -> Tuple[int, Optional[_dt.datetime]]:
        """Liefert ``(fehlversuche, gesperrt_bis)`` — ohne zu bewerten.

        Ob eine Sperre noch laeuft, entscheidet der Dienst. Hier wird gelesen,
        nicht entschieden — dieselbe Aufteilung wie bei
        :meth:`SitzungsRepository.finde_per_abdruck`.
        """
        verbindung = self._oeffnen()
        try:
            zeile = verbindung.execute(
                "SELECT fehlversuche, gesperrt_bis FROM app_anmeldeversuche WHERE abdruck=?",
                (abdruck,),
            ).fetchone()
            if not zeile:
                return 0, None
            bis = zeile["gesperrt_bis"]
            return int(zeile["fehlversuche"] or 0), (_als_zeitpunkt(bis) if bis else None)
        finally:
            verbindung.close()

    def fehlversuch(
        self, abdruck: str, art: str, fenster: _dt.timedelta,
        sperre_ab: int, sperrdauer: _dt.timedelta,
    ) -> Tuple[int, Optional[_dt.datetime]]:
        """Zaehlt einen Fehlversuch und sperrt, wenn die Schwelle faellt.

        Das gleitende Fenster ist der Grund, warum ``letzter_am`` mitgefuehrt
        wird: Ein Zaehler, der **nie** verfaellt, sperrt irgendwann jeden, der
        sich ueber Monate hinweg fuenfmal vertippt hat. Liegt der letzte
        Fehlversuch laenger als ``fenster`` zurueck, wird bei 1 neu begonnen.

        Beim Erreichen von ``sperre_ab`` wird die Sperre gesetzt **und der
        Zaehler auf 0 zurueckgesetzt**. Nach Ablauf der Sperre beginnt das
        Zaehlen dadurch von vorn — sonst schlaege die naechste Sperre schon
        beim ersten weiteren Fehlversuch zu, und aus der befristeten Sperre
        waere eine dauerhafte geworden.

        Returns:
            ``(fehlversuche_danach, gesperrt_bis)``.
        """
        jetzt = _jetzt()
        verbindung = self._oeffnen()
        try:
            zeile = verbindung.execute(
                "SELECT fehlversuche, letzter_am FROM app_anmeldeversuche WHERE abdruck=?",
                (abdruck,),
            ).fetchone()
            if zeile is None:
                zaehler = 0
            else:
                zaehler = int(zeile["fehlversuche"] or 0)
                if _als_zeitpunkt(zeile["letzter_am"]) < jetzt - fenster:
                    zaehler = 0
            zaehler += 1

            gesperrt_bis = None
            if zaehler >= sperre_ab:
                gesperrt_bis = jetzt + sperrdauer
                zaehler = 0

            werte = (
                art,
                zaehler,
                jetzt if self._pg else jetzt.isoformat(),
                (gesperrt_bis if self._pg else gesperrt_bis.isoformat()) if gesperrt_bis else None,
            )
            if zeile is None:
                verbindung.execute(
                    "INSERT INTO app_anmeldeversuche(abdruck,art,fehlversuche,letzter_am,gesperrt_bis) "
                    "VALUES(?,?,?,?,?)", (abdruck,) + werte)
            else:
                verbindung.execute(
                    "UPDATE app_anmeldeversuche SET art=?, fehlversuche=?, letzter_am=?, "
                    "gesperrt_bis=? WHERE abdruck=?", werte + (abdruck,))
            verbindung.commit()
            return zaehler, gesperrt_bis
        finally:
            verbindung.close()

    def zuruecksetzen(self, abdruecke: Iterable[str]) -> None:
        """Loescht die Zaehler — nach einer erfolgreichen Anmeldung.

        Beide Zaehler zugleich, E-Mail und IP: Wer sich anmelden konnte, hat
        das Passwort; dann waere es unsinnig, ihn kurz darauf wegen der
        Tippfehler davor auszusperren.
        """
        liste = [a for a in abdruecke if a]
        if not liste:
            return
        verbindung = self._oeffnen()
        try:
            for abdruck in liste:
                verbindung.execute("DELETE FROM app_anmeldeversuche WHERE abdruck=?", (abdruck,))
            verbindung.commit()
        finally:
            verbindung.close()

    def alte_entfernen(self, aelter_als: _dt.timedelta) -> int:
        """Raeumt Zaehler ab, die nichts mehr aussagen.

        Wird beim Anmelden mitausgefuehrt — dieselbe Loesung wie bei den
        abgelaufenen Sitzungen, und aus demselben Grund: So bleibt die Tabelle
        klein, ohne dass ein Hintergrundlauf noetig waere.

        Entfernt wird nur, was **weder gezaehlt noch gesperrt** ist: Eine
        laufende Sperre bleibt stehen, auch wenn ihr letzter Fehlversuch alt
        ist. Sonst liesse sie sich durch Abwarten aushebeln.
        """
        grenze = _jetzt() - aelter_als
        jetzt = _jetzt()
        verbindung = self._oeffnen()
        try:
            zeiger = verbindung.execute(
                "DELETE FROM app_anmeldeversuche WHERE letzter_am<? "
                "AND (gesperrt_bis IS NULL OR gesperrt_bis<=?)",
                (
                    grenze if self._pg else grenze.isoformat(),
                    jetzt if self._pg else jetzt.isoformat(),
                ),
            )
            verbindung.commit()
            return getattr(zeiger, "rowcount", 0) or 0
        finally:
            verbindung.close()
