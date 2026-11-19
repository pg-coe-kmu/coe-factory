-- Rueckweg v3.35 -> Stand v3.32 (nur falls noetig). Danach schema_v3.32_prozessdokumentation.sql erneut einspielen.
-- ACHTUNG: loescht alles, was BC4 seit v3.35 in Durchlaeufe, Agentenblatt, Tests, Messwerte geschrieben hat.
-- Vorher pruefen: SELECT count(*) FROM ki_testergebnisse;  -- sollte 0 sein
BEGIN;
DROP VIEW IF EXISTS v_rueckschreiben_je_bc, v_durchlauf_stand, v_erfuellungsgrad, v_werkzeug_abgleich_befund,
                    v_werkzeug_abgleich, v_prozess_dokumentation_stand;
DROP TABLE IF EXISTS ki_werkzeug_nutzung, ki_abweichungen, ki_messwerte, ki_testergebnisse, ki_testfaelle,
                     ki_akzeptanzkriterien, ki_kennzahlen, ref_erfuellung_gewichte,
                     prozess_dok_tests, prozess_dok_agenten, prozess_dok_werkzeuge, prozess_dokumentation;
DROP TRIGGER IF EXISTS laufdaten_nachtragen ON ki_laufdaten;
ALTER TABLE ki_laufdaten DROP CONSTRAINT IF EXISTS fk_ki_laufdaten_durchlauf;
ALTER TABLE ki_laufdaten DROP COLUMN IF EXISTS durchlauf_nr;
REVOKE UPDATE (kosten_eur, anfrage_id) ON ki_laufdaten FROM bc4_role;
DROP TABLE IF EXISTS ki_durchlauf;
DROP FUNCTION IF EXISTS trg_ki_laufdaten_nachtragen(), trg_ki_kennzahl_vor_test(), trg_dok_nur_pruefung(),
                        trg_ki_durchlauf_pruefen(), trg_ki_nur_anhaengen(), ist_kennung(text);
DROP DOMAIN IF EXISTS ki_kennung;
\echo '--- Rueckweg: Objekte weg (ERWARTET: f | f)'
SELECT to_regclass('public.ki_durchlauf') IS NOT NULL AS durchlauf, to_regclass('public.prozess_dokumentation') IS NOT NULL AS blatt;
COMMIT;
