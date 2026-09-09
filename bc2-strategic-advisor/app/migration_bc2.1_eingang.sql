-- ============================================================
-- BC2 · Migration bc2.1 — Eingangsprotokoll für BC0s Paket-Anstoß
-- Ticket #190 · Karte #158 · Stand 10.09.2026
-- ============================================================
--
-- Legt die eine Tabelle an, die der Trigger-Endpunkt braucht. Sie nimmt dem
-- späteren Entwurf von Schema `bc2` (#187) nichts vorweg: die Rohnutzlast
-- aufzuheben ist unabhängig davon richtig, weil sie das einzige Protokoll
-- dessen ist, was BC0 tatsächlich geschickt hat.
--
-- Ausführen mit der BC2-Rolle. Sie hat CREATE ausschließlich auf `bc2`
-- (ADR-003); auf `public` und `bc1`…`bc4` nur SELECT.
--
--     psql "$DATABASE_URL" -f migration_bc2.1_eingang.sql
--
-- Die Datei ist wiederholbar (IF NOT EXISTS durchgehend).

CREATE SCHEMA IF NOT EXISTS bc2;

CREATE TABLE IF NOT EXISTS bc2.eingang (
  -- Primärschlüssel, nicht bloß ein Index: **die Idempotenz aus #190 wird hier
  -- durchgesetzt, nicht im Anwendungscode.** Zwei gleichzeitige Aufrufe mit
  -- derselben Paket-ID können sich nicht überholen — einer gewinnt, der andere
  -- läuft ins ON CONFLICT. Ein Prüf-dann-Schreib im Python wäre genau hier
  -- offen.
  paket_id       text        PRIMARY KEY,

  company_id     text        NOT NULL,

  -- Der Zeitstempel, den BC0 mitschickt. **Protokollangabe, kein
  -- Zeitreise-Anker** (#165) — allerdings ist genau das seit dem 09.09.2026
  -- strittig: BC0s Code kennt `stand_zum()` und kommentiert „das Datum am Paket
  -- ist der Zeitpunkt, fuer den BC2 mit stand_zum() liest", die Antwort an #165
  -- sagt das Gegenteil. Rückfrage an Simeon läuft. Für diese Tabelle ist es
  -- gleich: sie hebt den Wert roh auf, egal wie er später gelesen wird.
  uebergeben_am  timestamptz NOT NULL,

  angenommen_am  timestamptz NOT NULL DEFAULT now(),

  -- Über welchen der beiden Wege das Paket hereinkam. Nicht in der
  -- Entscheidungstabelle von #190 aufgeführt, aber der einzige Weg, später zu
  -- sehen, ob BC0s Push tatsächlich funktioniert oder ob durchweg der
  -- Nachhol-Abgleich einspringt. Ohne die Spalte sähen beide Fälle gleich aus.
  quelle         text        NOT NULL DEFAULT 'push'
                             CHECK (quelle IN ('push', 'nachgeholt')),

  status         text        NOT NULL DEFAULT 'angenommen'
                             CHECK (status IN ('angenommen', 'in_arbeit', 'fertig', 'fehler')),

  -- Die Anfrage, wie sie ankam — unverändert, samt unbekannter Felder. Der
  -- Endpunkt ist tolerant (#190): Unbekanntes wird nicht abgewiesen, sondern
  -- protokolliert. Wenn BC0 morgen ein Feld ergänzt, steht es hier, auch wenn
  -- BC2 es noch nicht liest.
  nutzlast       jsonb       NOT NULL
);

COMMENT ON TABLE bc2.eingang IS
  'Eingangsprotokoll fuer BC0s Paket-Anstoss (#190). Ein Datensatz je Paket-ID. '
  'Briefkasten, nicht Arbeitsvorrat: hier wird nichts gerechnet.';

COMMENT ON COLUMN bc2.eingang.nutzlast IS
  'Die rohe Anfrage von BC0, unveraendert. Einziges Protokoll dessen, was '
  'tatsaechlich geschickt wurde.';

COMMENT ON COLUMN bc2.eingang.quelle IS
  'push = BC0 hat aufgerufen; nachgeholt = BC2 hat es selbst aus '
  'public.v_uebergabe_offen geholt.';

-- Der Nachhol-Abgleich fragt „welche Pakete dieser Firma kenne ich schon?".
CREATE INDEX IF NOT EXISTS eingang_company_idx
  ON bc2.eingang (company_id, uebergeben_am DESC);
