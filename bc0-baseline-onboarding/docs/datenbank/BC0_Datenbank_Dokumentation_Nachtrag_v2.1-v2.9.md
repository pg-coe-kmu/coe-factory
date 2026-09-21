# BC0 — Datenbankdokumentation · Nachtrag v2.1 bis v2.9

**Stand:** 04.09.2026 (mittags) · v2.6 bis v2.8 eingespielt am 04.09.; v2.9 zum Einspielen vorbereitet · Autor: Simeon Ehmer
**Ergänzt** `BC0_Datenbank_Dokumentation.md` (Stand 22.08., Schemastand v1.7). Diese Fassung
beschreibt, was seither dazugekommen ist — **geprüft an den Skripten im Klon**, nicht am
Gedächtnis. Maßgeblich bleibt das Skript; hier steht die Erklärung.

---

## 1. Schemastände seit v1.7

| Stand | Datum | Inhalt |
|---|---|---|
| v1.6 | 03.09.2026 | Beleg-Ingestion Stufe 2: Textauslesen, Volltextsuche über Belege |
| **v2.1** | 27.08.2026 | `ref_anfragen`: `process_id` (FK `ref_prozesse`, RESTRICT), `sub_process_id` (FK `ref_teilprozesse`, SET NULL), `zuordnung_quelle` ∈ `anfrage` · `vorschlag_bc0` · `vorschlag_bc1` · `interview`; `ck_anfrage_tp_gehoert_kp`; Sicht `v_anfrage_prozessbezug` für `bc_leser` |
| **v2.2** | 27.08.2026 | `ck_teilprozess_step_no` **1–9**; `aktiv` an `ref_prozesse` und `ref_teilprozesse`; `prozess_herkunft` (n:m, `art` ∈ geteilt · zusammengelegt · umbenannt · umgehaengt · stillgelegt, `grund` Pflicht); `ref_anfragen.status` mit `ck_anfrage_status`, `status_seit`, `erhofftes_ziel`, `ausloeser` |
| **v2.3** | 28.08.2026 | `process_id`/`zuordnung_quelle` wieder nullable; `ck_anfrage_fortschritt_braucht_prozess` (**ohne Prozess kein Fortschritt**); `ck_anfrage_bezug_paarweise`; `umfang_geschaetzt`; `status` in der Sicht |
| **v2.4** | 02.09.2026 | `GRANT REFERENCES` auf `companies`, `ref_prozesse`, `ref_teilprozesse`, `mandant_rollen`, `ref_erhebungen` **an `bc1_role`** (nur an diese); Entzug der 48 Doppelvergaben; `ref_personen`/`prozess_personen` bleiben Direktrechte von `bc1_role` |
| **v2.5** | 02.09.2026 | `app_anmeldeversuche` — Anmeldebremse (Abdrücke je E-Mail und IP, Sperre) |
| **v2.6** | **04.09.2026** | **Historie (R9), Paket an BC2, Einfrieren** — Abschnitt 2 |
| **v2.7** | **04.09.2026** | **Die Anfrage als Klammer:** `anfrage_prozesse` (n:m), Übergabe nur vollständig, Status `uebergeben` — Abschnitt 2a |
| **v2.7.1** | **04.09.2026** | `gate_paket_schnueren()` setzt `uebergeben` aus **jedem** Stand davor (auch `eingegangen`); Nachziehen der Anfragen mit Paket — Befund aus der Ausroll-Probe |
| **v2.8** | **04.09.2026** | **Nacherhebung:** Kennung `E-JJJJ-MM` **oder** `E-JJJJ-MM-N`; `erhebung_naechste_kennung()` — Abschnitt 2b |
| **v2.9** | 04.09.2026 (vorbereitet) | **Vorher / Nachher:** `v_erhebung_reihenfolge`, `bewertung_aktuell_bis()`, `reifegrad_tp_bis()`, `reifegrad_vergleich()` — Abschnitt 2c |

## 2. v2.6 — Historie, Paket, Einfrieren

**Leitsatz (03.09.2026):** Prozesse, die BC2 anfasst, werden nicht gesperrt. Jede Änderung wird mit
Zeitstempel und Zeilenbild festgehalten; ein Paket an BC2 ist Datum plus Liste. Das Paket sagt,
*was* BC2 bekommen hat, die Historie sagt, *wie es zu diesem Datum aussah*; was BC2 darüber
hinaus liest, entscheidet er aus dem Paket heraus.

