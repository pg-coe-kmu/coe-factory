# Auswirkungsprüfung BC0-Schema v3.8–v3.19c und Backend v3.20.1 auf BC1 — Gerüst und Sollsignatur (PR #354)

> Geprüft am 25.10.2026 gegen den PR-Stand (Commit `39bf834`, Zweig `bc0-v3.15-v3.20.1`): alle
> 14 SQL-Skripte und der `app.py`-Diff, statisch. Dazu Proben in einer Wegwerf-Datenbank (lokaler
> PostgreSQL-17-Container) mit einer Wegwerf-Kopie von BC1 — **nicht live, nichts im Repo
> geändert**. Anlass: BC0 bittet um Gegenlesen gegen `tests/db/bc0_geruest.sql` und die
> Sollsignatur. Ergänzt den Eintrag im Abschlussplan vom 25.10. („Lesepfade gegengelesen“): Die
> Lesepfade bleiben richtig, für Gerüst, Tests und künftige DDL gibt es Punkte.
> Pfade der BC0-Skripte: `bc0-baseline-onboarding/app/`.

## Big Picture

**Nichts bricht, und wir haben keinen falschen Grünstand gefunden.** BC1 liest weiter nur
Sichten plus `companies`, `ref_erhebungen` und `mandant_rollen`; `v_anfrage_teilprozesse`
liefert weiter `company_id`, `anfrage_id` und `sub_process_id`. Kein Skript des PR fasst ein
Objekt im Schema `bc1` an (keine Rechte, keine Trigger, keine Kommentare, keine neuen Rollen).
BC1s DDL bleibt beim erneuten Einspielen ein No-op („Fall 2“) — **gemessen** mit der Sicht aus
v3.19b, Wort für Wort übernommen.

**Neu und wichtig: BC0s Sicht hängt jetzt fest an unserer Tabelle.** Seit v3.16 liest
`v_anfrage_teilprozesse` direkt aus `bc1.prozessprofil` (auf `main` tat das noch keine Sicht;
BC0s Gate-Funktionen lesen sie auch, binden sich aber nicht daran). PostgreSQL merkt sich das.
Gemessen, was daraus folgt:

- BC1 kann die Tabelle nicht mehr löschen und bei fünf Spalten (`company_id`, `focus_step_id`,
  `profil_version`, `anfrage_id`, `status`) weder den Typ ändern noch die Spalte entfernen.
- Mit `CASCADE` geht es doch — und dann **löscht BC1 BC0s Sicht still mit** (nur eine Notiz,
  kein Fehler). Live hinge daran auch BC0s Übergabe-Sicht und das Gate-Nachziehen, das unser
  eigener Start aufruft.
- Die Sicht liest mit den Rechten ihres Eigentümers. Unser eigener Start (Anfrage →
  Teilprozesse) funktioniert deshalb nur, solange dieser Eigentümer unsere Tabelle lesen darf —
  heute über unser `GRANT SELECT … TO bc_leser`, das die Sollsignatur ohnehin festhält.
- In einer frischen Umgebung lässt sich v3.16 erst einspielen, wenn BC1s DDL (mit B5) steht.

Für die heutige DDL ist das folgenlos: Keine BC1-Datei löscht etwas oder ändert einen Typ. Es
ist eine **Regel für künftige Migrationen** und gehört ins Einspiel-Handbuch und zu BC0.

**Was das Gerüst nicht mehr abbildet (alles schon live, teils seit 23.09.):**

1. **Kernprozesse sind nicht mehr stilllegbar (v3.8).** Drei unserer Tests setzen einen
   Kernprozess per `UPDATE` auf stillgelegt — das weist BC0 ab. Die Tests prüfen unseren
   Zusatzschutz, keinen echten Fall. Die Frage aus der Prüfung vom 22.09. („Kaskadiert die
   Stilllegung?“) ist damit beantwortet: Es gibt sie nicht.
2. **`bc1_role` liest `companies` direkt (v3.9).** Das ist die Dauerzusage für unsere
   Löschkaskade. Zwei Tests nehmen das Gegenteil an.
