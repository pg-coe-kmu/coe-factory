# `prozessprofil.sql` und `sessions.sql` einspielen — Anleitung und Rechte-Ist-Stand

> Betriebsdoku für den Menschen, der die BC1-Tabellen in eine Datenbank bringt.
> Stand 13.09.2026. Alle Zahlen und Rollennamen hier sind **gemessen**, nicht angenommen.
> `prozessprofil.sql` ist seit dem 08.09. **in der Ziel-Supabase ausgeführt** (Abschnitt 9),
> `sessions.sql` (B1) seit dem 13.09. (Abschnitt 10).

## Das Wichtigste in fünf Sätzen

Die Datei legt drei Tabellen im Schema `bc1` an und prüft **vorher**, ob der Bestand zu
dem passt, was sie erwartet. Sie läuft in **einer** Transaktion: entweder alles oder
nichts. Trifft sie auf eine leere Datenbank, legt sie an (**Fall 1**); trifft sie den
exakt erwarteten Bestand, tut sie nichts (**Fall 2**); weicht irgendetwas ab, **bricht sie
ab und ändert nichts** (**Fall 3**). Die Prüfung vergleicht den Ist-Zustand des Katalogs
Zeile für Zeile mit einer im Skript hinterlegten **Sollsignatur** (177 Zeilen). Wer die
DDL ändert, muss die Signatur neu erzeugen — sonst blockiert sich das Skript selbst.

Seit B1 (13.09.2026) gibt es eine **zweite Datei `sessions.sql`** für die Sitzungstabelle
`bc1.sessions` (kompletter Interview-Zustand inklusive Rohtext): gleiche Dreifallregel,
eigene Sollsignatur (40 Zeilen), Geltungsbereich genau diese eine Tabelle — **eigenständig**
geprüft, einschließlich Mitgliedschafts-Kanten und der RI-Trigger auf beiden Seiten des
Fremdschlüssels zu `companies`. Sie läuft **nach** `prozessprofil.sql`; die erste Datei
bleibt davon unberührt und meldet weiter Fall 2 (im Container in beide Richtungen
getestet). Der Dienst legt die Sitzungstabelle nicht mehr selbst an — fehlt sie oder
fehlen der DSN-Rolle die Rechte, bricht er beim Start mit Verweis auf diese Anleitung ab.

Seit #255 (22.09.2026) gibt es eine **dritte Datei `prozessprofil_d3.sql`**, die **vor**
`prozessprofil.sql` läuft: BC2 hat Frage D3 gebunden (Vertrag 1.2), `step_frequency_per_year`
ist deshalb eine echte Spalte in `bc1.prozessprofil` (numeric, im Wertebereichs-CHECK). Weil
`prozessprofil.sql` einen Bestand nie verändert (nur anlegen oder bestätigen), bringt diese
Datei den **vorhandenen** Bestand auf den neuen Stand — eigene Vierfallregel: **M0** Tabelle
fehlt → nichts zu tun (frische DB) · **M1** Spalte fehlt + alter CHECK → Spalte anlegen, CHECK
erweitern, Nachprüfung in derselben Transaktion · **M2** schon migriert → nichts zu tun ·
**M3** alles andere → Abbruch ohne Änderung. Der Nachweis, dass die Migration stimmt, ist
`prozessprofil.sql` danach: **Fall 2**. Gleiches Muster wie BC0s `schema_v3.x`-Dateien.

---

## 1. Voraussetzungen: welche Rechte BC1 braucht

Erteilt von BC0 am 02.09.2026, in der Ziel-Supabase nachgemessen:

| Recht | Auf | Weg |
|---|---|---|
| `REFERENCES` | `companies`, `ref_prozesse`, `ref_teilprozesse`, `mandant_rollen`, `ref_erhebungen` | direkt an `bc1_role` |
| `SELECT` | `v_bewertung_aktuell`, `mandant_systeme`, `ref_teilprozesse`, `companies`, `v_prozesse_lesen` | über die Gruppenrolle `bc_leser` (in der `bc1_role` Mitglied ist) |
| `SELECT` | `ref_erhebungen` | erteilt, am 02.09. gemessen — Abschnitt 0 der DDL prüft es und bricht sonst ab |
| `REFERENCES` | `ref_personen`, `prozess_personen` | direkt an `bc1_role`; in Etappe 1 ungenutzt |

