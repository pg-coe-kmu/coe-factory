-- BC1 -> BC2 · Die Leseregel.
--
-- Sie ist Vertragsbestandteil, nicht Beiwerk: es liegen MEHRERE VERSIONEN je
-- Teilprozess vor, weil status='fertig' bei BC1 final ist und BC1 deshalb
-- nachlegt statt zu korrigieren. Wer "irgendeine" Zeile liest, liest still die
-- falsche -- am 08.09.2026 etwa eine Zeile ohne die Testdaten-Kennzeichnung.
--
-- Gilt: die JUENGSTE Version je Fokus-Schritt mit status='fertig'.
-- 'in_erhebung' bedeutet, dass gerade jemand im Interview sitzt.
--
-- Nachlegen gewinnt immer: eine juengere fertige Version verdraengt die aeltere
-- auch dann, wenn ihr Rechengroessen fehlen (NULL nach aufgegebenem Nachfragen,
-- siehe README "Was BC1 zusagt"). Wer Werte braucht, prueft profil->'ungeloeste_felder'
-- der gelieferten Zeile -- nicht die aeltere Version.
--
-- Der Zuschnitt kommt aus dem Paket (paket_id -> v_uebergabe_offen), nicht aus
-- dieser Abfrage; hier steht nur, WELCHE Profilzeile fuer einen Teilprozess gilt.

SELECT DISTINCT ON (p.focus_step_id)
       p.company_id,
       p.focus_step_id,
       p.profil_version,
       p.process_id,
       p.status,
       p.erhebung_id,
       p.paket_version,
       p.frequency_per_year,
       p.executions_per_run,
       p.total_duration_minutes,
       p.focus_step_duration_minutes,
       p.focus_step_duration_source,
       p.focus_step_duration_confidence_pct,
       p.upstream_process_id,
       p.downstream_process_id,
       p.process_owner_rolle_id,
       p.erstellt_am,
       p.aktualisiert_am,
       p.profil
  FROM bc1.prozessprofil p
 WHERE p.company_id = %(company_id)s
   AND p.focus_step_id = ANY(%(focus_step_ids)s)
   AND p.status = 'fertig'
 ORDER BY p.focus_step_id, p.profil_version DESC;

-- Die Rollen dazu. In BC1s Etappe 1 liefert das NULL ZEILEN -- die Tabelle ist
-- strukturell abgenommen und leer. Eine leere Liste ist hier der Normalfall,
-- kein Fehler (siehe README, "Was BC1 heute nicht liefert").
--
-- SET CONSTRAINTS ist hier nicht noetig: der verzoegerte Fremdschluessel auf
-- mandant_rollen betrifft nur BC1s Schreibpfad.

SELECT r.focus_step_id,
       r.profil_version,
       r.pos,
       r.rolle_id,
       r.rolle_freitext,
       r.zeitanteil_pct
  FROM bc1.profil_rollen r
 WHERE r.company_id = %(company_id)s
   AND (r.focus_step_id, r.profil_version) IN (
           SELECT DISTINCT ON (p.focus_step_id) p.focus_step_id, p.profil_version
             FROM bc1.prozessprofil p
            WHERE p.company_id = %(company_id)s
              AND p.focus_step_id = ANY(%(focus_step_ids)s)
              AND p.status = 'fertig'
            ORDER BY p.focus_step_id, p.profil_version DESC)
 ORDER BY r.focus_step_id, r.pos;

-- NICHT SO die Bitkom-Bewertungen holen:
--
--     ... WHERE erhebung_id = <die ID aus dem Profil>     -- FALSCH
--
-- erhebung_id nennt die Erhebung mit dem juengsten Stand, NICHT die, aus der
-- alle aktuellen Bewertungen stammen. v_bewertung_aktuell ist itemweise
-- aktuell: aktuelle Bewertungen aus aelteren Erhebungen stehen daneben. Wer
-- ueber die eine ID laedt, sieht zu wenig (Klaerpunkt K-L, von BC1 am
-- 08.09.2026 an BC2 gestellt und hier bestaetigt). Bewertungen kommen aus
-- v_bewertung_aktuell; erhebung_id ist Herkunftsanker.
