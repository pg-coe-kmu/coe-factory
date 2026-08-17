-- ============================================================
-- BC0 Onboarding — Schema-Nachtrag v1.2 (Teil 2): Stammdaten und Freigabe-Gate
-- Stand: 11.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- Herkunft:
--   * Beschreibungsspalte je Kernprozess — Wunsch aus der BC1-Rückmeldung zu ADR-003
--   * Rollen und Kostensätze — ROI-Kostenachse, Kostenklassen K1–K5 beschlossen 11.08.2026
--   * Prozess-Schnittstellen — Verflechtung rechenbar machen (ROI über mehrere Prozesse)
--   * Gate-Ereignisse — HitL-Freigabe nach dem Meeting-Beschluss vom 10.08.2026
--
-- ADDITIV. Keine bestehende Spalte wird geändert, keine Zeile angefasst. Der Bestand
-- (1 Mandant, 10 Prozesse, 50 Teilprozesse, 600 Bewertungen) bleibt unberührt —
-- das ist bei ADR-003 die Grundregel.
--
-- REIHENFOLGE: Teil 1 (Benutzerverwaltung, schema_v1.2_benutzerverwaltung.sql) sollte
-- vorher eingespielt sein — gate_ereignisse verweist auf app_benutzer.
--
-- EINSPIELEN:
--   psql "$DATABASE_URL" -f schema_v1.2_stammdaten_und_gate.sql
-- Alle Anweisungen sind wiederholbar (IF NOT EXISTS / OR REPLACE).
-- ============================================================


-- ============================================================
-- 10. BESCHREIBUNG JE KERNPROZESS
-- ============================================================
-- Zweck: Der BC1-Interview-Bot muss auf Rückfrage erklären können, was ein
-- Kernprozess umfasst — und darf dabei nichts erfinden (Kern-Invariante von BC1).
-- Ein bis zwei Sätze je Prozess, gepflegt in der BC0-Oberfläche.

ALTER TABLE ref_prozesse ADD COLUMN IF NOT EXISTS beschreibung TEXT;

COMMENT ON COLUMN ref_prozesse.beschreibung IS
  'Ein bis zwei Sätze, was dieser Kernprozess umfasst. Quelle für die Erklärung '
  'durch den BC1-Interview-Bot. Gepflegt von BC0.';


-- ============================================================
-- 11. ROLLEN UND KOSTENSÄTZE (Mandantenstammdaten)
-- ============================================================
-- Zweck: Kostenachse der ROI-Rechnung. BC2 rechnet Zeit × Menge × Satz; der Satz
-- kommt von hier.
--
-- ABGRENZUNG: BC0 liefert das VOKABULAR (welche Rollen gibt es, welche Klasse,
-- was kostet die Klasse). WER an einem Schritt WIE LANGE arbeitet, erhebt BC1 —
-- das ist Aufwandserhebung und gehört zum Automatisierungs-Fragenkatalog.
--
-- WARUM ROLLEN UND KEINE PERSONEN: Für den ROI ist nicht relevant, was eine
-- bestimmte Person verdient, sondern was eine Stunde einer Tätigkeit kostet. Das
-- ist genau genug, von Natur aus pseudonymisiert (Entscheidung vom 06.08.2026)
-- und passt zur Erhebung bei BC1, die Rollen erfasst.
--
-- WARUM KLASSEN UND KEINE EINZELSÄTZE: In einem Betrieb mit 20 Beschäftigten ist
-- "Leiter Buchhaltung" eine Person; ein exakter Satz wäre faktisch ihr Gehalt.
-- Fünf Klassen sind für den ROI ausreichend und schließen den Rückschluss auf
-- Einzelpersonen weitgehend aus.