`bc1.profil_write_status` ist unsere interne Tabelle — BC0 muss dafür nichts vorbereiten.

**Dauerregel (15.09.2026, an BC0 zugesichert):** Das SELECT von `bc1_role` auf `companies` — heute über `bc_leser` — ist keine Bequemlichkeit, sondern Voraussetzung für BC0s Löschkaskade: der Freeze-Trigger liest `public.companies` mit den Rechten von `bc1_role`, wenn BC0 einen Mandanten löscht. Fällt das Recht weg, bricht BC0s DSGVO-Löschung, nicht unser Dienst. Wer die Rechte umbaut, hält diesen Weg offen (Mitgliedschaft in `bc_leser` oder direktes SELECT).

## 2. Einspielen

Aus `bc1-context-discovery/`, **als `bc1_role`**:

```bash
psql "$BC1_DB_DSN" -v ON_ERROR_STOP=1 -1 -f bc1_service/db/prozessprofil_d3.sql \
                                         -f bc1_service/db/prozessprofil.sql \
  && psql "$BC1_DB_DSN" -v ON_ERROR_STOP=1 -1 -f bc1_service/db/sessions.sql
```

`-1` ist nicht optional: Die Dreifallregel verlässt sich darauf, dass ein Abbruch alles
zurückrollt. **`prozessprofil_d3.sql` und `prozessprofil.sql` laufen in EINER Transaktion**
(zwei `-f` hinter einem `-1`): Die Migration prüft nur Spalte und CHECK (M0–M3), die volle
Signaturprüfung macht erst `prozessprofil.sql` — meldet die Fall 3, rollt das die Migration
mit zurück, statt sie committet stehen zu lassen (Codex-Review 22.09., Test
`test_fall_3_von_prozessprofil_sql_rollt_die_migration_in_derselben_transaktion_zurueck`).
`sessions.sql` ist eine eigene Transaktion und prüft eigenständig (wie `prozessprofil.sql`
auch die Mitgliedschafts-Kanten). Das `&&` ist Pflicht: meldet die erste Klammer Fall 3,
darf `sessions.sql` gar nicht erst laufen — erst die Abweichung verstehen. Reihenfolge wie
in den Tests (`tests/db_fixture.py`), damit die Live-Meldungen in derselben Ordnung stehen.

## 3. Die Dreifallregel lesen

| Meldung | Bedeutung | Was tun |
|---|---|---|
| `NOTICE: Fall 1` | Datenbank war leer, alles wurde angelegt | fertig |
| `NOTICE: Fall 2` | Bestand entspricht exakt der Sollsignatur | fertig, nichts passiert |
| `Fall 3: Bestand weicht von der Sollsignatur ab` | **Vorprüfung**: es war schon etwas da, das nicht passt | **nichts wurde geändert.** Abweichungen stehen als `+ zuviel:` / `- fehlt:` |
| `Nachpruefung fehlgeschlagen — Rollback` | **Nachprüfung**: wir haben angelegt, aber das Ergebnis passt nicht zur Sollsignatur | ebenfalls **nichts geändert** (Rollback). Häufigster Grund: zusätzliche `acl\|…\|SELECT`-Zeilen ⇒ es gibt **Standardrechte im Schema** (`ALTER DEFAULT PRIVILEGES`), siehe Abschnitt 8 |

In beiden Fällen gilt: jede Abweichung Zeile für Zeile lesen und verstehen — **nie** die
Prüfung abschalten.

## 4. Sollsignatur: wann und wie neu erzeugen

**Wann:** nach *jeder* Änderung an der DDL, und beim Wechsel der PostgreSQL-Hauptversion.

```bash
# 1. Den Signaturblock in Abschnitt 0b DER JEWEILIGEN DATEI durch die eine Platzhalterzeile ersetzen:
#    ('platzhalter|wird|in|step7|ersetzt');
# 2. Aus bc1-context-discovery/, gegen den Test-Container (ohne Argument: prozessprofil.sql):
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" \
    uv run python tests/db/signatur_erzeugen.py bc1_service/db/sessions.sql
# 3. git diff lesen — jede geänderte Zeile muss erklärbar sein — dann committen.
```