3. **Namensregeln (v3.17, v3.19b):** Namen sind je Mandant eindeutig; ein unbenannter
   Teilprozess („Teilprozess N“) gehört nicht zur Anfrage. Unsere Testdaten halten das ein, das
   Gerüst erzwingt es nicht.

Gemessen: Mit diesen Regeln im Gerüst werden **genau diese fünf Tests rot**, alle anderen
bleiben grün (904 statt 909). Alle fünf schlagen laut fehl, keiner wird still grün — es gibt also
keinen falschen Grünstand, nur veraltete Annahmen.

**Was zu tun ist:** Klein und **zu erledigen**: den Kommentar „v2.7, wortgleich“ an der
Gerüst-Sicht berichtigen. **Empfohlen**: ein kleines Paket, das das Gerüst nachzieht (eine
Funktion, zwei Trigger, zwei Indizes, eine Filterzeile, ein Recht), die fünf Tests anpasst und
die neue Abhängigkeit im Einspiel-Handbuch festhält. Entscheidung der BC1-Projektleitung:
Behalten wir den Zusatzschutz „aktiver Elternprozess“? Empfehlung: ja, bis BC0 Frage 2 beantwortet
hat.

## Technischer Teil

### 1. Gerüst gegen den PR — je Objekt

| Objekt / Aspekt | Befund (Gerüst ↔ PR, Beleg) | Einstufung |
|---|---|---|
| `v_anfrage_teilprozesse` — welche Zeilen | Gerüst = v2.7 (`bc0_geruest.sql:298-324`, Kommentar „v2.7 Z. 129-154, wortgleich“). Nach dem PR (v3.16 → v3.17 → v3.19b) filtert die Herleitung beim Kernprozess-Bezug zusätzlich `NOT teilprozess_unbenannt(t.sub_process_name)` (`schema_v3.19b_anfragebindung_erhebung.sql:135`). BC1 berührt das: `start.lade_kontext` bildet daraus die SOLL-Liste und prüft „bewertet und aktiv“ (`start.py:94-103`). Ohne den Filter zeigte ein Test mit „Teilprozess N“ ein Ergebnis, das BC0 nie liefert. Heute kein Fall: Alle Testnamen sind benannt (`db_fixture.py:137-145`, `test_use_case_testprofile.py:98-103`); gemessen: Lesepfad mit Filter = ohne Filter | **sollte**: Filterzeile und `teilprozess_unbenannt` (`schema_v3.17_datenstand_und_namen.sql:54-57`) wortgleich übernehmen |
| `v_anfrage_teilprozesse` — Freigabe-Teil | v3.16/v3.17/v3.19b ändern `freigegeben` und hängen fünf Spalten hinten an (`freigabe_bc1_stand` … `datenstand_veraltet`). Dafür joint die Sicht jetzt `v_freigabe_datenstand` und zweimal `bc1.prozessprofil` (`…v3.19b…sql:159-179`). BC1 liest nur `sub_process_id` und filtert über `company_id`/`anfrage_id` (`bc0_lesepfade.py:155-162`) | **nicht nötig** im Gerüst (Stummel `v_gate_freigabe_aktuell` reicht). **Muss** aber: Der Kommentar an der Sicht und der Dateikopf (`bc0_geruest.sql:1-13`) sagen ehrlich, dass die Herleitung der Zeilen wortgleich v3.19b ist und der Freigabe-Teil ein Ausschnitt |
| Abhängigkeit `v_anfrage_teilprozesse` → `bc1.prozessprofil` im Gerüst | Wortgleich ginge nur, wenn die Sicht **nach** BC1s DDL angelegt wird (gemessen: vorher „relation bc1.prozessprofil does not exist“). Heute legt `frische_db` das Gerüst vor der DDL an (`db_fixture.py:65-72`) | **nicht nötig** für richtige Tests. Optional (Entscheidung): ein Test „BC1-DDL bleibt Fall 2 mit abhängiger BC0-Sicht“. Empfehlung: nicht jetzt (YAGNI), dafür die Regel unter 2. ins Handbuch |
| `anfrage_prozesse` — Trigger `anfrage_prozesse_benannt` | Neu in v3.19b (`…v3.19b…sql:34-53`): weist einen direkten Bezug auf einen unbenannten Teilprozess ab (`BEFORE INSERT OR UPDATE OF process_id, sub_process_id`). BC1 schreibt die Tabelle nicht, nur die Testdaten tun es (`db_fixture.py:279-288`, `test_use_case_testprofile.py:139-143, 286-290`); gemessen: alle Testdaten passieren den Trigger | **sollte** (wortgleich, billig; hält künftige Testdaten ehrlich) |
| `ref_teilprozesse`, `ref_prozesse` — eindeutige Namen | Neu in v3.17: `ux_teilprozess_name_je_mandant`, `ux_prozess_name_je_mandant` (`schema_v3.17…sql:215-224`). Laut Kopf gehören Schlüssel zum Anspruch. BC1 schreibt die Tabellen nicht; gemessen: alle Testdaten sind eindeutig | **sollte** |
| `ref_prozesse` — Trigger `kernprozess_bleibt_aktiv` | v3.8 (`schema_v3.8_kernprozess_unveraenderlich.sql:30-45`), live seit 23.09., jetzt erstmals im Repo. Weist `UPDATE … SET aktiv = false` ab, **nicht** `INSERT` mit `aktiv = false`. Drei Tests legen per `UPDATE` still (`test_bc0_lesepfade_aktiv.py:55-83`) — gemessen: mit dem Trigger rot. Kein falscher Grünstand: Sie prüfen BC1s Zusatzschutz (`bc0_lesepfade.py:33-35`), keinen Pfad, den BC0 liefert. Die Kommentare „ob BC0 kaskadiert, ist erfragt“ (`bc0_lesepfade.py:29-32`, `test_bc0_lesepfade_aktiv.py:73-75`) sind überholt | **sollte — Entscheidung**. Vorschlag: Trigger ins Gerüst; die drei Tests schalten ihn sichtbar ab (`ALTER TABLE … DISABLE TRIGGER`, Kommentar „Zustand, den BC0 per UPDATE verbietet“) oder legen den Kernprozess per `INSERT … aktiv = false` an. Zusatzschutz behalten, bis Frage 2 beantwortet ist |
| `companies` — direktes SELECT für `bc1_role` | v3.9 (a) (`schema_v3.9_companies_dauerrecht_bc1.sql:39`), live seit 23.09. Das Gerüst vergibt nur über `bc_leser` (`bc0_geruest.sql:347-348`). `test_db_fixture.py:56-79` behauptet „kein direktes SELECT an bc1_role“ (live falsch); `test_ddl_trigger.py:278-305` kappt den Weg nur bei `bc_leser` (`:294`). Gemessen: Beide werden mit dem nachgezogenen Gerüst laut rot (der zweite an seiner eigenen Wache `:295-297`) | **sollte**: `GRANT` ins Gerüst. Test 1 nimmt `companies` mit Begründung v3.9 aus; Test 2 entzieht bei `bc_leser` **und** `bc1_role` |
| `person_rollen` / `mandant_rollen` (v3.19a) | `person_rollen` steht nicht im Gerüst; BC1 hat kein Recht darauf (seit v3.10) und liest es nicht. `mandant_rollen` ist unverändert; v3.19a ändert nur den Fremdschlüssel von `person_rollen` (`schema_v3.19a_person_rollen_kaskade.sql:32-35`). Grenze, bekannt: Das Gerüst kann Blocker anderer BCs in der Löschkaskade nicht zeigen; unsere Kaskaden-Tests belegen nur BC1s Teil | **nicht nötig** |
| `ref_anfragen`, `ki_*` (v3.15) | v3.15 entzieht `SELECT` (`schema_v3.15_lesegruppe_anfragen_ki.sql:36-43`). Das Gerüst hat `ref_anfragen` nie freigegeben (`bc0_geruest.sql:345-351`), `ki_*` fehlen ganz — der Zielzustand war schon abgebildet | **nicht nötig** |
| `v_anfrage_prozessbezug` | unverändert (v2.3), Gerüst wortgleich (`bc0_geruest.sql:287-296`) | nichts |
| `v_freigabe_datenstand`, `gate_ereignisse.datenstand`/Trigger `gate_datenstand`, `v_uebergabe_kandidaten`, `ki_laufdaten`, `REFERENCES` für `bc3_role`, Prüfpunkt `rollen` aus | BC1 liest und schreibt keins davon | **nicht nötig** |
| Default-Privilegien | Kein `ALTER DEFAULT PRIVILEGES` im PR. Die Voreinstellung auf `public` bleibt (`schema_v3.15…sql:26-28`) | fremd, bekannt |