### `audit_log` — jetzt die Änderungshistorie (R9, #148)

Bestand seit v1.1, war leer. Drei Spalten dazu, Bedeutung neu:

| Spalte | Typ | Bedeutung |
|---|---|---|
| `audit_id` | bigserial | PK |
| `company_id` | uuid | aus der Zeile, ohne FK — die Historie überlebt den Mandanten |
| `entity` | text | Tabellenname |
| `entity_id` | text | Primärschlüssel als Text (Kompatibilität) |
| `action` | text | `INSERT` · `UPDATE` · `DELETE` · **`bestand`** (Bestandsaufnahme beim Einspielen) |
| `actor` | text | Sitzungsvariable `bc0.benutzer` (die App setzt je Verbindung die `benutzer_id`), sonst der Datenbankbenutzer — `psql` von Hand erscheint als `postgres` |
| `payload` | jsonb | = `neu` (Kompatibilität) |
| `at` | timestamptz | `now()` der Transaktion |
| **`pk`** | jsonb | Primärschlüssel als JSON — Anker der Zeitreise |
| **`alt`**, **`neu`** | jsonb | ganzes Zeilenbild vor und nach der Änderung |
| **`txid`** | bigint | Transaktion, für zusammengehörige Änderungen |

**Trigger `historie`** (AFTER INSERT/UPDATE/DELETE, FOR EACH ROW) auf **allen** Tabellen in
`public`, dynamisch aus dem Katalog — auch auf künftigen, sobald das Skript erneut läuft.
**Ausgenommen:** `app_benutzer` (Hashes), `app_sitzungen` (Schlüssel), `app_anmeldeversuche`
(Abdrücke), `audit_log` selbst. **Klarnamen nie:** `historie_pii_entfernen()` streicht `name`,
`email`, `telefon` aus jedem Zeilenbild von `ref_personen` (ADR-004 R5 — die Historie ist keine
zweite Stelle). Kaskaden werden protokolliert (`DELETE`-Zeilen bei Mandantenlöschung).

**Bestandsaufnahme:** beim ersten Einspielen jede vorhandene Zeile einmal als `bestand`. Ab
`historie_beginn()` ist die Historie vollständig; davor gibt es keine Antwort.

### Die Zeitreise

| Funktion | liefert |
|---|---|
| `historie_beginn()` | Zeitstempel der Bestandsaufnahme |
| `stand_zum(tabelle, datum[, company_id])` → `SETOF jsonb` | jede Zeile der Tabelle, wie sie zu `datum` war; gelöschte fehlen; vor dem Beginn Fehlermeldung; für ausgenommene Tabellen Fehlermeldung |
| `bewertung_aktuell_zum(company_id, datum)` | die Regel von `v_bewertung_aktuell` auf einen Zeitpunkt angewandt (je TP und Item die jüngste nicht verworfene Erhebung, wie sie damals bestand) |
| `reifegrad_tp_zum(company_id, datum)` | Ø-Stufe und Itemzahl je Teilprozess zum Zeitpunkt |
| Sicht `v_historie` | die Historie ohne Zeilenbilder, mit `process_id`/`sub_process_id` aus dem Zeilenbild — für Listen und Zählungen |

**Für BC2:** `SELECT * FROM v_uebergabe_offen` → `uebergeben_am` → `stand_zum('<tabelle>',
uebergeben_am, company_id)` für jede Tabelle, die er braucht, oder `bewertung_aktuell_zum()`.

### Erhebung einfrieren

| Trigger | Regel |
|---|---|
| `erhebung_eingefroren` auf `bitkom_bewertungen`, `bewertung_belege` | kein INSERT/UPDATE/DELETE, wenn die Erhebung `abgeschlossen` ist; Kaskaden (Mandantenlöschung) laufen durch |
| `erhebung_status_vorwaerts` auf `ref_erhebungen` | `abgeschlossen → offen` verboten; `verworfen` bleibt. Wer einen Fehler findet, verwirft und beginnt neu |

Die App (`_erhebung_offen()`) schreibt seit v2.6 nur noch in **offene** Erhebungen; das Gate
liest den Stand über `_erhebung_massgeblich()` ohne Nebenwirkung. *Bis v2.7 antwortete die App
nach einem Abschluss mit 400 (eine Erhebung je Monat); seit v2.8 legt sie die nächste an —
Abschnitt 2b.*

