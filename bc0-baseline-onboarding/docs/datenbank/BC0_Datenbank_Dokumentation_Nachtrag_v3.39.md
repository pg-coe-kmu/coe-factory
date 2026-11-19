# BC0 Datenbank-Dokumentation — Nachtrag v3.39

**Stand:** 13.11.2026 · schließt an den Nachtrag v3.34–v3.38a an

## v3.39 — Rückbau der Rolle Admin2 (13.11.2026)

**Anlass:** Entscheidung BC0 13.11.2026: „Admin2 findet nicht statt.“

**Änderung an der Datenbank** (`rueckbau_admin2_v3.39.sql`, md5 `405f4534233487249814a5b491fdfd80`):
- Konten mit `rolle = 'admin2'` werden auf `benutzer` gesetzt und gesperrt (`aktiv = false`); nichts wird gelöscht.
- Prüfregel `app_benutzer_rolle_check` wieder `CHECK (rolle IN ('benutzer','admin','leser'))` — Stand vor v3.38.

**Gegenprobe (13.11.2026, Produktion):** keine Zeile `admin2`; Konten admin t 1 · benutzer f 2 · benutzer t 12; Prüfregel wie oben.

**Überholte Aussagen:** Im Nachtrag v3.34–v3.38a beschriebene Rolle `admin2` (v3.38, v3.38a) und die erweiterte Prüfregel gelten nicht mehr.

**Sicherung vor der Änderung:** `sicherung_vor_v3.39_2026-11-13.sql` auf dem Server.
