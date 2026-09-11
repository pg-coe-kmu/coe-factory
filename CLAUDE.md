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
