# coe-factory — Guidance

Repo-weite Konventionen für Claude Code und Menschen. Pro Bounded Context gilt
zusätzlich die jeweilige `bc<N>-*/CLAUDE.md` — bei Konflikten gewinnt die
kontextspezifische Datei.

## Agent skills

### Issue tracker

Issues leben als GitHub Issues in `pg-coe-kmu/coe-factory` (via `gh` CLI).
Siehe `docs/agents/issue-tracker.md`.

### Triage labels

Kanonische Default-Labels; `wontfix` existiert bereits im Repo.
Siehe `docs/agents/triage-labels.md`.

### Domain docs

Multi-Context: [`CONTEXT-MAP.md`](./CONTEXT-MAP.md) im Root zeigt auf je ein
`CONTEXT.md` pro Bounded Context. **Die Karte existiert seit dem 11.09.2026; von
den sechs Contexts hat bislang nur BC2 ein `CONTEXT.md`.** Das Fehlen der übrigen
ist kein Mangel — ein `CONTEXT.md` entsteht, wenn Begriffe tatsächlich geklärt
werden, nicht auf Vorrat. Wer eines anlegt, trägt es in der Karte nach.
Siehe `docs/agents/domain.md`.

## Vorgänge

### ToDo-Vorgänge (ab 18.09.2026)

Vorgänge dieses Projekts stehen in `todo.db` (Projekt „Zusammenführung") und, soweit
gespiegelt, als GitHub Issues in `pg-coe-kmu/coe-factory`. Für beide Orte gilt:

- **Anlegen nur mit ausdrücklicher Zustimmung des Maintainers.** Ein Befund wird berichtet;
  ob daraus ein Vorgang oder ein Issue wird, entscheidet der Maintainer. „Vormerken" heißt
  vormerken, nicht anlegen.
- **Schließen nur mit ausdrücklicher Zustimmung** — `erledigt`, `verworfen`, `closed`. Eine
  Prüfung liefert Befund und Vorschlag, nicht den Statuswechsel. Eine Zurückstellung mit
  Bedingung ist kein Wegfall.
- **Jede Änderung an einem Vorgang wird im Drehbuch festgehalten** —
  `00_Start/Drehbuch_PG CoE_Chronologie_v2.md` im Projektordner `PG KI-CoE-KMU`, mit Nummer,
  Anlass und Begründung.
