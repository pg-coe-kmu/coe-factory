"""
BC2 · Der Rechenkern des Value- und Priorisierungsmodells (ADR-006 · BC2).

**Eine reine Funktion.** ``rechne_lauf`` liest nichts, schreibt nichts, ruft kein
LLM und kennt keine Uhr. Gleiche Eingänge, gleiche Zahlen — das ist die eine
Zusage, an der die Reproduzierbarkeit aus ADR-006 2.9 hängt, und sie ist genau
deshalb hier prüfbar und nicht erst im Betrieb.

**Was hier NICHT liegt.** Das Lesen aus der gemeinsamen Datenbank auf
``stand_zum(uebergeben_am)`` und das Erkennen, *welche* Potenziale ein Paket
überhaupt trägt, gehört zu [#194](https://github.com/pg-coe-kmu/coe-factory/issues/194).
Dieser Kern bekommt die Werte gereicht. Der Schnitt ist Absicht: die Rechnung
ist gegen Fixtures vollständig prüfbar, das Lesen nicht — und ein grüner
Doppelgänger beweist keine Datenbankgarantie (die Lehre aus #190/#205).

**Das LLM urteilt an genau vier Stellen** (ADR-006, 2.0) — Lösungsansatz-Klasse,
Lage im Korridor, die fünf Nutzwert-Kategorien und das begründete Überschreiben
der Umsetzungskomplexität. Alle vier kommen hier als *Eingang* an, nicht als
Aufruf. Was dieser Kern tut, rechnet er selbst.

Bezug: ADR-006 · BC2 · Vertrag ``contracts/bc2-to-bc3/konzept.schema.json`` v3.0 ·
Ticket [#238](https://github.com/pg-coe-kmu/coe-factory/issues/238).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from .parameter import STANDARD, Herkunft, Klasse, Parameter

__all__ = [
    "Spanne",
    "Quellwert",
    "Nutzwertkategorie",
    "Nutzwert",
    "Potenzialeingang",
    "Automatisierungsgrad",
    "Value",
    "Hinweis",
    "Potenzial",
    "Prozessrang",
    "Lauf",
    "rechne_lauf",
    "runde",
]


# ---------------------------------------------------------------------------
# Runden
# ---------------------------------------------------------------------------


def runde(wert: float, stellen: int = 0) -> float:
    """Kaufmännisch runden — 2,5 wird 3, nicht 2.

    **Warum nicht Pythons ``round``.** Das eingebaute ``round`` rundet zur
    geraden Zahl (``round(2.5) == 2``, ``round(3.5) == 4``). Für die
    Gleitkommarechnung ist das die bessere Wahl, hier ist es die schlechtere:
    ADR-006 verlangt, dass ein Prüfer die Zahlen **von Hand nachrechnen** kann,
    und von Hand rundet niemand zur geraden Zahl. Bei
    ``komplexitaet = round(11 − 2 × reife)`` trifft es real: eine Reife von 3,25
    ergibt 4,5 — kaufmännisch 5, bankmäßig 4, und das ist ein ganzer
    Score-Schritt Unterschied.

    ADR-006 schreibt nur »round«; diese Lesart ist die, die der Forderung nach
    Nachrechenbarkeit folgt, und sie ist hier festgehalten statt verschwiegen.
    """
    q = Decimal(1) if stellen == 0 else Decimal(1).scaleb(-stellen)
    gerundet = Decimal(str(wert)).quantize(q, rounding=ROUND_HALF_UP)
    return int(gerundet) if stellen == 0 else float(gerundet)


# ---------------------------------------------------------------------------
# Werttypen
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Spanne:
    """Eine Bandbreite statt eines Punktwerts (Vertrag v3.0, ``$defs/spanne``)."""

    min: float
    max: float

    def __post_init__(self) -> None:
        if self.min > self.max:
            raise ValueError(f"Spanne verkehrt herum: {self.min} > {self.max}")
        if self.min < 0:
            raise ValueError(f"Spanne darf nicht negativ sein: {self.min}")

    @property
    def mitte(self) -> float:
        return (self.min + self.max) / 2

    def als_dict(self, stellen: int = 0) -> dict[str, float]:
        return {"min": runde(self.min, stellen), "max": runde(self.max, stellen)}


@dataclass(frozen=True)
class Quellwert:
    """Ein gelesener Eingangswert samt Herkunft.

    Wandert unverändert nach ``konzept.eingangswerte[]``. Der Grund steht in
    ADR-006 2.9: die Lieferung geht als Datei an BC3 und als Präsentation an den
    Mandanten, und **beide müssen ohne Datenbankzugriff prüfbar sein**. Nicht der
    ganze Bestand — nur das Gerechnete.

    ``gelesen_am`` fehlt hier mit Absicht: es gilt für den ganzen Lauf und wird
    beim Ausgeben einmal gestempelt, statt an jeder Zeile wiederholt zu werden.
    """

    groesse: str
    wert: str | float | None
    herkunft_tabelle: str
    herkunft_spalte: str
    einheit: str | None = None
    herkunft_id: str | None = None
    betrifft_teilprozess_id: str | None = None
    #: Herkunftsvermerk aus der Quelle, z. B. BC1s Testdaten-Präfix aus
    #: ``open_remarks``. BC2 lehnt deshalb nicht ab, sondern reicht durch (#184).
    kennzeichnung: str | None = None


@dataclass(frozen=True)
class Nutzwertkategorie:
    """Eine der fünf Nutzwert-Kategorien: Wert 1–10 plus Begründungssatz."""

    wert: int
    begruendung: str

    def __post_init__(self) -> None:
        if not 1 <= self.wert <= 10:
            raise ValueError(f"Nutzwert-Kategorie ausserhalb 1–10: {self.wert}")


@dataclass(frozen=True)
class Nutzwert:
    """Die nicht-monetäre Nutzenseite (ADR-006, 2.4).

    Fünf Kategorien, **ungewichtetes** Mittel — aus demselben Grund, aus dem
    Bitkom es ist: eine Gewichtung wäre reine Setzung und ließe sich gegenüber
    einem Prüfer nicht begründen.

    Kostenreduktion gehört **nicht** dazu: sie *ist* der ``value`` und zählte
    über den Impact doppelt.
    """

    qualitaet: Nutzwertkategorie
    durchlaufzeit: Nutzwertkategorie
    fehlerreduktion: Nutzwertkategorie
    mitarbeiterzufriedenheit: Nutzwertkategorie
    compliance: Nutzwertkategorie

    @property
    def kategorien(self) -> tuple[Nutzwertkategorie, ...]:
        return (
            self.qualitaet,
            self.durchlaufzeit,
            self.fehlerreduktion,
            self.mitarbeiterzufriedenheit,
            self.compliance,
        )

    @property
    def mittel(self) -> float:
        return sum(k.wert for k in self.kategorien) / len(self.kategorien)


@dataclass(frozen=True)
class Potenzialeingang:
    """Was der Kern braucht, um ein Potenzial durchzurechnen.

    Die Feldnamen der gemessenen Größen sind **1:1 die des BC1-Vertrags** — das
    ist dort Vertragsbestandteil (#184) und erspart eine Übersetzungstabelle,
    an der sich ein Missverständnis festsetzen könnte.
    """

    # --- Identität ----------------------------------------------------------
    potenzial_id: str
    titel: str
    kp_id: str
    betroffene_teilprozess_ids: tuple[str, ...]

    # --- Geurteilt: die vier Stellen des LLM (ADR-006, 2.0) -----------------
    klasse: Klasse
    automatisierungsgrad_begruendung: str
    nutzwert: Nutzwert

    # --- Gemessen: BC1 ------------------------------------------------------
    frequency_per_year: float | None = None
    total_duration_minutes: float | None = None
    #: BC1s ``focus_step_duration_source``. ``None`` ⇒ **keine Value-Zahl**
    #: (ADR-006, 2.3) — eine Spanne von ±100 % wäre keine Aussage mehr.
    focus_step_duration_source: Herkunft | None = None
    #: Wird mitgeführt, **verfeinert die Bandbreite aber nicht**: aus einer
    #: geschätzten Prozentzahl eine feinere Spanne zu rechnen erfände die
    #: Genauigkeit, die die Spanne gerade eingestehen soll.
    focus_step_duration_confidence_pct: float | None = None
    #: ``documentation_status``, ``standardization_level``,
    #: ``data_availability_score``, ``stability_score`` — je 1–5. Fehlen sie,
    #: urteilt das LLM allein und die Herkunft wird ``geurteilt``.
    reifeskalen: tuple[int, int, int, int] | None = None
    #: BC1s ``automation_potential_estimate_pct``. **Kein Vorrang** — es hängt am
    #: Fokus-Schritt, der Grad gehört zum Lösungsansatz. Nur Plausibilitätsprobe.
    automation_potential_estimate_pct: float | None = None

    # --- Angesetzter Automatisierungsgrad -----------------------------------
    #: Die vom LLM im Korridor verortete Spanne. ``None`` ⇒ der ganze Korridor
    #: der Klasse. Der Korridor ist die **Leitplanke**, nicht der Wert: läge er
    #: immer selbst im Ergebnis, wäre das Vertragsfeld überflüssig.
    angesetzt_min_pct: float | None = None
    angesetzt_max_pct: float | None = None

    # --- Geurteilt / gesetzt ------------------------------------------------
    aufwand_schaetzung_pt: float | None = None
    komplexitaet_ueberschrieben: int | None = None
    komplexitaet_begruendung: str | None = None

    # --- Herkunftsnachweise -------------------------------------------------
    erhebung_id: str | None = None
    kennzeichnung: str | None = None
    #: Die gemessenen Größen sind **gesetzt, nicht erhoben** — dann trägt das
    #: Ergebnis ``value_quelle = "annahme"`` statt ``"berechnet"``.
    #:
    #: Ohne dieses Feld wäre der Vertragswert ``annahme`` aus dem Kern
    #: unerreichbar: er kennt sonst nur ``berechnet`` und ``keine``. Eine
    #: simulierte Lieferung käme damit als ``berechnet`` heraus — der stärkste
    #: Anspruch, auf erfundenen Eingängen, und genau der Zustand, gegen den
    #: ``annahme`` in v3.0 aufgenommen wurde
    #: ([#168](https://github.com/pg-coe-kmu/coe-factory/issues/168)).
    #:
    #: Es ändert **keine Zahl**. Die Rechnung ist dieselbe; nur ihre Herkunft
    #: wird anders ausgewiesen — die Zahlen sind ja nicht falsch, sie ruhen nur
    #: auf gesetzten statt erhobenen Eingängen.
    groessen_gesetzt: bool = False

    def __post_init__(self) -> None:
        if self.reifeskalen is not None:
            if len(self.reifeskalen) != 4 or not all(1 <= s <= 5 for s in self.reifeskalen):
                raise ValueError(
                    f"reifeskalen muss vier Werte von 1 bis 5 tragen, bekam {self.reifeskalen!r}"
                )
        if self.komplexitaet_ueberschrieben is not None and not self.komplexitaet_begruendung:
            # ADR-006 2.6: ueberschreiben darf das LLM nur **begruendet**.
            raise ValueError(
                f"{self.potenzial_id}: komplexitaet_ueberschrieben ohne Begruendung. "
                "ADR-006 2.6 laesst das Ueberschreiben nur begruendet zu."
            )


@dataclass(frozen=True)
class Automatisierungsgrad:
    klasse: str
    korridor: Spanne
    angesetzt: Spanne
    begruendung: str
    bc1_schaetzung_pct: float | None = None


@dataclass(frozen=True)
class Value:
    """Die monetäre Seite, als Spannen (ADR-006, 2.1 und 2.3)."""

    value_quelle: str  # 'berechnet' | 'annahme' | 'default' | 'keine'
    ist_kosten_eur_jahr: Spanne | None = None
    einsparung_eur_jahr: Spanne | None = None
    ersparnis_prozent: Spanne | None = None
    investition_eur_richtwert: float | None = None
    amortisation_monate: Spanne | None = None
    annahmen: tuple[str, ...] = ()
    grund: str | None = None
    #: Der zentrale Schätzwert der Einsparung, aus dem ``impact_monetaer``
    #: entsteht. Kein Vertragsfeld — er wird mitgeführt, damit die Herleitung
    #: des Impacts nachrechenbar bleibt, ohne sie erneut zu rechnen.
    einsparung_zentral_eur: float | None = None


@dataclass(frozen=True)
class Hinweis:
    """Ein formaler Prüfhinweis. BC2 hängt an und weist **nicht** zurück (#172)."""

    art: str
    text: str


@dataclass(frozen=True)
class Potenzial:
    """Ein durchgerechnetes Potenzial."""

    potenzial_id: str
    titel: str
    kp_id: str
    betroffene_teilprozess_ids: tuple[str, ...]

    jahresstunden: Spanne | None
    jahresstunden_zentral: float | None
    aufwand_herkunft: str  # gemessen | aus_system | geschaetzt | unbekannt
    konfidenz_pct: float | None

    automatisierungsgrad: Automatisierungsgrad
    value: Value

    nutzwert: float
    impact_monetaer: int | None
    impact: int
    impact_herleitung: str

    umsetzungskomplexitaet: int
    komplexitaet_herkunft: str  # gemessen | geurteilt
    komplexitaet_begruendung: str | None

    aufwand_schaetzung_pt: float | None

    prioritaet_score: int
    kategorie: str
    prioritaetsgruppe: str
    potenzialrang: int

    eingangswerte: tuple[Quellwert, ...]
    hinweise: tuple[Hinweis, ...]


@dataclass(frozen=True)
class Prozessrang:
    """Der Rang eines Kernprozesses: der seines **besten** Potenzials.

    Nicht die Summe (bevorzugte Prozesse mit vielen kleinen Potenzialen) und
    nicht das Mittel (bestrafte einen Prozess dafür, dass er neben seinem Quick
    Win noch schwierige Potenziale hat). Die Frage lautet »welchen Prozess fasse
    ich zuerst an«, und angefangen wird mit dem, was sich zuerst lohnt.
    """

    kp_id: str
    rang: int
    bestes_potenzial_id: str
    bester_score: int


@dataclass(frozen=True)
class Lauf:
    """Das Ergebnis eines Analyselaufs ``(company_id, paket_id)`` — ADR-005 · BC2."""

    company_id: str
    paket_id: str
    potenziale: tuple[Potenzial, ...]
    prozess_raenge: tuple[Prozessrang, ...]
    parameter: Parameter
    jahresstunden_gesamt: float
    hinweise: tuple[Hinweis, ...] = ()


# ---------------------------------------------------------------------------
# Die Rechnung
# ---------------------------------------------------------------------------


def _impact_monetaer(einsparung_eur: float, p: Parameter) -> int:
    """Absolute Euro-Schwellen, logarithmisch (ADR-006, 2.5).

    **Absolut, nicht relativ zum Lauf.** Bei relativer Normierung änderte sich
    der Impact eines Potenzials, sobald ein anderes Paket geschnitten wird — und
    das Konzept geht je Kernprozess an BC3: derselbe Prozess bekäme in zwei
    Lieferungen verschiedene Zahlen, ohne dass sich an ihm etwas geändert hätte.
    """
    if einsparung_eur <= 0:
        return 1
    spanne = math.log10(p.euro_schwelle_oben) - math.log10(p.euro_schwelle_unten)
    roh = 1 + 9 * (math.log10(einsparung_eur) - math.log10(p.euro_schwelle_unten)) / spanne
    return int(max(1, min(10, runde(roh))))


def _kategorie(impact: int, komplexitaet: int) -> str:
    """Etikett im Quadranten. Sagt **nichts** über die Reihenfolge.

    Die vierte Ecke heißt ``Zurueckgestellt``, nicht »Long Bet«: eine Wette
    verspricht einen Gewinn, den die Zahlen dort gerade nicht zeigen.
    """
    if impact >= 6:
        return "Quick Win" if komplexitaet <= 5 else "Strategisch"
    return "Optional" if komplexitaet <= 5 else "Zurueckgestellt"


def _prioritaetsgruppe(score: float, p: Parameter) -> str:
    if score >= p.band_prio1:
        return "PRIO 1"
    return "PRIO 2" if score >= p.band_prio2 else "PRIO 3"


def _angesetzter_korridor(e: Potenzialeingang, p: Parameter) -> tuple[Spanne, Spanne]:
    """Liefert (Korridor der Klasse, tatsächlich angesetzte Spanne).

    Die angesetzte Spanne muss **innerhalb** des Korridors liegen. Das ist der
    Sinn der fünf Korridore aus ADR-006 2.2: sie sind Leitplanke für das Urteil
    des LLM, nicht selbst das Urteil. Wer sie überschreitet, hat die Klasse
    falsch gewählt — und das soll auffallen, nicht stillschweigend gelten.
    """
    if e.klasse not in p.korridore:
        raise ValueError(f"Unbekannte Loesungsansatz-Klasse: {e.klasse!r}")
    lo, hi = p.korridore[e.klasse]
    korridor = Spanne(lo, hi)

    if e.angesetzt_min_pct is None and e.angesetzt_max_pct is None:
        return korridor, korridor
    if e.angesetzt_min_pct is None or e.angesetzt_max_pct is None:
        raise ValueError(
            f"{e.potenzial_id}: angesetzt_min_pct und angesetzt_max_pct gehoeren "
            "zusammen — entweder beide oder keines."
        )

    a_lo, a_hi = e.angesetzt_min_pct / 100, e.angesetzt_max_pct / 100
    if a_lo < lo or a_hi > hi:
        raise ValueError(
            f"{e.potenzial_id}: angesetzter Automatisierungsgrad "
            f"{e.angesetzt_min_pct}–{e.angesetzt_max_pct} % liegt ausserhalb des "
            f"Korridors der Klasse {e.klasse!r} ({lo * 100:.0f}–{hi * 100:.0f} %). "
            "Entweder ist die Klasse falsch gewaehlt oder die Lage falsch begruendet "
            "(ADR-006, 2.2)."
        )
    return korridor, Spanne(a_lo, a_hi)


def _komplexitaet(e: Potenzialeingang) -> tuple[int, str, str | None]:
    """Umsetzungskomplexität — **gemessen**, nicht geurteilt (ADR-006, 2.6).

    Gibt (Wert, Herkunft, Begründung) zurück.

    Bekannter Schönheitsfehler: die Formel erreicht die 10 nie, der Wertebereich
    ist 1–9. Jede Streckung wäre willkürlicher als die Lücke.
    """
    if e.komplexitaet_ueberschrieben is not None:
        # Auch bei begruendetem Ueberschreiben: 'geurteilt'. Der Vertrag sagt es
        # ausdruecklich (konzept.schema.json, komplexitaet_herkunft).
        wert = e.komplexitaet_ueberschrieben
        if not 1 <= wert <= 10:
            raise ValueError(f"{e.potenzial_id}: komplexitaet_ueberschrieben ausserhalb 1–10.")
        return wert, "geurteilt", e.komplexitaet_begruendung

    if e.reifeskalen is None:
        raise ValueError(
            f"{e.potenzial_id}: weder BC1s vier Reifeskalen noch ein begruendeter "
            "Ueberschreibwert. Fehlen die Skalen, urteilt das LLM allein — dann "
            "gehoert der Wert nach komplexitaet_ueberschrieben, mit Begruendung "
            "(ADR-006, 2.6)."
        )

    reife = sum(e.reifeskalen) / 4
    wert = int(runde(11 - 2 * reife))
    skalen = "/".join(str(s) for s in e.reifeskalen)
    return (
        wert,
        "gemessen",
        f"Mittel aus BC1s vier Skalen ({skalen}) = {reife:.2f}; "
        f"komplexitaet = round(11 − 2 × {reife:.2f}) = {wert}.",
    )


def _value_und_impact(
    e: Potenzialeingang,
    angesetzt: Spanne,
    p: Parameter,
) -> tuple[Value, Spanne | None, float | None, int | None, int, str]:
    """Value, Jahresstunden, ``impact_monetaer`` und ``impact`` in einem Zug.

    Sie hängen so eng zusammen, dass getrennte Funktionen die Fallunterscheidung
    »gibt es eine Value-Zahl« zweimal treffen müssten — und genau dort sitzt die
    Entscheidung aus #238.
    """
    nutzwert = e.nutzwert.mittel

    fehlt = _warum_keine_value_zahl(e)
    if fehlt is not None:
        # ── Entscheidung #238, Frage 2: der Nutzwert trägt den Impact allein. ──
        # ``impact_monetaer = 1`` wäre die Alternative gewesen und behandelte
        # eine **fehlende Messung** wie eine gemessene Wertlosigkeit — der
        # Schluss vom Artefakt auf die Absicht, vor dem diese Karte dreimal
        # warnt (#163, #186, #165). ADR-006 hat den analogen Fall bereits so
        # entschieden: bei NULL gar keine Zahl statt einer erfundenen.
        impact = int(runde(nutzwert))
        return (
            Value(value_quelle="keine", grund=fehlt),
            None,
            None,
            None,
            impact,
            f"Nur Nutzwert ({nutzwert:.1f}) — der monetaere Teil-Score entfaellt: {fehlt}",
        )

    breite = p.breite_je_herkunft[e.focus_step_duration_source]
    frequenz = e.frequency_per_year
    dauer = e.total_duration_minutes

    # ── Invariante I2 (BC1-Vertrag, #184) ────────────────────────────────────
    # Dauern gelten **je Prozessdurchlauf**; ``executions_per_run`` ist KEIN
    # Multiplikator. Er kommt in dieser Rechnung darum nicht vor — und das ist
    # kein Versehen: multipliziert ergibt die Reisebuchung 48.600 h/Jahr, das
    # Dreifache der Gesamtkapazität eines Zehn-Personen-Betriebs, für EINEN
    # Schritt. Wer ihn hier ergänzt, bricht den Vertrag.
    stunden_lo = frequenz * dauer * (1 - breite) / 60
    stunden_hi = frequenz * dauer * (1 + breite) / 60
    stunden_zentral = frequenz * dauer / 60

    # ── Eckenrechnung (ADR-006, 2.3) ─────────────────────────────────────────
    # Unteres Ende der Dauer × unteres Ende des Korridors, oberes × oberes.
    # Bewusst pessimistisch: sie unterstellt, dass beide Fehler gleichsinnig
    # auftreten. Monte-Carlo wurde verworfen — es verlangt Verteilungsannahmen,
    # die niemand erhoben hat.
    ist_lo, ist_hi = stunden_lo * p.mischsatz_eur_h, stunden_hi * p.mischsatz_eur_h
    einsparung_lo = ist_lo * angesetzt.min
    einsparung_hi = ist_hi * angesetzt.max

    # ── Entscheidung #238, Frage 1: die **Mitte der Eingänge**. ───────────────
    # Nicht die Mitte der Spanne: (lo·lo + hi·hi)/2 liegt systematisch ÜBER der
    # zentralen Schätzung, weil die Eckenrechnung beide Fehler gleichsinnig
    # multipliziert — sie erbt den Pessimismus als Überhöhung. Und nicht das
    # untere Ende: das zählt die Pessimismus-Annahme ein zweites Mal und drückte
    # am gemessenen Satz 4 von 10 Potenzialen auf den Bodenwert 1, womit der
    # monetäre Teil-Score seine Trennschärfe verlöre.
    einsparung_zentral = stunden_zentral * p.mischsatz_eur_h * angesetzt.mitte

    annahmen = [
        f"Mischsatz {p.mischsatz_eur_h:.0f} EUR/h aus dem NoroAI-Unternehmensprofil "
        "(#172) — die Rollenachse wird nicht erhoben.",
        f"Bausatz {p.bausatz_eur_pt:.0f} EUR/PT fuer die Investition; ein anderer Satz "
        "als die Einsparungsseite, mit Absicht (ADR-006, 2.1). Reine Setzung.",
        f"Automatisierungsgrad {angesetzt.min * 100:.0f}–{angesetzt.max * 100:.0f} % "
        f"aus dem Korridor der Klasse {e.klasse!r} — gesetzt, nicht erhoben.",
        f"Bandbreite ±{breite * 100:.0f} % aus der Herkunft der Dauer "
        f"({e.focus_step_duration_source}).",
        "Zusammensetzung als Eckenrechnung: bewusst pessimistisch, sie unterstellt "
        "gleichsinnige Fehler.",
    ]
    if e.groessen_gesetzt:
        # An den Anfang, nicht ans Ende: wer nur die erste Zeile liest, muss
        # genau das erfahren. Dieselbe Staffelung wie in der Lieferung vom
        # 30.08.2026 (#168), wo `annahmen[0]` den Warntext trug.
        annahmen.insert(
            0,
            "GESETZT, NICHT ERHOBEN — Haeufigkeit und Dauer dieses Potenzials sind "
            "angenommen. Die Rechnung darunter ist korrekt, ihre Eingaenge sind es "
            "nicht. Nicht fuer Entscheidungen, Angebote oder Gate-1-Freigaben.",
        )

    investition = None
    amortisation = None
    if e.aufwand_schaetzung_pt is not None:
        investition = e.aufwand_schaetzung_pt * p.bausatz_eur_pt
        # Hohe Einsparung ⇒ kurze Amortisation: die Spanne dreht sich um.
        amortisation = Spanne(
            investition / (einsparung_hi / 12) if einsparung_hi > 0 else 0.0,
            investition / (einsparung_lo / 12) if einsparung_lo > 0 else 0.0,
        )

    if investition is None:
        # Der Vertrag verlangt bei value_quelle != 'keine' **alle fuenf** Groessen.
        # Ohne Aufwandsschaetzung koennen Investition und Amortisation nicht
        # entstehen — dann lieber gar keine Zahl als eine halbe, die am Schema
        # scheitert.
        impact = int(runde(nutzwert))
        grund = (
            "Kein Aufwandsrichtwert (aufwand_schaetzung_pt) — ohne ihn gibt es keine "
            "Investition und keine Amortisation, und der Vertrag verlangt sie "
            "zusammen mit der Einsparung."
        )
        return (
            Value(value_quelle="keine", grund=grund),
            Spanne(stunden_lo, stunden_hi),
            stunden_zentral,
            None,
            impact,
            f"Nur Nutzwert ({nutzwert:.1f}) — {grund}",
        )

    impact_monetaer = _impact_monetaer(einsparung_zentral, p)
    impact = int(runde((impact_monetaer + nutzwert) / 2))

    value = Value(
        # 'annahme' ist kein schwächeres 'berechnet', sondern eine Aussage über
        # die **Eingänge**: gerechnet wurde gleich, erhoben wurde nichts.
        value_quelle="annahme" if e.groessen_gesetzt else "berechnet",
        ist_kosten_eur_jahr=Spanne(ist_lo, ist_hi),
        einsparung_eur_jahr=Spanne(einsparung_lo, einsparung_hi),
        # Die Eckenrechnung macht den Prozentsatz **exakt** zum angesetzten
        # Korridor: einsparung_lo / ist_lo == angesetzt.min, und oben ebenso.
        ersparnis_prozent=Spanne(angesetzt.min * 100, angesetzt.max * 100),
        investition_eur_richtwert=investition,
        amortisation_monate=amortisation,
        annahmen=tuple(annahmen),
        einsparung_zentral_eur=einsparung_zentral,
    )
    herleitung = (
        f"round(({impact_monetaer} + {nutzwert:.1f}) / 2) = {impact}. Der monetaere "
        f"Teil-Score stammt aus der Mitte der Eingaenge "
        f"({stunden_zentral:.1f} h x {p.mischsatz_eur_h:.0f} EUR/h x "
        f"{angesetzt.mitte * 100:.1f} % = {einsparung_zentral:,.0f} EUR/Jahr)."
    )
    return value, Spanne(stunden_lo, stunden_hi), stunden_zentral, impact_monetaer, impact, herleitung


def _warum_keine_value_zahl(e: Potenzialeingang) -> str | None:
    """``None``, wenn gerechnet werden kann — sonst der Grund im Klartext."""
    if e.focus_step_duration_source is None:
        return (
            "Die Herkunft der Dauer ist nicht erhoben (focus_step_duration_source "
            "ist NULL). Eine Spanne von ±100 % waere keine Aussage mehr; BC2 rechnet "
            "qualitativ weiter und vermerkt die Luecke (ADR-006, 2.3)."
        )
    if e.total_duration_minutes is None or e.frequency_per_year is None:
        return (
            "Dauer oder Haeufigkeit fehlen (total_duration_minutes / "
            "frequency_per_year) — ohne sie gibt es keine Jahresstunden."
        )
    if e.total_duration_minutes <= 0 or e.frequency_per_year <= 0:
        return (
            f"Dauer ({e.total_duration_minutes}) oder Haeufigkeit "
            f"({e.frequency_per_year}) ist nicht positiv — daraus entsteht keine "
            "belastbare Jahresstundenzahl."
        )
    return None


def _eingangswerte(e: Potenzialeingang, p: Parameter) -> tuple[Quellwert, ...]:
    """Die Werte, die in die Zahlen eingegangen sind — mit Herkunft.

    **Nicht der ganze Bestand, nur das Gerechnete** (ADR-006, 2.9). Auflage 2 aus
    #238: jeder ausgegebene Wert sagt, ob er gemessen, gesetzt oder geurteilt
    ist, und die Eingangswerte reisen mit.
    """
    tp = e.betroffene_teilprozess_ids[0] if e.betroffene_teilprozess_ids else None
    werte: list[Quellwert] = []

    def bc1(groesse: str, wert, einheit: str | None) -> Quellwert:
        return Quellwert(
            groesse=groesse,
            wert=wert,
            einheit=einheit,
            herkunft_tabelle="bc1.prozessprofil",
            herkunft_spalte=groesse,
            herkunft_id=e.erhebung_id,
            betrifft_teilprozess_id=tp,
            kennzeichnung=e.kennzeichnung,
        )

    werte.append(bc1("frequency_per_year", e.frequency_per_year, "Durchlaeufe/Jahr"))
    werte.append(bc1("total_duration_minutes", e.total_duration_minutes, "Minuten/Durchlauf"))
    werte.append(bc1("focus_step_duration_source", e.focus_step_duration_source, None))
    if e.focus_step_duration_confidence_pct is not None:
        werte.append(
            bc1("focus_step_duration_confidence_pct", e.focus_step_duration_confidence_pct, "%")
        )
    if e.automation_potential_estimate_pct is not None:
        werte.append(
            bc1("automation_potential_estimate_pct", e.automation_potential_estimate_pct, "%")
        )
    if e.reifeskalen is not None:
        for name, wert in zip(
            ("documentation_status", "standardization_level", "data_availability_score",
             "stability_score"),
            e.reifeskalen,
        ):
            werte.append(bc1(name, wert, "1-5"))

    # Die Setzungen reisen als eigene Zeilen mit — sonst stuende im Konzept eine
    # Zahl, deren Herkunft nur im ADR nachzulesen waere.
    werte.append(
        Quellwert(
            groesse="mischsatz_eur_h",
            wert=p.mischsatz_eur_h,
            einheit="EUR/h",
            herkunft_tabelle="(Setzung)",
            herkunft_spalte="NoroAI-Unternehmensprofil Kap. 9.2, #172",
        )
    )
    werte.append(
        Quellwert(
            groesse="bausatz_eur_pt",
            wert=p.bausatz_eur_pt,
            einheit="EUR/PT",
            herkunft_tabelle="(Setzung)",
            herkunft_spalte="ADR-006 BC2, 2.1",
        )
    )
    return tuple(werte)


def _hinweise(
    e: Potenzialeingang,
    jahresstunden_zentral: float | None,
    angesetzt: Spanne,
    p: Parameter,
) -> tuple[Hinweis, ...]:
    """Formale Prüfhinweise. BC2 hängt an und weist **nichts** zurück (#172)."""
    hinweise: list[Hinweis] = []

    if jahresstunden_zentral is not None:
        if jahresstunden_zentral > p.kapazitaet_hart_h:
            hinweise.append(
                Hinweis(
                    "kapazitaet_ueberschritten",
                    f"{jahresstunden_zentral:,.0f} h/Jahr uebersteigen die Brutto-Kapazitaet "
                    f"des Mandanten ({p.kapazitaet_hart_h:,.0f} h). Die Pruefung ist formal, "
                    "nicht fachlich — Plausibilitaet liegt bei BC0/BC1 (Invariante I3, #172).",
                )
            )
        elif jahresstunden_zentral > p.kapazitaet_warn_h:
            hinweise.append(
                Hinweis(
                    "kapazitaet_ueberschritten",
                    f"{jahresstunden_zentral:,.0f} h/Jahr liegen ueber der internen "
                    f"Warnschwelle von {p.kapazitaet_warn_h:,.0f} h (880 PT). Kein Abweisen, "
                    "nur ein Hinweis (Invariante I3, #172).",
                )
            )

    if e.automation_potential_estimate_pct is not None:
        bc1_grad = e.automation_potential_estimate_pct / 100
        tol = p.bc1_abweichung_toleranz_pp / 100
        if not (angesetzt.min - tol) <= bc1_grad <= (angesetzt.max + tol):
            hinweise.append(
                Hinweis(
                    "bc1_abweichung",
                    f"BC1 schaetzt den Automatisierungsgrad auf "
                    f"{e.automation_potential_estimate_pct:.0f} %, angesetzt sind "
                    f"{angesetzt.min * 100:.0f}–{angesetzt.max * 100:.0f} %. Die Schaetzung hat "
                    "keinen Vorrang (falsche Koernung, ADR-006 2.2) — die Abweichung ist das "
                    "Signal, an dem ein falsch gesetzter Korridor auffaellt.",
                )
            )

    if e.kennzeichnung and e.kennzeichnung.strip().lower().startswith("testdaten"):
        hinweise.append(
            Hinweis(
                "testdaten",
                f"Die Quelle ist als Testdaten gekennzeichnet: {e.kennzeichnung!r}. "
                "Durchgereicht statt abgewiesen (#184).",
            )
        )

    return tuple(hinweise)


def rechne_lauf(
    company_id: str,
    paket_id: str,
    eingaenge: Iterable[Potenzialeingang],
    parameter: Parameter = STANDARD,
) -> Lauf:
    """Rechnet einen Analyselauf durch. **Rein** — gleiche Eingänge, gleiche Zahlen.

    Die Einheit ist ``(company_id, paket_id)``: der Lauf **ist** das Paket, nicht
    der Mandant (ADR-005 · BC2). Ein Mandantenlauf über mehrere Pakete hätte
    keinen einzelnen Zeitpunkt für ``stand_zum()`` und keinen einheitlichen
    Freigabestand — und die Nachrechenbarkeit hängt genau daran.
    """
    eingaenge = list(eingaenge)
    if not eingaenge:
        raise ValueError("Ein Lauf ohne Potenziale ist kein Lauf.")

    doppelte = {e.potenzial_id for e in eingaenge}
    if len(doppelte) != len(eingaenge):
        raise ValueError("Doppelte potenzial_id im Lauf — eine Kennung, ein Inhalt (ADR-002).")

    roh: list[Potenzial] = []
    for e in eingaenge:
        korridor, angesetzt = _angesetzter_korridor(e, parameter)
        komplexitaet, k_herkunft, k_begruendung = _komplexitaet(e)
        value, stunden, stunden_zentral, im, impact, herleitung = _value_und_impact(
            e, angesetzt, parameter
        )

        score = int(impact * (11 - komplexitaet))
        roh.append(
            Potenzial(
                potenzial_id=e.potenzial_id,
                titel=e.titel,
                kp_id=e.kp_id,
                betroffene_teilprozess_ids=e.betroffene_teilprozess_ids,
                jahresstunden=stunden,
                jahresstunden_zentral=stunden_zentral,
                aufwand_herkunft=e.focus_step_duration_source or "unbekannt",
                konfidenz_pct=e.focus_step_duration_confidence_pct,
                automatisierungsgrad=Automatisierungsgrad(
                    klasse=e.klasse,
                    korridor=korridor,
                    angesetzt=angesetzt,
                    begruendung=e.automatisierungsgrad_begruendung,
                    bc1_schaetzung_pct=e.automation_potential_estimate_pct,
                ),
                value=value,
                nutzwert=e.nutzwert.mittel,
                impact_monetaer=im,
                impact=impact,
                impact_herleitung=herleitung,
                umsetzungskomplexitaet=komplexitaet,
                komplexitaet_herkunft=k_herkunft,
                komplexitaet_begruendung=k_begruendung,
                aufwand_schaetzung_pt=e.aufwand_schaetzung_pt,
                prioritaet_score=score,
                kategorie=_kategorie(impact, komplexitaet),
                prioritaetsgruppe=_prioritaetsgruppe(score, parameter),
                potenzialrang=0,  # wird gleich gesetzt
                eingangswerte=_eingangswerte(e, parameter),
                hinweise=_hinweise(e, stunden_zentral, angesetzt, parameter),
            )
        )

    # ── Potenzialrang: strikt nach Score über den ganzen Analyselauf. ─────────
    # Bei Gleichstand entscheidet die potenzial_id. Das ist willkürlich, aber
    # **stabil** — und Stabilität ist hier die Zusage: zwei Läufe desselben
    # Pakets müssen dieselbe Reihenfolge liefern, auch bei gleichem Score.
    # Ohne zweites Kriterium hinge sie an der Eingangsreihenfolge.
    sortiert = sorted(roh, key=lambda x: (-x.prioritaet_score, x.potenzial_id))
    potenziale = tuple(
        replace(pot, potenzialrang=i) for i, pot in enumerate(sortiert, start=1)
    )

    # ── Prozessrang: der Rang des besten Potenzials je Kernprozess. ──────────
    bestes: dict[str, Potenzial] = {}
    for pot in potenziale:
        if pot.kp_id not in bestes:  # potenziale ist bereits nach Rang sortiert
            bestes[pot.kp_id] = pot
    prozess_raenge = tuple(
        Prozessrang(
            kp_id=pot.kp_id,
            rang=i,
            bestes_potenzial_id=pot.potenzial_id,
            bester_score=pot.prioritaet_score,
        )
        for i, pot in enumerate(
            sorted(bestes.values(), key=lambda x: x.potenzialrang), start=1
        )
    )

    gesamt = sum(p.jahresstunden_zentral or 0.0 for p in potenziale)
    lauf_hinweise: list[Hinweis] = []
    if gesamt > parameter.kapazitaet_hart_h:
        lauf_hinweise.append(
            Hinweis(
                "kapazitaet_ueberschritten",
                f"Die Potenziale dieses Laufs summieren sich auf {gesamt:,.0f} h/Jahr und "
                f"uebersteigen damit die Brutto-Kapazitaet des Mandanten "
                f"({parameter.kapazitaet_hart_h:,.0f} h). Formal, nicht fachlich (#172).",
            )
        )
    elif gesamt > parameter.kapazitaet_warn_h:
        lauf_hinweise.append(
            Hinweis(
                "kapazitaet_ueberschritten",
                f"Die Potenziale dieses Laufs summieren sich auf {gesamt:,.0f} h/Jahr und "
                f"liegen ueber der internen Warnschwelle ({parameter.kapazitaet_warn_h:,.0f} h).",
            )
        )

    return Lauf(
        company_id=company_id,
        paket_id=paket_id,
        potenziale=potenziale,
        prozess_raenge=prozess_raenge,
        parameter=parameter,
        jahresstunden_gesamt=gesamt,
        hinweise=tuple(lauf_hinweise),
    )
