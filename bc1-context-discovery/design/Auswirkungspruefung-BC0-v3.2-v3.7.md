# Auswirkungsprüfung BC0-Schema v3.2–v3.7 auf BC1 — A7 (Gerüst gegen Live)

> Gemessen am 22.09.2026: dasselbe Lese-Skript wie bei A5 (`struktur_bc0.sql`, erweitert um die
> zwei neuen Sichten, `owner_rolle_id`, den Eigner-Index und `ref_personen`) gegen die Supabase
> (als `bc1_role`) und gegen einen frischen PG-17-Container mit dem nachgezogenen
> `tests/db/bc0_geruest.sql`; beide Ausgaben per Mengen-Diff verglichen. Quellen im Repo: nur
> `schema_v3.4_aktiv_und_owner.sql` (v3.3 war Code; v3.5–v3.7 liegen auf BC0s Zweig `bc0-doku-und-entscheidungen`,
> PR #259, am 22.09. noch nicht auf `main`) — dazu die Live-Messung und Simeons Ticket-Kommentare
> (#216, #201/#214, #211). Anlass: Simeons Brief vom 18.09. (v3.4) und sein
> PR-#201-Kommentar vom 22.09. (v3.6, Entzug der Betriebstabellen).

## Big Picture

**Nichts bricht.** Die vier Sichten, die BC1 liest (`v_prozesse_lesen`, `v_bewertung_aktuell`,
neu `v_teilprozesse_lesen`, `v_systeme_lesen`), sind live **wortgleich** mit dem Gerüst,
inklusive Spaltenliste; der Eigner-Index `ux_prozess_eigner_eindeutig` ist live identisch. Jede
Spalte, jeder Constraint und jedes Recht, das BC1 braucht, ist live vorhanden.

**Was sich seit A5 (12.09.) geändert hat — alles gewollt, nichts davon bricht uns:**

1. **`aktiv` wird jetzt gefiltert (v3.4).** `v_prozesse_lesen` und `v_bewertung_aktuell` filtern
   selbst; für die zwei Tabellen, die BC1 direkt las, gibt es `v_teilprozesse_lesen` und
   `v_systeme_lesen`. **BC1 liest seit heute nur noch über die Sichten** (`bc0_lesepfade.py`) —
   der Punkt „C2: `aktiv` im Lesepfad filtern" aus A5 ist damit erledigt. Live ist noch nichts
   stillgelegt (Simeon 18.09.); der Filter ist da und wartet.
2. **Genau ein Eigner je Prozess, `owner_rolle_id` in `v_prozesse_lesen` (v3.4).** Spalte steht
   am Ende der Sicht, unsere Abfragen sind unverändert gültig. Gelesen wird sie erst in **C1a**
   (Owner als Auswahl mit Vorbelegung). Dafür ist `ref_personen` jetzt im Gerüst (die Sicht
   joint es) — das Gerüst hat damit auch den FK aus `prozess_personen`, der bisher bewusst
   fehlte; es ist an dieser Stelle nicht mehr laxer als BC0.
3. **`bc1_role` hat kein direktes SELECT auf `prozess_personen` und `ref_personen` mehr —
   Schema v3.5 (`schema_v3.5_revoke_personen_bc1.sql`, eingespielt 21.09., #216).** A5 hatte das
   Recht auf `prozess_personen` live gemessen; heute sind für `bc1_role` weder Spalten noch ein
   Recht sichtbar. Das ist unser eigener Verzicht aus dem Brief vom 15.09. („Ihr könnt es
   entziehen") — BC0 hat ihn umgesetzt und in #216 selbst notiert, dass die Meldung an uns noch
   aussteht; wir haben es per Messung gefunden. Folgenlos: den Eigner liefert `v_prozesse_lesen`,
   und die Sicht läuft mit den Rechten ihres Eigentümers (BC0s Gegenprobe in #216: alle fünf
   Wege `t`). Klarnamen (`ref_personen`) waren für uns nie lesbar — richtig so.

**v3.6 (Entzug der fünf Betriebstabellen, 22.09., #201/#214) und v3.7 (App-Rolle `leser`, 22.09.,
#211):** berühren keines unserer Objekte; alle Rechte, die BC1 braucht, sind unverändert da
(Simeons Gegenprüfung bestätigt). v3.7 ist eine Rolle der Anwendung, nicht der Datenbank — unser
Anwendungskonto bleibt `benutzer` (Schreibrechte für B4).

## Technischer Teil — die Dreispalten-Liste

| Objekt / Aspekt | Befund | Einstufung |
|---|---|---|
| `v_prozesse_lesen`, `v_bewertung_aktuell`, `v_teilprozesse_lesen`, `v_systeme_lesen` | Definition **und** Spaltenliste live = Gerüst (Zeichen für Zeichen) | **geändert (v3.4) — nachgezogen**: Gerüst wortgleich, Lesepfad auf die Sichten |
| `v_prozesse_lesen.owner_rolle_id` (text, am Ende) | live vorhanden, wortgleich abgeleitet über `prozess_personen → ref_personen.rolle_id` | neu — Konsument kommt mit C1a |
| `ux_prozess_eigner_eindeutig` auf `prozess_personen` | live = Gerüst (`WHERE funktion = 'eigner'`) | neu — nachgezogen |
| `aktiv` auf `ref_prozesse`, `ref_teilprozesse`, `mandant_systeme` | live NOT NULL DEFAULT true; Gerüst jetzt ebenso (A5 hatte es als offen notiert) | nachgezogen; **BC1 filtert über die Sichten** (4 Tests) |
| Spalten/Constraints der neun Tabellen aus A5, die BC1 nennt | live vorhanden, gleich | gilt unverändert |
| `ref_personen` | live existiert, für `bc1_role` **unsichtbar** (kein Recht — Klarnamen); im Gerüst definitionsgleich (ohne `email`/`telefon` aus v1.5, die keine Sicht nennt) | neu im Gerüst, weil `v_prozesse_lesen` es joint |
| `prozess_personen` | live: Constraints und Index sichtbar, **Spalten/SELECT für `bc1_role` nicht mehr** (A5: direktes SELECT vorhanden) | **geändert (v3.5, #216) — gewollt** (unser Verzicht 15.09.), folgenlos |
| Rechte, die BC1 braucht (`bc_leser` SELECT auf alle vier Sichten + `companies`, `ref_teilprozesse`, `mandant_systeme`, `ref_erhebungen`, `mandant_rollen`; `REFERENCES` für FKs) | live vorhanden | gilt unverändert |
| Zusätzliche Rechte live: `bc1_role` **direkt** SELECT auf `v_teilprozesse_lesen`, `v_systeme_lesen`, `v_anfrage_steller` (zusätzlich zu `bc_leser`); `bc_leser` SELECT auf `ref_items`, `bitkom_bewertungen` | mehr als das Gerüst (das vergibt nur über `bc_leser`, wie `schema_v3.4` es schreibt) | fremd, harmlos |
| `v_anfrage_steller` | live mit GRANT (v3.4 Z. 173, „das Recht, das wir schuldig geblieben sind"); nicht im Gerüst | kommt mit **B5** ins Gerüst — nicht vorher (YAGNI) |
| Zusatzspalten live (`companies.branche/…`, `mandant_rollen.hinweis`, `ref_erhebungen.methode/…`), FK `mandant_systeme.katalog_id → ref_systeme_katalog` | wie A5; `katalog_id` selbst ist jetzt im Gerüst (Sicht nennt sie), der FK bewusst nicht | gilt unverändert, bewusst |
| Default-Privilegien `public` (Rolle `postgres`): `bc1_role=r`, `bc_leser=r` | unverändert — BC0 hat den Fall (v3.6) behoben, den Mechanismus nicht; Umzug der Betriebstabellen nach `bc0_betrieb` ist #262 (Soll 09.10.) | fremd, bekannt |
| Default-Privilegien Schema `bc1` | live keine Zeile; Gerüst simuliert sie weiter (Positivkontrolle, Entscheidung 12.09.) | unverändert |
| v3.6 Entzug (`app_benutzer`, `app_sitzungen`, `app_anmeldeversuche`, `app_benutzer_mandanten`, `bc_zustellungen`) | keine dieser Tabellen liest BC1; `v_anfrage_steller` liefert weiter (Sicht mit Eigentümerrechten, von BC0 gegengeprüft) | fremd, folgenlos |

**Bricht uns:** nichts.

**Zweitmeinung (Codex, 22.09.) — was daraus in den Bau ging:**

- **Stilllegung nach Draft-Anlage:** `erhebung_id()` lief nur beim Anlegen; ein danach
  stillgelegter Teilprozess wurde beim Abschluss trotzdem `fertig`. Der Freeze prüft jetzt erneut
  (503 statt `fertig`, Test in `test_profil_writer.py`). Rest ist K-K (C4).
- **Stillgelegter Kernprozess mit aktiven Kindern:** BC0s Sichten prüfen nur `tp.aktiv` — der
  Teilprozess bliebe interviewbar. BC1 verlangt zusätzlich den aktiven Elternprozess
  (`v_prozesse_lesen`); die Sichten bleiben wortgleich. **Frage an BC0:** kaskadiert die
  Stilllegung eines Kernprozesses auf seine Teilprozesse, oder ist das bewusst getrennt?
- **Snapshot-Modus (`BC1_SNAPSHOT_PFAD`):** die Kernprozess-Auswahl kommt dann aus der Datei und
  kennt `aktiv` nicht — dokumentierte Ausnahme, Ablösung mit B4 (Kleinpunkt).
- `prozessprofil.sql` §0 und `EINSPIELEN.md` §1 prüfen/nennen jetzt die Sichten statt der Tabellen.

## Werkzeug

`struktur_bc0.sql` (nur SELECT; SDD-Ordner, git-ignoriert; Fassung vom 22.09. mit den vier
Sichten, dem Index und `ref_personen`) — gegen Live per `lauf.sh sql struktur_bc0.sql`, gegen den
Container per `psql`; Vergleich mit `comm` auf den sortierten Ausgaben (`struktur_bc0.log`,
`struktur_bc0.container.log`). Für die nächste Schemaversion wiederholbar. Die Messung läuft
als `bc1_role`: was dort nicht erscheint, ist für uns nicht lesbar — das ist Teil des Befunds.
