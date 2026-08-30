# BC2 — Strategic Advisor · Guidance

> Für Claude Code **und** Menschen.

## Was BC2 ist

Erkennt aus BC0s Baseline **Automatisierungspotenziale**, bewertet ihren **Value**, priorisiert sie
und erzeugt eine entscheidungsreife Präsentation plus einen maschinenlesbaren Vertrag für BC3.
Zwischen Gate 0 und Gate 1. Verantwortlich: **Sergio, allein** — Eike ist seit dem 30.08.2026 raus.

**Stand:** Es gibt noch keinen BC2-Code. Der Bau beginnt bei null. Owner-Angaben in den Alt-Issues
(#84–#99) nennen teils Eike und sind damit hinfällig.

## Erst lesen

- **[Karte #158](https://github.com/pg-coe-kmu/coe-factory/issues/158)** — Ziel, getroffene Entscheidungen,
  Nebel. Wird pro Session einmal geladen. Die offenen Tickets sind ihre Sub-Issues; das nächste
  bearbeitbare ist das erste ohne offenen Blocker und ohne Assignee.
- **[Datenlage, Kommentar an #159](https://github.com/pg-coe-kmu/coe-factory/issues/159)** — was am
  30.08.2026 **gemessen** in der Datenbank lag. Maßgeblich gegenüber jedem Papier.

Arbeitsweise: ein Ticket je Session, Claim vor Arbeit (`gh issue edit <n> --add-assignee @me`),
Ergebnis als Kommentar, schließen, Zeiger an die Karte anhängen. Ein Issue = ein Branch = kleiner PR.

## Datenzugang

Gemeinsame PostgreSQL 17.6 bei Supabase (eu-west-1), **Session-Pooler Port 5432** — der
Transaction-Pooler auf 6543 hält keine Sitzung über die Anweisung hinaus.

```
host  aws-0-eu-west-1.pooler.supabase.com   port 5432   dbname postgres
user  bc2_role.<PROJEKTKENNUNG>             sslmode require
```

Kennung und Passwort stammen von Simeon (BC0), verteilt per SMS. Sie gehören **ausschließlich in
Umgebungsvariablen** — nicht in Repo, Issue, Code oder Kommentar (BC0-Regel 5).

Gegenprobe nach jedem Verbindungsaufbau: `current_user` liefert `bc2_role`, und ein `UPDATE` auf
`bitkom_bewertungen` scheitert mit `permission denied`. Scheitert es nicht, erst melden, dann weiterarbeiten.

## Was in den Altdokumenten überholt ist

Die BC2-Unterlagen sind über fünf Stände gewachsen und widersprechen sich. Maßgeblich ist die
Datenbank, danach die Karte. Diese Tabelle bewahrt davor, alte Schlüsse erneut zu ziehen:

| Aussage in Altdokumenten | Tatsächlich |
|---|---|
| Qdrant + fester Musterkatalog (Issues #84–#99, Vorbereitungsaufgabe) | verworfen — Potenziale werden offen erkannt |
| `use_cases[]` mit `empfohlenes_muster` (Schema v1.0) | `potenziale[]` (Schema v2.0) |
| n8n als Orchestrierung | reines Python, Agenten selbst gebaut |
| Übergabe per JSON-Datei, GitHub-Ordner oder REST | gemeinsame Datenbank, Schema-Trennung (ADR-003) |
| „Rollen und Kostensätze sind leer" (BC0-Papier 23.08.) | gefüllt seit 17.08.: K1–K5, 40–140 EUR/h, alle `geschaetzt` |
| „4 Kernprozesse bewertet, 600 Bewertungen" | 6 Kernprozesse, 690 Bewertungen für NoroAI |
| Sprints S1–S6, Meilensteine M1–M4, KW 20–31 | Zeitpläne gelten nicht mehr |

`contracts/examples/mock_prozessprofil.json` beschreibt „Krankentagegeld, KP-07, Aurelia Krankenkasse".
Real ist KP-07 die Buchhaltung und nicht erhoben; NoroAI ist eine KI-Beratung. Der Mock dient als
**Schema-Fixture**; die fachliche Grundlage ist die Datenbank.

## Wo BC2 liegt

Seit [#162](https://github.com/pg-coe-kmu/coe-factory/issues/162) an genau einem Ort — die drei
divergierenden Kopien unter `Projektgruppe/BC2/` sind aufgelöst und liegen dort nur noch in `_archiv/`.

| Was | Wo |
|---|---|
| Verträge an BC3 (v2.0) | `contracts/bc2-to-bc3/` — **Endlage, wird nicht mehr verschoben** |
| Mocks / Fixtures | `contracts/examples/` |
| `gen_mocks.py`, `validate.py` | `bc2-strategic-advisor/tools/` — aus dem Repo-Wurzelverzeichnis aufrufen |
| Systemarchitektur (27.06., teils überholt) | `bc2-strategic-advisor/architektur/` |

Der Vertrag verlor beim Sprung v1→v2 die Felder `akzeptanzkriterien_geschaeftlich`,
`fachliche_anforderungen` und die Tiefe von `to_be_vision`. **BC3 braucht sie** (Nachricht vom
20.08.2026); die Rückführung entscheidet
[#160](https://github.com/pg-coe-kmu/coe-factory/issues/160).

## Invarianten

- **Lesen** auf `public` und `bc1`…`bc4`, **schreiben ausschließlich in Schema `bc2`.** Die Datenbank
  setzt das durch (ADR-003).
- **Jede Ausgabe führt die Kernprozess-ID mit.** Ohne sie ist ein Ergebnis nicht zuordenbar und
  wird verworfen (Auflage BC0, 17.08.2026).
- **Jede Abfrage filtert nach `company_id`.** Es liegen zwei Mandanten in derselben Datenbank, und die
  Datenbank trennt sie nicht. NoroAI ist `7c2d5ee9-2a9a-5990-810f-502ea2b2012d`; der zweite Mandant
  ist ein Übungsmandant und trägt keine auswertbaren Werte.
- **`v_bewertung_aktuell` statt `bitkom_bewertungen`** für jede Auswertung — sonst fließen
  überschriebene Stände mit ein.
- **Das LLM bewertet qualitativ, rechnet aber nicht.** Zahlen entstehen deterministisch in Python,
  damit sie reproduzierbar und testbar bleiben.
- **Jede Annahme reist mit dem Ergebnis.** Stundensätze sind `geschaetzt`, Aufwandsgrößen fehlen
  teils ganz — die Ausgabe macht das sichtbar, statt Genauigkeit vorzutäuschen.
- **Die Bitkom-Skala ist nicht linear** (1 = 0 %, 2 = >0–40 %, 3 = >40–50 %, 4 = >50–95 %, 5 = >95 %).
  Der Sprung 3→4 ist der größte im Modell; eine lineare Übersetzung in Nutzen rechnet falsch.

## Stack & Sprache

Python 3.11+, FastAPI, `pytest`. Sprache durchgehend **Deutsch**, auch in Issues und Commits.

Tests sprechen die Anwendung über HTTP an (`fastapi.testclient.TestClient`), nicht über
Endpunktfunktionen — Vorbild ist `bc0-baseline-onboarding/app/tests/` samt
`TESTABDECKUNG.md`. Deren Lehre gilt auch hier: ein grüner Lauf gegen Fixtures ersetzt den Durchlauf
gegen das echte PostgreSQL nicht.

Die allgemeinen Coding-Prinzipien des Projekts stehen in `bc1-context-discovery/CLAUDE.md`
(Abschnitt „Sauber codieren") und gelten sinngemäß auch für BC2.