CREATE TABLE IF NOT EXISTS mandant_rollen (
  company_id   UUID NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  rolle_id     TEXT NOT NULL,              -- stabile ID, von BC0 vergeben (z. B. 'R-03')
  bezeichnung  TEXT NOT NULL,              -- 'Sachbearbeitung Auftragserfassung'
  klasse       TEXT NOT NULL CHECK (klasse IN ('K1','K2','K3','K4','K5')),
  hinweis      TEXT,                       -- optional: Abgrenzung, Beispiele
  aktiv        BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (company_id, rolle_id)
);
-- Nachtrag fuer Installationen, in denen die Tabelle vor dem 11.08.2026 entstand:
ALTER TABLE mandant_rollen ADD COLUMN IF NOT EXISTS aktiv BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN mandant_rollen.aktiv IS
  'Rollen werden GESPERRT, nicht geloescht. BC1 speichert die rolle_id im '
  'Prozessprofil; ein Verweis auf eine verschwundene Rolle waere nicht mehr '
  'aufloesbar, und ein ROI mit nicht zuordenbarem Kostensatz nicht '
  'reproduzierbar. Gleiche Ueberlegung wie bei app_benutzer.aktiv.';

COMMENT ON TABLE mandant_rollen IS
  'Rollen des Mandanten mit Kostenklasse. BC1 waehlt daraus im Interview und '
  'speichert die rolle_id statt eines Freitextes. Vorgezogener Teil des '
  'Entitaeten-Registers (#149) — Rollen sind Entitaeten und bekommen stabile IDs.';

CREATE INDEX IF NOT EXISTS idx_mandant_rollen_klasse ON mandant_rollen(company_id, klasse);

-- Kostenklassen (projektweit gleich, beschlossen 11.08.2026):
--   K1  gewerblich / Assistenz
--   K2  Sachbearbeitung
--   K3  Fachkraft / Spezialist
--   K4  Führung / Teamleitung
--   K5  Geschäftsführung

CREATE TABLE IF NOT EXISTS rollen_kostensaetze (
  company_id   UUID         NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  klasse       TEXT         NOT NULL CHECK (klasse IN ('K1','K2','K3','K4','K5')),
  satz_eur_h   NUMERIC(8,2) NOT NULL CHECK (satz_eur_h > 0),
  quelle       TEXT         NOT NULL
               CHECK (quelle IN ('erhoben','branchenreferenz','geschaetzt')),
  gueltig_ab   DATE         NOT NULL DEFAULT current_date,
  bemerkung    TEXT,                       -- z. B. angesetzter Gemeinkostenfaktor
  PRIMARY KEY (company_id, klasse, gueltig_ab)
);

COMMENT ON COLUMN rollen_kostensaetze.satz_eur_h IS
  'VOLLKOSTENSATZ, nicht Bruttolohn: enthaelt Arbeitgeberanteil, Ausfallzeiten '
  '(produktive Stunden 1500-1600 statt 2080) und Arbeitsplatzkosten. Typisch das '
  '1,7- bis 2,2-fache des Bruttostundenlohns. Der angesetzte Faktor gehoert in '
  'bemerkung — sonst ist der ROI nicht reproduzierbar.';

COMMENT ON COLUMN rollen_kostensaetze.quelle IS
  'Ein ROI aus Branchenreferenzwerten ist etwas anderes als einer aus den echten '
  'Zahlen des Mandanten. Gleiche Logik wie focus_step_duration_source bei BC1.';

COMMENT ON COLUMN rollen_kostensaetze.gueltig_ab IS
  'Im Schluessel, damit Satzaenderungen alte Rechnungen nicht rueckwirkend '
  'veraendern. Eine Freigabe haelt fest, mit welchem Stand gerechnet wurde.';

-- Jeweils gültiger Satz je Klasse (der jüngste, dessen gueltig_ab erreicht ist)
CREATE OR REPLACE VIEW v_rollen_kostensaetze_aktuell AS
SELECT DISTINCT ON (company_id, klasse)
       company_id, klasse, satz_eur_h, quelle, gueltig_ab, bemerkung
FROM rollen_kostensaetze
WHERE gueltig_ab <= current_date
ORDER BY company_id, klasse, gueltig_ab DESC;