### Das Paket

| Tabelle | Spalten | Regel |
|---|---|---|
| `gate_pakete` | `company_id`, `paket_id` (uuid), `uebergeben_am`, `uebergeben_von` (FK `app_benutzer`), `ereignis_id` (FK `gate_ereignisse`, CASCADE), `hinweis` | **append-only** (Trigger `nur_anhaengen`); Nachzügler = neues Paket |
| `gate_paket_inhalt` | `(company_id, paket_id, sub_process_id)` PK; `freigabe_ereignis_id` (FK, CASCADE); `anfrage_id` (FK `ref_anfragen`, SET NULL, **NULL = Portfolio-Weg**); `bc1_profil_stand`; `hinweis_an_bc2` | append-only; `sub_process_id` **ohne** FK — Protokoll überlebt Teilung und Stilllegung |

`gate_paket_schnueren(company_id, benutzer_id, hinweis)` → `paket_id`: **eine** Transaktion —
Ereignis `uebergeben` am Unternehmen (`objekt_typ = 'unternehmen'`, neu in `ck_gate_objekt_typ`),
Paket, Inhalt aus `v_uebergabe_kandidaten`. Ohne Kandidaten kein leeres Paket.

| Sicht | liefert | für |
|---|---|---|
| `v_uebergabe_kandidaten` | freigegebene TPs, deren aktuelle Freigabe in keinem Paket steckt | Vorschau vor dem Knopf, Nachzügler danach |
| `v_uebergabe_offen` | je Paket und TP; `paket_rang = 1` = jüngstes | **BC2** (`bc_leser`) |
| `v_stand_veraltet` | je freigegebenem TP: Änderungen seit Freigabe / seit Paket (aus der Historie, ohne `gate_*`), betroffene Tabellen, `stillgelegt`, `struktur_geaendert` | BC0 und BC2 — verbietet nichts |

### Löschen

Trigger `stilllegen_statt_loeschen` auf `ref_prozesse` und `ref_teilprozesse`: `DELETE` wird
abgewiesen (ADR-004 R4, `aktiv = false`); die Kaskade vom Mandanten läuft durch.

### Rechte

`GRANT SELECT` an `bc_leser` auf `audit_log`, `v_historie`, `v_uebergabe_offen`,
`v_uebergabe_kandidaten`, `v_stand_veraltet`. Die Pakettabellen selbst bleiben verschlossen —
gelesen wird über die Sichten.

## 2a. v2.7 — Die Anfrage als Klammer

**Regel (Simeon, 03.09.2026, spätabends):** Übergeben wird eine Anfrage nur **vollständig** —
alle Teilprozesse, die zu ihr gehören, sind freigegeben, sonst gibt es kein Paket. Ein ROI auf
einem Ausschnitt wäre falsch. Nachzügler gibt es bei einer Anfrage nicht; ändert sich der Umfang
nach der Übergabe, entsteht ein neues Paket der ganzen Anfrage.

### `anfrage_prozesse` — welche Kernprozesse und Teilprozesse eine Anfrage betrifft (Punkt 115)

| Spalte | Typ | Bemerkung |
|---|---|---|
| `bezug_id` | bigserial | PK |
| `company_id`, `anfrage_id` | uuid, text | FK `ref_anfragen`, CASCADE |
| `process_id` | varchar(8) | FK `ref_prozesse`, CASCADE (nur für die Mandantenlöschung — einzeln ist ein Prozess seit v2.6 nicht löschbar) |
| `sub_process_id` | varchar(16) | FK `ref_teilprozesse`; **NULL = ganzer Kernprozess** (alle aktiven Teilprozesse) |
| `rolle` | text | `haupt` · `beteiligt` — **genau ein `haupt` je Anfrage** (Teilindex `ux_ap_haupt`) |
| `zuordnung_quelle` | text | je Bezug: `anfrage` · `vorschlag_bc0` · `vorschlag_bc1` · `interview` |

Eindeutig je `(company_id, anfrage_id, process_id, coalesce(sub_process_id, ''))`. Der
Hauptbezug spiegelt sich per Trigger in `ref_anfragen.process_id/sub_process_id/zuordnung_quelle`
— die dortigen Spalten bleiben die Kurzform, und `ck_anfrage_fortschritt_braucht_prozess` gilt
weiter. Beim Einspielen wird der bisherige Einzelbezug jeder Anfrage als Hauptbezug übernommen.
Historie-Trigger inklusive.

