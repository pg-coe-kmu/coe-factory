# Triage Labels

Die Skills sprechen in fünf kanonischen Triage-Rollen. Diese Datei bildet die
Rollen auf die tatsächlichen Label-Strings dieses Repos ab.

| Label in mattpocock/skills | Label in unserem Tracker | Bedeutung                                     |
| -------------------------- | ------------------------ | --------------------------------------------- |
| `needs-triage`             | `needs-triage`           | Maintainer muss das Issue bewerten            |
| `needs-info`               | `needs-info`             | Wartet auf Rückmeldung der meldenden Person   |
| `ready-for-agent`          | `ready-for-agent`        | Vollständig spezifiziert, bereit für AFK-Agent |
| `ready-for-human`          | `ready-for-human`        | Erfordert menschliche Umsetzung               |
| `wontfix`                  | `wontfix`                | Wird nicht umgesetzt                          |

Wenn ein Skill eine Rolle nennt (z. B. „apply the AFK-ready triage label"), den
entsprechenden Label-String aus dieser Tabelle verwenden.

Die rechte Spalte anpassen, falls sich das Vokabular ändert.

## Bestand im Repo

`wontfix` existiert bereits („Wird nicht umgesetzt") und wird wiederverwendet —
nicht neu anlegen. Die anderen vier Labels existieren noch nicht und werden bei
Bedarf von `/triage` angelegt.

## Kein Teil des Triage-Vokabulars

Diese bestehenden Labels haben eine eigene Bedeutung und dürfen **nicht** auf
eine der fünf Rollen abgebildet werden:

- `needs-discussion` — im Meeting zu besprechen, nicht dasselbe wie `needs-triage`
- `blocker` — blockiert anderes Issue / anderes Team
- `good-first-task` — Einstiegs-geeignet
- `bc0`–`bc4`, `platform` — Zuordnung zum Bounded Context
- `gate-0`–`gate-3` — Phasen-Gates
- `enabler:*` — Zuständigkeit im Team
- `arbeitspaket`, `adr`, `contract`, `research`, `documentation` — Issue-Art

Triage-Labels kommen **zusätzlich** zu diesen Labels, sie ersetzen sie nicht.
