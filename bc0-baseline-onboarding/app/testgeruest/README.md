# BC0 Testgerüst `bc0sim`

Lokale PostgreSQL-Kopie des BC0-Schemas mit dem Simulations-Mandanten
„SIMULATION - NoroAI Consulting GmbH“. Damit lassen sich Rückschreibungen
in die `kir_*`-Tabellen (KI-Reifegrad) und die App-Endpunkte testen,
ohne die Produktionsdatenbank zu berühren.

## Voraussetzungen

- PostgreSQL 16 oder 17 lokal, Port 5498, Superuser `supabase_admin`
- Rolle `bc0_app` (LOGIN, ohne Superuser) – entspricht der App-Rolle ab v3.40
- Vorlage-Datenbank `bc0` mit dem BC0-Schema bis v3.37
  (`app/schema_*.sql` bis v3.19c, danach `app/schema_v3.21-v3.43/` in Versionsreihenfolge)
- `schema_bc123_15-11_pg16.sql`: Schema-Dump der Schemas `bc1`, `bc2`, `bc3`
  (nur Struktur, keine Daten). Nicht im Repository – bei Bedarf mit
  `pg_dump --schema-only -n bc1 -n bc2 -n bc3` aus einer eigenen Testinstanz erzeugen.

## Aufbau

```bash
cd bc0-baseline-onboarding/app/testgeruest
bash rig_aufbauen.sh          # Ausgabe am Ende: "Testgeruest bc0sim bereit"
```

Danach v3.42 und v3.43 einspielen:

```bash
psql -h localhost -p 5498 -U supabase_admin -d bc0sim -f ../schema_v3.21-v3.43/schema_v3.42_modellregister.sql
psql -h localhost -p 5498 -U supabase_admin -d bc0sim -f ../schema_v3.21-v3.43/schema_v3.43_ki_reifegrad_sei.sql
```

## Dateien

| Datei | Zweck |
|---|---|
| `rig_aufbauen.sh` | legt `bc0sim` aus Vorlage `bc0` neu an und spielt alles ein |
| `prod_public_triggerfunktionen.sql` | Triggerfunktionen im Schema `public` wie in Produktion |
| `rig_angleichen.sql` | Constraints/Fremdschlüssel wie in Produktion (NOT VALID) |
| `rig_sim_mandant.sql` | SIM-Mandant, Prozesse, Paket, Test-Admin (`admin@test.invalid`) |

## App-Tests v3.43

```bash
cd bc0-baseline-onboarding/app
MODUS=pg  DATABASE_URL=postgresql://bc0_app@localhost:5498/bc0sim python test_v343.py
MODUS=sqlite BC0_DB=/tmp/bc0_test.db python test_v343.py
```

## Hinweise für BC4

- Schreibrechte von `bc4_role`: INSERT auf 12 `kir_*`-Tabellen, nicht auf
  `kir_durchlauf` und `kir_gewichte`. UPDATE nur `ki_laufdaten.kosten_eur`,
  `ki_laufdaten.anfrage_id` und die Prüffelder des Agentenblatts.
- Die `kir_*`-Tabellen sind nur anhängbar (Trigger `nur_anhaengen`).
  Kennzahlen sind nach dem ersten Messwert oder Testergebnis je
  Unternehmen + Use Case gesperrt.
- Durchlauf-Nummern sind lückenlos; einen Durchlauf legt BC0 an.
- IDs (Story, Akzeptanzkriterium, Testfall) kommen aus dem Ticket-Set von BC3.