-- ============================================================
-- 12. PROZESS-SCHNITTSTELLEN (Verflechtung mit IDs statt Freitext)
-- ============================================================
-- Zweck: Fuer eine ROI-Rechnung ueber mehrere Prozesse ("B lohnt erst nach A")
-- braucht es Kanten mit IDs. Vorhanden sind heute nur Freitexte:
-- ref_prozesse.input_text/output_text, ref_teilprozesse.schnittstellen — sichtbar
-- in v_crossfunktional, aber nicht rechenbar.
--
-- Nur BC0 kann diese Kanten sauber setzen, weil BC0 die Prozess-IDs vergibt
-- (ID-Hoheit, 06.08.2026). Fuer BC1 wird upstream_process/downstream_process
-- damit von Freitext zur Auswahl aus der Baseline.

CREATE TABLE IF NOT EXISTS prozess_schnittstellen (
  company_id       UUID       NOT NULL,
  von_process_id   VARCHAR(8) NOT NULL,
  nach_process_id  VARCHAR(8) NOT NULL,
  art              TEXT       NOT NULL
                   CHECK (art IN ('daten','freigabe','material','information')),
  beschreibung     TEXT,
  PRIMARY KEY (company_id, von_process_id, nach_process_id, art),
  FOREIGN KEY (company_id, von_process_id)
    REFERENCES ref_prozesse(company_id, process_id) ON DELETE CASCADE,
  FOREIGN KEY (company_id, nach_process_id)
    REFERENCES ref_prozesse(company_id, process_id) ON DELETE CASCADE,
  CHECK (von_process_id <> nach_process_id)
);

CREATE INDEX IF NOT EXISTS idx_schnittstellen_nach
  ON prozess_schnittstellen(company_id, nach_process_id);


-- ============================================================
-- 13. GATE-EREIGNISSE (HitL-Freigabe, append-only)
-- ============================================================
-- Beschluss vom 10.08.2026: Zwischen BC1-Anreicherung und BC2 sitzt eine
-- Freigabe durch einen Menschen. Nicht jeder abgeschlossene Interview-Durchlauf
-- geht automatisch weiter.
--
-- Kette:   BC0 erfasst -> BC1 reichert an -> HitL prueft und gibt frei
--          -> BC0 uebergibt das Paket an BC2 -> BC2 rechnet ROI
--
-- WARUM EREIGNISTABELLE UND KEIN STATUSFELD: Eine Freigabe ist ein Ereignis, keine
-- Eigenschaft. Ein ueberschriebenes Statusfeld verliert genau die Geschichte, die
-- den Nachweis ausmacht. Der aktuelle Stand ergibt sich als juengste Zeile (View
-- unten). Passt zu ADR-003: nichts wird ueberschrieben.
--
-- WARUM GENERISCH (Spalte `gate`): Im Projekt sind mehrere Gates vorgesehen. Eine
-- append-only Tabelle laesst sich spaeter nicht ohne Migration der bereits
-- geschriebenen Historie umbauen. Der offene Schnitt kostet heute nichts.
-- Die OBERFLAECHE wird ausdruecklich nur fuer bc0-bc2 gebaut; ob andere BCs diese
-- Tabelle mitnutzen, ist ihre Entscheidung.

CREATE TABLE IF NOT EXISTS gate_ereignisse (
  ereignis_id  BIGSERIAL   PRIMARY KEY,
  gate         TEXT        NOT NULL,        -- 'bc0-bc2', spaeter ggf. weitere
  company_id   UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  objekt_typ   TEXT        NOT NULL,        -- 'prozess'
  objekt_id    TEXT        NOT NULL,        -- KP-XX
  ereignis     TEXT        NOT NULL
               CHECK (ereignis IN ('freigegeben','widerrufen','zurueckgewiesen','uebergeben')),
  benutzer_id  TEXT        REFERENCES app_benutzer(benutzer_id),
  am           TIMESTAMPTZ NOT NULL DEFAULT now(),
  grundlage    JSONB,                       -- worauf entschieden wurde, siehe unten
  grund        TEXT,                        -- Pflicht bei 'zurueckgewiesen'
  paket_id     UUID,                        -- gesetzt bei 'uebergeben'
  CHECK (ereignis <> 'zurueckgewiesen' OR (grund IS NOT NULL AND length(btrim(grund)) > 0)),
  CHECK (ereignis <> 'uebergeben'      OR paket_id IS NOT NULL)
);

