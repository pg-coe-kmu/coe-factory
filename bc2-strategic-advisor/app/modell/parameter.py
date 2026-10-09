"""
BC2 · Die **Setzungen** des Value- und Priorisierungsmodells.

ADR-006 · BC2 legt sich selbst eine Kalibrierung auf (2.5, 2.7): Euro-Schwellen
und Score-Bänder sind gesetzt, nicht geprüft. Damit das nachholbar bleibt,
stehen sie hier als benannte Voreinstellung statt als Zahl mitten im Rechenkern.

**Die Trennlinie dieses Moduls ist wichtig.** Hier liegt nur, was unter
Kalibrierungsvorbehalt steht oder als Marktgröße veralten kann. Was
*entschieden* ist, steht als Regel im Rechenkern und **nicht** hier — sonst
wäre jede getroffene Entscheidung über einen Aufrufparameter wieder offen:

- Dass ``impact_monetaer`` auf der **Mitte der Eingänge** beruht (#238, 20.09.2026),
- dass bei fehlender Value-Zahl der **Nutzwert allein** den Impact trägt (ebd.),
- dass ``executions_per_run`` **kein** Faktor ist (Invariante I2 des BC1-Vertrags),
- dass die Zusammensetzung eine **Eckenrechnung** ist (ADR-006, 2.3)

sind Modellregeln, keine Stellschrauben.

Gemessen am 20.09.2026 (#238) an elf durchgerechneten Potenzialen: die
Euro-Obergrenze ist **nicht** der Hebel, den man vermuten würde. Sie von
50.000 € auf 20.000 € zu senken ändert die Verteilung über die
Prioritätsgruppen um **null** — das Runden auf ganze Scores schluckt den
Unterschied. Der Deckel ist die Komplexitätsformel; siehe ``BAND_*`` unten.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# Die fünf Lösungsansatz-Klassen (ADR-006, 2.2). Als Literal statt als freier
# Text, damit ein Tippfehler beim Aufruf auffällt und nicht still in einen
# KeyError läuft. Die Schreibweise ist die des Vertrags v3.0
# (konzept.schema.json, potenziale[].automatisierungsgrad.klasse) — mit Schrägstrich
# ohne Leerzeichen; der Prototyp aus #167 schrieb sie anders und wäre am Vertrag
# gescheitert.
Klasse = Literal[
    "Regelwerk/Weiterleitung",
    "Integration",
    "Extraktion",
    "Textgenerierung",
    "Assistenz",
]

# Herkunft der Dauer, BC1s ``focus_step_duration_source``. ``None`` entspricht
# SQL-NULL und heißt: keine Value-Zahl (ADR-006, 2.3).
Herkunft = Literal["gemessen", "aus_system", "geschaetzt"]


@dataclass(frozen=True)
class Parameter:
    """Alle Setzungen eines Laufs an einer Stelle.

    ``frozen``, damit ein Lauf seine eigenen Parameter nicht unterwegs ändern
    kann — sonst wäre die Reproduzierbarkeit aus ADR-006 2.9 nicht mehr am
    Eingang ablesbar.
    """

    # --- Kostensätze ---------------------------------------------------------
    # Mischsatz aus dem NoroAI-Unternehmensprofil Kap. 9.2 (750.000 € / 2.200 PT
    # = 341 €/PT ≈ 43 €/h), entschieden in #172. Die Rollenachse wird nicht
    # erhoben; für die **Rangfolge** ist ein konstanter Faktor nachweislich
    # gleichwertig, weil er sich herauskürzt. Bei **absoluten** Beträgen
    # untertreibt er — das wird am Potenzial vermerkt, nicht weggerechnet.
    mischsatz_eur_h: float = 43.0

    # Der Bau fällt beim CoE zu Marktkonditionen an, nicht zu NoroAIs
    # Selbstkostensatz. **Zwei verschiedene Sätze mit Absicht** (ADR-006, 2.1):
    # derselbe Satz auf beiden Seiten kürzte sich in der Amortisation heraus und
    # wiese sie systematisch zu günstig aus — genau die Größe, auf die ein
    # Prüfer schaut. Reine Setzung, nicht erhoben.
    bausatz_eur_pt: float = 800.0

    # --- Automatisierungsgrad ------------------------------------------------
    # Der größte Hebel des Modells, und er wird von niemandem geliefert
    # (ADR-006, 2.2). Der Korridor ist hier die **Leitplanke**: das LLM setzt
    # eine Spanne an, und der Rechenkern prüft, dass sie innerhalb des Korridors
    # ihrer Klasse liegt. Wer den Korridor selbst als Wert einsetzte, machte das
    # Feld ``angesetzt_min_pct``/``angesetzt_max_pct`` des Vertrags überflüssig.
    korridore: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "Regelwerk/Weiterleitung": (0.70, 0.90),
            "Integration": (0.60, 0.85),
            "Extraktion": (0.50, 0.75),
            "Textgenerierung": (0.30, 0.50),
            "Assistenz": (0.10, 0.30),
        }
    )

    # --- Bandbreite je Herkunft der Dauer (ADR-006, 2.3) ---------------------
    # Der große Abstand nach oben ist Absicht: das einzige echte Beispiel trägt
    # ``geschaetzt`` bei 60 % Konfidenz und stammt aus einer Use-Case-Definition,
    # nicht aus einer Erhebung.
    breite_je_herkunft: dict[str, float] = field(
        default_factory=lambda: {
            "gemessen": 0.10,
            "aus_system": 0.15,
            "geschaetzt": 0.40,
        }
    )

    # --- Euro-Schwellen für impact_monetaer (ADR-006, 2.5) -------------------
    # ⚠ KALIBRIERUNGSVORBEHALT. Logarithmisch zwischen Untergrenze (Score 1) und
    # Obergrenze (Score 10), darunter und darüber gekappt. Die Obergrenze muss
    # unter NoroAIs Gesamtpersonalkosten bleiben (7.040 h × 43 €/h = 302.720 €/Jahr);
    # eine Skala, deren Spitze darüber liegt, könnte nie erreicht werden.
    euro_schwelle_unten: float = 1_000.0
    euro_schwelle_oben: float = 50_000.0

    # --- Score-Bänder für die Prioritätsgruppe (ADR-006, 2.7) ----------------
    # ⚠ KALIBRIERUNGSVORBEHALT, und der schärfste. Am 20.09.2026 (#238) über
    # elf Potenziale gemessen: mit diesen Grenzen landen **neun** in PRIO 2 —
    # die Gruppe sagt dann fast nichts mehr aus.
    #
    # Der Grund liegt aber **nicht** bei den Bändern allein, und deshalb steht
    # er hier: der Deckel ist ``komplexitaet = round(11 − 2 × reife)``. Bei
    # realistischer Prozessreife (3,5–3,75) ergibt das K = 4, also
    # ``score = impact × 7``; und der Impact kommt nicht über 6, weil der
    # Nutzwert bei ~6,6 endet und der monetäre Teil-Score bei einem Mandanten
    # dieser Größe meist 1–3 beträgt. PRIO 1 (≥ 50) verlangt damit entweder eine
    # Prozessreife, die es bei NoroAI nicht gibt, oder eine fünfstellige
    # Einsparung. Wer nur die Bänder verschiebt, behandelt das Symptom.
    #
    # Festgezurrt wird am ersten echten Lauf (#206, KW 40) — mit
    # ``tools/kalibrierung.py``, nicht nach Gefühl. Bis dahin bleiben die Werte
    # aus ADR-006 stehen, weil sie auf **erfundenen** Prototyp-Zahlen zu ändern
    # hieße, auf nichts zu kalibrieren.
    band_prio1: float = 50.0
    band_prio2: float = 20.0

    # --- Plausibilitätsschranke (Invariante I3, #172) ------------------------
    # 880 PT intern als Warnschwelle, 2.200 PT brutto als harte Grenze. Die
    # Prüfung ist **formal, nicht fachlich**: BC2 hängt einen Hinweis an und
    # weist nichts zurück — Plausibilität liegt bei BC0/BC1.
    kapazitaet_warn_h: float = 7_040.0
    kapazitaet_hart_h: float = 17_600.0

    # --- Plausibilitätsprobe gegen BC1 (ADR-006, 2.2) ------------------------
    # BC1s ``automation_potential_estimate_pct`` hat **keinen Vorrang** (falsche
    # Körnung: es hängt am Fokus-Schritt, der Grad gehört zum Lösungsansatz).
    # Es wird als Probe gelesen: liegt es außerhalb des angesetzten Korridors,
    # hängt BC2 einen Hinweis an — eine Abweichung ist das Signal, an dem ein
    # falsch gesetzter Korridor auffällt.
    bc1_abweichung_toleranz_pp: float = 0.0

    def __post_init__(self) -> None:
        if not 0 < self.euro_schwelle_unten < self.euro_schwelle_oben:
            raise ValueError(
                "Die Euro-Schwellen muessen 0 < unten < oben erfuellen, sonst ist "
                "der Logarithmus der Skala nicht definiert."
            )
        if not 0 < self.band_prio2 < self.band_prio1:
            raise ValueError(
                "Die Score-Baender muessen 0 < PRIO-2-Grenze < PRIO-1-Grenze "
                "erfuellen, sonst sind die Gruppen nicht zusammenhaengend."
            )
        for klasse, (lo, hi) in self.korridore.items():
            if not 0 <= lo <= hi <= 1:
                raise ValueError(f"Korridor {klasse!r} ist kein gueltiges Intervall in [0,1].")


#: Die Voreinstellung nach ADR-006 · BC2, Stand 20.09.2026. Wer sie ändert,
#: ändert eine Modellsetzung und schuldet einen Eintrag im ADR.
STANDARD = Parameter()
