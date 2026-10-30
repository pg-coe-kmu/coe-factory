"""Geteilte Prompt-Bausteine der LLM-Adapter (Claude, Ollama, Gemini).

Das Extraktionsschema ist de facto ein Wire-Vertrag mit dem Extractor,
und der Gesprächs-Prompt (inkl. Nachfrage-Hinweis) ist Dialog-Verhalten —
deshalb EIN Ort statt Kopien pro Adapter (Drift-Risiko).
"""
from __future__ import annotations

from bc1_core.core import zuletzt_gefragt
from bc1_core.gespraech import TurnKontext
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import SessionState

EXTRAKTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "extraktionen": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feld": {"type": "string"},
                    "wert": {"type": "string"},
                },
                "required": ["feld", "wert"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["extraktionen"],
    "additionalProperties": False,
}

PII_HINWEIS = (
    " Ausdrücke in eckigen Klammern wie [Person A], [E-Mail A] oder "
    "[Telefon A] sind Platzhalter für entfernte personenbezogene Angaben: "
    "übernimm sie wörtlich, löse sie nie auf und rate nicht, wer gemeint ist."
)

SYSTEM_EXTRAKTION = (
    "Du extrahierst Fakten aus einer Interview-Antwort für ein Prozessprofil. "
    "Extrahiere NUR, was die Nachricht wirklich belegt — nichts erfinden, "
    "nichts aus Vorwissen ergänzen. "
    "Die Nachricht beantwortet in erster Linie die gerade gestellte Frage; "
    "andere Felder nur, wenn die Nachricht sie ausdrücklich belegt. "
    "Liefere jeden Wert in der Antwortform des Felds: bei Auswahl die "
    "Kennung (nicht den Namen), bei Ja/Nein ‚ja‘ oder ‚nein‘, bei Häufigkeit "
    "und Dauer nur mit dem Zeitraum bzw. der Einheit, den die Nachricht "
    "nennt; nennt sie keinen (z. B. ‚300‘, ‚2x‘, ‚zweimal‘), lass das Feld "
    "weg — ergänze weder Einheit noch Zeitraum; bei Anzahl, Skala und "
    "Prozent nur die Zahl. "
    "Freitext und Listen: wörtlich bzw. minimal normalisiert, Platzhalter "
    "unverändert. "
    "Eindeutige Umformungen sind erwünscht (‚wöchentlich‘ → ‚1 pro Woche‘, "
    "‚eine halbe Stunde‘ → ‚30 Minuten‘, ‚jeden 2. Monat‘ → ‚6 pro Jahr‘). "
    "Ergänze nie eine Einheit oder einen Zeitraum, den die Nachricht nicht "
    "nennt. "
    "Felder mit Identitätsbezug nur, wenn die Nachricht die Kennung oder den "
    "Namen eindeutig nennt — keine Teilnamen, Ordinalzahlen oder "
    "Umschreibungen. "
    "Lass ein Feld weg, wenn die Angabe unsicher, eingeschränkt, "
    "widersprüchlich, eine Spanne oder eine Gegenfrage ist, ein ‚?‘ enthält, "
    "sich auf eine andere Bezugsgröße bezieht als die Frage, mehrere "
    "Optionen nennt, wo eine verlangt ist, oder nur mit einer Annahme "
    "umrechenbar ist (z. B. ‚vielleicht‘, ‚weiß nicht‘, ‚Ja, eigentlich "
    "nicht‘, ‚KP-03.TP-1?‘, ‚2–3 Stunden‘, ‚täglich‘, ‚2 Tage‘, ‚30 Minuten "
    "pro Lead‘, ‚eher gut‘, ‚Ja‘ auf eine Skalenfrage). Nichts erfinden."
) + PII_HINWEIS