### Sichten

| Sicht | liefert |
|---|---|
| `v_anfrage_teilprozesse` | die SOLL-Liste je Anfrage, aufgelöst auf Teilprozesse; je Zeile `freigegeben`, `freigabe_ereignis_id`, `im_paket` |
| `v_anfrage_uebergabe_stand` | je Anfrage: `soll`, `freigegeben`, `fehlend[]`, `vollstaendig`, `uebergabefaehig` (vollständig **und** nicht bereits mit genau diesen Freigaben übergeben), letztes Paket |

### `gate_paket_schnueren(company_id, benutzer_id, hinweis, anfrage_id, teilprozesse[])`

Mit `anfrage_id`: nur, wenn **alle** Teilprozesse der Anfrage freigegeben sind — sonst Abbruch
mit *„n von m — es fehlen …"*; ein identisches zweites Paket wird abgewiesen; Ereignis
`uebergeben` am Objekt `anfrage` (neu in `ck_gate_objekt_typ`); setzt `ref_anfragen.status =
'uebergeben'`. Ohne `anfrage_id`: Portfolio-Weg mit ausdrücklicher Liste aus
`v_uebergabe_kandidaten`, Ereignis am Objekt `unternehmen`. Die 3-Parameter-Fassung aus v2.6
ist entfernt.

### Status

`eingegangen → zugeordnet → im_interview → am_gate → uebergeben → bewertet → beauftragt → erledigt | abgelehnt`

**v2.7.1:** `gate_paket_schnueren()` setzte `uebergeben` zunächst nur aus `zugeordnet`, `im_interview`,
`am_gate`. Im Betrieb steht jede Anfrage auf `eingegangen` — niemand zieht den Status von Hand
weiter — und die Probe beim Ausrollen fand ein Paket mit Status `eingegangen` davor. Seit v2.7.1
folgt der Status dem Paket aus jedem Stand davor; ein Rücksprung aus `bewertet` und später bleibt
ausgeschlossen. Bereits übergebene Anfragen wurden nachgezogen (Historie: `ref_anfragen UPDATE`).

## 2b. v2.8 — Nacherhebung: mehrere Erhebungen je Monat

**Der Befund:** Seit v2.6 ist `abgeschlossen` eine Sperre (Trigger), und `E-JJJJ-MM` erlaubte eine
Erhebung je Monat. Wer am 4. abschloss, konnte bis zum 1. des Folgemonats nichts mehr bewerten.

**Die Regel (Simeon, 04.09.): dieselbe wie beim Paket — alt bleibt, neu kommt dazu.**

