# ADR-008 · BC2 — Schema `bc2`: Lauf, Ergebnis und Gate-1-Entscheidung

**Status:** Entwurf · 09.10.2026
**Bezug:** [#250](https://github.com/pg-coe-kmu/coe-factory/issues/250) · Karte [#158](https://github.com/pg-coe-kmu/coe-factory/issues/158)
**Baut auf:** ADR-007 · BC2 (Rückrichtung und Fassungen) · ADR-005 · BC2 (der Analyselauf ist das Paket) · ADR-003 (Schreibmodell)
**Schärft nach:** ADR-007 · BC2 §2.3/§2.4 — wer eine Fassung anstößt (siehe 2.1)
**Nummer:** Die Vergabe läuft über Bounded Contexts hinweg ([#220](https://github.com/pg-coe-kmu/coe-factory/issues/220)).
Deshalb durchgängig **ADR-008 · BC2** schreiben.

---

## 1. Kontext

Schema `bc2` hat eine Tabelle, `bc2.eingang`, den Briefkasten für BC0s Anstoß (#190). Seit dem Bau
der Oberfläche (#243) fehlt der zweite Ort, und zwar spürbar: **die Gate-1-Entscheidung liegt im
Arbeitsspeicher** und ist nach einem Neustart weg. An ihr hängt die ganze Lieferung an BC3.

Vier Lasten muss der Entwurf tragen:

| Last | Herkunft |
|---|---|
| Die Gate-1-Entscheidung — Freigabe je Potenzial, Begründung je Nicht-Freigabe, gesetzte Reihenfolge auf zwei Ebenen, Abweichungsbegründung | #167, #187, #243 |
| Das Ergebnis — Konzepte und Priorisierung, **Kernprozess-ID als Pflichtbezug** | Auflage BC0 17.08.2026, Festlegung 30.08.2026 |
| Die abgelehnten Läufe und die Fassungszählung — „die alte Fassung bleibt abrufbar" | ADR-007 · BC2 §2.3, §4 Punkt 4 |
| Der Rückkanal an BC0 — BC0 liest, statt einen Endpunkt zu bekommen | ADR-007 · BC2 §4 Punkt 3, #241 |

Beim Entwurf fiel ein Widerspruch in ADR-007 auf: §2.3 sagt „ein erneuter Lauf über **dasselbe
Paket** erzeugt eine neue Fassung", §2.4 „jede Neuberechnung beginnt mit einem **neuen Ruf von
BC0**" — also mit einem neuen Paket. `bc2.eingang` nimmt dasselbe Paket nur einmal an. Wer einen
zweiten Lauf über dasselbe Paket anstößt, stand nirgends.

## 2. Entscheidung

### 2.1 Eine Fassung ist ein Lauf über dasselbe Paket — angestoßen von BC2, nur nach Reject

Ein Analyselauf ist `(paket_id, fassung)`. **`f2`, `f3`, … stößt BC2 selbst an**, an Gate 1, und
**nur nach `rejected`**. Gerechnet wird wieder auf `stand_zum(uebergeben_am)`; anders sein kann der
Schnitt der Erkennung, ein Parameter, ein Hinweis aus der Ablehnung — nicht die Daten.

- **Nach `approved` gibt es keine neue Fassung.** Die Freigabe ist die Übergabe an BC3; wer danach
  ändern will, braucht neue Daten, und die kommen als neues Paket von BC0 (ADR-007 · BC2 §2.4).
- **Ein neues Paket beginnt bei `f1`.** `ersetzt_konzept_id` verkettet nur **innerhalb** eines
  Pakets; über Pakete hinweg veraltet ein Konzept, es wird nicht ersetzt.
- **Ein technischer Fehler ist keine Fassung.** Ohne Ergebnis gibt es nichts, das ersetzt würde;
  der Neuversuch läuft unter derselben Fassung.

Damit gilt §2.3 für den Reject, §2.4 für die Nacherhebung — beide bleiben richtig, sie meinten
verschiedene Anlässe.

### 2.2 Das Vertragsdokument liegt unverändert, Spalten nur zum Filtern und Verknüpfen

| Tabelle | Schlüssel | Spalten | Dokument |
|---|---|---|---|
| `bc2.lauf` | `priorisierung_id` (uuid) · eindeutig `(paket_id, fassung)` | `company_id`, `paket_id`, `fassung`, Zustand, Zeitpunkte | Priorisierung (JSONB) |
| `bc2.konzept` | `konzept_id` (uuid) | `priorisierung_id`, `kp_id` (Pflicht), `ersetzt_konzept_id` | Konzept (JSONB) |
| `bc2.potenzial` | `potenzial_id` | `konzept_id`, `kp_id`, Teilprozess-IDs, Score, Rang, Gruppe, `ersetzt_potenzial_ids` (nullbar, vorgehalten) | — |

**Ausgeliefert wird das Dokument, nicht eine Rekonstruktion.** Der Vertrag wird nie aus Spalten
zusammengesetzt; die Spalten sind eine Projektion für BC0 und für Abfragen, geschrieben in
derselben Transaktion aus demselben Ergebnis. Eine Vertragsänderung braucht damit nur dann eine
Migration, wenn sie ein Feld berührt, nach dem jemand filtert.

Das Ergebnis eines Laufs ist **nach dem Schreiben unveränderlich**.

### 2.3 Gate 1 liegt getrennt und ist bis zur Entscheidung veränderlich, danach fest

| Tabelle | Inhalt |
|---|---|
| `bc2.gate1` | eine Zeile je Lauf: Zustand, Entscheider, Kommentar, Abweichungsbegründung, `entschieden_am` |
| `bc2.gate1_potenzial` | je Potenzial: freigegeben, Begründung, finaler Rang |
| `bc2.gate1_prozess` | je Kernprozess: finaler Prozessrang — eigene Tabelle, weil das Konzept unveränderlich ist |

Die gesetzten Reihenfolgen liegen als **Rang-Spalten**, nicht als ID-Listen; die Vertragsform
(`finale_reihenfolge_potenzial_ids`, `finale_prozessreihenfolge_kp_ids`) leitet `als_vertrag()`
daraus ab. Anders als beim Ergebnis (2.2) wird hier zerlegt — die Entscheidung entsteht in der
Datenbank und kommt in keinem Dokument an.

**`pending` ist überschreibbar, `approved` und `rejected` sind endgültig — durchgesetzt in der
Datenbank:** `UPDATE … WHERE status = 'pending'`; null betroffene Zeilen sind ein Konflikt, kein
stilles Überschreiben. Wie beim Briefkasten (#190) gehört die Regel dorthin, wo zwei gleichzeitige
Schreiber sich nicht überholen können.

**Wer schreibt wann:** Erkennung und Rechnung schreiben das Ergebnis, bevor Gate 1 möglich ist.
Danach schreibt nur Gate 1, und nur in seine Tabellen. Ein Konflikt bleibt allein zwischen zwei
offenen Browsern, und den fängt die Zustandsbedingung.

### 2.4 Höchstens ein offener Lauf je Paket, Fassung vergibt die Datenbank

Ein **partieller eindeutiger Index** lässt je Paket höchstens einen nicht abgeschlossenen Lauf zu
(in Arbeit oder Gate 1 `pending`). Die Fassungsnummer ist die höchste plus eins, in derselben
Transaktion, abgesichert durch `UNIQUE (paket_id, fassung)`. Ein Doppelklick auf „neu rechnen"
erzeugt damit keine zwei Fassungen — dieselbe Idempotenz über den Schlüssel, die sich in
`bc2.eingang` bewährt hat.

### 2.5 Der Zustand des Rechnens zieht vom Briefkasten an den Lauf

`bc2.eingang.status` ist an das Paket gebunden und passt bei mehreren Fassungen nicht mehr. Er wird
**nicht mehr geschrieben** und im Spaltenkommentar als abgelöst vermerkt, aber nicht gelöscht.
`eingang` bleibt Briefkasten und Protokoll dessen, was BC0 geschickt hat. Ein fehlgeschlagener Lauf
ist eine Zeile in `bc2.lauf` mit Zustand `fehler`.

### 2.6 BC0 liest eine Sicht, nicht die Tabellen

`bc2.v_ergebnis_je_paket`: je Paket die jüngste Fassung, Gate-1-Zustand, `entschieden_am`, die
berührten Kernprozesse und die Zahl der freigegebenen Potenziale. **Die Sicht ist der Vertrag mit
BC0**, die Tabellen bleiben BC2-intern und umbaubar.

`SELECT` auf die Sicht vergibt BC2 selbst an `bc_leser` — die Objekte gehören `bc2_role`. **`USAGE`
auf Schema `bc2` kann nur BC0 vergeben** (ADR-003); darum gebeten an #241 und #286.

### 2.7 Was nicht in Schema `bc2` liegt

- **Die Präsentation** — sie wird aus den Daten erzeugt, nicht abgelegt; sie trägt keine eigene
  Information (CONTEXT.md).
- **Die mitgeführten Eingangswerte** — sie stehen im Konzeptdokument, keine eigene Tabelle.
- **Fremdschlüssel nach `public`** — `company_id`, `paket_id`, `kp_id` stehen als Werte. Ein
  `REFERENCES`-Recht wie bei `bc3_role` (v3.14) wird nicht beantragt, solange `anfrage_id` nicht
  gebraucht wird.
- **Die Tools beim Rückschreiben** (Simeons Auflage vom 07.09.2026) — bleiben Nebel der Karte.

## 3. Warum nicht anders

**Warum nicht ein Lauf mit allem als JSONB.** BC0 liest mit und müsste JSON-Pfade lesen; jede
Auswertung über Potenziale („alle freigegebenen Potenziale eines Mandanten") würde ein
`jsonb_array_elements` über verschachtelte Dokumente.

**Warum nicht voll normalisiert.** Der Vertrag ist die Form, in der ausgeliefert wird. Ihn in
Spalten zu zerlegen und beim Lesen wieder zusammenzusetzen ist Pflege ohne Gegenwert, macht jede
Vertragsänderung zur Migration und öffnet eine Stelle, an der das Ausgelieferte vom Abgelegten
abweichen kann.

**Warum Gate 1 nicht im Lauf-Dokument.** Das Ergebnis ist unveränderlich, die Entscheidung entsteht
danach und ändert sich bis zum Abschluss. Beides in eine Zeile zu legen hieße, ein unveränderliches
Dokument zu überschreiben.

**Warum kein Neulauf nach `approved`.** Dann lägen zwei geltende Lieferungen zum selben Paket im
Lieferordner, und BC3 müsste über die Verkettung herausfinden, welche gilt — nachdem es aus der
ersten womöglich schon Epics gebaut hat.

**Warum die Fassung nicht über Pakete zählt.** Dann wäre ein Reject eine Sackgasse, bis BC0 neu
schnürt — und BC0 hat dazu keinen Anlass, weil sich an den Daten nichts geändert hat.

## 4. Folgen

1. **Bau** — Migration `bc2.2`, Postgres-Umsetzung von `Gate1Buch` samt Vertragstest hinter
   `BC2_ECHTE_DB=1`. `Gate1Buch` schlüsselt heute nur nach `paket_id` und ersetzt immer; beides
   ändert sich (Fassung im Schlüssel, Konflikt statt Überschreiben nach Abschluss).
2. **`ersetzt_potenzial_ids`**: Die `potenzial_id` bleibt nicht gleich, weil jede Rechnung neu schneidet. BC3 rechnet aber seine
   Epic- und Story-IDs daraus (#242, Punkt 3). **Zwischen Fassungen eines Pakets trifft das BC3 nicht:**
   Ein Reject liefert nichts aus, und nach `approved` gibt es keine neue Fassung (2.1). BC3 sieht je Paket
   genau eine. Der Fall entsteht **über Pakete hinweg**, wenn nach einer Nacherhebung ein neues Paket zum
   selben Kernprozess kommt, und dort verkettet heute nichts, auch `ersetzt_konzept_id` nicht. Wer
   verknüpft und worauf, ist eine eigene Entscheidung mit Vertragsänderung
   ([#291](https://github.com/pg-coe-kmu/coe-factory/issues/291)). Schema `bc2` hält die Spalte vor.
   *(Berichtigt am 09.10.2026: Die erste Fassung verortete den Fall zwischen Fassungen.)*
   ✅ **Entschieden in ADR-009 · BC2** (#291): Anker ist der Teilprozess, nur 1:1, Streichliste in
   der Priorisierung, `ersetzt_konzept_id` bleibt auf ein Paket beschränkt — §2.1 hier gilt
   unverändert.
3. **BC0 muss `USAGE` auf `bc2` an `bc_leser` vergeben**, sonst ist die Sicht aus 2.6 unerreichbar.
   Ob BC0 zusätzlich ein Ereignis in `gate_ereignisse` braucht, bleibt BC0s Frage an #241.
4. **ADR-007 · BC2 §4 Punkt 4** („ein abgelehnter Lauf hat heute keinen Ablageort") ist mit dem Bau
   erledigt.