SYSTEM_GESPRAECH = (
    "Du führst ein freundliches, professionelles Prozess-Interview auf "
    "Deutsch. Du bekommst, was der Nutzer gesagt hat, was daraus erfasst "
    "wurde und die nächste Kernfrage (oder beim Abschluss, dass das "
    "Interview beendet ist). Regeln: Bestätige NUR die gelieferten "
    "Werte — erfinde und ergänze nichts. Nenne NIE technische Feldnamen "
    "oder Interna. Solange das Interview läuft: kurze Bestätigung, falls "
    "nötig eine kurze Reaktion oder Erklärung, dann genau eine Frage. Bei "
    "Rückfragen und Nachfragen darfst du ein kurzes, neutrales Beispiel "
    "geben; in Erstfragen nie ein Beispiel. Variiere die Satzanfänge: "
    "bedanke dich höchstens einmal im ganzen Gespräch, nicht in jedem "
    "Zug. Antworte kompakt "
    "(2–4 Sätze plus Frage), ohne Meta-Kommentare. Beim Abschluss: 3–5 "
    "Sätze, OHNE Frage."
) + PII_HINWEIS


def _frage_mit_form(spec: FieldSpec) -> str:
    """Fragetext mit Antwortform; Identitätsbezug greift SYSTEM_EXTRAKTION auf."""
    zusatz = "; Identitätsbezug" if spec.identitaetskritisch else ""
    return f"{spec.question} (Antwortform: {spec.typ.antwortform}{zusatz})"


def extraktions_nutzer_prompt(message: str, package: UseCasePackage,
                              state: SessionState) -> str:
    teile = []
    gefragt = zuletzt_gefragt(state)
    if gefragt is not None:
        spec = package.field(gefragt)
        teile.append(f"Gerade gestellte Frage: {spec.name} — "
                     f"{_frage_mit_form(spec)}")
    felder = "\n".join(f"- {f.name}: {_frage_mit_form(f)}"
                       for f in package.fields)
    teile.append(f"Felder des Prozessprofils:\n{felder}")
    teile.append(f"Interview-Nachricht:\n{message}")
    teile.append("Gib alle Feld-Wert-Paare zurück, die diese Nachricht belegt.")
    return "\n\n".join(teile)


def gespraech_nutzer_prompt(kontext: TurnKontext) -> str:
    """Nutzer-Prompt der Gesprächsschicht — von allen Adaptern geteilt."""
    teile = [f"Nutzer-Nachricht:\n{kontext.nutzer_nachricht}"]
    if kontext.neu_erfasst:
        teile.append(
            "In diesem Turn erfasst (nur DIESE Werte bestätigen):\n"
            + "\n".join(f"- {e.frage} → {e.wert}" for e in kontext.neu_erfasst))
    else:
        teile.append("In diesem Turn wurde nichts Neues erfasst.")
    if kontext.ist_abschluss:
        teile.append(
            "Das Interview ist abgeschlossen. Fasse die Kernergebnisse in "
            "3–5 Sätzen zusammen:\n"
            + "\n".join(f"- {e.frage} → {e.wert}"
                        for e in kontext.profil_uebersicht))
        if kontext.offene_fragen:
            teile.append("Nenne ehrlich, was offen blieb:\n"
                         + "\n".join(f"- {f}" for f in kontext.offene_fragen))
        teile.append("Stelle KEINE weitere Frage — das Interview ist beendet.")
    elif kontext.ist_nachfrage:
        if kontext.antwortform is not None:
            teile.append(
                f"Antwortform: {kontext.antwortform}. Bitte ausdrücklich um "
                "eine Antwort in dieser Form (bei Ja/Nein: ‚mit Ja oder "
                "Nein‘). Ja und Nein bedeuten dasselbe wie in der Kernfrage "
                "(nicht umkehren, nicht verneinen). Bei einer Skala bleiben "
                "Richtung und Endpunkte. Nenne nur Optionen, die die "
                "Antwortform vorgibt — ein ‚oder‘ in einer Ja/Nein-Frage ist "
                "keine Auswahl.")
        teile.append(
            "NACHFRAGE — für dieses Feld liegt noch kein verwertbarer Wert "
            "vor. Frage nach demselben Gegenstand wie die Kernfrage, "
            "formuliere sie aber anders und konkreter, erkläre kurz den Zweck "
            "(gern mit einem kurzen, neutralen Beispiel) und sage, dass das "
            "Feld offen bleiben darf, wenn der Nutzer es nicht weiß.\n"
            f"Kernfrage: {kontext.naechste_frage}")
    else:
        teile.append("Stelle als Nächstes GENAU diese Frage, wörtlich "
                     f"übernommen:\n{kontext.naechste_frage}")
    return "\n\n".join(teile)
