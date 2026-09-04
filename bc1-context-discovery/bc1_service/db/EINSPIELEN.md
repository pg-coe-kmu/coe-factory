# `prozessprofil.sql` einspielen — Anleitung und Rechte-Ist-Stand

> Betriebsdoku für den Menschen, der die BC1-Tabellen in eine Datenbank bringt.
> Stand 03.09.2026. Alle Zahlen und Rollennamen hier sind **gemessen**, nicht angenommen.

## Das Wichtigste in fünf Sätzen

Die Datei legt drei Tabellen im Schema `bc1` an und prüft **vorher**, ob der Bestand zu
dem passt, was sie erwartet. Sie läuft in **einer** Transaktion: entweder alles oder
nichts. Trifft sie auf eine leere Datenbank, legt sie an (**Fall 1**); trifft sie den
exakt erwarteten Bestand, tut sie nichts (**Fall 2**); weicht irgendetwas ab, **bricht sie
ab und ändert nichts** (**Fall 3**). Die Prüfung vergleicht den Ist-Zustand des Katalogs
Zeile für Zeile mit einer im Skript hinterlegten **Sollsignatur** (172 Zeilen). Wer die
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
| `Fall 3 … Nachpruefung fehlgeschlagen` | Bestand weicht ab | **nichts wurde geändert.** Die Meldung listet jede Abweichung als `+ zuviel:` oder `- fehlt:` — Zeile für Zeile lesen und verstehen, **nie** die Prüfung abschalten |

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
SELECT r.rolname,
       pg_has_role(r.oid, 'bc1_role'::regrole, 'USAGE')         AS via_bc1_role,
       pg_has_role(r.oid, 'bc_leser'::regrole, 'USAGE')         AS via_bc_leser,
       pg_has_role(r.oid, 'pg_read_all_data'::regrole, 'USAGE') AS via_read_all
  FROM pg_roles r
 WHERE NOT r.rolsuper AND r.rolname NOT LIKE 'pg\_%'
   AND (pg_has_role(r.oid, 'bc1_role'::regrole, 'USAGE')
     OR pg_has_role(r.oid, 'bc_leser'::regrole, 'USAGE')
     OR pg_has_role(r.oid, 'pg_read_all_data'::regrole, 'USAGE'))
 ORDER BY 1;
```

**Ergebnis in der Ziel-Supabase am 03.09.2026** (19 Nicht-Superuser-Rollen insgesamt):

| Rolle | kommt herein über | in der Ausnahmeliste? |
|---|---|---|
| `bc1_role`, `bc2_role`, `bc3_role`, `bc4_role`, `bc_leser` | unsere eigenen Rollen | nein — sie gehören zur Signatur |
| `postgres` | `bc1_role`, `bc_leser`, `pg_read_all_data` | **ja** — Supabase-Administration, dort kein Superuser |
| `supabase_read_only_user` | `pg_read_all_data` | **ja** |
| `supabase_etl_admin` | `pg_read_all_data` | **ja** |

**Was das kostet und was es nicht kostet:** Diese drei Rollen können unsere Tabellen lesen,
ohne dass die Prüfung anschlägt — das ist der bewusst bezahlte Preis. **Jede andere fremde
Rolle bricht weiter mit Fall 3 ab**, insbesondere ein `GRANT bc1_role TO <irgendwer>`; zwei
Tests halten beide Seiten fest (`test_bekannte_umgebungsrolle_bricht_das_einspielen_nicht_ab`
und `test_mitgliedschaft_in_bc1_role_wird_erkannt`).

**Vor dem Einspielen in eine neue Umgebung:** die Abfrage oben dort ausführen. Erscheint
eine Rolle, die hier nicht steht, **erst klären, dann entscheiden** — nicht blind
nachtragen. Jeder Eintrag braucht eine Begründung in derselben Zeile der DDL.

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
| **K-I** Standardrechte für Schema `bc1` | **OFFEN — blockiert den ersten Produktivlauf.** BC0 setzt für `bc1_role` in Schema `bc1` ein `ALTER DEFAULT PRIVILEGES` mit `bc_leser=r`. Damit ist **jede** Tabelle, die der Dienst dort anlegt, automatisch für BC2–BC4 lesbar — auch die Session-Tabelle mit dem Interview-Rohtext. BC0 wurde am 03.09. gebeten, das zu entfernen. **Erst danach produktiv starten.** |

---

## Anhang: Warum die Prüfung so streng ist

Die drei Tabellen stehen in einer Datenbank, die sich mehrere Bounded Contexts teilen, und
sie enthalten personenbezogene Angaben aus Interviews. Ein still hinzugefügtes Leserecht,
eine geänderte Spalte oder ein deaktivierter Trigger fiele ohne diese Prüfung niemandem
auf. Deshalb umfasst die Signatur nicht nur Tabellen und Spalten, sondern auch: ACLs
einschließlich Spaltenrechten, Mitgliedschaften in `bc1_role`, die **effektiven** Rechte
jeder Rolle (also auch geerbte), RLS-Zustand und Policies, Rewrite-Regeln, Trigger
einschließlich der internen FK-Trigger, Funktionsrechte und die Tabellenkommentare.