Der Generator liegt seit B1 **im Repo** (`tests/db/signatur_erzeugen.py`, bei den Tests, weil
er das BC0-Gerüst braucht und die Zieldatenbank wischt — **nie gegen die Supabase**). Ein
Test hält fest, dass er die committete `prozessprofil.sql`-Signatur byteidentisch reproduziert.

**Hauptversion (Klärpunkt K-H, entschieden 03.09.):** Test-Container **und** Ziel laufen
PostgreSQL 17. Der Container wird mit `postgres:17` gestartet. Gegen PostgreSQL 16 erzeugt,
fehlen der Signatur drei Zeilen `acl|<tabelle>|bc1_role|MAINTAIN|f` (PG 17 kennt ein achtes
Tabellenrecht) und das Einspielen bricht mit Fall 3 ab — an beiden Versionen gemessen.

## 5. Bekannte Umgebungsrollen (Klärpunkt K-G, entschieden 03.09.)

Die Signatur betrachtet **alle** Rollen der Zieldatenbank — nur drei namentlich genannte
sind ausgenommen (Temp-Tabelle `bc1_umgebungsrollen` in Abschnitt 0b). Ohne diese Ausnahme
bräche das Einspielen an der Umgebung ab, obwohl mit unserem Schema alles stimmt.

**So wurde die Liste bestimmt** — die Abfrage liefert genau die Rollen, die über
Mitgliedschaft oder `pg_read_all_data` an unsere Tabellen kämen:

```sql
-- 'MEMBER' ist Absicht und NICHT durch 'USAGE' ersetzbar: eine Mitgliedschaft
-- mit SET, aber ohne INHERIT liefert USAGE = false — per 'SET ROLE' bekommt die
-- Rolle den Zugriff aber trotzdem. Genau diese Klasse uebersieht eine reine
-- USAGE-Abfrage (Review 03.09., im Container bis zum Schreibzugriff nachgestellt).
SELECT r.rolname,
       pg_has_role(r.oid, 'bc1_role'::regrole, 'MEMBER')         AS via_bc1_role,
       pg_has_role(r.oid, 'bc_leser'::regrole, 'MEMBER')         AS via_bc_leser,
       pg_has_role(r.oid, 'pg_read_all_data'::regrole, 'MEMBER') AS via_read_all,
       pg_has_role(r.oid, 'bc1_role'::regrole, 'USAGE')          AS erbt_bc1_role
  FROM pg_roles r
 WHERE NOT r.rolsuper AND r.rolname NOT LIKE 'pg\_%'
   AND (pg_has_role(r.oid, 'bc1_role'::regrole, 'MEMBER')
     OR pg_has_role(r.oid, 'bc_leser'::regrole, 'MEMBER')
     OR pg_has_role(r.oid, 'pg_read_all_data'::regrole, 'MEMBER'))
 ORDER BY 1;
```

**Ergebnis in der Ziel-Supabase am 03.09.2026** (19 Nicht-Superuser-Rollen insgesamt):

| Rolle | kommt herein über | in der Ausnahmeliste? |
|---|---|---|
| `bc1_role`, `bc2_role`, `bc3_role`, `bc4_role`, `bc_leser` | unsere eigenen Rollen | nein — sie gehören zur Signatur |
| `postgres` | `bc1_role`, `bc_leser`, `pg_read_all_data` | **ja** — Supabase-Administration, dort kein Superuser |
| `supabase_read_only_user` | `pg_read_all_data` | **ja** |
| `supabase_etl_admin` | `pg_read_all_data` | **ja** |

**Was die Ausnahme kostet — genau und ungeschönt:** Für diese drei Namen prüfen wir
Mitgliedschaften und effektive Rechte nicht. Bekäme eine von ihnen zusätzliche Rechte auf
unseren Tabellen — auch **schreibende** —, fiele das nicht auf. Das ist der bewusst bezahlte
Preis; die Ausnahme gilt unbedingt, nicht nur fürs Lesen.

