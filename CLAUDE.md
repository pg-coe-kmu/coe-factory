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

Multi-Context: `CONTEXT-MAP.md` im Root zeigt auf je ein `CONTEXT.md` pro
Bounded Context. **Beides existiert noch nicht** — `/domain-modeling` legt es an,
sobald Begriffe tatsächlich geklärt werden; bis dahin ist das Fehlen kein Mangel.
Siehe `docs/agents/domain.md`.
