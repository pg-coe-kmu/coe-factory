# BC2 – Strategic Advisor

**Verantwortlich:** Sergio (allein, seit 30.08.2026)
**Phase:** zwischen Gate 0 und Gate 1 – Empfehlung

## Zweck
Erkennt aus der Baseline **Automatisierungspotenziale**, bewertet ihren **Value**, priorisiert sie
und erzeugt Konzept, Priorisierung und eine herunterladbare Präsentation — plus den
maschinenlesbaren Vertrag für BC3.

## Messages
- **Consumed:** Unternehmens- & Prozessdaten aus der gemeinsamen PostgreSQL (nur lesend)
- **Produced:** Automatisierungskonzept inkl. Value/ROI, Priorisierung, Präsentation

## Schnittstellen
- **Input:** gemeinsame PostgreSQL, direkt gelesen — **nicht** mehr `/contracts/bc1-to-bc2/` als
  Datei; BC1s Schema ist derzeit leer.
- **Output an BC3:** [`/contracts/bc2-to-bc3/`](../contracts/bc2-to-bc3/) (Schema v2.0),
  Beispiele in [`/contracts/examples/`](../contracts/examples/). Zusätzlich Tabellen in Schema
  `bc2`, jede Zeile mit Kernprozess-ID.

## Ordner
| Ordner | Inhalt |
|---|---|
| `tools/` | `gen_mocks.py`, `validate.py` — aus dem Repo-Wurzelverzeichnis aufrufen |
| `architektur/` | Systemarchitektur (Stand 27.06.2026, in Teilen überholt — Warnkasten beachten) |

## Stand
**Noch kein Anwendungscode.** Der Bau beginnt bei null. Was zu tun ist und in welcher Reihenfolge,
steht nicht hier, sondern auf der Karte
[#158](https://github.com/pg-coe-kmu/coe-factory/issues/158); die offenen Tickets sind ihre
Sub-Issues. Die Arbeitspakete BC2.1–BC2.8 (#84–#99) beschrieben eine verworfene Architektur
(Qdrant-Musterkatalog, n8n) und sind mit
[#162](https://github.com/pg-coe-kmu/coe-factory/issues/162) geschlossen worden.

Arbeitsweise und Invarianten: `CLAUDE.md` in diesem Ordner.
