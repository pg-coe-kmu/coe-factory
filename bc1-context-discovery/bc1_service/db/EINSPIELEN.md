# `prozessprofil.sql` einspielen — Anleitung und Rechte-Ist-Stand

> Betriebsdoku für den Menschen, der die BC1-Tabellen in eine Datenbank bringt.
> Stand 08.09.2026. Alle Zahlen und Rollennamen hier sind **gemessen**, nicht angenommen.
> Seit dem 08.09. ist der Inhalt **in der Ziel-Supabase ausgeführt** — siehe Abschnitt 9.

## Das Wichtigste in fünf Sätzen

Die Datei legt drei Tabellen im Schema `bc1` an und prüft **vorher**, ob der Bestand zu
dem passt, was sie erwartet. Sie läuft in **einer** Transaktion: entweder alles oder
nichts. Trifft sie auf eine leere Datenbank, legt sie an (**Fall 1**); trifft sie den
exakt erwarteten Bestand, tut sie nichts (**Fall 2**); weicht irgendetwas ab, **bricht sie
ab und ändert nichts** (**Fall 3**). Die Prüfung vergleicht den Ist-Zustand des Katalogs
Zeile für Zeile mit einer im Skript hinterlegten **Sollsignatur** (176 Zeilen). Wer die
DDL ändert, muss die Signatur neu erzeugen — sonst blockiert sich das Skript selbst.

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

## 2. Einspielen

Aus `bc1-context-discovery/`, **als `bc1_role`**:

```bash
psql "$BC1_DB_DSN" -v ON_ERROR_STOP=1 -1 -f bc1_service/db/prozessprofil.sql
```

`-1` ist nicht optional: Die Dreifallregel verlässt sich darauf, dass ein Abbruch alles
zurückrollt.

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
# 1. Den Signaturblock in Abschnitt 0b durch die eine Platzhalterzeile ersetzen:
#    ('platzhalter|wird|in|step7|ersetzt');
# 2. Aus bc1-context-discovery/, gegen den Test-Container:
BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" \
    .venv/bin/python ../../signatur-erzeugen.py
# 3. git diff lesen — jede geänderte Zeile muss erklärbar sein — dann committen.
```

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
> das Einspielen in der Ziel-Supabase nach dieser Änderung durchläuft, ist damit
> hergeleitet und an den gemessenen Rollen geprüft, **aber nicht dort ausgeführt**. Der
> erste echte Einspiel-Lauf ist deshalb mit wachem Auge zu fahren — Fall 3 dort bedeutet
> zuerst: die Abfrage oben erneut ausführen und mit dieser Tabelle vergleichen.

## 6. Als welche Rolle verbindet der Dienst?

`main.py` öffnet den Profil-Pool **ohne** `SET ROLE`. Produktiv entscheidet also allein der
Benutzer-Anteil von `BC1_DB_DSN`, wer schreibt.

> **`BC1_DB_DSN` muss als `bc1_role` verbinden.** Sonst gehören die Tabellen einer anderen
> Rolle, und weder die Tabellenrechte noch die getestete Mandantentrennung greifen so, wie
> die Tests sie nachweisen (die Tests setzen die Rolle explizit).

## 7. Leserechte: wer darf was

| Tabelle | `bc1_role` | `bc_leser` (und damit BC2–BC4) |
|---|---|---|
| `bc1.prozessprofil` | alles | `SELECT` |
| `bc1.profil_rollen` | alles | `SELECT` |
| `bc1.profil_write_status` | alles | **nichts** (ausdrückliches `REVOKE`) |

Unsere DDL vergibt diese Rechte selbst — BC0 muss nichts nachziehen. Offen ist nur BC0s
ausdrückliche Bestätigung, dass `bc_leser` auch für `profil_rollen` gilt (Rückfrage vom
02.09.); ohne Widerspruch stellen wir beide gleich.

## 8. Deploy-Gate: was vor dem ersten Produktivlauf erledigt sein muss

| Punkt | Stand 03.09.2026 |
|---|---|
| **K-C** Wertebereiche der Zahlenspalten | **erledigt.** Entschieden: 0 zulässig, Kommastellen und ganze Zahlen erlaubt — das ist der heutige CHECK, keine Änderung nötig |
| **K-G** Geltungsbereich der Signatur | **erledigt**, siehe Abschnitt 5 |
| **K-H** PostgreSQL-Hauptversion | **erledigt**, siehe Abschnitt 4 |
| **K-I** Standardrechte für Schema `bc1` | **erledigt 08.09.2026.** BC0 hat das `ALTER DEFAULT PRIVILEGES` für Schema `bc1` entfernt (`REVOKE ALL ON TABLES FROM bc_leser`) und das gemessen; **wir haben gegengemessen**: `pg_default_acl` enthält keine Zeile mehr für `bc1`. Die Defaults für `bc2`/`bc3`/`bc4` bestehen weiter — BC0 hat sie bewusst stehen lassen und den anderen Kontexten gemeldet. |

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