**Was sie nicht kostet:** Für alle anderen Rollen bleibt die Prüfung scharf, und zwar auf
drei sich gegenseitig deckenden Wegen: die ACL der Tabellen (`acl|`, gilt **auch** für die
drei ausgenommenen Rollen — ein direktes `GRANT` an sie bricht ab), die effektiven Rechte
(`effektiv|`, `effektiv_spalte|`) und die **Mitgliedschafts-Kanten** (`mitglied|`) in jede
Rolle, über die man hereinkäme. Der letzte Weg ist der wichtigste: Eine Mitgliedschaft mit
`SET`, aber ohne `INHERIT`, ist für die Effektiv-Sicht unsichtbar — `SET ROLE` funktioniert
trotzdem. Fünf Tests halten das fest, darunter
`test_set_mitgliedschaft_in_ausgenommener_rolle_wird_erkannt` und
`test_aehnlich_benannte_fremdrolle_ist_nicht_ausgenommen`.

**Vor dem Einspielen in eine neue Umgebung:** die Abfrage oben dort ausführen. Erscheint
eine Rolle, die hier nicht steht, **erst klären, dann entscheiden** — nicht blind
nachtragen. Jeder Eintrag braucht eine Begründung in derselben Zeile der DDL, und der Test
`test_ausnahmeliste_enthaelt_genau_die_drei_gemessenen_rollen` erzwingt, dass die Liste
bewusst geändert wird.

> **Restrisiko, ehrlich benannt:** Der Fall, der K-G ausgelöst hat — `postgres` als
> Nicht-Superuser mit Mitgliedschaft in `bc1_role` — ist im Test-Container **nicht**
> nachstellbar: dort ist `postgres` Superuser und fällt schon vorher aus der Prüfung. Dass
> das Einspielen in der Ziel-Supabase nach dieser Änderung durchläuft, war damit
> hergeleitet und an den gemessenen Rollen geprüft, **bis zum 08.09. aber nicht dort
> ausgeführt** — seitdem gemessen (Abschnitt 9). Für `sessions.sql` gilt derselbe Stand bis
> zu ihrem Live-Lauf (Abschnitt 10). Der erste echte Einspiel-Lauf einer Datei ist deshalb
> mit wachem Auge zu fahren — Fall 3 dort bedeutet zuerst: die Abfrage oben erneut
> ausführen und mit dieser Tabelle vergleichen.

## 6. Als welche Rolle verbindet der Dienst?

`main.py` öffnet beide Pools **ohne** `SET ROLE`. Produktiv entscheidet also der Benutzer-
Anteil von `BC1_DB_DSN` — oder eine `options=-c role=…`-Angabe in der DSN, wie sie die
Tests nutzen —, als wer der Dienst arbeitet.

> **`BC1_DB_DSN` muss als `bc1_role` arbeiten.** Nur sie hat die Rechte auf `bc1.*`
> (vergeben von `prozessprofil.sql` und `sessions.sql`). Der Session-Store prüft das beim
> Start — Tabelle vorhanden **und** `SELECT/INSERT/UPDATE/DELETE` für die DSN-Rolle — und
> bleibt sonst mit lesbarer Meldung stehen, statt beim ersten Turn zu scheitern.

## 7. Leserechte: wer darf was

| Tabelle | `bc1_role` | `bc_leser` (und damit BC2–BC4) |
|---|---|---|
| `bc1.prozessprofil` | alles | `SELECT` |
| `bc1.profil_rollen` | alles | `SELECT` |
| `bc1.profil_write_status` | alles | **nichts** (ausdrückliches `REVOKE`) |
| `bc1.sessions` (B1) | alles | **nichts** (ausdrückliches `REVOKE`; Sitzungszustand mit Rohtext) |

Unsere DDL vergibt diese Rechte selbst — BC0 muss nichts nachziehen. Offen ist nur BC0s
ausdrückliche Bestätigung, dass `bc_leser` auch für `profil_rollen` gilt (Rückfrage vom
02.09.); ohne Widerspruch stellen wir beide gleich.

