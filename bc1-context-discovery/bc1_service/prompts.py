"""Geteilte Prompt-Bausteine der LLM-Adapter (Claude, Ollama, Gemini).

Das Extraktionsschema ist de facto ein Wire-Vertrag mit dem Extractor,
und der Gesprächs-Prompt (inkl. Nachfrage-Hinweis) ist Dialog-Verhalten —
deshalb EIN Ort statt Kopien pro Adapter (Drift-Risiko).
"""
from __future__ import annotations

from bc1_core.gespraech import TurnKontext

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

SYSTEM_EXTRAKTION = (
    "Du extrahierst Fakten aus einer Interview-Antwort für ein Prozessprofil. "
    "Extrahiere NUR, was die Nachricht wirklich belegt — nichts erfinden, "
    "nichts aus Vorwissen ergänzen. Werte wörtlich bzw. minimal normalisiert."
)

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
)


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
        teile.append(
            "NACHFRAGE — für dieses Feld liegt noch kein verwertbarer Wert "
            "vor. Formuliere die Kernfrage anders und konkreter, nenne in der "
            "Frage enthaltene Optionen vollständig, erkläre kurz den Zweck "
            "(gern mit einem kurzen, neutralen Beispiel) und sage, dass das "
            "Feld offen bleiben darf, wenn der Nutzer es nicht weiß.\n"
            f"Kernfrage: {kontext.naechste_frage}")
    else:
        teile.append("Stelle als Nächstes GENAU diese Frage, wörtlich "
                     f"übernommen:\n{kontext.naechste_frage}")
    return "\n\n".join(teile)
