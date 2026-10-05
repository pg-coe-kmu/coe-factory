# Spec B5 — Anfragesteuerung (BC1 interviewt nur noch zu einer BC0-Anfrage)

> Stand 05.10.2026. Entschieden mit Richard in vier Schritten (Variante A, Pflicht, keine
> DB-Kopplung, Abschnitte 1–3 abgenommen). Überarbeitet nach Zweitmeinung (agy, 05.10.):
> Status-Recheck vor dem Freeze gestrichen, C4 (b) ausgelagert, Anfrage-Guard ergänzt. Quelle der Anforderung: Abschlussplan B5,
> BC0-Papier „Vom Anliegen zum Paket" (21.09.), #206 (Durchstich), #226 (Felderliste).
> Nächster Schritt nach Abnahme dieser Spec: Implementierungsplan.

## Big Picture

**Ziel.** BC1 führt Interviews nur noch zu einer Anfrage von BC0 und nur über die Teilprozesse
dieser Anfrage. Jedes fertige Profil trägt die Anfragenummer. Damit kann BC0 eine Anfrage
eindeutig ans Gate bringen, und der Durchstich (#206) hat seinen Anfang.

**Warum die Anfragenummer im Profil wirklich gebraucht wird.** BC0s Funktion
`anfrage_am_gate_nachziehen()` setzt eine Anfrage auf `am_gate`, sobald zu jedem ihrer
Teilprozesse das neueste BC1-Profil `fertig` ist — verknüpft nur über den Teilprozess. Ein
fertiges Profil aus einer *früheren* Anfrage zum selben Teilprozess schiebt eine neue Anfrage
sofort ans Gate. Mit `anfrage_id` im Profil kann BC0 das korrigieren — **die Korrektur selbst
liegt bei BC0**; bis dahin besteht die Kollision weiter. Für den Durchstich heißt das: einen
Teilprozess wählen, zu dem es noch kein fertiges BC1-Profil gibt.

**Was sich ändert (Klartext).**

1. **Start.** Neben der Firma wird die Anfrage eingestellt (`BC1_ANFRAGE_ID`, Pflicht). Der
   Chatbot startet nicht und sagt klar warum, wenn: keine Anfrage angegeben · Anfrage bei dieser
   Firma unbekannt · Anfrage nicht im Stadium `zugeordnet`/`im_interview` · ein Teilprozess der
   Anfrage bei BC0 unbewertet oder stillgelegt (BC0 übergibt eine Anfrage nur vollständig; ein unbewerteter
   Teilprozess würde sie dauerhaft blockieren — das soll man beim Start erfahren).
2. **Gespräch.** Bei „Um welchen Arbeitsschritt geht es?" stehen nur noch die Teilprozesse der
   Anfrage zur Auswahl. Mehrere Teilprozesse = mehrere Gespräche unter derselben Anfrage.
3. **Abschluss.** Das fertige Profil trägt die Anfragenummer. Das Stadium wird **nicht** erneut
   geprüft: Ein fertiges Profil zu einer inzwischen abgelehnten Anfrage schadet nicht (BC0 zieht
   nur `zugeordnet`/`im_interview` ans Gate, freigeben muss ein Mensch); eine Sperre an dieser
   Stelle hinterließe dagegen eine hängende Sitzung und einen verwaisten Entwurf, der den
   Teilprozess blockiert (agy C2).
4. **Schutz.** Eine Sitzung läuft nur in einer Instanz mit derselben Anfrage weiter — eigener
   Anfrage-Schutz wie beim Mandanten, ohne Ausnahme, auch beim Wiederholen eines Abschlusses.
5. **Datenbank.** Eine neue, leere Spalte `anfrage_id` in `bc1.prozessprofil`. Alte Profile
   bleiben leer (eingefroren, keine Nachzuordnung). Die Datenbank prüft nur die Form
   (`A-2026-03`); dass es die Anfrage gibt, prüft der Chatbot.

**Bewusst nicht in B5 (mit Ziel im Abschlussplan):**

| Punkt | Warum nicht jetzt | Ziel / Auslöser |
|---|---|---|
| Anfrage pro Sitzung über den Chat-Link (Variante B) | Mehr Umbau (Paketidentität je Sitzung), Durchstich braucht es nicht | B3 Teil 2 (Dauerbetrieb auf Server) |
| Status bei BC0 setzen (`im_interview`) | Eigener Baustein mit Anmeldung an BC0 | B4, direkt nach B5 |
| `gate_nachziehen` bei BC0 auslösen (Anfrage → `am_gate`) | Braucht die Anmeldung an BC0; kein Trigger bei BC0 | B4 (sonst im Durchstich von Hand) |
| C4 (b): RI-Trigger der referenzierten Seite in `prozessprofil.sql` signieren | Fachfremd; jede Live-Abweichung bräche die B5-Umstellung ab | eigenes kleines Paket direkt nach B5 |
| Hängende Sitzung + verwaister Entwurf, wenn BC0 während des Interviews die Bewertung verwirft (bestehender `erhebung_id`-Recheck → dauerhaft 503) | Vorbestehend, nicht durch B5 | Kleinpunkt im Abschlussplan, Ziel B3 Teil 1 |
| `chat_text` für 409-Antworten | Gilt für alle 409 | P3 (#269) |
| Anliegen-Text als Gesprächskontext | Sicht fehlt bei BC0 (#226) | nach BC0s Sicht; Felderliste geht mit B5 an #226 |
| Fragesteller vorbelegen (`v_anfrage_steller`) | Liefert Klarnamen, für Durchstich unnötig | nach C1a |
| Datenbank-Kopplung an `ref_anfragen` (Fremdschlüssel) | Braucht neues Recht von BC0 und kollidiert mit eingefrorenen Profilen | Frage an Simeon (Sammelliste Runde 2) |
| Zwei Anfragen zum selben Teilprozess gleichzeitig | Heute ein offener Entwurf je Teilprozess; Durchstich betrifft es nicht | wenn der Fall real auftritt |

**Wer ist betroffen.** BC0 liest `bc1.prozessprofil` schon (`bc_leser`) und sieht die Spalte
ohne neues Recht. BC2 liest über `contracts/bc1-to-bc2/lesen.sql` mit expliziter Spaltenliste —
kein Vertragsbruch, keine Vertragsänderung. n8n bleibt unverändert.

**BC0 v3.8–v3.11 (statisch geprüft am 05.10., Live-Messung im Plan):** nichts davon berührt
Schema `bc1`, `companies`, die Teilprozess-Sichten oder die Anfrage-Objekte. Entzüge treffen nur
`person_rollen` (v3.9/v3.10) und drei `ki_*`-Tabellen (v3.11). Eine Datei „v3.8" gibt es nicht
(der Inhalt steckt app-seitig in PR #259). Zwei Nebenbefunde gehen an BC0 (Sammelliste):
`ref_anfragen.originaltext` ist laut BC0s eigener Messung für `bc_leser` lesbar, entgegen ihrem
Schema-Kommentar; vier `ki_*`-Tabellen aus v3.11 sind über die Default-Rechte für BC1 lesbar.

## Technischer Teil

### 1. Start (`bc1_service/start.py`, `main.py`)

- `lies_anfrage_id(env)`: `BC1_ANFRAGE_ID` Pflicht, Format `^A-[0-9]{4}-[0-9]{2}$`
  (BC0-CHECK `ref_anfragen.anfrage_id`, v1.4).
- `lade_kontext(conn, company_id, anfrage_id)` — Reihenfolge der Prüfungen (die Sicht prüft
  `aktiv` nur bei Kernprozess-Bezug, nicht bei direkter TP-Zuordnung — Schritt 4 fängt das ab):
  1. Mandant existiert (wie heute).
  2. Status aus `v_anfrage_prozessbezug` (`company_id`, `anfrage_id`) — keine Zeile → Abbruch
     „Anfrage unbekannt"; Status ∉ {`zugeordnet`, `im_interview`} → Abbruch „nicht im
     Interview-Stadium" (dieselbe Menge, auf die `anfrage_am_gate_nachziehen()` reagiert).
  3. Teilprozesse aus `v_anfrage_teilprozesse` (löst `sub_process_id NULL` in alle aktiven TPs
     des Kernprozesses auf).
  4. Schnitt mit dem heutigen Lesepfad (`bewertete_teilprozesse`: aktiv, aktiver Elternprozess,
     Bewertung vorhanden). Fehlt ein Anfrage-TP im Schnitt → Abbruch mit Liste der fehlenden
     (unbewertet oder stillgelegt). Die TP-Namen kommen aus diesem Lesepfad
     (`v_anfrage_teilprozesse` hat keinen `sub_process_name`).
     Anfrage ohne TP → Abbruch (Wortlaut wie heute `MELDUNG_KEINE_TEILPROZESSE` sinngemäß).
- Neue Meldungskonstanten mit festem Wortlaut (wie `MELDUNG_KEINE_BEWERTUNG`), von Tests gepinnt.
- Lesezugriffe nur über Sichten, alle mit `company_id`-Filter (wie `bc0_lesepfade.py`).

### 2. Paket und Sitzung (`discovery_paket.py`, `bc1_core`, `api.py`)

- `Bc0Kontext` bekommt `anfrage_id`; `_ctx_fingerprint` nimmt sie auf (Paketidentität). **Der
  Schutz gegen eine fremde Anfrage hängt aber NICHT am Fingerabdruck** — `darf_recovery_replay`
  lässt einen abweichenden ctx-Hash ausdrücklich passieren (`core.py:41-65`, agy C1).
- `focus_step` bleibt `AUSWAHL`, Menge = TPs der Anfrage.
- `SessionState.anfrage_id` (`types.py`), (de)serialisiert in `serialize.py`, gesetzt in
  `process_turn(..., anfrage_id=...)` beim ersten Turn. **Keine** Spalte in `bc1.sessions`,
  `sessions.sql` bleibt unverändert.
- `pruefe_anfrage(state, anfrage_id)` analog `pruefe_mandant`: läuft in `api.py` nach jedem
  `load` direkt nach dem Mandanten-Guard, **vor** `darf_recovery_replay`, ohne Ausnahme;
  Mismatch oder Alt-Sitzung ohne `anfrage_id` → 409 `anfrage_konflikt`. Test
  `test_recovery_replay_wechselt_nie_die_anfrage`.

### 3. Writer (`profil_writer.py`)

- `_einfuegen` schreibt `state.anfrage_id` in die neue Spalte (Quelle = Sitzung, nicht die
  Instanz; der Guard oben garantiert Gleichheit); `_umbinden` unverändert (TP-Wechsel innerhalb
  derselben Anfrage).
- **Kein** Status-Recheck vor `_einfrieren` (siehe Big Picture, Punkt 3).

### 4. Datenbank

- `bc1.prozessprofil`: `anfrage_id text NULL` +
  `CONSTRAINT prozessprofil_anfrage_format CHECK (anfrage_id IS NULL OR anfrage_id ~ '^A-[0-9]{4}-[0-9]{2}$')`.
  Kein FK, kein neuer Index, **keine Änderung an Trigger-Funktionen** (fertige Zeilen sind
  vollständig gesperrt; Entwürfe schreibt nur der Writer).
- Umstellungseinheit `bc1_service/db/prozessprofil_b5.sql` nach Muster `prozessprofil_d3.sql`:
  M0 Tabelle fehlt → nichts · M1 Spalte und CHECK fehlen → `ADD COLUMN` + `ADD CONSTRAINT` +
  Nachprüfung (exakter `pg_get_constraintdef`) · M2 umgestellt → nichts · M3 sonst → Abbruch.
- Der exakte `pg_get_constraintdef`-Text für M1/M2 wird auf PG 17 gemessen, nicht geschrieben
  (wie `check_neu` in `prozessprofil_d3.sql`).
- `prozessprofil.sql`: `CREATE TABLE` mit Spalte und CHECK; Abschnitt 0 (Rechte-Vorprüfung) um
  `v_anfrage_prozessbezug` und `v_anfrage_teilprozesse` erweitern. Signatur neu erzeugen
  (`tests/db/signatur_erzeugen.py`, PG 17). C4 (b) **nicht** hier (eigenes Paket danach).
- Einspielreihenfolge: `psql -1 -f prozessprofil_d3.sql -f prozessprofil_b5.sql -f prozessprofil.sql && psql -1 -f sessions.sql`
  (`EINSPIELEN.md`, `tests/db_fixture.py`).
- Rechte: unverändert (tabellenweite Grants; `bc_leser` liest die Spalte mit).

### 5. Gerüst (`tests/db/bc0_geruest.sql`)

- `ref_anfragen` als Ausschnitt (Spalten, die die Sichten brauchen; Status-CHECK v2.7),
  `anfrage_prozesse` (v2.7), Stummel `gate_paket_inhalt` und `v_gate_freigabe_aktuell` soweit
  `v_anfrage_teilprozesse` sie braucht.
- `v_anfrage_prozessbezug` (v2.3) und `v_anfrage_teilprozesse` (v2.7) **wortgleich**; GRANTs an
  `bc_leser` wie live.
- Vorher Live-Struktur messen (`struktur_bc0.sql` erweitern; Lauf durch Richard). Abweichung
  live ↔ Repo → anhalten und melden, nicht anpassen.

### 6. Tests (TDD, bestehende Dateien erweitern)

- `test_start.py`: vier Abbrüche mit Wortlaut; Auswahl = Anfrage ∩ bewertet ∩ aktiv;
  Kernprozess ohne TP-Angabe aufgelöst.
- `test_discovery_paket.py`: Fingerabdruck reagiert auf `anfrage_id`.
- `test_api.py` / `test_api_profil.py`: Instanz mit anderer Anfrage → 409 `anfrage_konflikt`,
  auch beim terminalen Recovery-Replay; Alt-Sitzung ohne `anfrage_id` → 409.
- `test_serialize`/Store: `anfrage_id` überlebt den Rundlauf.
- `test_profil_writer.py`: `anfrage_id` in der Spalte.
- neu `test_ddl_b5_spalte.py` (Spiegel von `test_ddl_d3_spalte.py`): M0–M3, Format-CHECK, alte
  Zeilen `NULL`, danach `prozessprofil.sql` Fall 2.
- `test_ddl_einspielen.py`: Rechte-Vorprüfung meldet fehlende Anfrage-Sichten.
- `test_ddl_sessions.py`: `sessions.sql` bleibt Fall 2.
- `test_db_fixture.py`: Anfrage-Sichten im Gerüst für `bc1_role` lesbar.
- Testdaten (`db_fixture`): Anfragen für interviewbar / falscher Status / TP unbewertet /
  Kernprozess ohne TP-Angabe.
- Abschluss: volle Suite mit Container (PG 17).

### 7. Prüfung, Live, Mitteilungen

- Codex-Zweitmeinung (Pflicht, Datenmodell); Befunde nach Schwere adjudiziert, Richard vorgelegt.
- Lokal auf `bc1-b5-anfragesteuerung`; Push/PR nur nach Richards OK mit Vorab-Prüfung, was
  öffentlich wird.
- Live nach Merge: `lauf.sh b5` (Vorprüfung, Umstellung, Nachprüfung: Spalte da, alte Zeilen
  `NULL`, `lesen.sql` wörtlich unverändert) — ausgeführt von Richard.
- Doku: `EINSPIELEN.md`, `n8n/SMOKE.md`, README (`BC1_ANFRAGE_ID`).
- Entwürfe (Posten nur nach OK): #226 Felderliste + Klärpunkte · #206 Stand und neuer Termin ·
  Sammelliste Runde 2 (+ Gate-Funktion über `anfrage_id`, + Kopplung gewünscht?, + zwei
  Rechte-Befunde).
- Abschlussplan: B5 erledigt; Rückstellungen aus der Tabelle oben mit Ziel; C4 (b) als eigenes
  Paket direkt nach B5;
  offene Punkte aus Simeons Brief 23.09. (R-07 entfällt, P-07/#R1 geschlossen).