## 8. Deploy-Gate: was vor dem ersten Produktivlauf erledigt sein muss

| Punkt | Stand 03.09.2026 |
|---|---|
| **K-C** Wertebereiche der Zahlenspalten | **erledigt.** Entschieden: 0 zulässig, Kommastellen und ganze Zahlen erlaubt — das ist der heutige CHECK, keine Änderung nötig |
| **K-G** Geltungsbereich der Signatur | **erledigt**, siehe Abschnitt 5 |
| **K-H** PostgreSQL-Hauptversion | **erledigt**, siehe Abschnitt 4 |
| **K-I** Standardrechte für Schema `bc1` | **erledigt 08.09.2026.** BC0 hat das `ALTER DEFAULT PRIVILEGES` für Schema `bc1` entfernt (`REVOKE ALL ON TABLES FROM bc_leser`) und das gemessen; **wir haben gegengemessen**: `pg_default_acl` enthält keine Zeile mehr für `bc1`. Für die übrigen Kontexte hat BC0 gesondert entschieden und sie unterrichtet. |

---

## Anhang: Warum die Prüfung so streng ist

Die drei Tabellen stehen in einer Datenbank, die sich mehrere Bounded Contexts teilen, und
sie enthalten personenbezogene Angaben aus Interviews. Ein still hinzugefügtes Leserecht
**auf einer dieser drei Tabellen**, eine geänderte Spalte oder ein deaktivierter Trigger
fiele ohne diese Prüfung niemandem auf. Deshalb umfasst die Signatur: ACLs einschließlich
Spaltenrechten, Mitgliedschafts-Kanten in jede Rolle, über die man an die Tabellen käme,
die **effektiven** Rechte jeder Rolle (also auch geerbte), RLS-Zustand und Policies,
Rewrite-Regeln, Trigger einschließlich der internen FK-Trigger, Funktionsrechte und die
Tabellenkommentare.

**Was sie ausdrücklich NICHT abdeckt** (Review 03.09., jeder Punkt im Container
nachgestellt — kein Fall 3, Zugriff funktionierte):

- **Neue Objekte, die auf unsere Tabellen zeigen.** Eine View `bc1.export AS SELECT * FROM
  bc1.prozessprofil`, die `bc1_role` gehört, vermittelt Lesezugriff, ohne eine der drei
  Tabellen-ACLs zu berühren. Dasselbe gilt für eine `SECURITY DEFINER`-Funktion. Die
  Signatur inventarisiert nur die drei Tabellen und die drei Triggerfunktionen.
- **Standardrechte** (`pg_default_acl`) — sie wirken erst auf *künftige* Objekte, siehe
  Abschnitt 8 (K-I).
- **Diese Lücke gilt für beide Dateien.** `sessions.sql` prüft dieselben Arten wie
  `prozessprofil.sql` — einschließlich Mitgliedschafts-Kanten — und zusätzlich die
  RI-Trigger **beider** Seiten ihres Fremdschlüssels (der Kaskaden-Trigger sitzt auf
  `companies`; Review 13.09.). Funktionen prüft sie nicht, weil sie keine hat; eine fremde
  `SECURITY DEFINER`-Funktion oder View auf `bc1.sessions` sähe **keine** der beiden
  Dateien (Abschlussplan C4: Inventarprüfung fremder Objekte in `bc1`). Die Signatur-Sicht
  liegt zweimal im Repo (je Datei) — bewusst, solange es zwei Einheiten sind.

Wer im Schema `bc1` etwas anlegen darf, kann daran vorbei. Die Prüfung ersetzt also nicht
die Frage, **wer `CREATE` in diesem Schema hat** — sie sichert, dass die drei
Vertragstabellen selbst so stehen, wie wir sie angelegt haben.

---

## 9. Erster Live-Lauf in der Supabase — 08.09.2026

Ausgeführt als `bc1_role` gegen PostgreSQL **17.6** (Session Pooler, Port 5432).

