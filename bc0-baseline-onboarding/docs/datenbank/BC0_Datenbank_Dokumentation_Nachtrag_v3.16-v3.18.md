# BC0 — Datenbankdokumentation · Nachtrag v3.16 bis v3.18

**Stand:** 25.10.2026 · Autor: Simeon Ehmer
**Schließt an** `BC0_Datenbank_Dokumentation_Nachtrag_v3.13-v3.15.md` (Stand 21.10.2026) an.
**Grundlage:** Skripte in `v3.16_Freigabe_Datenstand/` und `v3.17_v3.18_Datenstand_und_IDs/` — **eingespielt am 25.10.2026, noch nicht im Repo**. Vorprüfung und Gegenprobe gegen die Produktion (Drehbuch S-170 bis S-173). Dazu Backend `14_App_V2/backend_v3.17_25-10-2026/app.py` (md5 b83c269e…) und `klon/index.html` (md5 f9571ded…), ausgerollt am 25.10.

---

## 1. Die Stände im Überblick

| Stand | Datei (md5) | Inhalt |
|:--|:--|:--|
| **v3.16** | `schema_v3.16_freigabe_datenstand.sql` (5a2448f3…) | Eine Freigabe zählt für eine Anfrage nur, wenn sie auf dem BC1-Profil **dieser** Anfrage beruht |
| **v3.17** | `schema_v3.17_datenstand_und_namen.sql` (ffec310c…) | Datenstand je Freigabe; Freigabe veraltet bei Nettoänderung der BC0-Daten; Gate 0 nur für benannte Teilprozesse; eindeutige Prozessnamen je Mandant |
| **v3.18** | `schema_v3.18_ids_bc3_bc4.sql` (37aa8884…) | `ki_laufdaten.paket_id` / `anfrage_id`; `REFERENCES` für `bc3_role` auf `gate_pakete`, `ref_anfragen` |
| Prüfung | `vorpruefung_v3.17_v3.18.sql` (d5e0e345…), `pruefung_v3.17_v3.18.sql` (503cf20a…) | nur lesend; Ergebnisse unten |

> **Nummern.** „v3.16“ war am 22.10. für die BC3/BC4-Spalten vorgesehen (Drehbuch S-169). Die Spalten sind jetzt v3.18.

---

## 2. Grundsätze (Simeon, 25.10.2026)

1. **Keine Anfrage, kein BC1-Interview.** Jedes BC1-Profil trägt eine `anfrage_id`. Ohne Anfrage geht ein Teilprozess direkt aus der PWA an Gate 0 (Portfolio-Weg in `gate_paket_schnueren`).
2. **Jeden Prozess gibt es je Mandant nur einmal.** Eine zweite Anfrage zum selben Thema verweist auf den bestehenden Teilprozess; es entsteht kein zweiter.
3. **Je Anfrage genau ein Interview.** Der Anfragestatus läuft nur vorwärts (`zugeordnet → im_interview → am_gate → uebergeben`).
4. **Erhebungs-ID ≠ Datenstand.** `erhebung_id` bleibt der Bitkom-Messzeitpunkt (ADR-004; nur `bitkom_bewertungen`, `bewertung_belege`, als Kopie in `gate_ereignisse`). Für „Stand aller BC0-Daten“ gibt es den **Datenstand** (höchste `audit_id`).

Eine Freigabe trägt damit drei Kennungen:

| Kennung | Spalte in `gate_ereignisse` | sagt |
|:--|:--|:--|
| Erhebung | `erhebung_id` | welche Bitkom-Messrunde |
| BC1-Fassung | `bc1_profil_stand` | welches Interview (nur mit Anfrage) |
| Datenstand | `datenstand` **(neu, v3.17)** | welcher Stand aller BC0-Daten — reproduzierbar über `audit_log` bis zu dieser Nummer bzw. `stand_zum()` |

---

## 3. v3.16 — Freigabe je Interview

**Befund (25.10.):** A-2026-05 (KP-05.TP-1) stand „übergabefähig“, ohne eigene Entscheidung. Die Freigabe vom 18.09. (Ereignis 4, ohne Anfrage, `bc1_profil_stand` NULL, später für A-2026-02 übergeben) galt je Teilprozess weiter, obwohl BC1 am 25.10. für A-2026-05 Profil V3 geschrieben hatte — unter derselben Erhebung E-2026-08.

**Änderung:** nur Sicht `v_anfrage_teilprozesse`. Spalte `freigegeben`:

| Fall | Freigabe zählt, wenn … |
|:--|:--|
| Anfrage hat ein fertiges BC1-Profil (`anfrage_id` = diese) | `bc1_profil_stand` = Version dieses Profils |
| Anfrage hat kein eigenes Profil (Altfall vor BC1 B5, z. B. A-2026-02) | die Freigabe nicht auf dem Profil einer **anderen** Anfrage beruht |