### 2. Sollsignatur und DDL

**Fall 3 durch den PR: nein.** Die Ist-Signatur (`prozessprofil.sql:318-515`) liest nur Objekte
in `bc1`: Regeln mit `ev_class` = unsere Tabellen (`:474-478`), interne Trigger auf unseren Tabellen
oder aus unseren Constraints (`:362-376`), Rechte und Mitgliedschaften, keine Abhängigkeiten
(`pg_depend`). Die Regel der BC0-Sicht hängt an der Sicht, nicht an unserer Tabelle. Im PR steht
kein `GRANT`/`REVOKE`/`COMMENT`/`ALTER` auf `bc1.*`, kein `CREATE ROLE`, keine neue
Mitgliedschaft (Suche nach `bc1.`, `bc1_role`, `GRANT`, `REVOKE`, `DEFAULT PRIVILEGES` über alle
14 Skripte). Abschnitt 0 (`prozessprofil.sql:42-60`) findet alle Rechte weiter: v3.15 prüft die
beiden Anfrage-Sichten selbst (`schema_v3.15…sql:69-73`); `REFERENCES` sind unverändert;
`companies` ist jetzt zusätzlich direkt lesbar.

**Gemessen** (Wegwerf-DB: Gerüst + BC1-DDL, dann v3.19b-Sicht wortgleich mit erweiterten Stummeln;
jede Operation als `bc1_role`, zurückgerollt):

