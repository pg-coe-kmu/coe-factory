# -*- coding: utf-8 -*-
"""
Anwendungsfälle der Benutzerverwaltung.

Hier steht der Ablauf — anmelden, abmelden, Sitzung auflösen, Benutzer anlegen —,
nicht seine technische Ausprägung. Dieses Modul kennt weder HTTP noch SQL: Es
arbeitet mit den Repositories aus :mod:`bc0_auth.repository` und den Typen aus
:mod:`bc0_auth.modelle`.

Der Nutzen dieser Trennung zeigt sich in den Tests: Die Anmeldung lässt sich
prüfen, ohne einen Webserver zu starten.
"""

from __future__ import annotations

import datetime as _dt
import logging
import time
from typing import Iterable, List, Optional, Tuple

from . import passwoerter
from .modelle import AnmeldeFehler, Benutzer, Rolle, Sitzung, ZuVieleVersuche
from .repository import (
    AnmeldeversuchRepository,
    BenutzerRepository,
    SitzungsRepository,
    VerbindungsFabrik,
)

_log = logging.getLogger("bc0.auth")

# --------------------------------------------------------------------------- #
# WARUM DREI MELDUNGEN AUF `warning` STEHEN UND NICHT AUF `info`
# --------------------------------------------------------------------------- #
# Die abgelehnten Anmeldungen (unbekannte Adresse, falsches Passwort, gesperrtes
# Konto) sind fachlich `info` — es ist der erwartbare Alltag, kein Stoerfall.
# Sie stehen trotzdem auf `warning`, und das ist kein Versehen:
#
#   Der Logger `bc0.auth` bekommt keine eigene Einstellung; es gilt die
#   Vorbelegung der Standardbibliothek, und die ist WARNING. Alles auf `info`
#   faellt damit lautlos weg. **Am 02.09.2026 gemessen:** elf Fehlversuche
#   gegen die Live-Anwendung erzeugten NULL Protokollzeilen.
#
#   Daran hingen zwei Zusicherungen. `modelle.py` sagt seit dem 10.08.2026 ueber
#   die absichtlich einheitliche 401: *„Welcher Fall vorlag, steht ausschliesslich
#   im Serverprotokoll."* Und `schema_v2.5` begruendet damit, dass
#   `app_anmeldeversuche` nur Abdruecke fuehrt: *„Die Tabelle zaehlt, das
#   Protokoll erzaehlt."* Beide waren leer, solange nichts geschrieben wurde.
#
# **Wer diese drei Zeilen auf `info` zurueckstellt, weil sie dort systematisch
# hingehoeren, nimmt beide Zusicherungen mit.** Dann gehoeren sie zuerst aus
# `modelle.py` und `schema_v2.5` heraus — oder der Logger bekommt eine eigene
# Einstellung, und dann duerfen sie zurueck. Der Test
# `test_abgelehnte_anmeldung_wird_sichtbar_protokolliert` haelt das fest.
#
# Die Verzoegerungsmeldung bleibt auf `info`: Dass gebremst wurde, steht
# ohnehin in der Sperrmeldung, und sie ist keine Auskunft ueber einen Versuch.

#: Standard-Gültigkeit einer Sitzung. Acht Stunden entsprechen einem Arbeitstag:
#: lang genug, um nicht zu stören, kurz genug, dass ein vergessener Rechner am
#: Folgetag nicht mehr angemeldet ist.
STANDARD_SITZUNGSDAUER = _dt.timedelta(hours=8)

# --------------------------------------------------------------------------- #
# Die Anmeldebremse (ToDo-Punkt 71, 02.09.2026)
# --------------------------------------------------------------------------- #
# Bis hierher nahm die Anmeldung unbegrenzt viele Versuche entgegen. Zwoelf
# Uebungszugaenge sind seit dem 26.08.2026 verteilt, die Adresse ist bekannt —
# damit war Durchprobieren nur eine Frage der Geduld. Aufgefallen am 20.08. bei
# der technischen Bestandsaufnahme, offen benannt in `BC0_Sicherheitskonzept.md`.
#
# ZWEI STUFEN, WEIL SIE VERSCHIEDENES LEISTEN
#   Die Verzoegerung macht Durchprobieren teuer, ohne jemanden auszusperren.
#   Die Sperre haelt auch den auf, der viele Versuche gleichzeitig schickt und
#   dem eine Wartezeit je Versuch deshalb nichts ausmacht.
#
# WARUM SIE SICH SELBST LOEST
#   Entschieden am 02.09.2026. Die Alternative — Sperre bis ein Admin sie
#   aufhebt — macht **eine Person zur Entsperrstelle fuer zwoelf Konten**, auch
#   sonntags. Wer sich dreimal vertippt und dann eine Stunde warten muss, ruft
#   an; wer bis Montag warten muss, arbeitet nicht mehr mit dem Werkzeug.

