-- ============================================================
-- BC0 — v2.2: Die Prozesslandkarte wird veraenderbar,
--             die Anfrage bekommt einen Status
-- Stand: 27.08.2026 · Autor: Simeon Ehmer
-- ============================================================
--
-- Rein additiv. Nimmt nichts weg, aendert keinen Primaerschluessel,
-- beruehrt keine bestehende Zeile. Der einzige veraenderte CHECK
-- (`step_no`) wird WEITER, nicht enger — jeder Bestandsdatensatz
-- erfuellt ihn weiterhin.
--
-- WOZU
--   Am 26.08. beim Entwurf des Anfrage-Zugangs gefunden: Die Anwendung
--   kann eine Prozesslandkarte nicht wachsen lassen. Ein elfter
--   Kernprozess laeuft in einen IndexError, ein sechster Teilprozess
--   scheitert am CHECK auf `step_no`, und ein wegfallender Prozess
--   laesst sich nicht stilllegen, weil das Merkmal fehlt.
--
--   Das ist kein Randfall. Es ist die Folge des eigenen Erfolgs:
--   Automatisierung veraendert die Landschaft, die sie vermessen hat.
--   Ein CoE, das wirkt, erzeugt genau den Fall, den sein Werkzeug
--   heute nicht kann.
--
-- WAS DIESE DATEI TUT
--   Sie macht die Landkarte WACHSEN und SCHRUMPFEN faehig — mehr
--   Kernprozesse, bis zu neun Teilprozesse, Stilllegen statt Loeschen.
--   Und sie legt `prozess_herkunft` an, damit nachvollziehbar bleibt,
--   was woraus wurde.
--
-- DIE REGEL DAHINTER STEHT SCHON UND WIRD HIER NUR DURCHGESETZT
--
--   1. Die Ursprungs-ID wird ueber ALLE Bounded Contexts mitgefuehrt.
--      Nicht als Bitte, sondern als Anforderung: BC1 bis BC4 tragen sie
--      in ihren Profilen, ROI-Rechnungen, Tickets und Bauteilen mit.
--      Ohne sie ist nach vier Kontexten nicht mehr feststellbar, worauf
--      sich eine Empfehlung eigentlich bezieht.
--
--   2. Bestehende Bewertungen werden NICHT angefasst.
--      Kein UPDATE, kein Kopieren, kein Umhaengen. Erhoben wurde damals
--      dieser Schritt; eine Bewertung umzuhaengen hiesse zu behaupten,
--      jemand haette etwas beurteilt, das es zum Erhebungszeitpunkt
--      nicht gab.
--
--   Beides folgt aus ADR-005 (Herkunftsnachweis), hier auf die STRUKTUR
--   angewandt statt auf die Werte. Es ist keine neue Entscheidung.
--
--   Was daraus folgt, ohne dass es eigens beschlossen werden muesste:
--     - Ein neu entstandener Teilprozess startet UNBEWERTET und ist
--       damit nicht freigabefaehig — das Gate verlangt 27 von 30. Das
--       ist richtig so: Er wurde nie erhoben.
--     - Eine erteilte Gate-Freigabe haengt an der alten ID und wandert
--       nicht mit. Sie bleibt lesbar, sie gilt nur nicht weiter.
--     - Der Zeitvergleich laeuft ueber die Kette, MIT dem Hinweis, dass
--       sich die Struktur an einem bestimmten Tag geaendert hat.
--
-- WARUM NEUN UND NICHT MEHR
--   Das ID-Muster erlaubt `TP-[0-9]+`, also auch `TP-12`. ADR-002 legt
--   den TP-Teil trotzdem als EINSTELLIG fest, und die Sortierung gibt
--   ihm recht: Bei gemischt ein- und zweistelliger Schreibweise steht
--   `TP-10` vor `TP-2`. Wer ueber neun hinaus will, aendert ADR-002 UND
--   zieht ueberall eine Sortierlogik nach. Neun ist deshalb eine
--   Entscheidung, kein Zufall.
--
-- Gegenproben am Dateiende.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. step_no: die harte Grenze bei fuenf faellt
-- ------------------------------------------------------------
-- Der alte CHECK heisst je nach Entstehungsweg anders. Deshalb wird er
-- ueber den Spaltenbezug gesucht und nicht ueber einen geratenen Namen:
-- Ein DROP CONSTRAINT IF EXISTS auf einen falschen Namen wuerde
-- schweigend nichts tun, und der Block darunter liefe ins Leere.

