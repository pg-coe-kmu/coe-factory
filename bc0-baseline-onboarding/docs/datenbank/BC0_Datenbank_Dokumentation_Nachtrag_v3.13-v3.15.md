# BC0 — Datenbankdokumentation · Nachtrag v3.13 bis v3.15

**Stand:** 21.10.2026 · Autor: Simeon Ehmer
**Schließt an** `BC0_Datenbank_Dokumentation_Nachtrag_v3.9-v3.12.md` (Stand 06.10.2026) an.
**Grundlage:** `origin/main` **bb52670** (v3.13, v3.14; 08.10.2026) und Zweig `bc0-v3.15-lesegruppe` (PR [#283](https://github.com/pg-coe-kmu/coe-factory/pull/283), **noch nicht gemergt**). Alle drei Stände am 08.10.2026 eingespielt und **live gegengeprüft** (Drehbuch S-164, S-165). Stand der Anfragen am 21.10. live gemessen (S-166).

---

## 1. Die Stände im Überblick

| Stand | Datum | Repo (`main`) | Datenbank | Inhalt |
|:--|:--|:--|:--|:--|
| **v3.13** | 08.10. | `main` (PR [#281](https://github.com/pg-coe-kmu/coe-factory/pull/281), `bb52670`) | eingespielt 08.10., Prüfung **7/7** gegen die Produktion | Gate je Anfrage: `anfrage_am_gate_nachziehen()` zählt nur Profile derselben `anfrage_id`; Endpunkt nimmt `?anfrage_id` |
| **v3.14** | 08.10. | `main` (PR #281, `bb52670`) | eingespielt 08.10. (zweiter Lauf, `COMMIT`) | `GRANT REFERENCES` für `bc3_role` auf `companies`, `ref_prozesse`, `ref_teilprozesse` (#279) |
| **v3.15** | 08.10. | **nur Zweig** (PR #283 offen) | eingespielt 08.10., Gegenprobe alle `f`, Sichten `t` | `ref_anfragen` und `ki_wissensdb`, `ki_strategie`, `ki_meilensteine`, `ki_laufdaten` aus der Lesegruppe entzogen |

> **Nummer v3.12.** v3.12 ist die Dokumentpflicht (Vorgang 917) — ohne Schemadatei, nur in `app.py`. Die drei Stände dieses Nachtrags hießen beim Bau zunächst v3.12/v3.13 und wurden vor dem Einspielen umnummeriert (Drehbuch S-164).

---

## 2. v3.13 — Gate je Anfrage (Vorgang 920)

**Anlass:** Review von PR #280 (BC1 B4, Dienst-Anmeldung an BC0). BC1 stößt nach jedem fertigen Profil `gate_nachziehen` an.

**Befund:** `anfrage_am_gate_nachziehen()` (v3.0) zählte ein fertiges BC1-Profil nur über **Mandant und Teilprozess**. Ein fertiges Profil aus einer *früheren* Anfrage schickte eine *neue* Anfrage auf demselben Teilprozess ans Gate, ohne dass für sie interviewt wurde. Der Endpunkt reichte die `anfrage_id` außerdem nicht an die Funktion weiter.

**Änderung (nur die Funktion, keine Tabelle, keine Daten):**

| Regel | |
|:--|:--|
| Gezählt wird | nur das jüngste Profil je Teilprozess **mit derselben `anfrage_id`** (Spalte seit BC1 B5, #277) |
| Profile ohne `anfrage_id` | zählen **nicht** (Bestand vor B5). Eine solche Anfrage setzt der Mensch von Hand ans Gate (`PUT …/anfragen/{id}/status`) |
| Spalte `bc1.prozessprofil.anfrage_id` fehlt | Funktion ändert nichts und sagt es im Hinweis |
| Signatur | unverändert `(p_company UUID, p_anfrage TEXT DEFAULT NULL)` |

**HTTP:** `POST /api/companies/{cid}/anfragen/gate_nachziehen` nimmt optional `?anfrage_id=A-JJJJ-NN`. Falsche Form → **400**, unbekannte Anfrage → **404**, ohne Parameter wie bisher (ganzer Mandant). BC1 schickt den Parameter seit PR [#282](https://github.com/pg-coe-kmu/coe-factory/pull/282).

**Prüfung:** `pruefung_v3.13_gate_je_anfrage.sql` gegen die Produktion 7/7 `ja` (ROLLBACK). Gegenprobe lokal mit der alten Funktion: Probe 3 schlägt fehl (`am_gate / 1 von 1`) — der Befund ist damit belegt.

---

## 3. v3.14 — `REFERENCES` für `bc3_role` (Vorgang 921, #279)

BC3 legt `bc3.lieferungen` selbst an (ADR-003 Regel 3) und verweist per Fremdschlüssel auf BC0:

| Fremdschlüssel | Ziel |
|:--|:--|
| `(company_id)` | `companies` — Empfehlung `ON DELETE CASCADE` |
| `(company_id, process_id)` | `ref_prozesse` |
| `(company_id, sub_process_id)` | `ref_teilprozesse` |

`REFERENCES` erlaubt nur Fremdschlüssel — kein Lesen, kein Schreiben. Vorbild: v2.4 für `bc1_role`. **Fehler beim ersten Lauf:** Die Gegenprobe zählte auch `bc3.lieferungen` (Eigentümerrecht von BC3) und brach ab — nichts geändert; korrigiert auf `table_schema = 'public'`, zweiter Lauf `COMMIT`. Vorgang 921 am 21.10. geschlossen (keine Rückfrage von BC3).

---

## 4. v3.15 — `ref_anfragen` und vier `ki_*` aus der Lesegruppe (Vorgang 922)

**Anlass:** vertraulicher Hinweis von BC1 (06.10., nicht im Repo), live bestätigt am 08.10.:

| Objekt | vorher `bc_leser` / `bc1_role` | Ursache |
|:--|:--|:--|
| `ref_anfragen` | `t` / `t` | Voreinstellung `pg_default_acl` auf `public` (#214); v1.4 wollte sie geschlossen halten (`originaltext` kann Personenbezug tragen) |
| `ki_wissensdb`, `ki_strategie` (mit `person_id`), `ki_meilensteine`, `ki_laufdaten` | `t` / `t` | v3.11 entzog der Lesegruppe nur `ki_schulungen`, `ki_research_bereiche`, `ki_research_notizen` |

**Änderung:** kein `SELECT` mehr für `bc_leser` und `bc1_role`–`bc4_role` auf diese fünf Tabellen. **BC4 behält** `SELECT, INSERT` auf `ki_laufdaten` (v3.11).

**Was bleibt:** BC1 liest Anfragen nur über `v_anfrage_prozessbezug` und `v_anfrage_teilprozesse` — die Sichten laufen mit Eigentümerrechten. Gemessen: Sicht vorher **5**, nachher **5** Zeilen; als `bc1_role` (lokal) liefert die Sicht weiter, direkter Zugriff → `permission denied`. BC2 liest nur Fachdaten (`stand_zum`, `companies`, `company_profile`) und ist nicht betroffen (Messung BC2 am 09.10., PR #284).

---

## 5. Was sich an Aussagen früherer Fassungen ändert

| frühere Aussage | gilt seit |
|:--|:--|
| Nachtrag v3.0, 2.3: Die Gate-Funktion zieht nach, „sobald BC1 geliefert hat“ | nur mit einem Profil **derselben Anfrage**, v3.13 |
| Nachtrag v3.0, 2.3: „BC1 muss es nicht dürfen, weil BC0 es selbst nachzieht“ | BC1 **stößt** das Nachziehen seit B4 (#280) über die API an und meldet `im_interview`; entscheiden tut weiter BC0 |
| `REFERENCES` nur für `bc1_role` (ROLLEN.md, v2.4) | auch `bc3_role` auf drei Tabellen, v3.14; `bc2_role`/`bc4_role` weiter ohne (ToDo 121) |
| Grunddokument v1.7, 8: `ref_anfragen` „für `bc_leser` gesperrt“ | war tatsächlich offen; **seit v3.15 gesperrt** |
| Nachtrag v3.9–v3.12, 5: vier `ki_*` „gewollt offen“ | **seit v3.15 entzogen** |

---

## 6. Stand der Anfragen (gemessen 21.10.2026)

`eingegangen` 3 · `uebergeben` 2 · `zugeordnet`/`im_interview`/`am_gate` 0. Keine Anfrage hängt wegen v3.13. Die beiden übergebenen Anfragen stammen aus der Zeit vor B5; ihre Profile tragen keine `anfrage_id` (Durchstich-Beleg A-2026-02: `15_Praesentationen/Durchstich_Beleg_KP-05_A-2026-02_21-10-2026.md`).

---

## 7. Was offen bleibt

| Punkt | Stand |
|:--|:--|
| PR #283 (v3.15) mergen | offen — Produktion ist dem Repo voraus |
| Voreinstellung `pg_default_acl` auf `public` | [#214](https://github.com/pg-coe-kmu/coe-factory/issues/214)/[#262](https://github.com/pg-coe-kmu/coe-factory/issues/262) — die nächste neue Tabelle ist wieder lesbar |
| Prüfpunkt „Rollen mit Zeitanteil“ (R-07) | sperrt nicht (`wartet_bc1` sortiert nur); Freigabe mit Güte `entfaellt`. Aus dem Code nehmen: nach 03.11. |
| v1.9 / v2.0 eingespielt? | seit 06.10. nicht gemessen |
| v3.8, v3.9 (a) ins Repo | weiterhin nur lokal |

---

*Grundlage: `schema_v3.13_gate_je_anfrage.sql`, `pruefung_v3.13_gate_je_anfrage.sql`, `schema_v3.14_references_bc3.sql`, `schema_v3.15_lesegruppe_anfragen_ki.sql`, `app.py` (`main` bb52670) · Gegenproben 08.10. und Messung 21.10. (Drehbuch S-164 bis S-166). Skripte: `10_DB_Dokumentation/v3.13_Gate_je_Anfrage/`, `v3.14_References_bc3/`, `v3.15_Lesegruppe_Anfragen_KI/`.*
