# ADR-005 — Der Analyselauf von BC2 ist das Paket, nicht der Mandant

**Status:** Entwurf · 10.09.2026
**Bezug:** [#164](https://github.com/pg-coe-kmu/coe-factory/issues/164) Domänenmodell BC2 · Karte [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158)
**Ersetzt nicht, sondern verengt:** die Festlegung „Arbeitseinheit ist der Mandant" vom 30.08.2026
**Baut auf:** ADR-003 (Schreibmodell), ADR-002 (stabile IDs als Vertrag)

---

## 1. Kontext

Am 30.08.2026 wurde als Arbeitseinheit von BC2 **der Mandant** festgelegt: BC2 solle mehrere
Prozesse einer Firma auf einmal betrachten und über sie hinweg priorisieren. Diese Festlegung
entstand, **bevor es das Paket gab**.

Seit Schema v2.6 vom 04.09.2026 schnürt BC0 nach der Gate-0-Freigabe ein **Paket** und vergibt dabei
eine `paket_id`. Der Anstoß an BC2 trägt genau diese eine ID (bestätigt durch BC0s gebauten Ruf,
Commit `9ddda89`). Damit standen zwei Bezugsgrößen nebeneinander, und die Karte hat die Auflösung
ausdrücklich diesem ADR-Vorgang überlassen.

Drei Messbefunde aus BC0s Schema:

| Befund | Quelle |
|---|---|
| Der Paketinhalt ist auf **Teilprozess**-Ebene geschlüsselt — `(company_id, paket_id, sub_process_id)` | `gate_paket_inhalt` |
| `stand_zum(<tabelle>, uebergeben_am, company_id)` liefert den Datenstand **je Paket** | `v_uebergabe_offen`, Kommentar |
| Das Paket ist append-only; ein Nachzügler ist ein **neues** Paket | `gate_pakete`, Kommentar |

## 2. Entscheidung

**Ein Analyselauf von BC2 ist die Bearbeitung genau eines Pakets.** Seine Identität ist
`(company_id, paket_id)`. Der Mandant bleibt Filter und Sicht, ist aber keine Laufeinheit.

Die prozessübergreifende Priorisierung, die das Ziel der Karte verlangt, findet **innerhalb des
Pakets** statt. Das trägt, weil BC0 beim Schnüren alle bis dahin freigegebenen und noch nicht
übergebenen Teilprozesse einsammelt — ein Paket enthält typischerweise mehrere Teilprozesse aus
mehreren Kernprozessen.

## 3. Warum nicht der Mandant

Ein Mandantenlauf über mehrere Pakete hat **keinen einzelnen Zeitpunkt**, zu dem sich sein
Datenstand reproduzieren ließe: `stand_zum()` braucht ein `uebergeben_am`, und mehrere Pakete haben
mehrere. Er hätte auch **keinen einheitlichen Freigabestand** — Teilprozesse aus verschiedenen
Paketen sind zu verschiedenen Zeitpunkten durch Gate 0 gegangen, und was dazwischen geändert wurde,
wäre in einem Ergebnis vermischt.

Die Nachrechenbarkeit, um die die Karte seit #166 ringt, hängt genau daran. Sie ist mit dem Paket
gegeben und mit dem Mandanten nicht.

## 4. Folgen

* Jedes Ergebnis von BC2 führt `company_id` **und** `paket_id`. Das Vertragsfeld `prozessprofil_ref`,
  das heute drei verschiedene Dinge trägt, wird dadurch ersetzt (Umsetzung: [#187](https://github.com/pg-coe-kmu/coe-factory/issues/187)).
* Eine **Portfolio-Sicht** über alle Pakete eines Mandanten bleibt möglich, ist aber eine reine
  Lesesicht und ändert die Laufeinheit nicht.
* Kommt ein Paket mit nur einem Teilprozess, gibt es innerhalb des Laufs nichts zu vergleichen. Das
  ist hingenommen: eine Rangfolge über Dinge, die zu verschiedenen Zeitpunkten freigegeben wurden,
  wäre keine bessere Aussage, sondern eine unbelegte.