DO $$
DECLARE c_name TEXT;
BEGIN
  SELECT con.conname INTO c_name
    FROM pg_constraint con
    JOIN pg_attribute att
      ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
   WHERE con.conrelid = 'ref_teilprozesse'::regclass
     AND con.contype  = 'c'
     AND att.attname  = 'step_no'
   LIMIT 1;

  IF c_name IS NOT NULL THEN
    EXECUTE format('ALTER TABLE ref_teilprozesse DROP CONSTRAINT %I', c_name);
    RAISE NOTICE 'Alter step_no-CHECK entfernt: %', c_name;
  ELSE
    RAISE NOTICE 'Kein step_no-CHECK gefunden — es wird nur der neue gesetzt.';
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_teilprozess_step_no') THEN
    ALTER TABLE ref_teilprozesse ADD CONSTRAINT ck_teilprozess_step_no
      CHECK (step_no BETWEEN 1 AND 9);
  END IF;
END $$;

-- ------------------------------------------------------------
-- 2. aktiv: stilllegen statt loeschen
-- ------------------------------------------------------------
-- `mandant_systeme` und `mandant_rollen` haben das Merkmal seit v1.3.
-- Bei den Prozessen fehlt es ohne erkennbaren Grund — und die Folge ist
-- schwerwiegender: Ein geloeschter Teilprozess nimmt ueber
-- ON DELETE CASCADE seine 30 Bewertungen mit. Ein stillgelegter nicht.
--
-- DEFAULT true, damit der Bestand unveraendert bleibt: Alles, was heute
-- existiert, gilt weiter als aktiv.

ALTER TABLE ref_prozesse      ADD COLUMN IF NOT EXISTS aktiv BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE ref_teilprozesse  ADD COLUMN IF NOT EXISTS aktiv BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN ref_prozesse.aktiv IS
  'FALSE = stillgelegt. Der Prozess verschwindet aus Auswahllisten und '
  'aus der Erhebung, bleibt aber mit allen Bewertungen, Belegen und '
  'Gate-Ereignissen erhalten. Loeschen ist der falsche Weg: Es nimmt '
  'die Vergangenheit mit.';

COMMENT ON COLUMN ref_teilprozesse.aktiv IS
  'FALSE = stillgelegt. Siehe ref_prozesse.aktiv. Ein stillgelegter '
  'Teilprozess ist NICHT freigabefaehig — das Gate prueft ihn nicht '
  'mehr, seine alten Entscheidungen bleiben aber lesbar.';

-- ------------------------------------------------------------
-- 3. prozess_herkunft: was wurde woraus?
-- ------------------------------------------------------------
-- n:m und nicht eine Spalte, weil eine Teilung MEHRERE Nachfolger und
-- eine Zusammenlegung MEHRERE Vorgaenger hat.
--
-- Die Bewertungen bleiben, wo sie erhoben wurden — siehe Regel 2 im
-- Kopf. Was fehlt, ist nicht das Umhaengen, sondern die KETTE. Mit ihr
-- wird moeglich, was ohne sie abreisst:
--   - Zeitvergleich ueber `ref_erhebungen` laeuft ueber den Bruch
--     hinweg, MIT dem Hinweis, dass sich die Struktur geaendert hat
--   - Das Gate kann sagen: "Fuer diesen Teilprozess liegt keine eigene
--     Bewertung vor. Sein Vorgaenger stand am TT.MM. bei X,XX."
--   - BC2, BC3 und BC4 fuehren die Ursprungs-ID mit — dieselbe
--     Herkunftslogik wie ADR-005, nur auf die STRUKTUR angewandt
--     statt auf die Werte.
--
-- Bewusst OHNE Fremdschluessel auf `ref_teilprozesse`: Ein Vorgaenger
-- kann geloescht worden sein, bevor diese Tabelle existierte, und die
-- Herkunft soll auch dann noch lesbar sein. Die Kette ist ein Protokoll,
-- kein Beziehungsgeflecht.

