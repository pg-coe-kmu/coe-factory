# BC0 — Datenbankdokumentation · Nachtrag v3.9 bis v3.12

**Stand:** 06.10.2026 · Autor: Simeon Ehmer
**Schließt an** `BC0_Datenbank_Dokumentation_Nachtrag_v3.5-v3.8.md` (Stand 23.09.2026) an.
**Grundlage:** `origin/main` **7cf132f** (05.10.2026), gelesen am 06.10.2026 — nicht ein lokaler Klon. Gegenproben aus den Ausrollungen (Drehbuch S-148, S-151, S-154, S-156). **Heute nicht neu gemessen:** keine Anmeldung an der Produktivdatenbank; Aussagen zum Betriebsstand stammen aus den Gegenproben der jeweiligen Ausrollung und sind so gekennzeichnet.

---

## 1. Die Stände im Überblick

| Stand | Datum | Repo (`main`) | Datenbank | Inhalt |
|:--|:--|:--|:--|:--|
| v3.5–v3.7 | 22.09. | **seit 29.09. in `main`** (PR [#259](https://github.com/pg-coe-kmu/coe-factory/pull/259), `7ff289f`) | eingespielt 22.09. | siehe Nachtrag v3.5–v3.8 |
| v3.8 | 23.09. | **nicht im Repo** | eingespielt 23.09. | Trigger `kernprozess_bleibt_aktiv` |
| **v3.9 (a)** | 23.09. | **nicht im Repo** | eingespielt 23.09. | `GRANT SELECT ON companies TO bc1_role` — Dauerrecht für BC1s Löschkaskade (P-07) |
| **v3.9 (b)** | 29.09. | `main` (PR [#273](https://github.com/pg-coe-kmu/coe-factory/pull/273), `7200b41`) | eingespielt 29.09., 4 Proben (Probe 2 abweichend → v3.10) | Tabelle `person_rollen` |
| **v3.10** | 29.09. | `main` (PR [#274](https://github.com/pg-coe-kmu/coe-factory/pull/274), `ce6347c`) | eingespielt 29.09., 71 → 0 offene Objekte | `anon`/`authenticated` ohne Rechte in `public`; Data API aus |
| **v3.11** | 04.10. | `main` (PR [#275](https://github.com/pg-coe-kmu/coe-factory/pull/275), `c24fc5a`) | eingespielt 04.10., Proben 7 · t t f f · f f f · 0 | KI-Controlling: 7 Tabellen `ki_*` |
| **v3.12** | 05.10. | `main` (PR [#276](https://github.com/pg-coe-kmu/coe-factory/pull/276), `7cf132f`) | **keine Schemaänderung** | Dokumentpflicht je Teilprozess — nur Anwendungsregeln |

> **Namenskollision v3.9.** Zwei verschiedene Skripte tragen die Nummer v3.9: `schema_v3.9_companies_dauerrecht_bc1.sql` (23.09., nur lokal in diesem Ordner) und `schema_v3.9_person_rollen.sql` (29.09., im Repo). Beide sind eingespielt. Hier als **v3.9 (a)** und **v3.9 (b)** unterschieden. Vorschlag: (a) beim Committen als `schema_v3.8.1_companies_dauerrecht_bc1.sql` führen — Entscheidung Simeon.

---

## 2. v3.9 (a) — Dauerrecht `companies` für `bc1_role` (23.09.)

`schema_v3.9_companies_dauerrecht_bc1.sql`, liegt in diesem Ordner. BC1s Freeze-Trigger liest beim Löschen eines Mandanten `public.companies` **mit den Rechten von `bc1_role`**. Bis dahin hatte `bc1_role` dieses Recht nur indirekt über `bc_leser`. Ein ausdrückliches `GRANT SELECT` mit Tabellenkommentar macht es sichtbar und schützt es beim Aufräumen direkter Rechte (Etappe 4c). Bestätigt in v3.10 Probe 3: `companies` für `bc1_role` = `t`.

## 3. v3.9 (b) — `person_rollen` (29.09., Vorgang 911)

| Spalte | Typ | Bedeutung |
|---|---|---|
| `company_id` | UUID | Mandant |
| `person_id` | TEXT | FK → `ref_personen` (ON DELETE CASCADE) |
| `rolle_id` | TEXT | FK → `mandant_rollen` |

PK `(company_id, person_id, rolle_id)`. **Hauptrolle bleibt `ref_personen.rolle_id`** — daraus liest `v_prozesse_lesen.owner_rolle_id` und BC1/BC2 `process_owner_rolle_id`; die Kette ist unverändert. Additiv, keine Spalte, keine Sicht geändert.
Endpunkte: `GET/PUT /api/companies/{cid}/entitaeten` liefern bzw. speichern je Person `weitere_rollen` (nur wenn der Schlüssel mitkommt; unbekannte Rolle → 400 ohne Schreiben).
**Rechte:** v3.9 entzog nur das Direktrecht von `bc1_role`; über `bc_leser` blieb die Tabelle lesbar (Probe 2 = `t`). Korrigiert in v3.10.

## 4. v3.10 — Supabase-Rollen ohne Rechte (29.09., Vorgang 912)

**Befund 29.09.:** Data API eingeschaltet, RLS aus, `anon`/`authenticated` mit SELECT/INSERT/UPDATE/DELETE/TRUNCATE auf **71 Objekte** in `public` — auch `app_benutzer`, `app_sitzungen`, `ref_personen`.
**Maßnahmen:** Data API abgeschaltet (Simeon, Dashboard); `REVOKE ALL` auf Tabellen, Sequenzen, Funktionen; `ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE ALL … FROM anon, authenticated` — **neue Tabellen sind damit für diese beiden Rollen von Anfang an zu**; `REVOKE ALL ON person_rollen FROM bc_leser`.
**Ergebnis:** 71 → 0. API-Logs der letzten 24 h ohne Zugriff (älter nicht prüfbar), Konten unverändert. Beschrieben in `SICHERHEIT.md` 3.9 (Repo).

## 5. v3.11 — KI-Controlling (04.10., Vorgang 915)

Fachkonzept: `13_Konzepte_Architektur/BC0_Konzept_KI-Transformation_KI-Controlling_v1_04-10-2026.md`. Die Anwendung legt die Tabellen beim Start an (`KIC_DDL_PG`); das Skript trägt dieselbe DDL plus Rechte und Proben.

| Tabelle | Schlüssel | Inhalt | Schreibt |
|---|---|---|---|
| `ki_schulungen` | `id` | Person, Thema, Termin, erledigt am, Nachweis | BC0 |
| `ki_research_bereiche` | `(company_id, bereich)` | verantwortliche Person je Bereich | BC0 |
| `ki_research_notizen` | `id` | Bereich, Datum, Person, Notiz (monatlich) | BC0 |
| `ki_wissensdb` | `company_id` | vorhanden `ja`/`nein`/`im_aufbau`, System, Ort, Person, aktualisiert am, Takt (Tage) | BC0 |
| `ki_strategie` | `company_id` | Sachstand `keine`/`entwurf`/`beschlossen`/`in_umsetzung`, Beschreibung, Person, beschlossen am, überarbeitet am | BC0 |
| `ki_meilensteine` | `id` | Titel, Zieldatum, erreicht am | BC0 |
| `ki_laufdaten` | `id`, Index `(company_id, zeitpunkt)` | je Modellaufruf: Prozess/Teilprozess, Kontext, Modell, Input-/Output-Token, Kosten €, Status `ok`/`fehler`/`abgebrochen`, korrigiert, Dauer ms | **BC4** |

`person_id` verweist fachlich auf `ref_personen` (keine Klarnamen in diesen Tabellen; geprüft im PUT gegen `ref_personen`).
**Rechte:** `ki_schulungen`, `ki_research_bereiche`, `ki_research_notizen` → `REVOKE ALL FROM bc_leser, bc1_role`; alle sieben → nichts für `anon`/`authenticated`; **`bc4_role`: `SELECT, INSERT` auf `ki_laufdaten`** + `USAGE` auf `ki_laufdaten_id_seq`. Proben 04.10.: 7 Tabellen · BC4 `t t f f` (insert, select, kein update, kein delete) · BC1 auf Personenbezug `f f f` · Supabase-Rollen `0`.
**Hinweis:** `ki_wissensdb`, `ki_strategie`, `ki_meilensteine`, `ki_laufdaten` sind über die Voreinstellung (`pg_default_acl`) für `bc_leser`/`bc1_role` lesbar — sie enthalten `person_id`, aber keine Namen. Gewollt offen; wird mit [#262](https://github.com/pg-coe-kmu/coe-factory/issues/262) neu bewertet.
Endpunkte: `GET /api/companies/{cid}/ki_controlling` (verdichtet `ki_laufdaten` je Tag × Modell und je Tag × Prozess), `PUT` (jeder Block optional, Listen ersetzen den Bestand, Fehler → 400 ohne Schreiben).
**Stand `ki_laufdaten`:** BC4 schreibt noch nicht (Mitteilung vorbereitet, nicht verschickt); die Oberfläche zeigt bis dahin gekennzeichnete Beispieldaten.

## 6. v3.12 — Dokumentpflicht je Teilprozess (05.10., Vorgang 917)

**Keine Schemaänderung.** Neue Regeln in der Anwendung über bestehende Tabellen:

| Tabelle | Regel |
|---|---|
| `beleg_dokumente` | Je Teilprozess muss mindestens ein Dokument mit `ref_id = 'KP-XX.TP-Y'` und `status <> 'verworfen'` vorliegen. Dokumente an `KP-XX` oder `MANDANT` zählen nicht. Status `hochgeladen` (Scan ohne Text) zählt. |
| `bitkom_bewertungen` | Text-Beleg je Item bleibt Pflicht (CHECK aus v1.1 + 400 in der Anwendung). Speichern ohne Dokument am TP = **Zwischenspeicherung** (Antwort `zwischenstand: true`). |
| `bitkom_bewertungen` (YAML) | `import_yaml` weist Stufen ohne Beleg mit 400 ab, **nichts** wird angelegt. Der frühere Ersatztext „Aus YAML übernommen“ entfällt. |
| Gate 0 | dritte Vorbedingung `dokument_vorhanden`; Hindernisart `dokument`. |
| Bericht | `tp_rows[].dokumente`, `tp_rows[].belegt`, `dok_quote`, `nicht_belegt[]`; Kurzfassung „Nicht belegt! …“. Der Reifegrad rechnet nicht belegte TP mit. |

**Bestand:** Bereits bewertete Teilprozesse ohne Dokument gelten ab 05.10. als nicht belegt und sind in Gate 0 gesperrt; Werte und entschiedene Bögen bleiben.

---

## 7. Was sich an Aussagen früherer Fassungen ändert

| frühere Aussage | gilt seit |
|:--|:--|
| v3.5–v3.7 nur im offenen PR #259 (Nachtrag v3.5–v3.8) | in `main` seit 29.09. (`7ff289f`) |
| `bc1_role` liest `companies` nur über `bc_leser` | ausdrückliches Recht, v3.9 (a) |
| Eine Person hat genau eine Rolle | Hauptrolle + weitere Rollen, v3.9 (b) |
| `anon`/`authenticated` (Supabase) spielen keine Rolle | hatten bis 29.09. Vollrechte; seit v3.10 keine, auch nicht für neue Tabellen |
| Belegpflicht = Text je Item | zusätzlich **Dokument je Teilprozess**, v3.12 |
| YAML-Import ersetzt fehlende Belege | weist ab, v3.12 |
| `v_gate_bogen.bogen_ausfuellbar` = Gate-Logik | **veraltet**: Die Sicht (v1.4) verlangt noch den Ansprechpartner (entfallen 18.08.) und kennt das Dokument nicht. Die Anwendung nutzt sie nicht. |

## 8. Was offen bleibt

| Punkt | Stand |
|:--|:--|
| `schema_v3.8` und v3.9 (a) committen; Nummer für (a) klären | nur lokal, eingespielt — Entscheidung Simeon |
| Eigenes Schema `bc0_betrieb` | [#262](https://github.com/pg-coe-kmu/coe-factory/issues/262) offen, **Soll 09.10.2026** |
| `v_gate_bogen`/`v_gate_vorbedingungen` an die Anwendung angleichen oder als veraltet kennzeichnen | Befund S-156, kein Vorgang |
| `schema_v1.9_ki_readiness` und `schema_v2.0_prozessdokumentation` | im Repo, **laut Drehbuch und Oberfläche nicht eingespielt** (Endpunkte antworten 501) — heute nicht gemessen |
| BC4 schreibt `ki_laufdaten` | Mitteilung vorbereitet (S-154), nicht verschickt |
| OCR-Worker (Beleg-Ingestion Stufe 2, Schritt 5) | nicht gebaut; Scans bleiben `hochgeladen` ohne Text (S-155) |

---

*Grundlage: `origin/main` 7cf132f (`schema_v3.9_person_rollen.sql`, `schema_v3.10_supabase_rechte.sql`, `schema_v3.11_ki_controlling.sql`, `app.py`) · `schema_v3.9_companies_dauerrecht_bc1.sql` (lokal) · Gegenproben 23.09., 29.09., 04.10., 05.10. (Drehbuch S-124, S-148–S-151, S-154, S-156).*
