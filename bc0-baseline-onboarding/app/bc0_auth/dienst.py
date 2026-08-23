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
from typing import Iterable, List, Optional, Tuple

from . import passwoerter
from .modelle import AnmeldeFehler, Benutzer, Rolle, Sitzung
from .repository import BenutzerRepository, SitzungsRepository, VerbindungsFabrik

_log = logging.getLogger("bc0.auth")

#: Standard-Gültigkeit einer Sitzung. Acht Stunden entsprechen einem Arbeitstag:
#: lang genug, um nicht zu stören, kurz genug, dass ein vergessener Rechner am
#: Folgetag nicht mehr angemeldet ist.
STANDARD_SITZUNGSDAUER = _dt.timedelta(hours=8)


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
    def anmelden(self, email: str, passwort: str) -> Tuple[Benutzer, str, Sitzung]:
        """Prüft die Zugangsdaten und eröffnet eine Sitzung.

        Returns:
            Ein Tripel aus Benutzer, **Sitzungsschlüssel** und Sitzung. Der
            Schlüssel wird nur hier einmalig herausgegeben — gespeichert wird
            ausschließlich sein Abdruck.

        Raises:
            AnmeldeFehler: bei unbekannter Adresse, falschem Passwort oder
                gesperrtem Konto. Die Ausnahme ist für alle drei Fälle dieselbe,
                damit die Antwort nicht verrät, welche Adressen existieren.
                Welcher Fall vorlag, steht im Serverprotokoll.
        """
        treffer = self.benutzer.finde_per_email(email)
        if treffer is None:
            # Auch ohne Treffer wird ein Hash berechnet. Sonst wäre an der
            # Antwortdauer ablesbar, ob eine Adresse existiert.
            passwoerter.hash_pruefen(passwort or "", _BLINDHASH)
            _log.info("Anmeldung abgelehnt: unbekannte Adresse %r", email)
            raise AnmeldeFehler("Anmeldung fehlgeschlagen.")

        benutzer, gespeicherter_hash = treffer
        if not passwoerter.hash_pruefen(passwort or "", gespeicherter_hash):
            _log.info("Anmeldung abgelehnt: falsches Passwort für %s", benutzer.email)
            raise AnmeldeFehler("Anmeldung fehlgeschlagen.")

        if not benutzer.aktiv:
            _log.info("Anmeldung abgelehnt: Konto gesperrt (%s)", benutzer.email)
            raise AnmeldeFehler("Anmeldung fehlgeschlagen.")

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
