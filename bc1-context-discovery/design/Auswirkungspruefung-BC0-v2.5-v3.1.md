# Auswirkungsprüfung BC0-Schema v2.5–v3.1 auf BC1 — Schritt D (Gerüst gegen Live)

> Gemessen am 12.09.2026: dasselbe Lese-Skript (Spalten, Constraints, Sichtdefinitionen,
> Rechte, Default-Privilegien der elf BC0-Objekte, die BC1 liest oder per FK referenziert)
> gegen die Supabase und gegen einen frischen PG-17-Container mit `tests/db/bc0_geruest.sql`;
> beide Ausgaben per Mengen-Diff verglichen. Schritte A–C (Lesepfade sammeln, BC0-Dateien
> lesen, live messen) liefen am 08.09. bis v2.9 und heute für v3.0/v3.1.

## Big Picture

**Nichts bricht.** Die beiden Sichten, die BC1 liest (`v_prozesse_lesen`, `v_bewertung_aktuell`),
sind live **wortgleich** mit dem Gerüst; jede Spalte und jeder Constraint, den BC1 anfasst, ist
live vorhanden. Schema v3.0/v3.1 berührt keines unserer Objekte (nur `ref_anfragen`,
`app_benutzer_mandanten`, `v_anfrage_steller`, `anfrage_am_gate_nachziehen()`, `bc_zustellungen`).

**Zwei Dinge haben sich geändert, ohne uns zu brechen — beide gehören nachgezogen:**

1. **Stilllegung statt Löschen (v2.2, v2.6).** `ref_prozesse.aktiv`, `ref_teilprozesse.aktiv`
   (und `mandant_systeme.aktiv`) existieren live; BC0 sagt: „FALSE = stillgelegt, verschwindet aus
   Auswahllisten und aus der Erhebung, ist NICHT freigabefähig". Die Sichten filtern das **nicht**,
   und BC1 filtert es auch nicht: ein stillgelegter Teilprozess mit alten Bewertungen wäre bei uns
   interviewbar, ein stillgelegtes System als S-NN gültig. Heute folgenlos (kein stillgelegter
   Bestand bekannt), fachlich aber falsch → **BC1 filtert `aktiv` im Lesepfad** (Paket C2).
2. **Nacherhebungs-IDs (v2.8).** Live erlaubt `E-2026-08-2`, das Gerüst nur `E-2026-08`. Unsere
   Auswahl der jüngsten Erhebung (`stand DESC, erhebung_id DESC`) sortiert solche IDs richtig;
   das Gerüst ist hier strenger als die Realität → CHECK im Gerüst angleichen.

## Technischer Teil — die Dreispalten-Liste

| Objekt / Aspekt | Befund | Einstufung |
|---|---|---|
| `v_prozesse_lesen`, `v_bewertung_aktuell` | Definition live = Gerüst (Zeichen für Zeichen) | gilt unverändert |
| Spalten/Constraints von `companies`, `ref_prozesse`, `ref_teilprozesse`, `mandant_rollen`, `mandant_systeme`, `ref_erhebungen`, `ref_items`, `bitkom_bewertungen`, `prozess_personen`, die BC1 nennt | alle live vorhanden, gleiche Typen | gilt unverändert |
| Rechte, die BC1 braucht (`bc_leser` SELECT auf Lese-Objekte, `REFERENCES` für FKs) | live vorhanden | gilt unverändert |
| Zusatzspalten live (`companies.branche/mitarbeitende/…`, `ref_teilprozesse.api/medienbrueche/schnittstellen`, `mandant_systeme.katalog_id/einsatz`, `*.hinweis`, `ref_erhebungen.methode/angelegt_am`) | BC1 nennt sie nie; Gerüst lässt sie bewusst weg | gilt unverändert (Anspruch des Gerüsts) |
| `ref_prozesse.aktiv`, `ref_teilprozesse.aktiv`, `mandant_systeme.aktiv` (NOT NULL, DEFAULT TRUE) | Stilllegungs-Semantik, von BC1 nicht ausgewertet | **geändert — nachziehen (C2)** |
| `ref_erhebungen` CHECK auf `erhebung_id` | live `^E-[0-9]{4}-[0-9]{2}(-[2-9]\|-[1-9][0-9]+)?$`, Gerüst ohne Nacherhebungs-Suffix | **geändert — Gerüst angleichen** |
| Zusätzliche Rechte live: `bc_leser` SELECT auf `mandant_rollen`, `ref_items`, `bitkom_bewertungen`; `bc1_role` direkt SELECT auf `prozess_personen` | mehr als das Gerüst; `mandant_rollen` braucht C1a → Gerüst-GRANT ergänzen, wenn C1a kommt | geändert, unkritisch |
| Default-Privilegien Schema `bc1` | live **keine** Zeile (K-I geschlossen 08.09.); Gerüst simuliert sie weiter (Zeile 168) | Entscheidung: Positivkontrolle behalten, Kommentar korrigieren |
| Default-Privilegien `bc2`/`bc3`/`bc4` | live weiterhin `bc_leser=r` | fremd, bekannt |
| Default-Privilegien Schema `public` (Rolle `postgres`) | jede neue BC0-Tabelle in `public` ist automatisch für `bc1_role` **und** `bc_leser` lesbar | fremd; BC0 fragen, ob gewollt (Personendaten) |
| `erhebung_id`-Auswahl bei Nacherhebungs-IDs | `ORDER BY e.stand DESC, e.erhebung_id DESC` — `E-2026-08-2` sortiert vor `E-2026-08` | gilt unverändert |
| Schema v3.0 / v3.1 | keine DDL auf BC1-Objekte; `anfrage_am_gate_nachziehen()` **liest** `bc1.prozessprofil` (Konsument unserer DDL, kein Eingriff) | gilt unverändert |

**Bricht uns:** nichts.

## Werkzeug

`struktur_bc0.sql` (nur SELECT; lokal im SDD-Ordner, git-ignoriert) — gegen Live per `lauf.sh sql`,
gegen den Container per `psql`; Vergleich mit `comm` auf den sortierten Ausgaben. Für die nächste
Schemaversion wiederholbar.
