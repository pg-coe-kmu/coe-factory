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
        self._verbindung_erzeugen = verbindung_erzeugen
        self._pg = bool(ist_postgres)

    # Kleine Helfer, damit die Methoden unten lesbar bleiben.
    def _oeffnen(self):
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
        zeilen = verbindung.execute(
            "SELECT " + self._uuid_lesen + " FROM app_benutzer_mandanten WHERE benutzer_id=?",
            (benutzer_id,),
        ).fetchall()
        return frozenset(str(z["company_id"]) for z in zeilen)

    def _zu_benutzer(self, verbindung, zeile) -> Benutzer:
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
        verbindung = self._oeffnen()
        try:
            zeile = verbindung.execute(
                "SELECT * FROM app_benutzer WHERE benutzer_id=?", (benutzer_id,)
            ).fetchone()
            return self._zu_benutzer(verbindung, zeile) if zeile else None
        finally:
            verbindung.close()

    def alle(self) -> List[Benutzer]:
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
