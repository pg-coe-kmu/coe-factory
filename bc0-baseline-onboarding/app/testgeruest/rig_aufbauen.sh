#!/bin/bash
# Testgerüst bc0sim = bc0 (v3.37) + Produktionsstand bc1–bc3 + Kettenangleich + SIM-Mandant wie Produktion
set -e
P="psql -h localhost -p 5498 -U supabase_admin -v ON_ERROR_STOP=1 -q"
$P -d postgres -c "DROP DATABASE IF EXISTS bc0sim WITH (FORCE)" -c "CREATE DATABASE bc0sim TEMPLATE bc0"
$P -d bc0sim -c "DROP SCHEMA IF EXISTS bc1 CASCADE; DROP SCHEMA IF EXISTS bc2 CASCADE; DROP SCHEMA IF EXISTS bc3 CASCADE;" 2>/dev/null
$P -d bc0sim -f schema_bc123_15-11_pg16.sql >/dev/null
$P -d bc0sim -f prod_public_triggerfunktionen.sql
$P -d bc0sim -f rig_angleichen.sql 2>/dev/null
$P -d bc0sim -c "CREATE VIEW public.teilprozess_abgeloest AS SELECT NULL::uuid AS company_id, NULL::text AS sub_process_id, NULL::text AS anfrage_id WHERE false"
$P -d bc0sim -c "SET ROLE bc0_app" -v commit=1 -f ../schema_v3.21-v3.43/sicht_v3.41_bc2_vorgabe.sql | tail -1
$P -d bc0sim -f rig_sim_mandant.sql
echo "Testgeruest bc0sim bereit"