Neue Spalten (hinten): `freigabe_bc1_stand`, `anfrage_bc1_stand`, `freigabe_veraltet`, `freigabe_bc1_anfrage`. `v_anfrage_uebergabe_stand` und `gate_paket_schnueren` folgen ohne eigene Änderung. Portfolio-Weg unberührt.

**Verworfen (eigene Fehlvorschläge, S-170):** Freigabe nur je Anfrage (bräche den Portfolio-Weg); „jede BC0-Änderung“ als Kriterium (zählte Anfrage-Buchführung mit); neue Erhebungs-ID bei jeder Änderung (verfälschte die Reifegradkurve, S-171).

---

## 4. v3.17 — Datenstand und eindeutige Namen

| Teil | Objekt | Wirkung |
|:--|:--|:--|
| A | `gate_ereignisse.datenstand BIGINT`, Trigger `gate_datenstand` (BEFORE INSERT) | setzt `max(audit_id)` bei jeder Gate-Entscheidung; die Anwendung muss nichts tun |
| B | derselbe Trigger, Funktion `teilprozess_unbenannt()` | **Freigabe** eines Teilprozesses mit leerem Namen oder „Teilprozess N“ wird abgelehnt (`check_violation`); Zurückstellen/Zurückweisen bleibt möglich |
| C | Sicht `v_freigabe_datenstand` | je aktueller Freigabe: Zahl der **Nettoänderungen** je Zeile seit dem Datenstand (Zeilenbild damals gegen jetzt; Löschen und identisch neu Anlegen zählt nicht). Umfang: Zeilen des Teilprozesses und Zeilen des Kernprozesses ohne Teilprozessbezug (z. B. `prozess_personen`). Nicht gezählt: `gate*`, `ref_anfragen`, `anfrage_prozesse`, `bc_zustellungen`, `ki_laufdaten`. Freigaben vor v3.17 (`datenstand` NULL) über den Zeitpunkt |
| D | `v_anfrage_teilprozesse` (Weg Anfrage), `v_uebergabe_kandidaten` (Weg Portfolio) | veraltete Freigaben zählen nicht; neue Spalte `datenstand_veraltet` |
| E | `ux_teilprozess_name_je_mandant`, `ux_prozess_name_je_mandant` (UNIQUE, partiell) | Name je Mandant eindeutig (aktiv, `lower(btrim(...))`); Platzhalter „Teilprozess N“ ausgenommen |

Rechte: `SELECT` auf `v_freigabe_datenstand` für `bc_leser`.

**Vorprüfung (25.10.):** `aktiv` boolean; keine doppelten echten Namen (Kern- und Teilprozesse, alle drei Mandanten); Platzhalter „Teilprozess 1–5“ mehrfach in KP-05 bis KP-10 (NoroAI, Übungsmandant); seit 18.09. an KP-05.TP-1 nur `prozess_personen` (3× DELETE, 3× INSERT).

---

## 5. v3.18 — Reproduzierbarkeits-IDs für BC3 und BC4

| Tabelle | Eigentümer | Änderung |
|:--|:--|:--|
| `ki_laufdaten` | postgres (BC0), BC4 schreibt (`INSERT` auf die Tabelle) | `paket_id UUID` → `gate_pakete(company_id, paket_id)`; `anfrage_id TEXT` → `ref_anfragen(company_id, anfrage_id)`; Index `idx_ki_laufdaten_paket`. Alte Zeilen NULL |
| `bc3.lieferungen` | **bc3_role** (BC3) | BC0 ändert nach ADR-003 nur Rechte: `GRANT REFERENCES ON gate_pakete, ref_anfragen TO bc3_role`. BC3 ergänzt die Spalten selbst (Befehl am Ende des Skripts) |

Regel (ADR-003/ADR-002): Die IDs werden **vom Vorgänger übergeben** und unverändert mitgeschrieben — `company_id`, `anfrage_id` (falls es eine Anfrage gibt), `paket_id`, `process_id`, `sub_process_id`.

---

## 6. Gegenprobe (25.10.2026, Produktion)

| Probe | Ergebnis |
|:--|:--|
| P1 Kommentare | v3.17 in `v_anfrage_teilprozesse` und `v_freigabe_datenstand` |
| P2 | Trigger `gate_datenstand`, `historie`; beide `ux_…`-Indizes |
| P3 | Freigabe 4 (KP-05.TP-1) **veraltet**, 4 Nettoänderungen in `prozess_personen` |
| P4 | A-2026-05 `freigegeben f`, `freigabe_veraltet t`; A-2026-02 `datenstand_veraltet t` (bleibt übergeben); A-01/-03 `f` |
| P5/P6 | nichts übergabefähig; keine Portfolio-Kandidaten |
| P7 | `ki_laufdaten.paket_id uuid`, `anfrage_id text`; `bc3_role` REFERENCES `t`/`t` |

