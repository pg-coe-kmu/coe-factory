# Nachtrag DB-Dokumentation v3.41 — Sicht `v_bc2_vorgabe` (14.11.2026)

| | |
|---|---|
| Skript | `14_App_V2/v3.41_Vorgabe_aus_BC2_14-11-2026/sicht_v3.41_bc2_vorgabe.sql` (md5 e74e8463…), ausgeführt als `bc0_app` |
| Art | neue Sicht, nur lesend; keine Tabellen-, Daten- oder Rechteänderung |

## `public.v_bc2_vorgabe`
- Eigentümerin `bc0_app`. Keine Rechte für andere Rollen erteilt.
- Liest `bc2.v_ergebnisakte` (`dokument` jsonb) über die Mitgliedschaft in `bc_leser`.
- Eine Zeile je in Gate 1 freigegebenem Potenzial **und** Teilprozess (`approved_potenzial_ids`, `betroffene_teilprozess_ids`).
- Spalten:
  - Mandant, Paket, Fassung, `priorisierung_id`, eingefroren am, lieferbar, Gate-1-Status
  - Potenzial, Konzept, Rang, finaler Rang, Prioritätsgruppe, Score, `kp_id`, `sub_process_id`
  - **`teilprozess_bekannt`**: gibt es den Teilprozess in `ref_teilprozesse`?
  - Titel, User Story, Akzeptanzkriterien (jsonb) und deren Anzahl
  - Automatisierung min/max %, Handarbeit h/J heute, Aufwand PT
  - Einsparung, Kosten heute, Ersparnis %, Amortisation (jsonb-Spannen), Investition
  - Wertquelle, Impact, Umsetzungskomplexität, Kategorie
- Stand 14.11.2026: 6 Zeilen. NoroAI b7e0b991 hat 2 Potenziale auf KP-06.TP-2 bis -5, Übungsmandant c4e30d28 hat 2 auf KP-01.TP-1 und -2; alle Teilprozesse sind bekannt.

## Lesewege der App (v3.41)
- `GET /api/companies/{cid}/bc2_vorgabe` liefert:
  - die Sicht
  - die Präsentationen der Akte
  - `geliefert`: Kriterien mit `quelle` `bc2:…` aus `kir_akzeptanzkriterien` und Kennzahlen mit `bezug_potenzial_id` aus `kir_kennzahlen`
  - `messung_ak`: erfüllte Kriterien je Durchlauf über `kir_testfaelle` → `kir_testergebnisse`
  - `messung_kz`: Messwerte aus `kir_messwerte`
- `GET /api/companies/{cid}/bc2_praesentation/{priorisierung_id}`: die pptx aus `bc2.v_ergebnisakte.inhalt`, mit Anmeldung, als Download.

## Konventionen für BC3/BC4 (Grundlage der Diagramme)
- BC3: `kir_akzeptanzkriterien.quelle = 'bc2:<priorisierung_id>/<potenzial_id>/<Nr.>'`.
- BC4: `kir_kennzahlen.bezug_potenzial_id`; `quelle_vorher = 'bc2:automatisierungsgrad'` bzw. `'bc2:handarbeit'`. Kennzahlen müssen vor dem ersten Test festgelegt sein; das erzwingt der Trigger `trg_kir_kennzahl_vor_test`.