CREATE TABLE IF NOT EXISTS prozess_herkunft (
  company_id     UUID        NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
  nachfolger_id  TEXT        NOT NULL,
  vorgaenger_id  TEXT        NOT NULL,
  art            TEXT        NOT NULL,
  gueltig_ab     DATE        NOT NULL,
  grund          TEXT        NOT NULL,
  erfasst_am     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (company_id, nachfolger_id, vorgaenger_id, gueltig_ab)
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_herkunft_art') THEN
    ALTER TABLE prozess_herkunft ADD CONSTRAINT ck_herkunft_art
      CHECK (art IN ('geteilt','zusammengelegt','umbenannt','umgehaengt','stillgelegt'));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_herkunft_grund') THEN
    ALTER TABLE prozess_herkunft ADD CONSTRAINT ck_herkunft_grund
      CHECK (length(btrim(grund)) > 0);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_herkunft_nicht_selbst') THEN
    ALTER TABLE prozess_herkunft ADD CONSTRAINT ck_herkunft_nicht_selbst
      CHECK (nachfolger_id <> vorgaenger_id);
  END IF;
END $$;

COMMENT ON TABLE prozess_herkunft IS
  'Protokoll der Strukturaenderungen. Die Bedingung, unter der eine '
  'Landkarte sich aendern darf, ist nicht, dass nichts verloren geht — '
  'sondern dass nachvollziehbar bleibt, was woraus wurde. '
  'Verbindlich: Die Ursprungs-ID wird ueber alle Bounded Contexts '
  'mitgefuehrt, bestehende Bewertungen werden nicht angefasst.';

COMMENT ON COLUMN prozess_herkunft.grund IS
  'Pflichtfeld, nicht leer. Gleiche Begruendung wie bei '
  'bitkom_bewertungen.beleg: Wer eine Struktur aendert, soll in einem '
  'Satz sagen, warum. In sechs Monaten weiss es sonst niemand mehr.';

COMMENT ON COLUMN prozess_herkunft.art IS
  'geteilt · zusammengelegt · umbenannt · umgehaengt · stillgelegt. '
  'umgehaengt ist strukturell immer ein Neuanlegen: Die Teilprozess-ID '
  'traegt den Kernprozess in sich, KP-05.TP-1 kann nicht zu KP-06 '
  'wandern. Das ist der Preis sprechender IDs und er ist es wert.';

-- ------------------------------------------------------------
-- 4. Status der Anfrage
-- ------------------------------------------------------------
-- `ref_anfragen` hat seit v1.4 keinen Status. Damit kann niemand sagen,
-- wo eine Anfrage steht — und der Anfragende erfaehrt nie etwas. Ohne
-- Status ist die Anfrage ein Eintrag ohne Leben; mit Status ist sie der
-- Faden, an dem die ganze Kette haengt.
--
-- Die Werteliste bildet die Kette ab, MIT Gate 0 zwischen BC1 und BC2:
--   eingegangen -> zugeordnet -> im_interview -> am_gate
--               -> bewertet -> beauftragt -> erledigt | abgelehnt
--
-- DEFAULT 'eingegangen': Bestandszeilen bekommen den Anfangszustand,
-- was fuer die drei Testdaten-Anfragen vom 24.08. zutrifft.

ALTER TABLE ref_anfragen ADD COLUMN IF NOT EXISTS status          TEXT NOT NULL DEFAULT 'eingegangen';
ALTER TABLE ref_anfragen ADD COLUMN IF NOT EXISTS status_seit     DATE;
ALTER TABLE ref_anfragen ADD COLUMN IF NOT EXISTS erhofftes_ziel  TEXT;
ALTER TABLE ref_anfragen ADD COLUMN IF NOT EXISTS ausloeser        TEXT;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_anfrage_status') THEN
    ALTER TABLE ref_anfragen ADD CONSTRAINT ck_anfrage_status
      CHECK (status IN ('eingegangen','zugeordnet','im_interview','am_gate',
                        'bewertet','beauftragt','erledigt','abgelehnt'));
  END IF;
END $$;

COMMENT ON COLUMN ref_anfragen.status IS
  'eingegangen -> zugeordnet -> im_interview -> am_gate -> bewertet -> '
  'beauftragt -> erledigt | abgelehnt. Gate 0 steht ZWISCHEN Interview '
  'und ROI-Rechnung, nicht dahinter: Ein ROI vor der Freigabe hebt den '
  'Sinn des Gates auf.';

COMMENT ON COLUMN ref_anfragen.erhofftes_ziel IS
  'Was sich der Anfragende davon verspricht, in einem Satz. Der '
  'Originaltext beschreibt fast immer das PROBLEM; woran am Ende '
  'gemessen wird, ob die Kette geliefert hat, steht selten darin — und '
  'niemand fragt spaeter danach.';

COMMENT ON COLUMN ref_anfragen.ausloeser IS
  'Warum jetzt? Jemand ist ausgeschieden, ein Kunde hat sich beschwert, '
  'eine Pruefung steht an. Erklaert die Dringlichkeit besser als jede '
  'Prioritaetsstufe und ist in vier Wochen nicht mehr rekonstruierbar.';

-- Bewusst CHECK und kein ENUM: Ein weiterer Status ist eine additive
-- Erweiterung, ein ENUM-Wert waere ein Typumbau. Gleiche Begruendung
-- wie bei zuordnung_quelle in v2.1.

-- ------------------------------------------------------------
-- 5. Leserechte
-- ------------------------------------------------------------
-- prozess_herkunft enthaelt keine personenbezogenen Daten — nur IDs,
-- Datum und einen Satz Begruendung. Sie gehoert zu den Registern, die
-- alle BCs lesen duerfen: Ohne sie koennen BC2 bis BC4 die Ursprungs-ID
-- nicht mitfuehren, und genau das ist der Zweck.

GRANT SELECT ON prozess_herkunft TO bc_leser;

COMMIT;

-- ============================================================
-- GEGENPROBEN
-- ============================================================
-- Erwartet: 1..9 statt 1..5
-- SELECT pg_get_constraintdef(oid) FROM pg_constraint
--  WHERE conname = 'ck_teilprozess_step_no';
--
-- Erwartet: zweimal aktiv, beide NOT NULL mit DEFAULT true
-- SELECT table_name, column_name, is_nullable, column_default
--   FROM information_schema.columns
--  WHERE column_name = 'aktiv'
--    AND table_name IN ('ref_prozesse','ref_teilprozesse');
--
-- Erwartet: alles aktiv — kein Bestandsdatensatz wurde stillgelegt
-- SELECT count(*) FILTER (WHERE aktiv) AS aktiv,
--        count(*) FILTER (WHERE NOT aktiv) AS still
--   FROM ref_teilprozesse;
--
-- Erwartet: unveraendert. Je Mandant getrennt zaehlen —
-- eine Zahl ohne Mandantenbezug ist seit dem Uebungsmandanten wertlos.
-- SELECT c.name, count(*) FROM ref_teilprozesse t
--   JOIN companies c ON c.company_id = t.company_id GROUP BY c.name ORDER BY c.name;
-- SELECT c.name, count(*) FROM bitkom_bewertungen b
--   JOIN companies c ON c.company_id = b.company_id GROUP BY c.name ORDER BY c.name;
--
-- Erwartet: acht Status, DEFAULT eingegangen
-- SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck_anfrage_status';
-- SELECT anfrage_id, status FROM ref_anfragen ORDER BY anfrage_id;
--
-- Erwartet: FEHLER (leerer Grund)
-- INSERT INTO prozess_herkunft(company_id,nachfolger_id,vorgaenger_id,art,gueltig_ab,grund)
-- VALUES ('<mandant>','KP-06.TP-6','KP-06.TP-2','geteilt',current_date,'   ');
--
-- Erwartet: FEHLER (Nachfolger gleich Vorgaenger)
-- INSERT INTO prozess_herkunft(company_id,nachfolger_id,vorgaenger_id,art,gueltig_ab,grund)
-- VALUES ('<mandant>','KP-06.TP-2','KP-06.TP-2','umbenannt',current_date,'Probe');
--
-- Erwartet: geht jetzt (sechster Teilprozess)
-- INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation)
-- VALUES ('<mandant>','KP-06.TP-6','KP-06',6,'Probe','');
-- DELETE FROM ref_teilprozesse WHERE sub_process_id = 'KP-06.TP-6';
--
-- Erwartet: FEHLER (zehnter Teilprozess — ADR-002, einstellig)
-- INSERT INTO ref_teilprozesse(company_id,sub_process_id,process_id,step_no,sub_process_name,notation)
-- VALUES ('<mandant>','KP-06.TP-10','KP-06',10,'Probe','');
-- ============================================================