COMMENT ON COLUMN gate_ereignisse.grundlage IS
  'Der Datenstand, auf den sich die Entscheidung bezieht — bewusst JSONB, weil '
  'jedes Gate andere Kennzahlen festhaelt. Fuer bc0-bc2: bc1_profil_version, '
  'bc0_stand, reifegrad_fokusschritt, items_gesamt, roi_kernmenge_vollstaendig. '
  'Ohne diese Angabe laesst sich spaeter nicht sagen, WORAUF freigegeben wurde: '
  'schreibt BC1 danach nach, wurde etwas anderes freigegeben als BC2 liest.';

COMMENT ON COLUMN gate_ereignisse.paket_id IS
  'Klammert die Prozesse einer Uebergabe. Macht den Trigger an BC2 idempotent — '
  'zweimal ausgeloest darf BC2 nicht zweimal rechnen lassen.';

CREATE INDEX IF NOT EXISTS idx_gate_objekt
  ON gate_ereignisse(gate, company_id, objekt_id, am DESC);
CREATE INDEX IF NOT EXISTS idx_gate_paket
  ON gate_ereignisse(paket_id) WHERE paket_id IS NOT NULL;

-- Aktueller Freigabestand je Objekt: die juengste Zeile gewinnt.
CREATE OR REPLACE VIEW v_gate_freigabestand AS
SELECT DISTINCT ON (gate, company_id, objekt_id)
       gate, company_id, objekt_typ, objekt_id,
       ereignis   AS status,
       benutzer_id,
       am         AS status_seit,
       grundlage,
       grund,
       paket_id
FROM gate_ereignisse
ORDER BY gate, company_id, objekt_id, am DESC, ereignis_id DESC;


-- ============================================================
-- 14. GATE-DASHBOARD: BC0-Seite je Kernprozess
-- ============================================================
-- Grundlage der Freigabeansicht (Etappe 4d). Liefert je Kernprozess die
-- BC0-Kennzahlen und den daraus folgenden Sperrgrund.
--
-- SCHWELLEN (Projektsetzung, nicht Bitkom-Vorgabe — der Leitfaden gibt
-- ausdruecklich keine Handlungsempfehlungen vor und ueberlaesst die Ableitung
-- dem Anwender):
--   * Vollstaendigkeit  je Teilprozess >= 90 % der 30 Items, also >= 27
--   * Reifegrad         je Teilprozess >= 3,5 (Mittelwert; Bitkom aggregiert
--                       ausdruecklich ueber Mittelwerte, S. 20 des Leitfadens)
--
-- Die Teilprozess-Ebene ist die bindende: Wer sie erfuellt, erfuellt das
-- Kernprozess-Aggregat automatisch — umgekehrt nicht. So kann ein blinder Fleck
-- nicht von guten Nachbarn kompensiert werden.
--
-- items_unter_3 ist bewusst KEINE Sperre, sondern eine Warnzahl: Ein Mittelwert
-- von 3,5 kann gleichmaessig oder gespalten zustande kommen.
--
-- Die BC1-Seite (Pflichtfelder, ROI-Kernmenge, Profil-Version) fehlt hier noch —
-- sie kommt, sobald bc1.bc1_prozessprofil steht. Bis dahin zeigt die Oberflaeche
-- ehrlich "BC1 noch nicht angeliefert".

