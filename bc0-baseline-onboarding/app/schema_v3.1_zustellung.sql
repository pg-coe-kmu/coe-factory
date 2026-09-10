-- Schema v3.1 — Zustellung an BC2: Protokoll und Wiederholung (08.09.2026)
--
-- Beschluss Projektmeeting 07.09.2026: **REST-API fuer die BC2-Aktivierung,
-- JSON-IDs statt Datei-Check.** Beim Schnueren des Pakets ruft BC0 den
-- BC2-Dienst und uebergibt NUR die Kennungen: company_id, paket_id,
-- uebergeben_am. Die Daten holt BC2 mit der paket_id selbst.
--
-- Warum nur Kennungen: Eine Nachricht ist nicht wiederholbar lesbar, ein
-- Zustand schon. Die Nachricht ist der Zettel mit der Nummer, nicht der
-- Inhalt — die Datenbank bleibt alleinige Quelle (ADR-003 Regel 4).
-- v_uebergabe_offen bleibt die Rueckfallebene: **ein verpasster Ruf ist kein
-- verlorenes Paket.**
--
-- Was hier entsteht, ist NUR das Protokoll. Zieladresse und Geheimnis stehen
-- bewusst NICHT in der Datenbank, sondern in der .env des Servers
-- (BC2_HOOK_URL, BC2_HOOK_SECRET) — ein Geheimnis gehoert nicht in eine
-- Tabelle, die vier Kontexte lesen duerfen.
--
-- Rein additiv. Ausfuehren: als Eigentuemer, in einer Transaktion.

BEGIN;

-- Append-only: jeder Versuch steht drin, auch der gescheiterte. Ohne das
-- waere "wir haben gerufen" eine Behauptung. Kein UPDATE, kein DELETE —
-- dieselbe Regel wie am Gate.
CREATE TABLE IF NOT EXISTS bc_zustellungen (
  zustellung_id BIGSERIAL PRIMARY KEY,
  company_id    UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  paket_id      UUID        NOT NULL,
  ziel_bc       TEXT        NOT NULL CHECK (ziel_bc IN ('bc2','bc3','bc4')),
  ziel_url      TEXT,                                  -- ohne Geheimnis, nur der Ort
  versuch       INTEGER     NOT NULL DEFAULT 1 CHECK (versuch > 0),
  ergebnis      TEXT        NOT NULL CHECK (ergebnis IN ('zugestellt','fehler','kein_ziel')),
  http_code     INTEGER,
  meldung       TEXT,                                  -- Fehlertext, gekuerzt
  gesendet_am   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE bc_zustellungen IS
  'Protokoll der aktiven Rufe an BC2 (Beschluss 07.09.2026). Append-only. '
  'kein_ziel = es ist keine Adresse hinterlegt, also wurde nicht gerufen — '
  'das ist kein Fehler, sondern ein Zustand, und er soll sichtbar sein.';

CREATE INDEX IF NOT EXISTS ix_zustellung_paket ON bc_zustellungen (company_id, paket_id);

-- Was ist offen? Ein Paket gilt als zugestellt, sobald EIN Versuch
-- 'zugestellt' war. Alles andere steht hier — mit Anzahl der Versuche und
-- dem letzten Ergebnis, damit man sieht, ob es klemmt oder nur wartet.
CREATE OR REPLACE VIEW v_zustellung_offen AS
SELECT p.company_id,
       p.paket_id,
       p.uebergeben_am,
       coalesce(z.versuche, 0)                     AS versuche,
       z.letztes_ergebnis,
       z.letzte_meldung,
       z.zuletzt_am
  FROM gate_pakete p
  LEFT JOIN LATERAL (
         -- Sortiert wird nach Zeitstempel UND laufender Nummer. Der
         -- Zeitstempel allein genuegt nicht: `now()` ist der Beginn der
         -- Transaktion, zwei Versuche im selben Vorgang tragen also
         -- denselben Wert — und dann entschied der Zufall, welcher als
         -- "letzter" galt. Aufgefallen am 08.09.2026 in Probe 3.
         SELECT count(*)                                        AS versuche,
                max(gesendet_am)                                AS zuletzt_am,
                (array_agg(ergebnis ORDER BY gesendet_am DESC, zustellung_id DESC))[1] AS letztes_ergebnis,
                (array_agg(meldung  ORDER BY gesendet_am DESC, zustellung_id DESC))[1] AS letzte_meldung
           FROM bc_zustellungen z2
          WHERE z2.company_id = p.company_id AND z2.paket_id = p.paket_id
            AND z2.ziel_bc = 'bc2') z ON TRUE
 WHERE NOT EXISTS (SELECT 1 FROM bc_zustellungen z3
                    WHERE z3.company_id = p.company_id AND z3.paket_id = p.paket_id
                      AND z3.ziel_bc = 'bc2' AND z3.ergebnis = 'zugestellt');

COMMENT ON VIEW v_zustellung_offen IS
  'Pakete, die BC2 noch nicht bestaetigt bekommen hat. Grundlage fuer die '
  'Wiederholung — und der Beleg, dass ein verpasster Ruf kein verlorenes '
  'Paket ist: das Paket steht weiterhin in v_uebergabe_offen.';

COMMIT;

-- Gegenprobe:
--   \d bc_zustellungen
--   SELECT * FROM v_zustellung_offen WHERE company_id = '<uuid>';
