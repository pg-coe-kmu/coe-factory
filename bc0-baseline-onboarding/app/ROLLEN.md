# Datenbank-Rollen und Rechte

*Eingerichtet 08.08.2026 · BC0 · Supabase PostgreSQL 17.6*

> **Status:** Rollen und Rechte sind in der Produktivdatenbank **eingerichtet und geprüft**.
> Diese Datei ist noch **nicht ins Repo gepusht** — das ist für **Dienstag, 11.08.2026** vorgesehen, zusammen mit den übrigen offenen Änderungen. Bis dahin liegt sie nur lokal.

---

## Modell

Jeder Bounded Context bekommt eine eigene Login-Rolle und ein eigenes Schema. Das Leserecht hängt an einer gemeinsamen Gruppenrolle.

```
                        ┌─────────────────────────┐
                        │  bc_leser               │
                        │  Gruppe, kein Login     │
                        │  trägt ALLE Leserechte  │
                        └────────────┬────────────┘
                                     │ Mitglied
            ┌────────────┬───────────┼───────────┬────────────┐
            │            │           │           │            │
       ┌────┴────┐  ┌────┴────┐ ┌────┴────┐ ┌────┴────┐
       │bc1_role │  │bc2_role │ │bc3_role │ │bc4_role │
       └────┬────┘  └────┬────┘ └────┬────┘ └────┬────┘
            │            │           │           │
     schreibt│    schreibt│   schreibt│   schreibt│
            ▼            ▼           ▼           ▼
       ┌─────────┐  ┌─────────┐ ┌─────────┐ ┌─────────┐
       │ Schema  │  │ Schema  │ │ Schema  │ │ Schema  │
       │  bc1    │  │  bc2    │ │  bc3    │ │  bc4    │
       └─────────┘  └─────────┘ └─────────┘ └─────────┘

       ┌──────────────────────────────────────────────┐
       │  Schema  public   —   BC0-Baseline           │
       │  companies · ref_prozesse · ref_teilprozesse │
       │  bitkom_bewertungen · beleg_dokumente · …    │
       │                                              │
       │  NUR LESEN für alle BCs · Schreiben nur BC0  │
       └──────────────────────────────────────────────┘
```

**Alle Pfeile zeigen in eine Richtung.** Jeder BC schreibt ausschließlich nach unten in sein eigenes Schema. Nach `public` zeigt kein einziger Schreibpfeil.

### Rechte-Matrix

Zeile = wer, Spalte = worauf.

| | `public` (BC0) | `bc1` | `bc2` | `bc3` | `bc4` |
|---|---|---|---|---|---|
| **BC0** (`postgres`) | **R + W** | R + W | R + W | R + W | R + W |
| **`bc1_role`** | **R** | **R + W** | R | R | R |
| **`bc2_role`** | **R** | R | **R + W** | R | R |
| **`bc3_role`** | **R** | R | R | **R + W** | R |
| **`bc4_role`** | **R** | R | R | R | **R + W** |

`R` = SELECT · `W` = INSERT/UPDATE/DELETE/CREATE · leer gibt es nicht — **jeder liest alles**.

**Drei Aussagen stecken in dieser Matrix:**

**Die Spalte `public` hat genau ein W** — bei BC0. Ein Fehler in einem BC kann Baseline-Werte nicht überschreiben. Die Datenbank weist es ab, unabhängig davon, was der Code versucht.

**Die Diagonale ist das einzige W je Zeile.** Jeder BC ist Herr im eigenen Schema und Gast in allen anderen.

**Es gibt keine leeren Felder.** Lesen ist umfassend, entsprechend der Kaskade BC0 → BC1 → BC2 → BC3 → BC4: Jede Stufe braucht alles Vorherige. BC2 rechnet den ROI aus BC0-Baseline **und** BC1-Anreicherung — beides muss lesbar sein.

### Was die Matrix nicht zeigt

Die geplante **Anreicherung von BC0-Zeilen** — also dass BC1 unter derselben ID eine eigene Spalte in `public` beschreibt. Das wäre ein zusätzliches, sehr eng begrenztes `W` in der Spalte `public`, auf Spaltenebene statt auf Tabellenebene (`GRANT UPDATE (bc1_spalte_a, …)`). Es kommt erst, wenn ADR-003 entschieden ist — siehe „Noch offen".

### Was die Matrix verschweigt — Befund vom 23.08.2026

Die Matrix beschreibt das **gewollte** Modell. Die Datenbank folgt ihm nicht überall.

Neben den Rechten aus `bc_leser` bestehen **direkte** Berechtigungen an `bc1_role`: bei `ref_personen` und `prozess_personen` ausschließlich direkt, bei sieben weiteren Tabellen doppelt. Praktische Folge: **Ein `REVOKE ... FROM bc_leser` ändert nichts.** Belegt am 23.08.2026 an `ref_prozesse` — das Entzugsskript meldete Vollzug, `bc1_role` las die Tabelle weiter.

Wer Rechte prüft, prüft deshalb mit `\dp <tabelle>` an der Datenbank und nicht anhand dieser Matrix. Wer Rechte entzieht, entzieht sie der Gruppenrolle **und** jeder direkt berechtigten Rolle.

---

## Der Stolperstein: `GRANT CONNECT`

Supabase entzieht `PUBLIC` das Verbindungsrecht auf die Datenbank. Eine neu angelegte Rolle kann sich deshalb **nicht anmelden**, obwohl `rolcanlogin = t` gesetzt und ein SCRAM-Passwort hinterlegt ist.

Die Fehlermeldung ist irreführend:

```
FATAL: password authentication failed for user "bc1_role"
```

