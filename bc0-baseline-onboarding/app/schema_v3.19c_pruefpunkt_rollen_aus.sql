-- Schema v3.19c — Pruefpunkt "Beteiligte Rollen mit Zeitanteil" abschalten (25.10.2026)
--
-- Anlass: BC2 rechnet seit 20.09. mit einem Mischsatz (#172, Vertrag 1.2) und braucht
-- keine Rollen mit Zeitanteil; BC1 erhebt sie deshalb nicht (bc1.profil_rollen bleibt
-- leer). Der Pruefpunkt verlangte bei jeder Freigabe "entfaellt" von Hand.
-- Entscheidung Simeon 25.10.2026 (Rueckfrage BC1 Punkt 7, #206; #233 Weg (a)).
-- Wie "zulaessigkeit": Zeile bleibt, nur aktiv = false. Wieder einschalten:
--   UPDATE ref_gate_pruefpunkte SET aktiv = true WHERE pruefpunkt = 'rollen';
-- Backend v3.20.1 zaehlt die Angabe dann nicht mehr als "fehlt bei BC1".
-- Ausfuehren als postgres, eine Transaktion.

BEGIN;
\echo '--- vorher (ERWARTET: rollen | t)'
SELECT pruefpunkt, aktiv FROM ref_gate_pruefpunkte WHERE pruefpunkt = 'rollen';

UPDATE ref_gate_pruefpunkte
   SET aktiv = false,
       erlaeuterung = erlaeuterung || ' — ABGESCHALTET 25.10.2026: BC2 rechnet mit Mischsatz (#172), BC1 erhebt keine Rollen.'
 WHERE pruefpunkt = 'rollen' AND aktiv;

\echo '--- nachher (ERWARTET: rollen | f) und aktive Punkte (ERWARTET: ohne rollen und zulaessigkeit)'
SELECT pruefpunkt, aktiv FROM ref_gate_pruefpunkte WHERE pruefpunkt = 'rollen';
SELECT string_agg(pruefpunkt, ', ' ORDER BY reihenfolge) AS aktive_punkte
  FROM ref_gate_pruefpunkte WHERE aktiv;
COMMIT;
