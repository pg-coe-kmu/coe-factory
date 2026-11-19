# BC0 — Datenbankdokumentation · Nachtrag v3.34 bis v3.38a

**Stand:** 10.11.2026 · Autor: BC0
**Schließt an** `BC0_Datenbank_Dokumentation_Nachtrag_v3.19-v3.33.md` (Stand 04.11.2026) an.
**Grundlage:** die Skripte und Rolloutbeschreibungen in `14_App_V2/v3.34_…` bis `14_App_V2/v3.38a_…`, das Drehbuch S-247 bis S-268 und die Proben im Browser gegen die Produktion.
**Repo:** `origin/main` steht weiter auf v3.20.2. **v3.21 bis v3.38a sind eingespielt, aber noch nicht im Repo** (Governance-Handbuch V1.2, E11).

> **Maßgeblich ist das Skript, nicht dieses Dokument.** Die md5-Summen nennen die eingespielte Fassung.

---

## 1. Die Stände im Überblick

| Stand | Datei (md5) | Art | Inhalt | eingespielt |
|:--|:--|:--|:--|:--|
| v3.34 | — | nur Anfrage-App | „Liste neu laden“, Hinweis „Noch nicht zugeordnet“; Service Worker `coe-anfrage-v5` | 05.11. |
| v3.34a | `Caddyfile` (4c844ebb…) | Betrieb | CORS nur noch bc0-3; unter bc0 geht alles außer `/api/*` mit 308 nach bc0-3; bc0-2 abgeschaltet | 05.11. |
| ~~v3.35~~ | `schema_v3.35_ki_durchlaeufe.sql` (fdf2ff69…) | Schema | Durchläufe 1..x in den Agentenblatt-Tabellen von KI-Transformation, **zurückgenommen** | 05.11., zurück 06.11. |
| ~~v3.35a~~ | `schema_v3.35a_prozessdok_sicht.sql` (c7065266…) | Schema | Korrektur der Sicht `v_prozess_dokumentation_stand` nach v3.35 (501 auf `/prozessdok`), **mit v3.35 zurückgenommen** | 05.11., zurück 06.11. |
| **v3.36** | `rueckweg_v3.35.sql` (09380f7e…) → `schema_v3.32_prozessdokumentation.sql` (7044b5a2…) → `laufdaten_zurueck_v3.36.sql` (4f4811dc…) → `schema_v3.36_ki_reifegrad.sql` (3aa8293d…) | Schema + Daten | v3.35 zurück, Agentenblatt v3.32 wieder hergestellt, 7 Läufe vom 02.11. zurück, **eigene `kir_`-Tabellen für KI-Reifegrad** | 06.11. |
| v3.36b | — | nur Anwendung | Modell-Drift zeigt Beispiel-Regelkarten, bis BC4 `korrigiert` einträgt (Lesespalte `korrigiert_erfasst`) | 06.11. |
| v3.37 | — | nur Anwendung | Lese-Endpunkt `/ki_reifegrad/durchlaeufe`; „Prozessdoku & Verantwortung“ unter KI-Reifegrad | 06.11. |
| **v3.38** | `schema_v3.38_admin2.sql` (6ee1651f…) | Schema | Prüfregel `app_benutzer.rolle` um `admin2` erweitert; vierte Rolle Admin2 | 10.11. |
| v3.38a | — | nur Anwendung | Admin2 auch ohne KI-Reifegrad (Gruppe 6) | 10.11. |

Vor jedem Schema-Stand wurde eine Vollsicherung angelegt: `sicherung_vor_v3.35_2026-11-05.sql`, `sicherung_vor_v3.36_2026-11-06.sql` und `sicherung_vor_v3.38_2026-11-10.sql`, je etwa 5,6 MB, mit dem Schema `public` und `bc1` bis `bc4`.

---

## 2. v3.35 und seine Rücknahme (Lehre)

v3.35 hat die Durchläufe 1..x in die vorhandenen, leeren Agentenblatt-Tabellen (`prozess_dokumentation` und ihre drei Kindtabellen) geschrieben. Deren Schlüssel bekam dabei `paket_id` und `durchlauf_nr`, und `ki_laufdaten` eine Spalte `durchlauf_nr`. Zwei Fehler, beide selbst verursacht:

1. **Die App-Abfrage wurde nicht gegen die neue Sicht geprüft.** `v_prozess_dokumentation_stand` verlor zwei Spalten, und `/prozessdok` antwortete mit 501. v3.35a hat das behoben.
2. **Fachlich falsch.** BC0 am 06.11.: „Ich sagte nicht, wir übernehmen die alten Prozesse.“ Die Durchläufe gehören ausschließlich unter KI-Reifegrad. Das Agentenblatt von KI-Transformation bleibt, wie es ist.