Das Passwort ist in Ordnung. Es fehlt:

```sql
GRANT CONNECT ON DATABASE postgres TO <rolle>;
```

Der Fehler tritt sowohl über den Pooler als auch über die IPv6-Direktverbindung auf. Am 08.08.2026 hat das rund eine Stunde Suche gekostet — inklusive vergeblicher Prüfung von Passwort, Pooler-Cache und `pg_hba` (letzteres ist bei Supabase nicht einsehbar: `permission denied for function pg_hba_file_rules`).

---

## Eine neue BC-Rolle anlegen

Als `postgres` ausführen. `<bcN>` und `<PASSWORT>` ersetzen; das Passwort **nur aus Buchstaben und Ziffern**, weil es in Verbindungs-URLs landet.

```sql
-- 1. Rolle
CREATE ROLE <bcN>_role WITH LOGIN PASSWORD '<PASSWORT>';

-- 2. Verbindungsrecht — ohne diese Zeile schlaegt die Anmeldung fehl
GRANT CONNECT ON DATABASE postgres TO <bcN>_role;

-- 3. In die Lesegruppe
GRANT bc_leser TO <bcN>_role;

-- 4. Eigenes Schema
CREATE SCHEMA <bcN>;
GRANT USAGE, CREATE ON SCHEMA <bcN> TO <bcN>_role;

-- 5. Das neue Schema fuer alle lesbar machen
GRANT USAGE ON SCHEMA <bcN> TO bc_leser;
GRANT SELECT ON ALL TABLES IN SCHEMA <bcN> TO bc_leser;

-- 6. Kuenftige Tabellen automatisch lesbar
--    Setzt voraus, dass der ausfuehrende Nutzer Mitglied der Rolle ist:
GRANT <bcN>_role TO CURRENT_USER;
ALTER DEFAULT PRIVILEGES FOR ROLE <bcN>_role IN SCHEMA <bcN>
  GRANT SELECT ON TABLES TO bc_leser;
```

Schritt 6 ist der Grund, warum neue Tabellen eines BC ohne Nacharbeit für die anderen lesbar sind. Ohne ihn müsste nach jeder neuen Tabelle nachgefasst werden.

---

## Verbindungsstring

```
postgresql://<bcN>_role.<PROJEKTREF>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require
```

Der Benutzername trägt die Projektreferenz nach einem Punkt — das verlangt der Supabase-Pooler. Ohne diesen Zusatz kommt `Tenant or user not found`.

Passwort über die Umgebungsvariable `PGPASSWORD` übergeben, nicht in die URL schreiben. Sonst müssen Sonderzeichen prozentkodiert werden, und das Passwort steht in Prozesslisten und Logs.

---

## Gegenprobe

Nach jeder neuen Rolle ausführen. Ein Rechtemodell, das man nicht geprüft hat, ist eine Vermutung.

```
docker run --rm -e PGPASSWORD="$PW" postgres:17 psql "postgresql://<bcN>_role.<PROJEKTREF>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require" -t \
  -c "SELECT 'Verbunden als '||current_user;" \
  -c "SELECT 'Liest BC0: '||count(*) FROM bitkom_bewertungen;" \
  -c "UPDATE bitkom_bewertungen SET stufe=1 WHERE 1=0;" \
  -c "CREATE TABLE <bcN>.test (id int);" \
  -c "CREATE TABLE bc1.fremdzugriff (id int);" \
  -c "DROP TABLE <bcN>.test;"
```

**Erwartetes Ergebnis:**

| Prüfung | erwartet |
|---|---|
| Verbindung | `Verbunden als <bcN>_role` |
| BC0 lesen | `600` (Stand 08.08.2026) |
| BC0 schreiben | `ERROR: permission denied for table bitkom_bewertungen` |
| eigenes Schema | `CREATE TABLE` |
| fremdes Schema | `ERROR: permission denied for schema bc1` |

Zwei der fünf Zeilen **müssen** Fehler sein. Wenn nicht, ist das Modell nicht dicht.

---

## Passwörter

Nicht in dieser Datei, nicht im Repo, nicht per Chat, Screenshot oder Mail. Übergabe an die BC-Verantwortlichen direkt.

Ein Passwort neu setzen:

```sql
ALTER ROLE <bcN>_role WITH PASSWORD '<NEUES PASSWORT>';
```

Betrifft nur diese eine Rolle — die anderen BCs und BC0 bleiben davon unberührt. Das ist der praktische Vorteil getrennter Rollen gegenüber einem geteilten Zugang.

---

## Noch offen

**Spaltenbezogene Schreibrechte** für die Anreicherung von BC0-Zeilen (`GRANT UPDATE (bc1_spalte_a, …)`). Erst sinnvoll, wenn das Schreibmodell entschieden ist — siehe ADR-003 und #148. Bis dahin gilt: kein Schreibzugriff auf `public`.

**Row-Level-Security** für die Mandantentrennung (Schema v1.1, Abschnitt 7). Relevant, sobald mehr als ein echter Mandant in der Datenbank liegt.

**Direkte Grants bereinigen.** Sieben Tabellen sind doppelt vergeben, zwei ausschließlich direkt. Solange das so ist, ist die Gruppenrolle Dokumentation und keine Steuerung. Eigenes Skript, zusammen mit der Korrektur an `schema_v1.3_teil_a2`, dessen Kopfkommentar („Wer den Namen zu einer `person_id` braucht, fragt in BC0 nach") das Gegenteil des eingerichteten Zustands behauptet.

**Änderungsprotokoll.** `audit_log` ist angelegt, wird aber nicht befüllt. Mit vier schreibenden Rollen wird das dringlicher — siehe R9 in #148.