| Operation | Ergebnis |
|---|---|
| `prozessprofil_d3.sql` → `_b5.sql` → `prozessprofil.sql` erneut, eine Transaktion | „Fall 2 … No-op“ |
| `sessions.sql` erneut | „Fall 2 … No-op“ |
| `pg_depend` der Sicht auf `bc1.prozessprofil` | Spalten `anfrage_id`, `company_id`, `focus_step_id`, `profil_version`, `status` |
| `DROP TABLE bc1.prozessprofil` | Fehler: „other objects depend on it“ |
| `DROP TABLE bc1.prozessprofil CASCADE` | läuft — löscht `v_anfrage_teilprozesse` mit (nur NOTICE) |
| `DROP SCHEMA bc1 CASCADE` | ebenso |
| `ALTER COLUMN anfrage_id / focus_step_id / profil_version TYPE …` | Fehler: „column used by a view or rule“ |
| `DROP COLUMN status` | Fehler |
| `DROP COLUMN profil`, `ADD COLUMN`, `RENAME COLUMN anfrage_id` | läuft (die Sicht folgt der Umbenennung; BC0s Backend liest aber per Name, `app.py:4282`, `:5381` — das bräche zur Laufzeit, wie schon vorher) |
| Sicht mit einem Eigentümer ohne Leserecht auf `bc1.prozessprofil` | BC1s Lesepfad scheitert: „permission denied for table prozessprofil“; mit Mitgliedschaft in `bc_leser` läuft er |
| v3.19b-Sicht anlegen, bevor BC1s DDL steht | Fehler: „relation bc1.prozessprofil does not exist“ |

**Auf `main` war das noch nicht so.** Keine Sicht auf `main` liest `bc1.*` (alle Skripte
durchsucht). v3.0 und v3.13 lesen `bc1.prozessprofil` nur in plpgsql-Funktionen
(`schema_v3.0_steller_und_am_gate.sql:131-169`, `schema_v3.13_gate_je_anfrage.sql:36-76`). Die
prüfen mit `to_regclass`, ob die Tabelle da ist, und hinterlassen keine Abhängigkeit. Neu ist
die Kopplung mit v3.16 (`schema_v3.16_freigabe_datenstand.sql:73-89`), live seit 25.10.