| Schritt | Ergebnis |
|---|---|
| Vorprüfung | Rollen **exakt die acht aus Abschnitt 5** (Schema v3.0 brachte keine neue), alle geforderten Rechte `t`, Schema `bc1` leer, K-I geschlossen |
| Lauf 1 | `NOTICE: Fall 1: kein Vertragsobjekt vorhanden — vollstaendige Anlage.` + `NOTICE: Sollsignatur bestaetigt.` |
| Lauf 2 | `NOTICE: Fall 2: Bestand ist identisch zur Sollsignatur — No-op.` — Idempotenz **im Ziel** bewiesen, nicht nur im Container |
| Nachprüfung | drei Tabellen mit Eigentümer `bc1_role`; `bc_leser` hat `SELECT` auf `prozessprofil` und `profil_rollen`, **nichts** auf `profil_write_status`; drei eigene Trigger aktiv; zehn Fremdschlüssel validiert |

**Das Restrisiko aus Abschnitt 5 hat sich nicht bestätigt.** Die Konstellation, die K-G
ausgelöst hatte — `postgres` als Nicht-Superuser mit Mitgliedschaft in `bc1_role` — ist im
Test-Container nicht nachstellbar; der Live-Lauf zeigt, dass die Ausnahmeliste dort genau so
greift wie hergeleitet. Damit ist die Herleitung durch eine Messung ersetzt.

**Für BC0 heißt das:** ein `GRANT SELECT` auf `bc1.prozessprofil` und `bc1.profil_rollen` ist
**nicht nötig** — unsere DDL vergibt das Leserecht an `bc_leser` selbst (Abschnitt 7).

---

## 10. Zweiter Lauf: `sessions.sql` in der Supabase — 13.09.2026

Ausgeführt als `bc1_role` (Session Pooler), Signatur **40 Zeilen**, alle Zeilen gemessen
(`einspielen.log`, `einspielen-sessions.log`, `einspielen-nachpruefung-sessions.log`):

| Schritt | Erwartung | Gemessen |
|---|---|---|
| Vorbedingung | `prozessprofil.sql` erneut: `NOTICE: Fall 2` (die alte Datei ist unberührt) | **`Fall 2` in beiden Läufen von `lauf.sh ein` und erneut als Vorbedingung im `sessions`-Lauf** — die vierte Tabelle beeinflusst die alte Datei nicht, jetzt auch live belegt |
| Umgebungsrollen | Abfrage aus Abschnitt 5 liefert dieselben acht Rollen wie am 12.09. | nicht erneut abgefragt; die Sollsignatur (inkl. `mitglied\|`, `effektiv\|`) wurde ohne Abweichung bestätigt — eine neue Rolle mit Zugriff wäre als Fall 3 aufgefallen |
| Lauf 1 | `NOTICE: Fall 1: bc1.sessions nicht vorhanden — Anlage.` + `NOTICE: Sollsignatur bestaetigt.` | **genau so** |
| Lauf 2 | `NOTICE: Fall 2: Bestand ist identisch zur Sollsignatur — No-op.` | **genau so** — Idempotenz im Ziel bewiesen |
| Nachprüfung A | vier Tabellen in `bc1`, `sessions` gehört `bc1_role`, ACL ohne `bc_leser` | **4 Tabellen; `sessions` = `bc1_role`, `relacl = {bc1_role=arwdDxtm/bc1_role}`** |
| Nachprüfung B | `bc1_role` SELECT/INSERT `t`; `bc_leser`, `bc2`–`bc4` `f` | **wie erwartet.** Zusätzlich `postgres` `t/t` — die Supabase-Administration ist Mitglied von `bc1_role` (Umgebungsrolle, Abschnitt 5); kein Befund, aber sichtbar gemacht |
| Nachprüfung C | `sessions_company_fk` validiert | **alle vier Constraints `convalidated = t`** (FK, `sessions_mandant_konsistent`, PK, `version_positiv`) |

**Für BC0 heißt das:** nichts zu tun — `bc1.sessions` ist eine interne Tabelle, kein
Fremdschema liest sie, ein `GRANT` ist weder nötig noch erwünscht. Die Löschkaskade von
`companies` läuft mit den Rechten von `bc1_role` (im Container unter einem rechtelosen
Löschkonto gemessen, Test `test_kaskade_raeumt_die_sitzung_auch_unter_rechtelosem_loeschkonto`).