**Danach (S-173):** Gate 0 für A-2026-05 neu (Ereignis 7, Fassung 3, Erhebung E-2026-10), Paket **61875f12-1926-4412-ad60-b4904f775c6f**, Zustellung an BC2 HTTP 202, BC2 angenommen.

---

## 7. Anwendung (app.py / index.html, 25.10.)

- **Gate:** `freigabe_veraltet` je Teilprozess (aus `v_freigabe_datenstand` und BC1-Fassung). Veraltete Freigabe ist nicht „entschieden“, sondern wird wie offen eingeordnet; Oberfläche zeigt „veraltet“ mit Grund.
- **Verlauf:** BC3/BC4 über `paket_id`/`anfrage_id` (BC3 über `to_jsonb`, solange die Spalten fehlen); BC3/BC4 nur „erledigt“ bei Zuordnung über ID; Teilprozess-Einträge vor Eingang der Anfrage ausgeblendet.

---

## 8. Was sich an früheren Aussagen ändert

- Nachtrag v3.13–v3.15 / Drehbuch S-169: „v3.16 = BC3/BC4-Spalten“ → jetzt **v3.18**; BC3 ergänzt die eigene Tabelle selbst.
- `v_stand_veraltet` (v2.6) bleibt als Hinweissicht bestehen; maßgeblich für „zählt die Freigabe noch“ ist ab v3.17 `v_freigabe_datenstand`.
- Eine Freigabe ist nicht mehr „für immer“ gültig: neue BC1-Fassung oder geänderte BC0-Daten → neu entscheiden.

## 9. Offene Punkte

1. Skripte v3.16–v3.18 und Backend ins Repo (PR), zusammen mit v3.15 (#283).
2. BC3: Spalten in `bc3.lieferungen` ergänzen und mitschreiben; Testlieferungen vom 23.10. (ohne Übergabe) einordnen.
3. BC4: `paket_id`/`anfrage_id` in `ki_laufdaten` mitschreiben.
4. BC1: Profil V3 verweist auf Erhebung E-2026-08, maßgeblich ist E-2026-10 — klären.
5. Platzhalter „Teilprozess N“ bei NoroAI benennen, bevor sie an Gate 0 gehen.


---

## 10. Nachtrag v3.19a und v3.19b (25.10.2026, eingespielt)

Skripte: `v3.19_Kaskade_und_Anfragebindung/` (nicht im Repo).

**v3.19a — DSGVO-Löschung über `person_rollen`.** Der FK `person_rollen → mandant_rollen` blockierte das Löschen eines Mandanten („still referenced from table person_rollen“), weil `mandant_rollen` früher in der Kaskade fällt als `person_rollen`. Neu: `person_rollen_rolle_fk` als `DEFERRABLE INITIALLY DEFERRED`. Die Mandantenlöschung läuft, eine einzelne Rolle mit Personen bleibt geschützt (Fehler beim COMMIT), eine unbekannte Rolle wird abgewiesen. Gleiche Lösung, die BC1 für `profil_rollen` gemessen hat.

**v3.19b — Anfrage nur mit benannten Teilprozessen; verworfene Erhebung.**

| Objekt | Änderung |
|---|---|
| Trigger `anfrage_prozesse_benannt` (BEFORE INSERT / UPDATE OF process_id, sub_process_id) | Weist einen direkten Bezug auf einen unbenannten Teilprozess ab (`teilprozess_unbenannt()`, ERRCODE check_violation) |
| `v_anfrage_teilprozesse` | Bei Bezug auf den ganzen Kernprozess gehören unbenannte Teilprozesse nicht zur SOLL-Liste. Spalten unverändert |
| `v_freigabe_datenstand` | `veraltet` auch, wenn die Erhebung der Freigabe (`bc0_stand`) `verworfen` ist; neue Spalte hinten `erhebung_verworfen`; `geaenderte_tabellen` nennt „Erhebung E-… verworfen“ |

Maßgeblich ist nur die Erhebung der Freigabe. Eine im BC1-Profil abweichende oder verworfene Erhebung verlangt kein neues Interview (Entscheidung 25.10.); neu entschieden wird Gate 0 mit der dann maßgeblichen Erhebung.

Gegenprobe Produktion (zurückgerollt): unbenannter Teilprozess abgewiesen, benannter angenommen; Verwerfen von E-2026-10 macht KP-05.TP-1 veraltet, A-2026-02 und A-2026-05 stehen `freigegeben f`.

Offen: lesbare Meldung im Backend für die Platzhalter-Sperre; Gate/Freigabe lesen das BC1-Profil der gewählten Anfrage (Backend).
