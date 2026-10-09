-- ============================================================
-- BC2 · Migration bc2.3 — Sperrgrund und Hinweise statt Warnung
-- Ticket #306 · Entscheidung #305 (ADR-007 · BC2, Nachtrag) · Karte #158 · Stand 09.10.2026
-- ============================================================
--
-- Bis hierher lag in `bc2.lauf.warnung` zweierlei: warum ein Lauf nicht
-- geliefert werden kann (Messsatz, kein Potenzial) und was der Entscheider nur
-- wissen soll (Modellurteil). Jeder Text dort sperrte die Ablage — ein echter
-- Lauf kam darum nie im Lieferordner an. Jetzt sind es zwei Spalten:
--
--   sperrgrund  gesetzt heißt: nicht lieferbar. Freigeben lässt sich der Lauf
--               trotzdem; die Freigabe ist die Entscheidung des Menschen, der
--               Sperrgrund ein Merkmal des Laufs.
--   hinweise    nur Anzeige — Oberfläche, Titelfolie, Nachricht an BC3.
--
-- Ausführen mit der BC2-Rolle, wie bc2.2:
--
--     psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migration_bc2.3_sperrgrund.sql
--
-- Setzt bc2.2 voraus. Wiederholbar: ADD COLUMN IF NOT EXISTS, und die
-- Übertragung fasst nur Zeilen an, die noch nicht übertragen sind.

ALTER TABLE bc2.lauf ADD COLUMN IF NOT EXISTS sperrgrund text;
ALTER TABLE bc2.lauf ADD COLUMN IF NOT EXISTS hinweise   text[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN bc2.lauf.sperrgrund IS
  'Warum der Lauf nicht geliefert werden kann; NULL heisst lieferbar (ADR-007 · BC2, '
  'Nachtrag #305). Sperrt die Freigabe nicht, nur die Lieferung.';
COMMENT ON COLUMN bc2.lauf.hinweise IS
  'Was der Entscheider wissen soll, ohne dass es die Lieferung aufhaelt (Modellurteil u. a.).';

-- Die alten Zeilen. Einen Hinweis erkennt nur, wer seinen Text kennt: der echte
-- Weg schrieb das Modellurteil (laeufe.MODELLURTEIL), ggf. nach Hinweisen der
-- Erkennung. Alles andere wird **Sperrgrund** — im Zweifel nicht liefern, denn
-- was im Lieferordner liegt, gilt als übergeben (ADR-007 · BC2, 2.3). Der Lauf
-- ohne Potenzial schrieb das Modellurteil nicht und landet damit richtig.
UPDATE bc2.lauf
   SET hinweise = ARRAY[warnung]
 WHERE warnung IS NOT NULL
   AND sperrgrund IS NULL AND hinweise = '{}'
   AND warnung LIKE '%Schnitt und Bewertung sind Modellurteile%'
   AND warnung NOT LIKE 'Aus diesem Paket ist kein Potenzial geschnitten worden.%';

UPDATE bc2.lauf
   SET sperrgrund = warnung
 WHERE warnung IS NOT NULL
   AND sperrgrund IS NULL AND hinweise = '{}';

COMMENT ON COLUMN bc2.lauf.warnung IS
  'ABGELOEST seit bc2.3 (#306): wird nicht mehr geschrieben, uebertragen nach sperrgrund '
  'bzw. hinweise. Nicht geloescht, damit alte Zeilen lesbar bleiben.';