**Was das für BC1 heißt:**

- **Heute folgenlos.** `prozessprofil.sql` legt nur an (Fall 1) oder tut nichts (Fall 2); b5
  und d3 fügen nur Spalten hinzu und tauschen einen CHECK aus (`prozessprofil_b5.sql:54-55`,
  `prozessprofil_d3.sql:78-82`). Die Tests mit `DROP … CASCADE` (`test_ddl_einspielen.py:115`,
  `db_fixture.py:65`) laufen gegen das Gerüst, in dem es die Abhängigkeit nicht gibt.
- **Regel für künftige Migrationen (sollte, ins Handbuch `EINSPIELEN.md`):** Typ ändern oder
  Spalte entfernen bei den fünf Spalten sowie Tabelle neu aufbauen nur mit BC0 zusammen (BC0
  nimmt die Sicht kurz heraus und legt sie neu an). **Nie `CASCADE`** auf `bc1.prozessprofil`
  oder das Schema `bc1` — live risse das `v_anfrage_teilprozesse` mit, damit auch
  `v_anfrage_uebergabe_stand` (`schema_v2.7…sql:184-186`), und BC0s Gate-Funktion, die die Sicht
  joint (`schema_v3.13…sql:69`), bräche zur Laufzeit. Ziel: mit dem Nachzieh-Paket; Auslöser
  spätestens die nächste Migration an `prozessprofil` (z. B. DSGVO-Schicht, C4).
- **Unser `GRANT SELECT ON bc1.prozessprofil TO bc_leser` trägt jetzt auch unseren eigenen
  Start.** Die Sollsignatur hält es fest (`prozessprofil.sql:135`, angelegt `:893-895`). Der
  Eigentümer der Sicht ist live vermutlich `postgres`, Mitglied von `bc1_role` und `bc_leser` (am
  03.09. gemessen, `prozessprofil.sql:103-104`) — für die Signatur eine Umgebungsrolle. Fiele
  diese Mitgliedschaft weg, scheiterte unser Start am Lesen der Anfrage.

### 3. BC1-Lesepfade im Betrieb

- **`ref_anfragen` und `ki_*` liest BC1 nicht direkt — bestätigt.** `bc1_service` liest
  `companies` (`bc0_lesepfade.py:25`), `v_teilprozesse_lesen`, `v_prozesse_lesen`,
  `v_bewertung_aktuell`, `ref_erhebungen` (`:34-130`), `v_systeme_lesen` (`:67`),
  `mandant_rollen` (`:75`), `v_anfrage_prozessbezug` (`:150`) und `v_anfrage_teilprozesse`
  (`:160`); sonst nur `bc1.*`. `ref_anfragen` kommt nur in Kommentaren vor (`start.py:24`,
  `prozessprofil.sql:616-617`).
- **`v_anfrage_teilprozesse` liefert weiter `company_id`, `anfrage_id`, `sub_process_id` —
  bestätigt** (`…v3.19b…sql:138`; BC1 nennt die Spalten beim Namen). Gemessen: gleiche Zeilen
  für die Testanfragen vor und nach der v3.19b-Sicht. Inhaltlich neu nur: Beim
  Kernprozess-Bezug fehlen unbenannte Teilprozesse. Das passt zur Entscheidung vom 25.10.,
  die eigene Startprüfung entfallen zu lassen.
- **v3.8 berührt nichts, was BC1 schreibt.** BC1 schreibt nur `bc1.*`; unsere Fremdschlüssel auf
  `ref_prozesse` sind davon unberührt (der Trigger feuert nur bei `UPDATE OF aktiv`, BC1 ändert
  `ref_prozesse` nie). Was BC1 erwartet („stillgelegter Kernprozess wird nicht angeboten“), gilt
  weiter. Der Fall ist nur noch über `INSERT … aktiv = false` oder einen abgeschalteten
  Trigger erreichbar.

