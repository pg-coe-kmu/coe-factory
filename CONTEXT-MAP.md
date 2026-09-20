# Context Map

Die sechs Bounded Contexts der CoE Factory, wo ihre Domänensprache steht und wie sie
zusammenhängen. Nach `docs/agents/domain.md`: wer an einer Grenze arbeitet, liest **beide**
beteiligten `CONTEXT.md` und den Vertrag dazwischen.

> **Diese Karte ist unvollständig, und das ist kein Mangel.** Ein `CONTEXT.md` entsteht erst, wenn
> Begriffe tatsächlich geklärt wurden — bislang hat das nur BC2 getan. Die übrigen Zeilen nennen den
> Kontext und seinen Ort; die Sprache steht dort noch in `README.md` und `CLAUDE.md`.

## Contexts

| Context | Verantwortung | Domänensprache |
|---|---|---|
| **BC0 — Baseline & Onboarding** (`bc0-baseline-onboarding/`) | Simeon | noch kein `CONTEXT.md` · `README.md`, `ADR-004` |
| **BC1 — Interactive Context Discovery** (`bc1-context-discovery/`) | Richard, Philipp | noch kein `CONTEXT.md` |
| **BC2 — Strategic Advisor** (`bc2-strategic-advisor/`) | Sergio | **[`CONTEXT.md`](./bc2-strategic-advisor/CONTEXT.md)** · `docs/adr/` |
| **BC3 — Engineering Architect** (`bc3-engineering-architect/`) | Svetlana, Sabrina | noch kein `CONTEXT.md` |
| **BC4 — Autonomous Builder** (`bc4-autonomous-builder/`) | Zakaria, Ozan | noch kein `CONTEXT.md` |
| **Platform & Integration** (`platform/`) | Mehdi, Sabrina, Ozan, Zakaria, Sergio | noch kein `CONTEXT.md` |

## Relationships

Hier steht nur, was einen Vertrag im Repo oder eine gebaute Schnittstelle hat. Was nur besprochen
ist, steht nicht hier — die Karte soll nicht zur sechsten widersprüchlichen Quelle werden.

- **Außenwelt → BC1**: eine **Anfrage** löst BC1 aus. Sie liegt als `ref_anfragen` in der
  gemeinsamen Datenbank; BC0 legt sie an, stößt BC1 aber nicht an.
- **BC0 → BC2**: **Paket-Anstoß** nach der Gate-0-Freigabe, REST mit JSON-Nutzlast und
  HMAC-Signatur. Vertrag: [`contracts/bc0-to-bc2/`](./contracts/bc0-to-bc2/). Gebaut und im Betrieb
  (#165, #190). Die Nachricht trägt nur Kennungen — den Zuschnitt liest BC2 selbst aus der Datenbank.
- **BC1 → BC2**: **Prozessprofil** über die gemeinsame Datenbank, nicht als Nachricht. Vertrag:
  [`contracts/bc1-to-bc2/`](./contracts/bc1-to-bc2/) (#184).
- **BC2 → BC3**: **Konzept** (je Kernprozess) und **Priorisierung** (je Analyselauf) als Datei.
  Vertrag: [`contracts/bc2-to-bc3/`](./contracts/bc2-to-bc3/).
- **BC3 → BC4**: **Tickets** je Lieferung. Vertrag:
  [`contracts/bc3-to-bc4/`](./contracts/bc3-to-bc4/).
- **Alle ↔ gemeinsame PostgreSQL**: BC0 hält die Baseline; jeder Context liest sie und schreibt
  ausschließlich in sein eigenes Schema. **ADR-003**, durchgesetzt von der Datenbank.

## Wo Begriffe kollidieren

Die Grenzen sind die Stellen, an denen dasselbe Wort zwei Dinge meint. Was bisher aufgefallen ist:

| Wort | Bedeutung A | Bedeutung B |
|---|---|---|
| **Prozessprofil** | BC1s Erhebungsergebnis je Teilprozess (`bc1.prozessprofil`) | bei BC3 und in BC2s Altlieferung das Feld `prozessprofil_ref` — dort steht eine Anfrage-ID bzw. ein Snapshot-Zeiger |
| **Durchlauf** | eine Ausführung des Prozesses beim Mandanten (BC1) | eine Bearbeitung eines Pakets durch BC2 (**Analyselauf**) |
| **Use Case** | BC0s **Anfrage** `A-JJJJ-NN` | bei BC3/BC4 der Name einer Lieferung (`uc1-reisebuchung`) |

BC2 löst diese drei in seinem [`CONTEXT.md`](./bc2-strategic-advisor/CONTEXT.md) auf. Für die
anderen Contexts ist die Auflösung offen — wer dort ein `CONTEXT.md` anlegt, sollte hier anfangen.
