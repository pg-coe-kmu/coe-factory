"""
BC2 · Läufe für die Oberfläche — die Naht zwischen Anzeige und Herkunft.

Die Oberfläche (#243) zeigt **einen Lauf**: seine Potenziale, in Rangfolge,
gegliedert nach Kernprozess. Woher die kommen, geht sie nichts an. Hier liegt
das Protokoll dazwischen.

**Zwei Quellen, eine Form.** Die Form ist der Vertrag v3.0 — die Oberfläche
zeigt, was an BC3 geht, und nicht eine eigene Sicht daneben. Das ist kein
Schönheitsargument: eine Oberfläche mit eigener Datenform behauptet früher oder
später etwas anderes als die Lieferung, und der Mensch gibt dann frei, was er
nicht gesehen hat.

- ``MesssatzLaufquelle`` rechnet einen Messsatz durch (siehe
  ``modell/laden.py``). **Das ist die heutige Quelle**, und sie ist eine
  Behelfslösung: die Potenzial-Erkennung aus dem echten Datenstand ist #194 und
  noch offen. Ein Messsatz ist nicht auf ``stand_zum(uebergeben_am)`` gelesen,
  seine Zahlen sind darum nicht nachrechenbar — die Quelle reicht die Warnung
  der Datei bis in die Oberfläche durch, statt sie zu schlucken.
- ``SpeicherLaufquelle`` nimmt fertige Ansichten entgegen; die Tests benutzen
  sie.

Was **nicht** hier liegt: die Gate-1-Entscheidung. Die hat ihr eigenes Modul
(``gate1.py``), weil sie einen anderen Lebenslauf hat — sie wird geschrieben,
der Lauf wird gerechnet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from modell import Lauf, Potenzialeingang, rechne_lauf
from modell.ausgabe import als_eintraege, als_konzept_potenzial, als_prozess_raenge
from modell.laden import lies_messsatz

__all__ = [
    "SCORE_FORMEL",
    "Laufkopf",
    "Laufansicht",
    "Laufquelle",
    "MesssatzLaufquelle",
    "SpeicherLaufquelle",
    "aus_lauf",
]

# Das Vertragsfeld ``score_formel`` ist Markdown, kein Parameter: es soll einen
# Prüfer die Zahl **ohne Datenbank** nachrechnen lassen. Es steht deshalb hier
# als Text und nicht in ``modell/parameter.py``, wo die Zahlen liegen.
SCORE_FORMEL = (
    "`score = impact × (11 − umsetzungskomplexitaet)`, Bereich 1…100.\n\n"
    "- `impact = round((impact_monetaer + nutzwert) / 2)` — beide auf 1–10.\n"
    "- `umsetzungskomplexitaet = round(11 − 2 × Mittel der vier BC1-Skalen)`; "
    "fehlen die Skalen, urteilt das LLM und die Herkunft ist `geurteilt`.\n"
    "- Die **lineare** Umkehrung der Komplexität ist bewusst gesetzt, obwohl der "
    "Sprung ins sehr Aufwendige fachlich überproportional wäre — offengelegt, "
    "nicht kaschiert (ADR-006 · BC2)."
)


@dataclass(frozen=True)
class Laufkopf:
    """Was in der **Liste der Läufe** steht — dem Einstieg der Oberfläche.

    Kein Profil, keine Mandantenwahl: seit #165 stößt BC0 an und seit ADR-005
    ist der Lauf das Paket. Die Liste ist deshalb die Startseite und nicht eine
    Seite davor (#167, Frage 1).
    """

    paket_id: str
    company_id: str
    uebergeben_am: datetime
    fassung: int = 1
    anzahl_potenziale: int = 0
    kp_ids: tuple[str, ...] = ()
    gate1_status: str = "pending"
    #: Warum dieser Lauf nicht nachrechenbar ist, falls er es nicht ist.
    warnung: str | None = None

    def als_json(self) -> dict:
        eintrag = {
            "paket_id": self.paket_id,
            "company_id": self.company_id,
            "uebergeben_am": self.uebergeben_am.isoformat(),
            "fassung": self.fassung,
            "anzahl_potenziale": self.anzahl_potenziale,
            "kp_ids": list(self.kp_ids),
            "gate1_status": self.gate1_status,
        }
        if self.warnung:
            eintrag["warnung"] = self.warnung
        return eintrag


@dataclass(frozen=True)
class Laufansicht:
    """Ein ganzer Lauf, in Vertragsform v3.0 plus dem, was die Anzeige braucht.

    ``eintraege`` und ``prozess_raenge`` sind **wörtlich** die Blöcke aus
    ``priorisierung.schema.json``. ``potenziale`` trägt je Potenzial zusätzlich
    die gerechneten Felder des Konzepts (Value-Spannen, Nutzwert-Kategorien,
    Automatisierungsgrad, Hinweise) — das ist der Inhalt der Detail-Schublade.

    Was hier **fehlt**, fehlt ehrlich: ``beschreibung``, ``to_be_vision``,
    ``user_story``, die Akzeptanzkriterien und der Name des Kernprozesses
    entstehen beim LLM (#194) bzw. stehen in ``public.ref_kernprozesse``. Die
    Oberfläche zeigt an dieser Stelle die Kennung und sagt an, dass der Text
    noch nicht da ist, statt einen Platzhalter zu erfinden.
    """

    kopf: Laufkopf
    score_formel: str
    eintraege: list[dict]
    prozess_raenge: list[dict]
    potenziale: dict[str, dict]
    #: ``kp_id`` → Klartextname, soweit bekannt.
    kp_namen: dict[str, str] = field(default_factory=dict)

    def potenzial_ids(self) -> list[str]:
        """Alle Potenziale des Laufs, in **gerechneter** Rangfolge."""
        return [e["potenzial_id"] for e in self.eintraege]

    def kp_ids(self) -> list[str]:
        """Alle Kernprozesse, in **gerechneter** Prozessrangfolge."""
        return [r["kp_id"] for r in self.prozess_raenge]

    def als_json(self) -> dict:
        return {
            "kopf": self.kopf.als_json(),
            "score_formel": self.score_formel,
            "eintraege": self.eintraege,
            "prozess_raenge": self.prozess_raenge,
            "potenziale": self.potenziale,
            "kp_namen": self.kp_namen,
        }


def aus_lauf(
    lauf: Lauf,
    eingaenge: list[Potenzialeingang],
    *,
    uebergeben_am: datetime,
    fassung: int = 1,
    warnung: str | None = None,
    kp_namen: dict[str, str] | None = None,
) -> Laufansicht:
    """Baut die Ansicht aus einem gerechneten :class:`~modell.rechnen.Lauf`.

    ``eingaenge`` muss mitkommen, weil ein gerechnetes ``Potenzial`` nur das
    **Mittel** des Nutzwerts trägt, nicht die fünf Kategorien mit ihren
    Begründungssätzen — die gehören zum Urteil des LLM und nicht ins
    Rechenergebnis (so der Schnitt in ``modell/ausgabe.py``). Die Oberfläche
    zeigt sie im Detail, also müssen sie von hier kommen.

    ``konzept_ids`` verlangt die Vertragsabbildung, weil jede **Fassung** eine
    neue Konzept-Kennung bekommt (ADR-007 · BC2, 2.5). Solange nicht
    ausgeliefert wird, gibt es noch keine — hier steht deshalb eine ableitbare
    Kennung aus Paket, Fassung und Kernprozess. Sie ist stabil (derselbe Lauf
    ergibt dieselbe) und ersetzt die echte nicht: die entsteht beim Ausliefern.
    """
    konzept_ids = {
        r.kp_id: f"{lauf.paket_id}-f{fassung}-{r.kp_id}" for r in lauf.prozess_raenge
    }
    nutzwerte = {e.potenzial_id: e.nutzwert for e in eingaenge}

    return Laufansicht(
        kopf=Laufkopf(
            paket_id=lauf.paket_id,
            company_id=lauf.company_id,
            uebergeben_am=uebergeben_am,
            fassung=fassung,
            anzahl_potenziale=len(lauf.potenziale),
            kp_ids=tuple(r.kp_id for r in lauf.prozess_raenge),
            warnung=warnung,
        ),
        score_formel=SCORE_FORMEL,
        eintraege=als_eintraege(lauf, konzept_ids),
        prozess_raenge=als_prozess_raenge(lauf, konzept_ids),
        potenziale={
            pot.potenzial_id: als_konzept_potenzial(pot, nutzwerte[pot.potenzial_id])
            for pot in lauf.potenziale
        },
        kp_namen=dict(kp_namen or {}),
    )


class Laufquelle(Protocol):
    """Was die Oberfläche von ihrer Datenquelle braucht — mehr nicht."""

    def uebersicht(self, company_id: str | None = None) -> list[Laufkopf]:
        """Die Läufe, neueste zuerst.

        ``company_id`` filtert. **Der Filter ist keine Bequemlichkeit:** es
        liegen zwei Mandanten in derselben Datenbank, und die Datenbank trennt
        sie nicht (Invariante aus ``CLAUDE.md``, bestätigt in #167 Frage 1 —
        im Eingang liegt ein Paket des Übungsmandanten neben denen von NoroAI).
        """
        ...

    def ansicht(self, paket_id: str) -> Laufansicht | None:
        """Der ganze Lauf, oder ``None``, wenn es ihn nicht gibt."""
        ...


class MesssatzLaufquelle:
    """Rechnet Messsätze aus einem Verzeichnis durch.

    **Behelfsquelle bis #194.** Sie liest keine Datenbank und kann darum auch
    nicht auf dem Freigabestand rechnen; die ``warnung`` der Datei reist
    deshalb bis in die Kopfzeile der Oberfläche.
    """

    def __init__(self, verzeichnis: Path | str, uebergeben_am: datetime | None = None) -> None:
        self._verzeichnis = Path(verzeichnis)
        # Ein Messsatz trägt keinen Freigabezeitpunkt — er kommt nicht von BC0.
        # Statt einen zu erfinden, wird die Änderungszeit der Datei genommen und
        # in der Oberfläche als das ausgewiesen, was sie ist.
        self._uebergeben_am = uebergeben_am

    def _dateien(self) -> list[Path]:
        if not self._verzeichnis.is_dir():
            return []
        return sorted(self._verzeichnis.glob("*.json"))

    def _ansicht_aus_datei(self, pfad: Path) -> Laufansicht:
        satz = lies_messsatz(pfad)
        lauf = rechne_lauf(satz.company_id, satz.paket_id, satz.eingaenge)
        zeitpunkt = self._uebergeben_am or datetime.fromtimestamp(
            pfad.stat().st_mtime
        ).astimezone()
        return aus_lauf(
            lauf, satz.eingaenge, uebergeben_am=zeitpunkt, warnung=satz.warnung
        )

    def uebersicht(self, company_id: str | None = None) -> list[Laufkopf]:
        koepfe = []
        for pfad in self._dateien():
            kopf = self._ansicht_aus_datei(pfad).kopf
            if company_id is None or kopf.company_id == company_id:
                koepfe.append(kopf)
        return sorted(koepfe, key=lambda k: k.uebergeben_am, reverse=True)

    def ansicht(self, paket_id: str) -> Laufansicht | None:
        for pfad in self._dateien():
            ansicht = self._ansicht_aus_datei(pfad)
            if ansicht.kopf.paket_id == paket_id:
                return ansicht
        return None


@dataclass
class SpeicherLaufquelle:
    """Fertige Ansichten im Arbeitsspeicher — für die Tests."""

    ansichten: list[Laufansicht] = field(default_factory=list)

    def uebersicht(self, company_id: str | None = None) -> list[Laufkopf]:
        koepfe = [
            a.kopf
            for a in self.ansichten
            if company_id is None or a.kopf.company_id == company_id
        ]
        return sorted(koepfe, key=lambda k: k.uebergeben_am, reverse=True)

    def ansicht(self, paket_id: str) -> Laufansicht | None:
        for a in self.ansichten:
            if a.kopf.paket_id == paket_id:
                return a
        return None
