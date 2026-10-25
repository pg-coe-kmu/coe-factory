# BC0 — Datenbankdokumentation · Nachtrag v3.5 bis v3.8

**Stand:** 23.09.2026 · Autor: Simeon Ehmer
**Schließt an** `BC0_Datenbank_Dokumentation_Nachtrag_v3.0-v3.4.md` (Stand 21.09.2026) an.

**Abweichend vom bisherigen Verfahren:** v3.5 bis v3.7 sind auf der Produktivdatenbank
ausgerollt, aber **nicht auf `origin/main`** — sie liegen im offenen PR
[#259](https://github.com/pg-coe-kmu/coe-factory/pull/259). v3.8 ist weder gemerged noch
committet; die Datei liegt lokal in `10_DB_Dokumentation/` und wird **bewusst zurückgehalten**,
bis mehr zusammenkommt (Entscheidung Simeon, 23.09.). Dieser Nachtrag beschreibt den
**tatsächlichen Stand der Datenbank**, nicht den des Repos — Punkt 12 CLAUDE.md gilt auch hier:
Repo-Stand und Betriebsstand werden nicht verwechselt.

---

## 1. Die Stände im Überblick

| Stand | Datum | Repo-Stand | Inhalt | Schema? |
|:------|:-----|:-----------|:------------------------------------|:-----|
| **v3.5** | 22.09.2026 | PR #259, offen | `bc1_role` verliert direktes SELECT auf `ref_personen`, `prozess_personen` (#216) | ja |
| **v3.6** | 22.09.2026 | PR #259, offen | Betriebstabellen (`app_benutzer` u. a.) für alle Fremdkontexte entzogen (#214) | ja |
| **v3.7** | 22.09.2026 | PR #259, offen | Anwendungsrolle „leser" — sehen ohne Schreibrecht (#211) | ja |
| **v3.8** | 23.09.2026 | **nicht committet** | Kernprozess technisch nicht mehr stilllegbar | ja |

---

## 2. v3.5 — Personendaten nicht mehr für BC1

`schema_v3.5_revoke_personen_bc1.sql`. `bc1_role` durfte `ref_personen` und `prozess_personen`
lesen — dort stehen die Klarnamen, die nach ADR-004 R5 an genau einer Stelle liegen sollen.
Entzogen. `companies` bleibt unangetastet, BC1 braucht den Mandantennamen für die Anzeige.
Vier Gegenproben im Skript. Richard hatte das Recht am 15.09. selbst als nicht benötigt
zurückgegeben (S-085); der Entzug war damit gefahrlos.

## 3. v3.6 — Betriebstabellen nicht mehr für Fremdkontexte

`schema_v3.6_betriebstabellen_entzug.sql`. Gemessen am 22.09.: `bc_leser` und alle vier
Kontextrollen konnten `app_benutzer` (einschließlich Passwort-Abdrücke), `app_sitzungen`,
`app_anmeldeversuche`, `app_benutzer_mandanten` und `bc_zustellungen` lesen — keine dieser
Tabellen gehört zum Fachvertrag irgendeines Kontexts. `REVOKE SELECT … FROM bc_leser, bc1_role,
bc2_role, bc3_role, bc4_role`.

**Ursache bleibt bestehen:** `pg_default_acl` macht jede neue Tabelle in `public` automatisch für
`bc_leser` und `bc1_role` lesbar. Der dauerhafte Weg — eigenes Schema `bc0_betrieb` — ist
[#262](https://github.com/pg-coe-kmu/coe-factory/issues/262) (R-06), Soll 09.10.2026.

## 4. v3.7 — Rolle „leser"

`schema_v3.7_rolle_leser.sql`. Dritte Anwendungsrolle neben `benutzer`/`admin`: Bericht,
Prozesse, Historie und Belegliste sichtbar, Beleg öffnen und Volltextsuche sowie jedes Schreiben
gesperrt. 16 schreibende Endpunkte und 2 Beleg-Endpunkte umgestellt, 38 neue Tests (366 gesamt).
Ausgerollt 22.09., kein Leserzugang bisher vergeben.

**Nicht verwechseln mit `bc_leser`** — das ist die PostgreSQL-Gruppenrolle aus Abschnitt 3.
`leser` hier ist eine Rolle der Anwendung.

## 5. v3.8 — Kernprozess technisch nicht mehr stilllegbar

`schema_v3.8_kernprozess_unveraenderlich.sql`, eingespielt 23.09. per SSH/psql.

**Anlass:** Richards Frage (Brief 22.09., Abschnitt 1.4) zur Kaskade Stilllegung Kernprozess →
Teilprozesse. Entscheidung Simeon: Ein Kernprozess wird im Unternehmen fachlich nie stillgelegt,
nur Teilprozesse — die Kaskadenfrage stellt sich damit nicht mehr.

**Lücke vor dem Skript:** `ref_prozesse.aktiv` existiert seit v2.2 und war technisch weiterhin auf
`false` setzbar (DELETE war seit v2.6 über `trg_stilllegen_statt_loeschen` bereits abgewiesen,
UPDATE nicht). Die fachliche Aussage hätte sonst eine offene technische Möglichkeit gelassen.

**Umsetzung:** neuer Trigger `kernprozess_bleibt_aktiv` (BEFORE UPDATE OF aktiv ON ref_prozesse)
weist jedes `UPDATE … SET aktiv = false` ab. `ref_teilprozesse` unverändert — dort bleibt
Stilllegen der vorgesehene Weg.

**Drei Proben, alle bestanden:**

| Probe | Ergebnis |
|---|---|
| `SELECT count(*) FROM ref_prozesse WHERE NOT aktiv` | 0 |
| `UPDATE ref_prozesse SET aktiv=false WHERE process_id='KP-01'` | `ERROR: Kernprozess KP-01 kann nicht stillgelegt werden …` |
| `UPDATE ref_teilprozesse SET aktiv=false …` (Transaktion, ROLLBACK) | `UPDATE 2`, kein Fehler |

---

## 6. Was sich an Aussagen früherer Fassungen ändert

| frühere Aussage | gilt seit |
|:-------------------------------------|:------------------------|
| `bc1_role` liest `ref_personen`, `prozess_personen` direkt | entzogen (v3.5) |
| `bc_leser`/`bc1_role`–`bc4_role` lesen Betriebstabellen (`app_benutzer` u. a.) | entzogen (v3.6) — Ursache (Default-Privileg) bleibt |
| Zwei Anwendungsrollen (`benutzer`, `admin`) | drei — `leser` dazu (v3.7) |
| `ref_prozesse.aktiv` ist wie `ref_teilprozesse.aktiv` frei setzbar | seit v3.8 auf `ref_prozesse` gesperrt, `ref_teilprozesse` unverändert |

## 7. Was offen bleibt

| Punkt | Vorgang |
|:--------------------------------------------|:-------------|
| PR #259 (v3.5–v3.7) mergen — Repo hinkt dem Betriebsstand hinterher | Simeon, GitHub-Integration hat nur Leserechte |
| `schema_v3.8` committen | zurückgestellt, bis mehr zusammenkommt (Simeon, 23.09.) |
| Eigenes Schema `bc0_betrieb` für Betriebstabellen | #262 / R-06, Soll 09.10.2026 |
| Gate-0-Prüfpunkt „Rollen mit Zeitanteil" in der PWA umbauen | R-07, Entscheidung steht, Umsetzung offen |
| Weg für `companies` vor Etappe 4c | P-07 |

---

*Grundlage: `schema_v3.8_kernprozess_unveraenderlich.sql` (lokal) · PR #259 (Diff-Text) ·
Proben vom 23.09.2026 gegen die Produktivdatenbank, nicht gegen einen Klon.*