#: Ab dem wievielten Fehlversuch verzoegert geantwortet wird.
VERZOEGERUNG_AB = 5

#: Ab dem wievielten Fehlversuch gesperrt wird.
SPERRE_AB = 10

#: Wie lange die Sperre gilt. Sie laeuft von allein ab.
SPERRDAUER = _dt.timedelta(minutes=15)

#: Gleitendes Fenster: Ein Fehlversuch, der laenger zurueckliegt, zaehlt nicht
#: mehr mit. Ohne das Fenster summierten sich Tippfehler ueber Monate.
ZAEHLFENSTER = _dt.timedelta(minutes=15)

#: Obergrenze der Verzoegerung. Sie ist nicht kosmetisch: Die Anmelderoute ist
#: eine gewoehnliche (nicht-asynchrone) Funktion und laeuft damit in FastAPIs
#: Threadpool. Ein `sleep` blockiert dort einen Arbeiter-Thread, nicht die
#: Ereignisschleife — aber der Threadpool ist endlich. Acht Sekunden mal die
#: Zahl gleichzeitiger Versucher ist die Rechnung, die diese Grenze setzt.
VERZOEGERUNG_MAX = _dt.timedelta(seconds=8)

#: Nach dieser Zeit ohne Fehlversuch wird ein Zaehler abgeraeumt.
ZAEHLER_AUFBEWAHRUNG = _dt.timedelta(hours=24)


def wartezeit(fehlversuche: int) -> float:
    """Verzoegerung in Sekunden nach ``fehlversuche`` Fehlversuchen.

    Verdoppelt sich je weiterem Versuch (1, 2, 4, 8 …) und ist bei
    :data:`VERZOEGERUNG_MAX` gedeckelt. Unterhalb von :data:`VERZOEGERUNG_AB`
    ist sie 0 — die ersten vier Versuche sollen sich normal anfuehlen, weil
    Vertippen der Normalfall ist und Angriff der Ausnahmefall.

    Als eigene Funktion und nicht als Ausdruck im Ablauf, damit die Kurve
    ohne Datenbank und ohne Uhr pruefbar ist (``test_anmeldebremse.py``).
    """
    if fehlversuche < VERZOEGERUNG_AB:
        return 0.0
    return min(2.0 ** (fehlversuche - VERZOEGERUNG_AB), VERZOEGERUNG_MAX.total_seconds())


