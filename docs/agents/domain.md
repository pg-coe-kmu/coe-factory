# Domain Docs

Wie die Engineering-Skills die Domain-Dokumentation dieses Repos beim Erkunden
des Codes konsumieren sollen.

## Vor dem Erkunden lesen

- **`CONTEXT.md`** im Root, oder
- **`CONTEXT-MAP.md`** im Root, falls vorhanden: sie zeigt auf je ein
  `CONTEXT.md` pro Bounded Context. Jedes zum Thema passende lesen.
- **`docs/adr/`**: die ADRs lesen, die den Bereich betreffen, in dem gearbeitet
  wird. In Multi-Context-Repos zusätzlich `bc<N>-*/docs/adr/` für
  kontextspezifische Entscheidungen prüfen.

Wenn eine dieser Dateien nicht existiert: **stillschweigend fortfahren.** Ihr
Fehlen nicht anmerken, ihre Anlage nicht vorab vorschlagen. Das Skill
`/domain-modeling` (erreichbar über `/grill-with-docs` und
`/improve-codebase-architecture`) legt sie erst an, wenn Begriffe oder
Entscheidungen tatsächlich geklärt werden.

## Dateistruktur

Dieses Repo ist **multi-context**: die Bounded Contexts liegen als
Top-Level-Ordner vor, nicht unter `src/`.

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← systemweite Entscheidungen
├── bc0-baseline-onboarding/
│   ├── CONTEXT.md
│   └── docs/adr/                      ← kontextspezifische Entscheidungen
├── bc1-context-discovery/
│   ├── CONTEXT.md
│   └── docs/adr/
├── bc2-strategic-advisor/
├── bc3-engineering-architect/
├── bc4-autonomous-builder/
├── platform/
└── contracts/                         ← Verträge zwischen den Contexts
```

`contracts/` beschreibt die Übergaben zwischen den Contexts (z. B. `bc3 - bc4`).
Wer an einer Grenze arbeitet, liest beide beteiligten `CONTEXT.md` **und** den
zugehörigen Vertrag.

Neben den Domain-Docs existiert pro Context eine `CLAUDE.md` mit
Arbeitsanweisungen — die ist etwas anderes als `CONTEXT.md` und ersetzt sie
nicht.

## Das Vokabular des Glossars verwenden

Wenn eine Ausgabe ein Domänenkonzept benennt (Issue-Titel, Refactoring-Vorschlag,
Hypothese, Testname), den Begriff so verwenden, wie er in `CONTEXT.md` definiert
ist. Nicht auf Synonyme ausweichen, die das Glossar explizit vermeidet.

Ist das benötigte Konzept noch nicht im Glossar, ist das ein Signal: entweder
wird Sprache erfunden, die das Projekt nicht verwendet (überdenken), oder es gibt
eine echte Lücke (für `/domain-modeling` vormerken).

## ADR-Konflikte kennzeichnen

Widerspricht eine Ausgabe einem bestehenden ADR, das explizit benennen statt es
still zu übergehen:

> _Widerspricht ADR-0007 (event-sourced orders), lohnt aber eine Neubewertung, weil…_
