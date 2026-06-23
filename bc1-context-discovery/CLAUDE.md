# BC1 — Interactive Context Discovery · Guidance

> Für Claude Code **und** Menschen. Diese Prinzipien tendieren zu Sorgfalt vor Tempo; bei trivialen Aufgaben mit Augenmaß anwenden.

## Was BC1 ist
Wandelt unstrukturierte Eingaben (MVP: Text-Chat) in ein strukturiertes **Prozessprofil (JSON)** + Vollständigkeits-/Confidence-Status + Doku und übergibt am **Gate 0** an BC2.

## Erst lesen
- `architektur/BC1_Systemarchitektur.md` — Bauweise (Hybrid: n8n-Hülle + Code-Kern) + Module
- `design/Design-Spec.md` — das *Warum*
- `design/Implementierungsplan-MVP-Kern.md` — Anleitung pro Arbeitspaket (TDD, inkl. Code/Tests)
- Arbeitspakete: **#48** (Übersicht/Reihenfolge) + **#120–#126**

## Wie man arbeitet
Issue wählen (Reihenfolge siehe #48) → verlinkten Plan-Task lesen → Test zuerst → **ein Issue = ein Branch = kleiner PR**. Die „Consumes/Produces"-Blöcke im Plan sind der Vertrag zwischen parallelen Paketen.

## Sauber codieren

### 1. Erst denken, dann coden
*Keine Annahmen. Verwirrung nicht verbergen. Tradeoffs offenlegen.*
- Annahmen explizit benennen. Bei Unsicherheit: nachfragen.
- Bei mehreren Deutungen alle nennen — nicht still eine wählen.
- Gibt es einen einfacheren Weg, sag es; begründet widersprechen, wenn angebracht.
- Ist etwas unklar: innehalten, benennen was verwirrt, nachfragen.

### 2. Einfachheit zuerst
*Minimaler Code, der das Problem löst. Nichts Spekulatives.*
- Keine Funktionen über das Verlangte hinaus.
- Keine Abstraktionen für einmalig genutzten Code.
- Keine „Flexibilität"/„Konfigurierbarkeit", die nicht verlangt wurde.
- Keine Fehlerbehandlung für unmögliche Fälle.
- Wenn 200 Zeilen auch 50 sein könnten, neu schreiben.
- Prüffrage: „Würde ein erfahrener Entwickler das überkompliziert nennen?" → dann vereinfachen.

### 3. Chirurgische Änderungen
*Nur anfassen, was nötig ist. Nur den eigenen Schmutz aufräumen.*
- Umliegenden Code, Kommentare, Formatierung nicht „verbessern"; nichts refaktorieren, was nicht kaputt ist.
- Bestehenden Stil übernehmen, auch wenn man es anders machen würde.
- Unzusammenhängender toter Code: erwähnen — nicht löschen.
- Nur Imports/Variablen/Funktionen entfernen, die erst durch die eigene Änderung ungenutzt wurden; vorbestehenden toten Code nicht entfernen (außer auf Anfrage).
- Test: Jede geänderte Zeile lässt sich direkt auf die Anfrage zurückführen.

### 4. Ziel-getriebene Umsetzung
*Erfolgskriterien definieren. Iterieren bis verifiziert.*
- Aufgaben in verifizierbare Ziele übersetzen: „Validierung hinzufügen" → „Tests für ungültige Eingaben schreiben, dann grün machen"; „Bug fixen" → „Test schreiben, der ihn reproduziert, dann grün machen"; „X refaktorieren" → „Tests vorher und nachher grün".
- Bei mehrstufigen Aufgaben einen kurzen Plan nennen (Schritt → verify). Starke Erfolgskriterien erlauben eigenständiges Iterieren; schwache („mach, dass es geht") erzwingen ständige Rückfragen.

### Zusätzlich (bei uns wichtig — von oben nicht abgedeckt)
- **Der ordentliche Weg, keine Abkürzungen.** Echtes Fundament statt Workaround; die Ursache beheben, nicht das Symptom.
- **Review-Disziplin.** Findings nach Schwere bewerten; jeden Fix selbst verifizieren statt blind übernehmen; Verschobenes mit Ziel festhalten. Sorgfalt vor Tempo.
- **Ehrlich über den Status.** Nichts als „fertig"/„grün" ausgeben, das nicht verifiziert ist; Risiken und eigene Fehler klar benennen.
- **Eine Roadmap für Aufgeschobenes.** Vertagtes mit Ziel und nächstem Schritt festhalten — nichts still fallen lassen.
- **Zweistufige Dokumente.** Längere Docs: Big Picture (Klartext) + separater technischer Teil; zu groß gewordene Dateien aufteilen.

## Architektur-Invarianten (nicht aufweichen)
- Persistenz im **Code-Kern** (atomar, versioniert); Transport/n8n schreibt **nie** den State.
- **Keine erfundenen Confidence-Zahlen** — erklärbare Status (`fehlt/gueltig/ungueltig/unklar/ungeloest`) + **gezählte** Vollständigkeit.
- LLM nur hinter dem **LLM-Client**; Tests gegen **Fake-LLM** (kein Netz in Tests).
- **Generisch bleiben:** nicht auf Use-Case-Namen verzweigen; Fall-Spezifika ins **Use-Case-Paket**.
- Output trägt **Vollständigkeit + ungelöste Felder + `schema_version`**.
- **Nicht BC1:** DB/Infra/Audit/Verschlüsselung → Platform.

## Stack & Sprache
Python 3.11+, `pytest`, Standardbibliothek (kein pydantic im Kern). Sprache: **Deutsch**.

---
*Die vier Prinzipien unter „Sauber codieren" sinngemäß nach den „Karpathy-Guidelines" (Andrej Karpathy); die Zusätze aus dem Partforge-Projekt. Auf BC1 zugeschnitten.*