class AuthDienst:
    """Führt die Anwendungsfälle rund um Anmeldung und Benutzerpflege aus.

    Args:
        verbindung_erzeugen: Fabrik für Datenbankverbindungen (siehe
            :mod:`bc0_auth.repository`).
        ist_postgres: ``True`` im Betrieb, ``False`` für die SQLite-Entwicklung.
        sitzungsdauer: Gültigkeit neu angelegter Sitzungen.
    """

    def __init__(
        self,
        verbindung_erzeugen: VerbindungsFabrik,
        ist_postgres: bool,
        sitzungsdauer: _dt.timedelta = STANDARD_SITZUNGSDAUER,
    ):
        """Setzt den Dienst über den beiden Repositories zusammen.

        Die Verbindungsfabrik wird **hereingereicht**, nicht hier erzeugt. Das
        ist die Stelle, an der die Testbarkeit des ganzen Pakets hängt: In den
        Tests wird eine SQLite-Datei in einem temporären Verzeichnis gereicht,
        im Betrieb die PostgreSQL-Verbindung. Das Anmeldepaket selbst kennt
        weder ``.env`` noch ``DATABASE_URL``.
        """
        self.benutzer = BenutzerRepository(verbindung_erzeugen, ist_postgres)
        self.sitzungen = SitzungsRepository(verbindung_erzeugen, ist_postgres)
        self.versuche = AnmeldeversuchRepository(verbindung_erzeugen, ist_postgres)
        self.sitzungsdauer = sitzungsdauer

    # ------------------------------------------------------------------ #
    # Einrichtung
    # ------------------------------------------------------------------ #
    def einrichten(self) -> None:
        """Legt die benötigten Tabellen an. Beim Start der Anwendung aufzurufen."""
        self.benutzer.tabellen_anlegen()

    def ist_eingerichtet(self) -> bool:
        """Meldet, ob überhaupt ein Benutzer existiert.

        Solange das nicht der Fall ist, kann sich niemand anmelden. Das ist
        beabsichtigt: Es wird bewusst **kein** Standardkonto angelegt. Der erste
        Zugang entsteht über ``benutzer_verwalten.py`` auf dem Server. Ein
        vorkonfiguriertes Konto mit bekanntem Passwort wäre die verwundbarste
        Stelle der ganzen Anwendung.
        """
        return self.benutzer.anzahl() > 0

    # ------------------------------------------------------------------ #
    # Anmeldung
    # ------------------------------------------------------------------ #
    def _bremse_schluessel(self, email: str, herkunft: Optional[str]) -> List[Tuple[str, str]]:
        """Die Zaehler, die fuer diesen Versuch gelten — je Art einer.

        Fehlt die Herkunft (etwa in einem Test oder bei einem Aufruf ohne
        HTTP), zaehlt nur die E-Mail. Ein Platzhalter wie ``unbekannt`` waere
        hier schaedlich: Alle Aufrufe ohne IP teilten sich EINEN Zaehler und
        sperrten sich gegenseitig aus.
        """
        schluessel = [("email", self.versuche.abdruck("email", email or ""))]
        if herkunft:
            schluessel.append(("ip", self.versuche.abdruck("ip", herkunft)))
        return schluessel

    def _bremse_pruefen(self, schluessel: List[Tuple[str, str]]) -> None:
        """Wirft :class:`ZuVieleVersuche`, solange eine Sperre laeuft.

        Laeuft **vor** jeder Passwortpruefung. Sonst waere die Sperre nur eine
        andere Fehlermeldung und keine Bremse: Der Aufwand, den ein Angreifer
        erzeugt, entstuende weiter.

        Es entscheidet der **strengste** Zaehler. Ist die IP gesperrt, hilft
        eine andere Adresse nicht, und umgekehrt.
        """
        jetzt = _dt.datetime.now(_dt.timezone.utc)
        rest = 0
        for art, abdruck in schluessel:
            _, gesperrt_bis = self.versuche.stand(abdruck)
            if gesperrt_bis and gesperrt_bis > jetzt:
                rest = max(rest, (gesperrt_bis - jetzt).total_seconds())
        if rest > 0:
            raise ZuVieleVersuche(int(rest) + 1)

    def _bremse_verzoegern(self, schluessel: List[Tuple[str, str]]) -> None:
        """Wartet, wenn schon Fehlversuche vorliegen — vor der Pruefung.

        Die Wartezeit richtet sich nach dem hoechsten der beiden Zaehler.
        """
        hoechster = 0
        for _art, abdruck in schluessel:
            zaehler, _ = self.versuche.stand(abdruck)
            hoechster = max(hoechster, zaehler)
        dauer = wartezeit(hoechster)
        if dauer > 0:
            _log.info("Anmeldung verzoegert um %.0fs (%d Fehlversuche)", dauer, hoechster)
            time.sleep(dauer)

    def _bremse_fehlversuch(self, schluessel: List[Tuple[str, str]], email: str) -> None:
        """Zaehlt den Fehlversuch auf allen Zaehlern und sperrt gegebenenfalls."""
        for art, abdruck in schluessel:
            zaehler, gesperrt_bis = self.versuche.fehlversuch(
                abdruck, art, ZAEHLFENSTER, SPERRE_AB, SPERRDAUER)
            if gesperrt_bis:
                # Die Adresse steht im Protokoll, nicht in der Tabelle — dort
                # liegt nur ihr Abdruck. Siehe AnmeldeversuchRepository.
                _log.warning(
                    "Anmeldebremse: %s gesperrt bis %s (Versuch mit %r)",
                    art, gesperrt_bis.isoformat(timespec="seconds"), email)

    def anmelden(
        self, email: str, passwort: str, herkunft: Optional[str] = None
    ) -> Tuple[Benutzer, str, Sitzung]:
        """Prüft die Zugangsdaten und eröffnet eine Sitzung.

        Args:
            email: eingegebene Adresse.
            passwort: eingegebenes Passwort.
            herkunft: IP-Adresse des Aufrufers, oder ``None``. Sie kommt aus
                ``request.client.host`` und ist erst seit dem Ausrollen von
                ``--proxy-headers`` am 02.09.2026 die **echte** Adresse des
                Benutzers. Vorher stand dort Caddys eigene Adresse — ein
                Zaehler je IP haette damals alle Benutzer als einen gezaehlt
                und der erste mit fuenf Tippfehlern haette den Rest
                ausgesperrt. **Das ist der Grund, warum Punkt 71 auf Punkt 47
                gewartet hat.**

        Returns:
            Ein Tripel aus Benutzer, **Sitzungsschlüssel** und Sitzung. Der
            Schlüssel wird nur hier einmalig herausgegeben — gespeichert wird
            ausschließlich sein Abdruck.

        Raises:
            ZuVieleVersuche: solange die Anmeldebremse sperrt. Dieser Fall
                **darf** sich zu erkennen geben, weil er nichts ueber Konten
                verraet — gezaehlt wird der Versuch, nicht das Konto.
            AnmeldeFehler: bei unbekannter Adresse, falschem Passwort oder
                gesperrtem Konto. Die Ausnahme ist für alle drei Fälle dieselbe,
                damit die Antwort nicht verrät, welche Adressen existieren.
                Welcher Fall vorlag, steht im Serverprotokoll.
        """
        bremse = self._bremse_schluessel(email, herkunft)
        self._bremse_pruefen(bremse)
        self._bremse_verzoegern(bremse)

        treffer = self.benutzer.finde_per_email(email)
        if treffer is None:
            # Auch ohne Treffer wird ein Hash berechnet. Sonst wäre an der
            # Antwortdauer ablesbar, ob eine Adresse existiert.
            passwoerter.hash_pruefen(passwort or "", _BLINDHASH)
            _log.warning("Anmeldung abgelehnt: unbekannte Adresse %r", email)
            self._bremse_fehlversuch(bremse, email)
            raise AnmeldeFehler("Anmeldung fehlgeschlagen.")

        benutzer, gespeicherter_hash = treffer
        if not passwoerter.hash_pruefen(passwort or "", gespeicherter_hash):
            _log.warning("Anmeldung abgelehnt: falsches Passwort für %s", benutzer.email)
            self._bremse_fehlversuch(bremse, email)
            raise AnmeldeFehler("Anmeldung fehlgeschlagen.")

        if not benutzer.aktiv:
            _log.warning("Anmeldung abgelehnt: Konto gesperrt (%s)", benutzer.email)
            # Ein gesperrtes Konto zaehlt mit. Sonst waere es der eine Weg,
            # auf dem sich beliebig oft probieren laesst, sobald ein Angreifer
            # eine gesperrte Adresse kennt.
            self._bremse_fehlversuch(bremse, email)
            raise AnmeldeFehler("Anmeldung fehlgeschlagen.")

        self.versuche.zuruecksetzen([a for _art, a in bremse])
        self.versuche.alte_entfernen(ZAEHLER_AUFBEWAHRUNG)

        # Kostenparameter nachziehen, falls der Hash aus einer früheren Fassung stammt.
        if passwoerter.muss_neu_gehasht_werden(gespeicherter_hash):
            self.benutzer.passwort_setzen(
                benutzer.benutzer_id, passwoerter.hash_erzeugen(passwort)
            )
            _log.info("Passwort-Hash für %s auf aktuelle Parameter gehoben", benutzer.email)

        self.sitzungen.abgelaufene_entfernen()
        schluessel = passwoerter.sitzungsschluessel_erzeugen()
        sitzung = self.sitzungen.anlegen(
            benutzer.benutzer_id, passwoerter.schluessel_abdruck(schluessel), self.sitzungsdauer
        )
        self.benutzer.anmeldung_vermerken(benutzer.benutzer_id)
        _log.info("Angemeldet: %s (%s)", benutzer.email, benutzer.rolle.value)
        return benutzer, schluessel, sitzung

    def abmelden(self, sitzungsschluessel: str) -> None:
        """Beendet die zum Schlüssel gehörende Sitzung.

        Ein unbekannter Schlüssel ist kein Fehler — das Ziel, keine gültige
        Sitzung zu hinterlassen, ist dann bereits erreicht.
        """
        if sitzungsschluessel:
            self.sitzungen.beenden(passwoerter.schluessel_abdruck(sitzungsschluessel))

    def benutzer_zu_sitzung(self, sitzungsschluessel: Optional[str]) -> Optional[Benutzer]:
        """Löst einen Sitzungsschlüssel in den zugehörigen Benutzer auf.

        Liefert ``None``, wenn kein Schlüssel vorliegt, die Sitzung unbekannt oder
        abgelaufen ist oder das Konto inzwischen gesperrt wurde.

        Der Benutzer wird bei **jeder** Anfrage frisch aus der Datenbank geladen.
        Das kostet eine kleine Abfrage, hat aber zur Folge, dass Änderungen an
        Rolle, Mandantenzuordnung oder Sperrstatus sofort wirken und nicht erst
        nach der nächsten Anmeldung.
        """
        if not sitzungsschluessel:
            return None
        sitzung = self.sitzungen.finde_per_abdruck(
            passwoerter.schluessel_abdruck(sitzungsschluessel)
        )
        if sitzung is None:
            return None
        if sitzung.ist_abgelaufen():
            self.sitzungen.beenden(passwoerter.schluessel_abdruck(sitzungsschluessel))
            return None
        benutzer = self.benutzer.finde_per_id(sitzung.benutzer_id)
        if benutzer is None or not benutzer.aktiv:
            return None
        return benutzer

    # ------------------------------------------------------------------ #
    # Benutzerpflege
    # ------------------------------------------------------------------ #
    def benutzer_anlegen(
        self,
        email: str,
        name: str,
        passwort: str,
        rolle: Rolle,
        mandanten: Iterable[str] = (),
    ) -> Benutzer:
        """Legt einen Benutzer an.

        Raises:
            bc0_auth.passwoerter.PasswortFehler: wenn das Passwort zu kurz ist.
            ValueError: wenn die Adresse bereits vergeben ist.
        """
        passwoerter.pruefe_mindestanforderungen(passwort)
        angelegt = self.benutzer.anlegen(
            email=email,
            name=name,
            passwort_hash=passwoerter.hash_erzeugen(passwort),
            rolle=rolle,
            mandanten=mandanten,
        )
        _log.info("Benutzer angelegt: %s (%s)", angelegt.email, angelegt.rolle.value)
        return angelegt

    def passwort_aendern(self, benutzer_id: str, neues_passwort: str) -> None:
        """Setzt ein neues Passwort und beendet alle offenen Sitzungen.

        Das Beenden ist Absicht: Ein Passwortwechsel geschieht häufig, weil ein
        Verdacht besteht. Bliebe eine alte Sitzung gültig, ginge der Zweck
        verloren. Der Wechselnde muss sich anschließend neu anmelden.
        """
        passwoerter.pruefe_mindestanforderungen(neues_passwort)
        self.benutzer.passwort_setzen(benutzer_id, passwoerter.hash_erzeugen(neues_passwort))
        self.sitzungen.alle_beenden(benutzer_id)
        _log.info("Passwort geändert, alle Sitzungen beendet: %s", benutzer_id)

    def benutzer_sperren(self, benutzer_id: str) -> None:
        """Sperrt ein Konto und beendet seine Sitzungen.

        Konten werden gesperrt, nicht gelöscht: ``freigegeben_durch`` in
        ``ref_prozesse`` verweist auf den Benutzer, und ein Nachweis, dessen
        Urheber verschwunden ist, ist kein Nachweis.
        """
        self.benutzer.aktiv_setzen(benutzer_id, False)
        self.sitzungen.alle_beenden(benutzer_id)
        _log.info("Benutzer gesperrt: %s", benutzer_id)

    def benutzer_entsperren(self, benutzer_id: str) -> None:
        """Hebt eine Sperre auf.

        Anders als :meth:`benutzer_sperren` ist das **nicht** symmetrisch: Die
        Sperre hat die laufenden Sitzungen beendet, das Entsperren stellt sie
        nicht wieder her. Der Benutzer muss sich neu anmelden. Das ist
        beabsichtigt — eine Sperre soll nicht rückstandslos verschwinden.
        """
        self.benutzer.aktiv_setzen(benutzer_id, True)

    def alle_benutzer(self) -> List[Benutzer]:
        """Liefert alle Konten — ohne Passwort-Hash, ohne Mandantenfilter.

        Der Filter fehlt hier bewusst: Der Endpunkt darüber ist Admins
        vorbehalten (``Depends(admin)`` in :mod:`bc0_auth.routen`), und ein
        Admin sieht ohnehin alles. Wer diese Methode einem anderen Endpunkt
        zugänglich macht, muss den Filter dort ergänzen.
        """
        return self.benutzer.alle()


#: Gültig aufgebauter, aber zu keinem Passwort gehörender Hash. Er dient
#: ausschließlich dazu, bei unbekannter E-Mail-Adresse denselben Rechenaufwand zu
#: erzeugen wie bei einer bekannten (siehe :meth:`AuthDienst.anmelden`).
_BLINDHASH = passwoerter.hash_erzeugen("nur-fuer-den-zeitausgleich-2026")