**Lehre:**
- Neue Fachlichkeit bekommt eigene Tabellen und baut keine bestehenden um.
- Nach jeder DB-Änderung wird die App im Browser geprüft, nicht nur das SQL.

---

## 3. v3.36 — KI-Reifegrad (`kir_`)

**Rücknahme und Wiederherstellung**, jeder Schritt in einer eigenen Transaktion:
1. `rueckweg_v3.35.sql`
2. `schema_v3.32_prozessdokumentation.sql`: das Agentenblatt genau wie am 03.11.
3. `laufdaten_zurueck_v3.36.sql`: die 7 Läufe vom 02.11. (id 1–7) aus der Sicherung vor v3.33, **mit `paket_id` NULL**, weil das Paket nicht mehr besteht. Damit zeigen die KI-Controlling-Grafiken wieder 02.11. und 03.11.

**Neue Objekte** (alle mit dem Präfix `kir_`; bestehende Tabellen bleiben unverändert):

| Objekt | Zweck | Regel |
|:--|:--|:--|
| Domain `kir_kennung`, Funktion `kir_ist_kennung()` | Personenkennung | `^(P-[0-9]{2,3}\|BC[0-4]-[A-Z0-9]{2,8}\|uuid)$`; Klarnamen werden abgewiesen (ADR-004 R5) |
| `kir_durchlauf` | Durchlauf je Paket | PK `company_id, paket_id, durchlauf_nr`; `use_case` `UC\d`; Nummern lückenlos (Trigger `trg_kir_durchlauf_pruefen`); Entscheidung `weiter`/`nachbessern`/`verwerfen` nur einmal und nur mit Begründung; Historie |
| `kir_agentenblatt` + `_werkzeuge`, `_agenten`, `_tests` | Agentenblatt **je Durchlauf** und TP | Nur Anhängen (`trg_kir_nur_anhaengen`); nachtragen lässt sich nur die Prüfung (`geprueft_am/_von`, einmal) |
| `kir_kennzahlen` | Kennzahlen je UC | gesperrt ab dem ersten Test |
| `kir_akzeptanzkriterien` | Kriterien je TP | INSERT durch `bc3_role` und `bc4_role` (mit Quelle) |
| `kir_testfaelle`, `kir_testergebnisse` | Testfall → Kriterium; Ergebnis je Durchlauf und Wiederholung | `herkunft` = `generiert` / `generiert_geprueft` / `mensch`; mit Commit, Modell, Prompt-Fassung |
| `kir_messwerte`, `kir_abweichungen` | vorher/nachher je Kennzahl; Soll, Ist, Ursache, Maßnahme | nur Anhängen |
| `kir_werkzeug_nutzung` | tatsächlich verwendete Werkzeuge | Abgleich mit dem Agentenblatt |
| `kir_lauf_zuordnung` | `ki_laufdaten.id` → Durchlauf | Läufe eines Pakets ohne Zuordnung zählen als Durchlauf 1 |
| `kir_gewichte` | Gewichte des Erfüllungsgrads | ab 05.11.2026: A 40, K 40, W 20; nur Anhängen |
| Sichten `v_kir_rueckschreiben_je_bc`, `v_kir_durchlauf_stand`, `v_kir_werkzeug_abgleich(_befund)`, `v_kir_erfuellungsgrad`, `v_kir_agentenblatt_stand` | Datenstruktur, Prozessdokumentation, KI-Readiness | nur lesen |

**Erfüllungsgrad** (deterministisch; Entscheidungen D1–D3 vom 05.11.):
- **A** = Akzeptanzkriterien, deren Testfälle im Durchlauf in **jeder** Wiederholung bestanden sind, geteilt durch alle Kriterien.
- **K** = Kennzahlen mit erreichtem Zielwert, geteilt durch alle Kennzahlen des UC.
- **W** = Werkzeuge, die hinterlegt **und** verwendet sind, geteilt durch alle hinterlegten oder verwendeten.

Ergebnis = 40·A + 40·K + 20·W. Ist n = 0, zählt der Anteil 0 und wird als „nicht messbar“ ausgewiesen. Die Gewichte gelten ab dem Tag, an dem der Durchlauf angelegt wurde.

**`ki_laufdaten`:** keine neue Spalte. `bc4_role` darf `kosten_eur` und `anfrage_id` **nachtragen, aber nicht überschreiben** (Trigger `kir_laufdaten_nachtragen`, `GRANT UPDATE (kosten_eur, anfrage_id)`).

