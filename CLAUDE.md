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

### ToDo-Vorgänge in BC0 (ab 18.09.2026)

> **Geltungsbereich: BC0.** Diese Regeln beschreiben BC0s Arbeitsweise und setzen `todo.db`
> und das Drehbuch voraus — beides liegt im Projektordner `PG KI-CoE-KMU`, nicht im Repo, und
> steht den übrigen Contexts nicht zur Verfügung. Wer sie für sein Vorgehen übernehmen will,
> kann das; verbindlich sind sie für BC0. **BC2 führt seine Vorgänge über die Wayfinder-Karte
> [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158)**, in der das Auflösen eines
> Tickets und sein Schließen ein Vorgang sind — die Begründung steht als Auflösungskommentar
> am Ticket und als Zeile in der Karte, nicht in einem Drehbuch.
>
> *(Eingegrenzt am 20.09.2026: Der Abschnitt stand ohne Geltungsbereich in der repo-weiten
> Datei und galt damit dem Wortlaut nach für alle sechs Contexts — einschließlich der Pflicht,
> jede Änderung in einer Datei festzuhalten, auf die fünf von ihnen keinen Zugriff haben.)*

Vorgänge stehen in `todo.db` (Projekt „Zusammenführung") und, soweit
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