## 11. Dritter Lauf: `prozessprofil_d3.sql` in der Supabase — 22.09.2026 (#255)

Anlass: BC2 liest über `contracts/bc1-to-bc2/lesen.sql` `p.step_frequency_per_year`; ohne die
Spalte parst die Vertragsabfrage nicht, BC2 liest **über den Vertragsweg** nichts (#255,
gemessen von BC2 am 21.09.2026; BC2s Dienstcode liest D3 übergangsweise aus dem JSON).
Ausgeführt am 22.09.2026 von Richard per `lauf.sh d3` als `bc1_role` (Session Pooler), alle
Zeilen gemessen (`einspielen-d3.log` im SDD-Ordner). Damit läuft BC2s Vertragsabfrage wieder —
vor dem Durchstich KW 40 (#206).

**Bestandsannahmen vorab (BC2-Messung #249):** 6 Zeilen, kein gültiger D3-Wert im JSON.
Gemessen: 6 Zeilen, **alle 6 `fertig`** (3 Teilprozesse × 2 Fassungen; `lesen.sql` nimmt die
jüngste je Teilprozess), 0 JSON-D3 — M1 lief ohne Abbruch. Hätte eine Zeile einen gültigen
JSON-D3-Wert getragen, wäre die Übernahme zu entscheiden gewesen (fertige Zeilen: neue
Fassung, kein UPDATE), nicht das Skript zu lockern.

| Schritt | Erwartung | Gemessen |
|---|---|---|
| Vorprüfung | neue `prozessprofil.sql` allein am Altbestand: `Fall 3` mit `- fehlt: spalte\|prozessprofil\|step_frequency_per_year\|…` und je einer `fehlt`/`zuviel`-Zeile für den CHECK — **Rollback, nichts geändert**. Mehr Zeilen = der Bestand weicht auch anderswo ab → STOPP | **genau 3 Zeilen** (`+ zuviel` alter CHECK, `- fehlt` neuer CHECK, `- fehlt` Spalte), `ERROR … Abbruch OHNE Aenderung`, Rollback |
| Lauf 1 (eine Transaktion) | `NOTICE: M1: Bestand ohne Spalte, kein JSON-D3-Wert — Spalte anlegen und CHECK erweitern.` · `NOTICE: M1: erledigt …` · `prozessprofil.sql`: `NOTICE: Fall 2` | **genau so** — `M1: Bestand ohne Spalte, kein JSON-D3-Wert …`, `M1: erledigt …`, `Fall 2` (beide DO-Blöcke) |
| Lauf 2 (Idempotenz) | `NOTICE: M2: Spalte und CHECK bereits auf Stand #255 — No-op.` · `Fall 2` | **genau so** — Idempotenz im Ziel bewiesen |
| Nichtbeeinflussung | `sessions.sql`: `NOTICE: Fall 2` | **genau so** (Signatur 40 Zeilen) |
| Nachprüfung A–C | Spalte numeric/nullable · CHECK validiert und nennt die Spalte · Zeilen gesamt / mit Spaltenwert (0) / mit gültigem JSON-D3 (0) / fertig | **`numeric`/`YES` · `convalidated = t`, nennt die Spalte · 6 / 0 / 0 / 6** |
| Nachprüfung D | `lesen.sql` **wörtlich** per psycopg als `bc1_role` je Mandant ausgeführt: parst, liefert die fertigen Profile, D3 = NULL | **parst, 1 Mandant, 3 Profile (jüngste Fassung je TP), 20 Spalten, D3 in der Spaltenliste, Werte NULL** — KP-05.TP-1 (260 / 25 min), KP-06.TP-1 (40 / 60), KP-06.TP-2 (180 / 90) |

**Was D nicht beweist:** den Lesezugriff von `bc2_role` — den kann nur BC2 messen (die
Tabellen-ACL gilt für die neue Spalte mit, es gibt keine Spalten-ACLs; ein zusätzlicher GRANT
ist nicht nötig). Deshalb nach dem Lauf in #255 melden und BC2 um die Gegenprobe bitten.
**Für BC0 heißt das:** nichts zu tun.
