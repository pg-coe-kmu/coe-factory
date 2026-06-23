# BC1 — Interactive Context Discovery · Guidance

> Für Claude Code **und** Menschen. Bewusst kurz — wenn diese Datei zum „Riesenschiff" wird, widerspricht sie sich.

## Was BC1 ist
Wandelt unstrukturierte Eingaben (MVP: Text-Chat) in ein strukturiertes **Prozessprofil (JSON)** + Vollständigkeits-/Confidence-Status + Doku und übergibt am **Gate 0** an BC2.

## Erst lesen
- `architektur/BC1_Systemarchitektur.md` — Bauweise (Hybrid: n8n-Hülle + Code-Kern) + Module
- `design/Design-Spec.md` — das *Warum*
- `design/Implementierungsplan-MVP-Kern.md` — Anleitung pro Arbeitspaket (TDD, inkl. Code/Tests)
- Arbeitspakete: **#48** (Übersicht/Reihenfolge) + **#120–#126**

## Wie man arbeitet
Issue wählen (Reihenfolge siehe #48) → verlinkten Plan-Task lesen → **TDD** (Test zuerst, dann minimal implementieren) → **ein Issue = ein Branch = kleiner PR**. Die „Consumes/Produces"-Blöcke im Plan sind der Vertrag zwischen parallelen Paketen — daran halten, dann kollidiert nichts.

## Bau-Prinzipien
- **Einfach & verständlich, kein Over-Engineering (YAGNI).** Kleinste Lösung, die funktioniert.
- **TDD** — Test zuerst.
- **Architektur-Invarianten (nicht aufweichen):**
  - Persistenz im **Code-Kern** (atomar, versioniert); Transport/n8n schreibt **nie** den State.
  - **Keine erfundenen Confidence-Zahlen** — erklärbare Status (`fehlt/gueltig/ungueltig/unklar/ungeloest`) + **gezählte** Vollständigkeit.
  - LLM nur hinter dem **LLM-Client**; Tests laufen gegen ein **Fake-LLM** (kein Netz in Tests).
  - **Generisch bleiben:** nicht auf Use-Case-Namen verzweigen; Fall-Spezifika gehören ins **Use-Case-Paket**.
  - Output trägt **Vollständigkeit + ungelöste Felder + `schema_version`**.
- **Nicht BC1:** DB/Infra/Audit/Verschlüsselung → Platform.

## Stack & Sprache
Python 3.11+, `pytest`, Standardbibliothek (kein pydantic im Kern). Sprache: **Deutsch**.
