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