| | |
|---|---|
| Kennung | `E-JJJJ-MM` für die erste Erhebung des Monats, `E-JJJJ-MM-2`, `-3` … für weitere. `CHECK (erhebung_id ~ '^E-[0-9]{4}-[0-9]{2}(-[2-9]\|-[1-9][0-9]+)?$')`. Fremdschlüssel sind Text — nichts weiter ändert sich |
| `erhebung_naechste_kennung(company_id, datum DEFAULT current_date)` | Basis, wenn es sie noch nicht gibt, sonst höchste Nummer + 1. **Verworfene zählen mit** — eine Kennung wird nie ein zweites Mal vergeben. `bc_leser` darf sie aufrufen |
| Nach dem Abschluss | Die nächste Bewertung legt automatisch die nächste Erhebung an („Nacherhebung MM/JJJJ", `hinweis` nennt die Vorgängerin). Die abgeschlossene bleibt unverändert — **das** ist die Sperre: nicht „niemand darf bewerten", sondern „das Alte wird nicht überschrieben" |
| Abschließen / Beginnen | bewusste Handlung von **BC0 (Admin)** — Knopf im Self-Rating-Reiter. `neu` nur, wenn keine Erhebung offen ist (zwei offene hätten keinen eindeutigen Empfänger). **Nicht** an das Paket gekoppelt: ein Paket betrifft eine Anfrage, eine Erhebung den ganzen Mandanten |
| Was gilt | je Item der jüngste Wert über alle nicht verworfenen Erhebungen (unverändert seit v1.3). **Ab dem Paket gilt für BC2 der Stand zum Paketdatum** (`stand_zum`), nicht die Erhebung; `v_stand_veraltet` zeigt die Bewegung danach |
| Was keine Erhebung braucht | Prozesse, Personen, Systeme, Rollen — Stammdaten stehen in der Historie (v2.6) |

Die Erhebung ist seit R9 kein Einfrierpunkt mehr, sondern der **Name einer Messkampagne** —
damit der Reifegradbericht Kampagnen vergleichen kann und die Gate-Freigabe eine lesbare Kurzform
(`bc0_stand`) trägt.

## 2c. v2.9 — Vorher / Nachher: der Stand nach einer Erhebung

**Die Frage (Simeon, 04.09.):** *„Werden die Items geändert, ändert sich der Reifegrad je Prozess.
Und immer auf aktuellem Stand — wie machen wir eine Vor-/Nachher-Betrachtung?"* Der Bericht liest
immer die Zusammensetzung aus allen nicht verworfenen Erhebungen (`v_bewertung_aktuell`); der
Status `abgeschlossen` filtert dort nichts. Eine Nacherhebung verändert den Bericht — das Vorher war weg.

| | |
|---|---|
| `v_erhebung_reihenfolge` | Erhebungen je Mandant in der Ordnung (`stand`, `erhebung_id`) — derselben, die `v_bewertung_aktuell` benutzt — mit `rang`, `bewertungen` und **`fest`**: diese und alle früheren Erhebungen sind nicht mehr offen |
| `bewertung_aktuell_bis(company_id, erhebung_id)` | `v_bewertung_aktuell`, aber nur über die Erhebungen bis einschließlich der genannten. Der **Stand nach X**. Leer bei unbekannter oder verworfener Kennung |
| `reifegrad_tp_bis(company_id, erhebung_id)` | Ø Stufe und Itemzahl je Teilprozess im Stand nach X |
| `reifegrad_vergleich(company_id, von, bis)` | je Teilprozess `vorher`, `nachher`, `delta`, `geaendert` (Item in beiden Ständen, Wert verschieden), `neu_bewertet` (nur im Nachher) |

**Die Rolle des Abschlusses:** Der Stand nach X ist genau dann **fest**, wenn X und alle Erhebungen
davor abgeschlossen (oder verworfen) sind — eine offene Erhebung kann sich noch ändern. Abschließen
heißt für den Bericht: *„Dieses Vorher steht."* Dafür braucht es keine Historie; die Ordnung der
Erhebungen reicht, also für alles seit Juni. Der Stichtag per **Datum** (`bewertung_aktuell_zum`, v2.6)
bleibt der Weg für BC2 und das Paketdatum.

Die App rechnet dasselbe in Python (SQLite-Betrieb): `GET …/report?bis=E-…` (Bericht auf den Stand
nach X, `bis.fest` im Ergebnis) und `GET …/report/vergleich?von=&bis=` (Gesamt, Dimensionen,
Teilprozesse, geänderte Items mit altem und neuem Wert). Regel in der Datenbank, Ergebnis in der App.

## 3. HTTP-Schnittstelle — neu seit v1.7

| Methode | Pfad | Recht | seit | Zweck |
|---|---|---|---|---|
| `GET`/`POST` | `/api/companies/{cid}/anfragen` | Mandant | 27.08. | Anfragen lesen (seit v2.7 mit `bezuege`), anlegen (`A-JJJJ-NN`; ein Bezug wird Hauptbezug) |
| `GET` | `…/anfragen/{id}/vorschlaege` | Mandant | 03.09. | Trichter 3, regelbasiert, bis zu drei Vorschläge |
| `PUT` | `…/anfragen/{id}/zuordnung` | Mandant | 02.09. / **v2.7** | Prozessbezug nachtragen; **`bezuege` (Liste, n:m, genau ein `haupt`) oder Einzelform** (setzt den Hauptbezug, Beteiligte bleiben); ändert den Status nicht |
| `PUT` | `…/anfragen/{id}/status` | Mandant | 02.09. | Status setzen; kein Fortschritt ohne Bezug; kein Rücksprung außer `abgelehnt` |
| `POST` | `…/prozesskanten` | Mandant | 02.09. | Kante zwischen Kernprozessen, `art` Pflicht |
| `GET` | `…/erhebungen` | Mandant | 17.08. / **v2.8** | Erhebungen lesen; seit v2.8 mit `offen`, `naechste`, `massgeblich` (ohne verworfene) |
| `POST` | `…/erhebungen` | **Admin** (v2.8) | 17.08. / **v2.8** | `abschliessen` · `neu` (nur ohne offene; Kennung nach Regel; `bezeichnung`) · `verwerfen` |
| `POST` | `…/rating` | Mandant | **v2.8** | antwortet zusätzlich mit `erhebung_id` und `erhebung_neu` — wohin geschrieben wurde |
| `GET` | `…/report?bis=` | Mandant | **v2.9** | Reifegradbericht auf den Stand nach einer Erhebung; `bis` mit `fest` im Ergebnis |
| `GET` | `…/report/vergleich?von=&bis=` | Mandant | **v2.9** | Vorher/Nachher: Gesamt, Dimensionen, Teilprozesse, geänderte Items |
| `POST` | `…/process/{pid}/subprocess/add` | Mandant | 27.08. | Teilprozess ergänzen, bis 9 |
| `GET`/`POST` | `…/documents/suche`, Beleg-Endpunkte Stufe 2 | Mandant | 03.09. | Volltextsuche über Belege |
| `GET` | `…/uebergabe` | **Admin** | **v2.6/v2.7** | je Anfrage `soll`/`freigegeben`/`fehlend`/`uebergabefaehig`, Portfolio-Kandidaten, bisherige Pakete |
| `POST` | `…/uebergabe` | **Admin** | **v2.6/v2.7** | Paket schnüren: `anfrage_id` (nur vollständig) **oder** `teilprozesse[]` (Portfolio); `hinweis` optional |
| `GET` | `…/uebergabe/veraltet` | **Admin** | **v2.6** | `v_stand_veraltet` |
| `POST` | `…/gate/{tp}/widerrufen` | **Admin** | **v2.6** | Freigabe widerrufen, `grund` Pflicht |
| `GET` | `…/stand?datum=` | Mandant | **v2.6** | Reifegrad je TP zum Zeitpunkt (`reifegrad_tp_zum`) |
| `GET` | `…/historie?tp=&seit=&limit=` | Mandant | **v2.6** | `v_historie` des Mandanten |
| `GET` | `/anfrage/` (+ `sw.js`, `manifest.json`) | — | 02.09. | die Anfrage-PWA, zweite Anwendung |

Die v2.6-Endpunkte außer dem Widerruf antworten im SQLite-Modus mit **501** und sagen es.

**Die drei BC1-Endpunkte (Zuordnung, Status, Kanten) brauchen ein Anwendungskonto** —
`Depends(angemeldeter_benutzer)`, nicht `bc1_role`.

## 4. Was sich an Aussagen der Doku v1.7 ändert

| Doku v1.7 sagt | gilt seit |
|---|---|
| `ref_teilprozesse.step_no` `BETWEEN 1 AND 5` | **1 AND 9** (v2.2) |
| `audit_log` „derzeit leer, Etappe 4c" | **Änderungshistorie mit Zeilenbildern** (v2.6) |
| `gate_ereignisse.objekt_typ` ∈ prozess · teilprozess | + **`unternehmen`** (v2.6) |
| `gate_ereignisse.grundlage` „der Datenstand" | wird von der Freigabe **nicht** geschrieben; den Stand liefert die Historie (`stand_zum`) |
| `ref_erhebungen.status` „abgeschlossen = Grundlage für Freigaben" | **abgeschlossen = eingefroren**, technisch erzwungen (v2.6) |
| `ref_anfragen`: sieben Spalten | + `process_id`, `sub_process_id`, `zuordnung_quelle`, `status`, `status_seit`, `erhofftes_ziel`, `ausloeser`, `umfang_geschaetzt` (v2.1–v2.3); **ein Bezug je Anfrage** → seit v2.7 n:m in `anfrage_prozesse`, `ref_anfragen` trägt den Hauptbezug |
| „ref_prozesse: derzeit kein `aktiv`" (implizit) | `aktiv` an beiden Prozesstabellen (v2.2); `DELETE` abgewiesen (v2.6) |
| Abschnitt 13 „Kein Erhebungsbezug … noch nicht gebaut" | überholt seit v1.3 Teil C (17.08.) |
| Abschnitt 15 „v2.1 offen" | v2.1–v2.5 eingespielt, v2.6 am 04.09. |