### 4. Nur BC0 — zur Kenntnis

- Das Backend liest `bc1.prozessprofil` und `bc1.profil_rollen` beim Spaltennamen
  (`app.py:4239-4290`, seit v3.20 auch `anfrage_id`). Unsere Spaltennamen bleiben also
  Vertrag, wie bisher.
- v3.8 und v3.9 (a) sind seit 23.09. live und erst jetzt im Repo (unser Eintrag vom 06.10.:
  „eine Datei v3.8 gibt es nicht“). Zwei verschiedene Skripte heißen „v3.9“; BC0s eigener
  Nachtrag v3.9–v3.12 (Abschnitt 1) schlägt für (a) die Nummer v3.8.1 vor, der PR behält v3.9.
- Einspielreihenfolge in einer frischen Umgebung: BC0 bis v3.15 → BC1-DDL (mit B5) → BC0 ab
  v3.16. Anders als die Gate-Funktionen sieht die Sicht nicht nach, ob die Tabelle da ist.

### 5. Fragen an BC0

1. **Ist die Bindung `v_anfrage_teilprozesse` → `bc1.prozessprofil` gewollt?** Der Nachtrag
   v3.16–v3.18 nennt sie nicht. Vorschlag zur Absprache: BC1 kündigt Typänderungen und das
   Entfernen der fünf Spalten vorher an; niemand nutzt `CASCADE` auf `bc1.*`; die
   Einspielreihenfolge kommt ins Handbuch.
2. **v3.8: Soll auch `INSERT … aktiv = false` abgewiesen werden?** Davon hängt ab, ob BC1s
   Zusatzschutz „aktiver Elternprozess“ noch einen erreichbaren Fall hat.
3. **Entspricht der Live-Stand den committeten Dateien** (v3.19a–c; für v3.16–v3.18 nennt der
   Nachtrag md5-Summen)? **Ist `postgres` Eigentümer der Sicht?**
4. **v3.9 (a): Bleibt die Nummer, oder wird es v3.8.1?** (Für unsere Fundstellen.)

### 6. Messung und Grenzen

**Selbst geprüft:** PR-Dateiliste und Inhalt aller 14 SQL-Skripte; Suche nach Sichten mit
`bc1.` auf `main` und im PR; BC1-Code und -Tests. Die Testsuite der Wegwerf-Kopie lief gegen
eine Wegwerf-Datenbank: unverändert 909 bestanden / 4 übersprungen; mit den PR-Regeln im Gerüst
(Funktion, Filterzeile, zwei Trigger, zwei Indizes, `GRANT companies`) 904 bestanden / 5 rot —
genau die oben genannten. Dazu die Proben aus Abschnitt 2.

**Nicht gemessen, angenommen:** Live entspricht den committeten Skripten (BC0 sagt
„eingespielt“; md5 nicht von uns verglichen). Der Eigentümer der Sicht ist `postgres` und
Mitglied von `bc1_role`/`bc_leser` (Stand 03.09.). Dass `CASCADE` live zusätzlich
`v_anfrage_uebergabe_stand` trifft, folgt aus `schema_v2.7…sql:186` und ist nicht gemessen
(nicht im Gerüst). Die Proben liefen auf PostgreSQL 17 im Container, nicht in der Supabase.
**Nächster Schritt dafür:** eine Live-Messung als `bc1_role` wie bei A7 — Sichtdefinition,
`pg_depend` auf `bc1.prozessprofil`, Rechte (nur die BC1-Projektleitung hat Zugang). Ziel: vor
oder direkt nach dem Merge von #354.

**Werkzeug:** Wegwerf-Kopie von `bc1-context-discovery` und ein Probe-Skript (Abhängigkeit,
DROP/ALTER, Eigentümerrechte, Reihenfolge), beides lokal und nicht im Repo; die Datenbank ist
wieder gelöscht. Wiederholbar: Gerüst in einer Kopie nachziehen, Suite gegen eine eigene
Datenbank laufen lassen.
