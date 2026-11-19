# Nachtrag DB-Dokumentation v3.40 — Eigene Rolle der App (14.11.2026)

| | |
|---|---|
| Skript | `14_App_V2/v3.40_Eigene_DB-Rolle_App_14-11-2026/teil_b_v3.40.sql` (md5 8d4bca55…) |
| Art | Rechte und Eigentum, keine Daten- oder Strukturänderung |
| Sicherung vorher | `/opt/bc0/sicherung_vor_v3.40_2026-11-14.sql` (md5 d42e631b…) |

## Neue Rolle `bc0_app`
- Eigenschaften:
  - LOGIN
  - kein Superuser, kein CREATEDB, kein CREATEROLE, kein BYPASSRLS
- Mitgliedschaften und Rechte:
  - Mitglied von `bc_leser`: liest `bc1`–`bc3` wie bisher
  - USAGE und CREATE auf `public`
  - `postgres` ist Mitglied von `bc0_app`; das ermöglicht Eingriffe und den Rückfall
- **Eigentümerin** aller Objekte von BC0 in `public`: 64 Tabellen, 43 Sichten, 8 Sequenzen (über ihre Tabellen), 33 Funktionen, 5 Typen. Die Erweiterungen bleiben bei `postgres` bzw. `supabase_admin`.
- Kein Ändern, Löschen oder Leeren in `bc1`–`bc4`.

## Unverändert
- Rechte aller anderen Rollen auf `public`: 992 Einträge, vorher und nachher gleich. Betroffen sind bc1–bc4, `bc_leser`, `service_role`, anon und authenticated.
- `postgres` bleibt die Verwaltungsrolle für einzeln ausgerollte Eingriffe.

## Verbindung
`.env` der App: `DATABASE_URL` mit Benutzer `bc0_app.<Projektkennung>` über den Pooler. BC1 nutzt weiter die eigene `.env.bc1`.

## Folge für künftige Schemaänderungen
Neue Tabellen legt die App selbst als `bc0_app` an. Bei Skripten, die als `postgres` neue Objekte in `public` anlegen, muss danach `ALTER … OWNER TO bc0_app` folgen. Sonst kann die App sie nicht ändern. Rechte für andere Contexts werden weiter ausdrücklich erteilt.

## Ablauf und Gegenprobe (Ausrollen 14.11.2026)
| Prüfung | Ergebnis |
|---|---|
| Inventur Teil A (`inventur_v3.40.sql`) | `postgres`: kein Superuser, BYPASSRLS und CREATEROLE; bc1–bc3 besitzen ihre Tabellen selbst |
| Probelauf mit ROLLBACK | B0–B4 bestanden |
| Echter Lauf | COMMIT, B4 bestanden |
| Verbindung der App | `current_user = bc0_app`; `has_table_privilege('bc2.lauf','DELETE') = f` |
| Browserprobe | alle Bereiche 200; Verlauf liest `bc1.prozessprofil`, `bc2.eingang`, `bc2.lauf`, `bc2.gate1`, `bc3.lieferungen` |

Ausrollblatt mit allen Schritten: `14_App_V2/v3.40_Eigene_DB-Rolle_App_14-11-2026/AUSROLLEN_v3.40.md`.

## Rechte nach v3.40 im Überblick
| Rolle | `public` (BC0) | `bc1` | `bc2` | `bc3` | `bc4` |
|---|---|---|---|---|---|
| `bc0_app` (App) | Eigentümerin, alles | lesen | lesen | lesen | – |
| `postgres` (Verwaltung) | über Mitgliedschaft in `bc0_app` | wie bisher | wie bisher | wie bisher | wie bisher |
| `bc1_role`–`bc4_role` | wie bisher, ausdrücklich erteilt | eigenes Schema | eigenes Schema | eigenes Schema | eigenes Schema |
| `bc_leser` | Lesesichten wie bisher | lesen | lesen | lesen | lesen |
| `service_role` (Supabase) | voll, wie bisher; Schlüssel nicht in der App gesetzt, Dashboard nur beim Verfasser | | | | |

## Löschen von Folgedaten anderer Contexts
- Die App kann Daten von BC1 bis BC4 nicht mehr ändern oder löschen.
- Wird ein Use Case **unter denselben IDs** neu aufgesetzt, wie bei den Bereinigungen v3.31b und v3.33, müssen die Folgedaten der anderen Contexts weiter gelöscht werden. Das geschieht auf Verwaltungsebene, einzeln ausgerollt, mit Sicherung vorher. Grund: IDs werden nie geändert und nie wiederverwendet (ADR-003 Regel 2, ADR-004 R3). Alte Ergebnisse unter denselben IDs wären keinem Stand mehr eindeutig zuzuordnen.
- Die Alternative ist ein neuer Use Case mit neuen IDs.

## Befund zur Ergebnisakte von BC2 (gelesen am 14.11.2026)
`bc2.ergebnisakte`, `bc2.ergebnisakte_datei` und die Sicht `bc2.v_ergebnisakte` gehören `bc2_role`; `bc_leser` darf lesen. Abweichungen von ADR-003:
1. Kein Fremdschlüssel von `company_id`/`paket_id` auf BC0 (nur Text).
2. Keine Spalte und kein Fremdschlüssel für die Prozess-ID. Die IDs stehen nur im JSON-Inhalt (`kontext.kp_id`, `potenziale[].betroffene_teilprozess_ids`, `eintraege[].kp_id`) und im Dateinamen; die DB setzt die Zuordnung nicht durch. *(Berichtigt 14.11.: zuerst hieß es „nur im Dateinamen“.)*
3. Kaskade vom Lauf löscht die Akte mit. Die Trigger `…_fest` sperren nur UPDATE.
4. Öffentlicher Präsentationslink bei beiden Akten aktiv.
5. Klarname im Ordnernamen.

Einzelheiten: `14_App_V2/Pruefung_Ergebnisakte_BC2_14-11-2026/ERGEBNIS_Pruefung_14-11-2026.md`. Mitteilung an BC2 vorbereitet für den 17.11.2026.

## Bestand `public` am 14.11.2026
64 Tabellen, 43 Sichten, 8 Sequenzen, 33 Funktionen, 5 Typen.
