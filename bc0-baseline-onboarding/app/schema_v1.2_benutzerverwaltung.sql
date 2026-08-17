-- ============================================================
-- BC0 Onboarding — Schema-Nachtrag v1.2 (Teil 1): Benutzerverwaltung
-- Stand: 10.08.2026 · Autor: Simeon Ehmer · PostgreSQL >= 15
--
-- Herkunft: Aufgabe 4 aus dem Team-Meeting vom 10.08.2026, Etappe 4a.
-- Bis dahin war die Anwendung ohne Anmeldung erreichbar und schreibbar.
--
-- ADDITIV. Keine bestehende Tabelle wird geändert, keine Zeile angefasst.
-- Der Bestand (1 Mandant, 10 Prozesse, 50 Teilprozesse, 600 Bewertungen)
-- bleibt unberührt — das ist bei ADR-003 die Grundregel und gilt auch hier.
--
-- AUSFÜHRUNG
--   Nicht zwingend erforderlich: Die Anwendung legt diese Tabellen beim Start
--   selbst an (bc0_auth/repository.py, CREATE TABLE IF NOT EXISTS). Diese Datei
--   ist der dokumentierte Vollstand — damit das Schema vollständig aus SQL
--   lesbar ist und nicht nur aus dem Python-Quelltext. Beides muss übereinstimmen;
--   Abweichungen fallen beim Ist-Abgleich auf (siehe den Befund vom 07.08.2026,
--   der zu v1.1.1 geführt hat).
--
-- ABGRENZUNG
--   Teil 2 von v1.2 (Freigabeverwaltung: ref_prozesse um freigabe_status,
--   freigegeben_am, freigegeben_durch) folgt mit Etappe 4d.
--   Das Entitäten-Register (#149) ist ebenfalls für v1.2 vorgesehen.
-- ============================================================

-- ============================================================
-- 9. BENUTZERVERWALTUNG (Anwendungsschicht)
-- ============================================================
-- Namensregel: Tabellen mit dem Präfix `app_` gehören zur Anwendungsschicht und
-- nicht zu den Fachdaten. Die Leserolle `bc_leser` und damit BC1–BC4 brauchen
-- keinen Zugriff darauf — wer die Baseline liest, muss nicht wissen, welche
-- Menschen sie erfasst haben.

CREATE TABLE IF NOT EXISTS app_benutzer (
  benutzer_id       TEXT PRIMARY KEY,             -- UUID als Text, von der Anwendung vergeben
  email             TEXT NOT NULL UNIQUE,         -- Anmeldename, immer kleingeschrieben abgelegt
  name              TEXT NOT NULL,                -- Anzeigename; erscheint später in freigegeben_durch
  passwort_hash     TEXT NOT NULL,                -- pbkdf2_sha256$<durchlaeufe>$<salz>$<abdruck>
  rolle             TEXT NOT NULL CHECK (rolle IN ('benutzer','admin')),
  aktiv             BOOLEAN NOT NULL DEFAULT TRUE,-- gesperrt statt gelöscht, siehe unten
  angelegt_am       TIMESTAMPTZ NOT NULL DEFAULT now(),
  letzte_anmeldung  TIMESTAMPTZ
);

-- Warum gesperrt statt gelöscht:
--   freigegeben_durch (Etappe 4d) verweist auf benutzer_id. Ein Nachweis, dessen
--   Urheber gelöscht wurde, ist kein Nachweis mehr. Ausgeschiedene Personen
--   werden deshalb auf aktiv = FALSE gesetzt.

-- Warum der Hash als Text und nicht in Einzelspalten:
--   Verfahren und Kostenparameter stehen im Wert selbst. Wird der Parameter
--   später erhöht, bleiben alte Hashes gültig und werden bei der nächsten
--   erfolgreichen Anmeldung still nachgezogen. Eine Migration entfällt.

-- ------------------------------------------------------------
-- Mandantenzuordnung (n:m)
-- ------------------------------------------------------------
-- Die Regel aus dem Meeting lautet „Benutzer sieht nur sein Unternehmen" — im
-- Regelfall also genau eine Zeile je Benutzer. Die Entscheidung vom 06.08.2026
-- spricht dagegen von „seinen Mandanten" (Mehrzahl), etwa für eine Beraterin,
-- die mehrere Unternehmen betreut. Die n:m-Tabelle deckt beides ab und kostet
-- gegenüber einer Spalte in app_benutzer nur diese eine Tabelle.
--
-- Ein Admin braucht hier keine Einträge: Er sieht alle Mandanten.

CREATE TABLE IF NOT EXISTS app_benutzer_mandanten (
  benutzer_id  TEXT NOT NULL REFERENCES app_benutzer(benutzer_id) ON DELETE CASCADE,
  company_id   UUID NOT NULL REFERENCES companies(company_id)     ON DELETE CASCADE,
  PRIMARY KEY (benutzer_id, company_id)
);

-- ------------------------------------------------------------
-- Sitzungen
-- ------------------------------------------------------------
-- Serverseitige Sitzungen statt eines signierten Tokens (JWT). Der Grund ist die
-- Widerrufbarkeit: Ein JWT bleibt bis zum Ablauf gültig, auch wenn das Konto
-- inzwischen gesperrt wurde. Eine Zeile in dieser Tabelle lässt sich löschen —
-- und die Sitzung ist sofort beendet. Bei der hier vorliegenden Zugriffszahl ist
-- die zusätzliche Abfrage je Anfrage ohne Belang.
--
-- WICHTIG: Gespeichert wird nur der SHA-256-Abdruck des Sitzungsschlüssels,
-- nicht der Schlüssel selbst. Wer diese Tabelle lesen kann — etwa über ein
-- Backup —, kann damit keine fremde Sitzung übernehmen.

CREATE TABLE IF NOT EXISTS app_sitzungen (
  sitzung_id         TEXT PRIMARY KEY,
  benutzer_id        TEXT NOT NULL REFERENCES app_benutzer(benutzer_id) ON DELETE CASCADE,
  schluessel_abdruck TEXT NOT NULL UNIQUE,        -- SHA-256 des Schlüssels, hex
  angelegt_am        TIMESTAMPTZ NOT NULL DEFAULT now(),
  laeuft_ab          TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sitzung_benutzer ON app_sitzungen(benutzer_id);

-- ============================================================
-- Betriebshinweise
-- ============================================================
-- Erster Zugang (auf dem Server, nicht über die Oberfläche):
--   docker compose exec app python benutzer_verwalten.py anlegen \
--     --email <adresse> --name "<Name>" --rolle admin
--
-- Es wird bewusst kein Standardkonto angelegt. Ein vorkonfigurierter Zugang mit
-- bekanntem Passwort wäre die verwundbarste Stelle der Anwendung.
--
-- Prüfen, wer Zugang hat:
--   SELECT email, rolle, aktiv, letzte_anmeldung FROM app_benutzer ORDER BY email;
--
-- Offene Sitzungen einsehen (ohne Schlüssel, der steht nirgends im Klartext):
--   SELECT b.email, s.angelegt_am, s.laeuft_ab
--     FROM app_sitzungen s JOIN app_benutzer b USING (benutzer_id)
--    ORDER BY s.angelegt_am DESC;
--
-- Alle Sitzungen sofort beenden (Notfall):
--   DELETE FROM app_sitzungen;
--
-- ============================================================
-- Ende v1.2 Teil 1. Fortsetzung mit Etappe 4d (Freigabeverwaltung).
-- ============================================================
