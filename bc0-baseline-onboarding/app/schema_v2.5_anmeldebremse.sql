-- ============================================================================
-- schema_v2.5 — Anmeldebremse: Fehlversuche zählen, befristet sperren
-- BC0 · Simeon Ehmer · 02.09.2026 · ToDo-Punkt 71
-- ============================================================================
--
-- ANLASS
--   Die Anmeldung nahm bis heute **unbegrenzt viele Versuche** entgegen. Kein
--   Zähler, keine Verzögerung, keine Sperre. Seit dem 26.08.2026 sind zwölf
--   Übungszugänge verteilt und die Adresse ist bekannt — Durchprobieren war
--   damit nur eine Frage der Geduld.
--
--   Aufgefallen am 20.08.2026 bei der technischen Bestandsaufnahme, seither
--   offen benannt in `BC0_Sicherheitskonzept.md`. Die lange Aufgabenliste
--   nennt die Frist: **vor** der Freigabe an externe Mandanten.
--
-- WARUM ERST JETZT
--   Punkt 71 hing an Punkt 47. Bis zum 02.09.2026 lief die Anwendung ohne
--   `--proxy-headers`; sie sah als Absender jeder Anfrage **Caddys eigene
--   Adresse**, nicht die des Benutzers. Ein Zähler je IP hätte damals alle
--   zwölf Nutzer als einen gezählt — der erste mit fünf Tippfehlern hätte den
--   Rest ausgesperrt. Ein Schutz, der genau die trifft, die er schützen soll.
--
-- ============================================================================
-- Die Regel
-- ============================================================================
--   ab  5 Fehlversuchen  verzögerte Antwort (1s, 2s, 4s, 8s — gedeckelt)
--   ab 10 Fehlversuchen  Sperre für 15 Minuten
--   gleitendes Fenster   15 Minuten; ältere Fehlversuche zählen nicht mehr mit
--
--   Gezählt wird **zweigleisig, je E-Mail und je IP**, und der strengere
--   Zähler entscheidet. Beides ist nötig: Nur je E-Mail zu zählen ließe
--   jemanden EIN Passwort gegen alle zwölf Konten probieren, ohne dass ein
--   einziger Zähler seine Schwelle erreicht. Nur je IP zu zählen ließe sich
--   mit wechselnden Adressen umgehen.
--
--   Die Sperre **läuft von allein ab** — entschieden am 02.09.2026. Die
--   Alternative, Sperre bis ein Admin sie aufhebt, macht eine Person zur
--   Entsperrstelle für zwölf Konten, auch sonntags.
--
-- ============================================================================
-- Warum in der Tabelle keine Adressen stehen
-- ============================================================================
--   Gespeichert wird der SHA-256-Abdruck des Schlüssels (`email:<adresse>`
--   oder `ip:<adresse>`) — dieselbe Regel wie bei `app_sitzungen`, hier aber
--   aus einem zusätzlichen Grund:
--
--   **Der Zähler entsteht auch für Adressen, die es nicht gibt.** Wer die
--   Anmeldemaske mit fremden E-Mail-Adressen befüllt, würde sonst dafür
--   sorgen, dass BC0 genau diese Adressen ablegt — personenbezogene Daten von
--   Menschen, die mit dem Projekt nichts zu tun haben. Das wäre eine
--   Datensammlung, die durch den Zweck nicht gedeckt ist.
--
--   **Die Tabelle zählt, das Protokoll erzählt.** Wer wissen will, WER es
--   versucht hat, liest das Serverprotokoll: dort steht die Adresse im
--   Klartext, und dort verschwindet sie beim Rotieren wieder. Wer zu einer
--   bekannten Adresse nachsehen will, ob sie gerade gesperrt ist, bildet ihren
--   Abdruck und fragt danach (Beispiel unten).
--
-- ============================================================================
-- WICHTIG: Diese Datei ist Dokumentation, kein Einspielschritt
-- ============================================================================
--   Wie schon bei `schema_v1.2_benutzerverwaltung.sql` gilt: Die Tabellen der
--   Anwendungsschicht (Präfix `app_`) legt die Anwendung beim Start selbst an
--   (`bc0_auth/repository.py`, `CREATE TABLE IF NOT EXISTS`). Diese Datei hält
--   den Vollstand fest, damit er nachlesbar ist, ohne den Quelltext zu öffnen.
--   Sie **muss nicht** von Hand eingespielt werden — schaden tut es auch nicht.

CREATE TABLE IF NOT EXISTS app_anmeldeversuche (
  abdruck       TEXT PRIMARY KEY,               -- SHA-256 von 'email:…' bzw. 'ip:…'
  art           TEXT NOT NULL CHECK (art IN ('email','ip')),
  fehlversuche  INTEGER NOT NULL DEFAULT 0,     -- im laufenden Fenster
  letzter_am    TIMESTAMPTZ NOT NULL,           -- Bezugspunkt des Fensters
  gesperrt_bis  TIMESTAMPTZ                     -- NULL = nicht gesperrt
);

-- Für das Abräumen: Zähler, die weder etwas zählen noch sperren, fallen beim
-- nächsten erfolgreichen Anmelden heraus.
CREATE INDEX IF NOT EXISTS idx_anmeldeversuch_alt ON app_anmeldeversuche(letzter_am);

-- ============================================================
-- Betriebshinweise
-- ============================================================
-- Läuft gerade eine Sperre?
--   SELECT art, fehlversuche, gesperrt_bis
--     FROM app_anmeldeversuche
--    WHERE gesperrt_bis > now();
--
-- Ist eine BESTIMMTE Adresse gesperrt? (Abdruck bilden, nicht suchen)
--   docker compose exec app python -c "from bc0_auth.repository import \
--     AnmeldeversuchRepository as R; print(R.abdruck('email','name@firma.de'))"
--   SELECT * FROM app_anmeldeversuche WHERE abdruck = '<ausgabe von oben>';
--
-- Jemanden von Hand befreien — der Regelfall ist Abwarten, 15 Minuten:
--   DELETE FROM app_anmeldeversuche WHERE abdruck = '<abdruck>';
--
-- Wer hat es versucht? Steht nicht hier, sondern im Protokoll:
--   docker compose logs app | findstr /C:"Anmeldebremse"
