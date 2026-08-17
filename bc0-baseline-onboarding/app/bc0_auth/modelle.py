# -*- coding: utf-8 -*-
"""
Fachliche Typen der Benutzerverwaltung.

Dieses Modul ist bewusst frei von technischen Abhängigkeiten: kein FastAPI, keine
Datenbank, kein Netzwerk. Es beschreibt ausschließlich, *was* ein Benutzer, eine
Rolle und eine Sitzung im Sinne von BC0 sind. Alles Weitere baut darauf auf.

Warum das getrennt ist: Die Regeln „Ein Benutzer sieht nur seine Mandanten" und
„Löschen darf nur der Admin" sind fachliche Entscheidungen aus dem Meeting vom
10.08.2026. Sie sollen an genau einer Stelle stehen und dort nachlesbar sein —
nicht verstreut über Endpunkte und SQL-Bedingungen.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Optional


class Rolle(str, Enum):
    """Die beiden Oberflächen der Anwendung.

    Beschluss vom 10.08.2026: Es gibt genau zwei Rollen. Eine dritte Stufe
    (z. B. „nur lesen") ist bewusst nicht vorgesehen — sie hätte ohne konkreten
    Bedarf nur die Rechteprüfung verkompliziert.

    Der Wert wird als Text in der Datenbank abgelegt (nicht als Zahl), damit ein
    Blick in die Tabelle ohne Nachschlagewerk verständlich ist. Die Ableitung von
    ``str`` erlaubt den direkten Vergleich mit dem gespeicherten Wert.
    """

    BENUTZER = "benutzer"
    ADMIN = "admin"

    @classmethod
    def aus_text(cls, wert: str) -> "Rolle":
        """Wandelt einen gespeicherten Text in eine Rolle um.

        Ein unbekannter Wert wird **nicht** stillschweigend zu ``BENUTZER``
        gemacht, sondern führt zu einem Fehler. Grund: Ein Tippfehler in der
        Datenbank darf nicht dazu führen, dass jemand unbemerkt weniger — oder
        schlimmer, mehr — Rechte bekommt als vorgesehen.
        """
        try:
            return cls(str(wert).strip().lower())
        except ValueError as fehler:
            raise ValueError("Unbekannte Rolle in der Datenbank: %r" % wert) from fehler


@dataclass(frozen=True)
class Benutzer:
    """Ein angemeldeter oder anzumeldender Mensch.

    Attribute:
        benutzer_id: Technische ID (UUID als Text). Wird von der Anwendung vergeben.
        email:       Anmeldename. Kleingeschrieben und ohne Leerzeichen gespeichert,
                     damit „Simeon@…" und „simeon@…" derselbe Zugang sind.
        name:        Anzeigename für die Oberfläche und für ``freigegeben_durch``.
        rolle:       Siehe :class:`Rolle`.
        mandanten:   IDs der Mandanten, die dieser Benutzer sehen darf. Für einen
                     Admin ist die Menge bedeutungslos — er sieht ohnehin alle.
        aktiv:       Deaktivierte Benutzer können sich nicht anmelden. Bewusst ein
                     Schalter statt einer Löschung, damit ``freigegeben_durch`` in
                     alten Datensätzen auflösbar bleibt.

    Die Klasse ist unveränderlich (``frozen=True``). Ein einmal geladener Benutzer
    kann während der Verarbeitung einer Anfrage nicht versehentlich umgeschrieben
    werden — insbesondere nicht seine Rolle.
    """

    benutzer_id: str
    email: str
    name: str
    rolle: Rolle
    mandanten: FrozenSet[str] = field(default_factory=frozenset)
    aktiv: bool = True

    @property
    def ist_admin(self) -> bool:
        return self.rolle is Rolle.ADMIN

    def darf_mandanten_sehen(self, mandant_id: str) -> bool:
        """Kernregel der Mandantentrennung.

        Der Admin sieht alle Mandanten. Jeder andere sieht ausschließlich die ihm
        zugeordneten. Diese Methode ist die einzige Stelle, an der diese Regel
        formuliert ist; alle Endpunkte fragen hier nach.
        """
        if self.ist_admin:
            return True
        return str(mandant_id) in self.mandanten

    def darf_loeschen(self) -> bool:
        """Löschen ist dem Admin vorbehalten (Beschluss vom 10.08.2026)."""
        return self.ist_admin

    def darf_freigeben(self) -> bool:
        """Die Freigabe eines Prozesses an BC2 ist eine Entscheidung des HitL.

        Sie liegt bei der Admin-Rolle, weil sie das gesamte Unternehmen betrifft
        und den nachgelagerten Bounded Context auslöst. Siehe Etappe 4d.
        """
        return self.ist_admin


@dataclass(frozen=True)
class Sitzung:
    """Eine offene Anmeldung.

    Der Sitzungsschlüssel selbst wird **nicht** in diesem Objekt gehalten und auch
    nicht in der Datenbank gespeichert — dort liegt nur sein SHA-256-Abdruck (siehe
    :mod:`bc0_auth.repository`). Wer die Datenbank lesen kann, kann damit keine
    fremde Sitzung übernehmen.

    Attribute:
        sitzung_id:  Technische ID des Datensatzes.
        benutzer_id: Wem die Sitzung gehört.
        angelegt_am: Zeitpunkt der Anmeldung (UTC).
        laeuft_ab:   Zeitpunkt, ab dem die Sitzung ungültig ist (UTC).
    """

    sitzung_id: str
    benutzer_id: str
    angelegt_am: _dt.datetime
    laeuft_ab: _dt.datetime

    def ist_abgelaufen(self, jetzt: Optional[_dt.datetime] = None) -> bool:
        vergleich = jetzt or _dt.datetime.now(_dt.timezone.utc)
        ablauf = self.laeuft_ab
        if ablauf.tzinfo is None:  # SQLite liefert naive Zeitstempel
            ablauf = ablauf.replace(tzinfo=_dt.timezone.utc)
        return ablauf <= vergleich


class AnmeldeFehler(Exception):
    """Anmeldung fehlgeschlagen.

    Wird für *alle* Fehlerursachen verwendet — unbekannte E-Mail, falsches
    Passwort, deaktiviertes Konto. Absicht: Die Antwort nach außen darf nicht
    verraten, ob eine Adresse existiert. Die genaue Ursache steht ausschließlich
    im Serverprotokoll.
    """


class RechteFehler(Exception):
    """Der angemeldete Benutzer darf das Angeforderte nicht."""
