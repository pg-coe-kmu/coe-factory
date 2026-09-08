# BC1 — Interactive Context Discovery

**Team:** Richard, Philipp
**Phase:** 1 — Discovery

## Zweck
Übersetzt unstrukturierte Eingaben (im MVP: Text-Chat; später Sprache/Dokumente/Bilder) in ein strukturiertes **Prozessprofil (JSON)** + **Confidence-/Vollständigkeits-Status** + **Prozessdoku** und übergibt am **Gate 0** an BC2. BC1 liefert das vollständige Prozessbild; die Auswahl konkreter Use Cases passiert außerhalb von BC1.

## Messages
- **Consumed:** Chat (MVP) · später Sprache, Dokumente, Bilder · Baseline (read-only)
- **Produced:** Prozessprofil (JSON), Confidence-Report, Prozessdoku → `contracts/bc1-to-bc2/`

## Bauweise
**Hybrid:** n8n-Hülle (Verrohrung) + Code-Kern (Gehirn). **MVP-first:** schlanker Text-Interview→JSON-Kern zuerst; weitere Schichten docken an, ohne den Kern zu ändern.

## Struktur
- `architektur/` — Systemarchitektur (technische Ebene, Überblick)
- `design/` — Design-Spec (das *Warum*) + Implementierungsplan (die *Anleitung pro Arbeitspaket*, inkl. Code/Tests)

## Wie man hier mitarbeitet
Ein Arbeitspaket (Issue unter [#48](https://github.com/pg-coe-kmu/coe-factory/issues/48)) öffnen → den dort verlinkten **Plan-Task** lesen (volle Anleitung) → die genannten **Abhängigkeiten** beachten → loslegen. Reihenfolge & Aufteilung stehen in der Arbeitspaket-Übersicht.

## Arbeitspakete
[#48 KI-Interviewer](https://github.com/pg-coe-kmu/coe-factory/issues/48) · [#49 Voice/OCR](https://github.com/pg-coe-kmu/coe-factory/issues/49) · [#50 PII-Filter](https://github.com/pg-coe-kmu/coe-factory/issues/50) · [#51 JSON-Compiler](https://github.com/pg-coe-kmu/coe-factory/issues/51) · [#52 Doku-Generator](https://github.com/pg-coe-kmu/coe-factory/issues/52) · [#53 Mapper & Verifier](https://github.com/pg-coe-kmu/coe-factory/issues/53)

## Schnittstellen
- **Input von BC0:** Baseline-Lookup (KP/TP/Reifegrad)
- **Output an BC2:** `contracts/bc1-to-bc2/` (Schema + Mock; gemeinsam mit BC2 + Platform)

## Setup und Start

Voraussetzungen: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), Docker (für die Test-Datenbank), `psql`.

```bash
uv sync                                                            # .venv anlegen
docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:17
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q -W error
```

Dienst starten (Pflicht: `BC1_DB_DSN` als `bc1_role`, `BC1_COMPANY_ID`; LLM-Wahl über `BC1_LLM` = `claude` | `ollama` | `gemini`, Key des Anbieters aus der Umgebung):

```bash
export BC1_DB_DSN="postgresql://…"        # Datenbank mit eingespielter DDL, siehe unten
export BC1_COMPANY_ID="<uuid des Mandanten>"
export BC1_LLM=ollama                      # lokal, ohne API-Key
.venv/bin/uvicorn bc1_service.main:app --port 8000
```

Der Dienst startet nur, wenn der Mandant bewertete Teilprozesse hat — die beiden regulären Startabbrüche und der Chat-Aufbau stehen in [`bc1_service/n8n/SMOKE.md`](bc1_service/n8n/SMOKE.md). Die Datenbanktabellen kommen aus [`bc1_service/db/prozessprofil.sql`](bc1_service/db/prozessprofil.sql); wie man sie einspielt und was die Dreifallregel bedeutet, steht in [`bc1_service/db/EINSPIELEN.md`](bc1_service/db/EINSPIELEN.md). Was das Interview fragt und in welche Spalte es fließt: [`design/Spalte-zu-Feld-Tabelle.md`](design/Spalte-zu-Feld-Tabelle.md). Was noch fehlt: [`design/Abschlussplan-BC1.md`](design/Abschlussplan-BC1.md).
