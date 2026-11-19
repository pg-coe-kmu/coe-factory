-- BC0 · v3.36 · Laufdaten vom 02.11.2026 zurückholen (Entscheidung BC0 06.11.: "Alte Laufdaten zurückholen")
-- Quelle: sicherung_vor_v3.33_2026-11-03.sql (COPY public.ki_laufdaten, ids 1-7), gelöscht mit v3.33 am 03.11.
-- Das Paket 63d585ee… existiert nicht mehr (v3.33). Die Läufe kommen deshalb OHNE paket_id zurück;
-- alles Übrige (Mandant, Zeitpunkt, Teilprozess, Kontext, Modell, Tokens, Status, Dauer) unverändert.
BEGIN;
\echo '--- Vorher (ERWARTET: 0 Zeilen mit id 1-7)'
SELECT count(*) AS vorhanden_1_bis_7 FROM ki_laufdaten WHERE id BETWEEN 1 AND 7;
INSERT INTO ki_laufdaten (id, company_id, zeitpunkt, process_id, sub_process_id, kontext, modell,
                          input_tokens, output_tokens, kosten_eur, status, korrigiert, dauer_ms, paket_id, anfrage_id) VALUES
 (1,'7c2d5ee9-2a9a-5990-810f-502ea2b2012d','2026-11-02 17:59:56.987+00','KP-06','KP-06.TP-2','bc4_generator','gpt-4o-2024-08-06',12881, 3530,NULL,'ok',NULL, 21767,NULL,NULL),
 (2,'7c2d5ee9-2a9a-5990-810f-502ea2b2012d','2026-11-02 18:00:22.412+00','KP-06','KP-06.TP-2','bc4_generator','gpt-4o-2024-08-06',16183, 3233,NULL,'ok',NULL, 20692,NULL,NULL),
 (3,'7c2d5ee9-2a9a-5990-810f-502ea2b2012d','2026-11-02 18:00:47.487+00','KP-06','KP-06.TP-2','bc4_generator','claude-opus-5-5',  14298,18298,NULL,'ok',NULL,139229,NULL,NULL),
 (4,'7c2d5ee9-2a9a-5990-810f-502ea2b2012d','2026-11-02 18:03:10.287+00','KP-06','KP-06.TP-2','bc4_generator','claude-opus-5-5',  14120,14168,NULL,'ok',NULL,107729,NULL,NULL),
 (5,'7c2d5ee9-2a9a-5990-810f-502ea2b2012d','2026-11-02 18:05:01.443+00','KP-06','KP-06.TP-2','bc4_generator','claude-opus-5-5',  13052, 9541,NULL,'ok',NULL, 72969,NULL,NULL),
 (6,'7c2d5ee9-2a9a-5990-810f-502ea2b2012d','2026-11-02 18:06:17.778+00','KP-06','KP-06.TP-2','bc4_generator','claude-opus-5-5',  13935,19699,NULL,'ok',NULL,154126,NULL,NULL),
 (7,'7c2d5ee9-2a9a-5990-810f-502ea2b2012d','2026-11-02 18:08:55.393+00','KP-06','KP-06.TP-2','bc4_generator','claude-opus-5-5',  13560,19819,NULL,'ok',NULL,147860,NULL,NULL)
ON CONFLICT (id) DO NOTHING;
\echo '--- Nachher (ERWARTET: 2026-11-02 | 7  und  2026-11-03 | 8)'
SELECT zeitpunkt::date AS tag, count(*) FROM ki_laufdaten WHERE company_id='7c2d5ee9-2a9a-5990-810f-502ea2b2012d' GROUP BY 1 ORDER BY 1;
COMMIT;
