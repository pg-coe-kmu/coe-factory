# Issue tracker: GitHub

Issues und Specs für dieses Repo leben als GitHub Issues in
`pg-coe-kmu/coe-factory`. Alle Operationen laufen über die `gh` CLI.

## Konventionen

- **Issue anlegen**: `gh issue create --title "..." --body "..."`. Für
  mehrzeilige Bodies ein Heredoc verwenden.
- **Issue lesen**: `gh issue view <number> --comments`, Kommentare per `jq`
  filtern und Labels mit abrufen.
- **Issues auflisten**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`
  mit passenden `--label`- und `--state`-Filtern.
- **Kommentieren**: `gh issue comment <number> --body "..."`
- **Labels setzen / entfernen**: `gh issue edit <number> --add-label "..."` /
  `--remove-label "..."`
- **Schließen**: `gh issue close <number> --comment "..."`

Das Repo wird aus `git remote -v` abgeleitet; `gh` macht das innerhalb eines
Clones automatisch.

## Issue-Templates

`.github/ISSUE_TEMPLATE/` enthält vier Templates. Beim Anlegen eines Issues die
passende Art benennen und das gleichnamige Label setzen, statt ein nacktes Issue
zu erzeugen:

| Template              | Label          | Wofür                                   |
| --------------------- | -------------- | --------------------------------------- |
| `arbeitspaket.yml`    | `arbeitspaket` | Arbeitspaket aus dem Projektplan        |
| `bug.yml`             | `bug`          | Fehler                                  |
| `adr.yml`             | `adr`          | Architecture Decision Record            |
| `contract-change.yml` | `contract`     | Änderung an einer Schnittstelle         |

Zusätzlich, wo bekannt: den Bounded Context (`bc0`–`bc4`, `platform`) und ggf.
das Gate (`gate-0`–`gate-3`) als Label setzen. Triage-Labels siehe
`docs/agents/triage-labels.md`.

Ein Issue = ein Branch = ein kleiner PR (siehe `bc1-context-discovery/CLAUDE.md`).

## Pull Requests als Triage-Fläche

**PRs als Request-Fläche: nein.** _(Auf `ja` setzen, falls dieses Repo externe
PRs als Feature Requests behandelt; `/triage` liest dieses Flag.)_

Bei `ja` laufen PRs über dieselben Labels und Zustände wie Issues, mit den
`gh pr`-Äquivalenten:

- **PR lesen**: `gh pr view <number> --comments`, Diff via `gh pr diff <number>`.
- **Externe PRs für Triage auflisten**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`,
  dann nur `authorAssociation` von `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR` oder
  `NONE` behalten (`OWNER`/`MEMBER`/`COLLABORATOR` verwerfen).
- **Kommentieren / labeln / schließen**: `gh pr comment`,
  `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub teilt einen Nummernraum zwischen Issues und PRs, ein bloßes `#42` kann
also beides sein: mit `gh pr view 42` auflösen, sonst auf `gh issue view 42`
zurückfallen.

## Wenn ein Skill sagt „publish to the issue tracker"

Ein GitHub Issue anlegen.

## Wenn ein Skill sagt „fetch the relevant ticket"

`gh issue view <number> --comments` ausführen.

## Wayfinding-Operationen

Verwendet von `/wayfinder`. Die **Map** ist ein einzelnes Issue mit **Child**-Issues
als Tickets.

- **Map**: ein Issue mit Label `wayfinder:map`, enthält Notes /
  Decisions-so-far / Fog im Body. `gh issue create --label wayfinder:map`.
- **Child-Ticket**: ein Issue, das als GitHub Sub-Issue an die Map gehängt wird
  (`gh api` auf den Sub-Issues-Endpunkt). Wo Sub-Issues nicht aktiviert sind: das
  Child in eine Task-Liste im Map-Body eintragen und `Part of #<map>` an den
  Anfang des Child-Bodys setzen. Labels: `wayfinder:<type>`
  (`research`/`prototype`/`grilling`/`task`). Nach dem Claim wird das Ticket der
  treibenden Person zugewiesen.
- **Blocking**: GitHubs **native Issue Dependencies**, die kanonische, in der UI
  sichtbare Darstellung. Kante hinzufügen mit
  `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`,
  wobei `<blocker-db-id>` die numerische **Datenbank-ID** des Blockers ist
  (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _nicht_ die `#number` oder
  die `node_id`). GitHub meldet `issue_dependencies_summary.blocked_by` (nur
  offene Blocker, das eigentliche Gate). Wo Dependencies nicht verfügbar sind:
  Rückfall auf eine Zeile `Blocked by: #<n>, #<n>` am Anfang des Child-Bodys. Ein
  Ticket ist unblocked, wenn jeder Blocker geschlossen ist.
- **Frontier-Query**: offene Children der Map auflisten (`gh issue list --state open`,
  begrenzt auf die Sub-Issues / die Task-Liste der Map), alle mit offenem Blocker
  (`issue_dependencies_summary.blocked_by > 0` bzw. ein offenes Issue in der
  `Blocked by`-Zeile) oder mit Assignee verwerfen; das erste in Map-Reihenfolge
  gewinnt.
- **Claim**: `gh issue edit <n> --add-assignee @me`, der erste Schreibvorgang der
  Session.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, dann `gh issue close <n>`,
  dann einen Context-Pointer (Gist + Link) an Decisions-so-far der Map anhängen.