CREATE OR REPLACE VIEW v_gate_prozessstand AS
WITH tp AS (
  SELECT rt.company_id,
         rt.process_id,
         rt.sub_process_id,
         count(b.id)                                    AS items,
         round(avg(b.stufe)::numeric, 2)                AS reifegrad,
         count(*) FILTER (WHERE b.stufe < 3)            AS items_unter_3,
         (rt.medienbrueche IS NOT NULL
          AND length(btrim(rt.medienbrueche)) > 0)      AS hat_medienbruch
  FROM ref_teilprozesse rt
  LEFT JOIN bitkom_bewertungen b
    ON b.company_id     = rt.company_id
   AND b.sub_process_id = rt.sub_process_id
  GROUP BY rt.company_id, rt.process_id, rt.sub_process_id, rt.medienbrueche
)
SELECT rp.company_id,
       rp.process_id,
       rp.process_name,
       rp.kategorie::text                                   AS kategorie,
       rp.beschreibung,
       count(tp.sub_process_id)                             AS teilprozesse,
       sum(tp.items)                                        AS items_gesamt,
       min(tp.items)                                        AS items_schwaechster_tp,
       round(avg(tp.reifegrad), 2)                          AS reifegrad_kp,
       min(tp.reifegrad)                                    AS reifegrad_schwaechster_tp,
       sum(tp.items_unter_3)                                AS items_unter_3,
       count(*) FILTER (WHERE tp.hat_medienbruch)           AS tp_mit_medienbruch,
       CASE
         -- coalesce, weil ein Prozess ohne jeden Teilprozess NULL statt 0 ergaebe
         -- und dann durch den CASE bis zum ELSE durchfiele — also faelschlich als
         -- freigabefaehig gaelte. Im Zweifel sperren, nicht durchlassen.
         WHEN coalesce(count(tp.sub_process_id), 0) = 0 THEN 'nicht erhoben'
         WHEN coalesce(sum(tp.items), 0)          = 0 THEN 'nicht erhoben'
         WHEN coalesce(min(tp.items), 0)         < 27 THEN 'unvollstaendig'
         WHEN coalesce(min(tp.reifegrad), 0)    < 3.5 THEN 'reifegrad zu niedrig'
         ELSE                                              'bc0 ok'
       END                                                  AS bc0_sperre,
       coalesce(fs.status, 'offen')                         AS freigabe_status,
       fs.status_seit                                       AS freigabe_seit,
       fs.benutzer_id                                       AS freigabe_durch
FROM ref_prozesse rp
LEFT JOIN tp
  ON tp.company_id = rp.company_id
 AND tp.process_id = rp.process_id
LEFT JOIN v_gate_freigabestand fs
  ON fs.gate       = 'bc0-bc2'
 AND fs.company_id = rp.company_id
 AND fs.objekt_id  = rp.process_id
GROUP BY rp.company_id, rp.process_id, rp.process_name, rp.kategorie, rp.beschreibung,
         fs.status, fs.status_seit, fs.benutzer_id;


-- ============================================================
-- 15. LESERECHTE FÜR DIE BOUNDED CONTEXTS
-- ============================================================
-- Neue Tabellen und Views werden von ALTER DEFAULT PRIVILEGES nur erfasst, wenn
-- sie von der Rolle angelegt wurden, fuer die die Vorgabe gilt (siehe ROLLEN.md,
-- Schritt 6). Diese hier legt `postgres` an, deshalb einmalig nachziehen.
-- Lesen: alle. Schreiben: weiterhin nur BC0.

GRANT SELECT ON mandant_rollen,
                rollen_kostensaetze,
                v_rollen_kostensaetze_aktuell,
                prozess_schnittstellen,
                gate_ereignisse,
                v_gate_freigabestand,
                v_gate_prozessstand
      TO bc_leser;

-- Bewusst NICHT fuer bc_leser freigegeben: app_benutzer, app_benutzer_mandanten,
-- app_sitzungen. Wer die Baseline liest, muss nicht wissen, welche Menschen sie
-- erfasst haben.


-- ============================================================
-- Ende v1.2 Teil 2.
--
-- Offen fuer Teil 3 (sobald bc1.bc1_prozessprofil steht):
--   * BC1-Spalten in v_gate_prozessstand (Pflichtfelder, ROI-Kernmenge, Version)
--   * Entitaeten-Register vollstaendig (#149) — mandant_rollen ist ein Vorgriff
--   * spaltenbezogene GRANT UPDATE fuer die Anreicherung (#148, nach ADR-003 frei)
-- ============================================================