**Daten:** Durchlauf 1 für das NoroAI-Paket vom 03.11. (`cc7f4d1b…`, UC1).

**Prüfung:** `pruefung_v3.36.sql` ergibt im Testgerüst 26 von 26 „ja“.

---

## 4. v3.36b und v3.37 — Lesen, ohne die Datenbank zu ändern

- **v3.36b:** `GET /ki_controlling` liefert je Tag und Prozess zusätzlich `korrigiert_erfasst`. Solange der Wert 0 ist, zeigt Modell-Drift die Beispiel-Regelkarten mit einem Hinweis. **Drift-Daten gab es nie:** BC4 hat bei keinem Lauf `korrigiert` eingetragen.
- **v3.37:** `GET /ki_reifegrad/durchlaeufe` liest:
  - `kir_durchlauf`, `v_kir_erfuellungsgrad` und `v_kir_durchlauf_stand`
  - `gate_paket_inhalt` (Anfrage › KP › TP)
  - `ki_laufdaten` je Durchlauf und TP, über `kir_lauf_zuordnung`
  - `kir_kennzahlen`, `kir_messwerte` und `kir_agentenblatt`

  Gemessen am 06.11.:
  - D1 UC1 0 % (A und K nicht messbar)
  - 8 Läufe auf KP-06.TP-2 mit 128.055 Token und im Schnitt 40,5 s, Modelle claude-opus-5-5 und gpt-4o-2024-08-06
  - 7 Läufe vom 02.11. ohne Durchlauf

---

## 5. v3.38 und v3.38a — Rolle Admin2

**Datenbank:** Die Prüfregel `app_benutzer_rolle_check` lautet jetzt `rolle IN ('benutzer','admin','leser','admin2')`. Das Skript bricht ab, wenn es nicht genau eine Rollen-Prüfregel findet. Der Rückweg (`rueckweg_v3.38.sql`) verweigert, solange ein Konto die Rolle `admin2` hat. Gemessen vorher und nachher: admin 1, benutzer 13; danach 1 Konto admin2.

**Rechte (Server, `bc0_auth`):**

| was | admin | admin2 | benutzer | leser |
|:--|:--|:--|:--|:--|
| Mandanten | alle | **alle** | zugeordnete | zugeordnete |
| Mandantendaten lesen und ändern (inkl. Reifegradbericht) | ja | **ja** | ja | nur lesen |
| HitL Gate 0, Übergabe Gate 0, Erhebung steuern, Altbestand entscheiden | ja | **ja** (`gate_berechtigt`) | nein | nein |
| Verlauf einer Anfrage über die BCs | ja | **nein** (403) | nein | nein |
| Gruppe 6: KI-Transformation und KI-Reifegrad (`/ki_controlling`, `/ki_readiness`, `/prozessdok`, `/ki_reifegrad/durchlaeufe`) | ja | **nein** (404) | ja | nur lesen |
| Mandant anlegen, YAML-Import, OCR, Benutzerverwaltung, löschen | ja | **nein** | nein | nein |

`ist_admin` bleibt für Admin2 falsch. Neue reine Admin-Funktionen stehen Admin2 deshalb nicht versehentlich offen.

**Probe 10.11. als Admin2:**
- Menü: Mandanten, Cockpit, Kennzahlen, Unternehmensdaten, Gate 0.
- API: Gruppe 6 liefert 404, Verlauf 403, Gate und Übergabe 200.
- In Gate 0 sind die „▸ Verlauf“-Links ausgeblendet.

---

## 6. Überholte Aussagen

| Dokument | Aussage | richtig |
|:--|:--|:--|
| Nachtrag v3.19–v3.33, Abschn. 6 | Abweichungen der Durchläufe gehen in `prozess_dok_tests` mit Paket-ID in `verfahren` | seit v3.36 `kir_abweichungen` / `kir_testergebnisse` je Durchlauf |
| Nachtrag v3.19–v3.33, Abschn. 8 | `ki_laufdaten` leer nach v3.33 | 7 Läufe vom 02.11. zurückgeholt (v3.36), 8 Läufe vom 03.11. |
| `AUTH.md` Abschn. 2 | zwei Rollen, „keine dritte Stufe“ | vier Rollen: benutzer, admin, leser (22.09.), admin2 (10.11.) |
| Mitteilung an die BCs vom 04.11. | Tabellennamen aus v3.35 | `kir_*` und `kir_lauf_zuordnung` (v3.36) |

---

*Nachtrag v3.34–v3.38a · 10.11.2026 · BC0 · Drehbuch S-269*
