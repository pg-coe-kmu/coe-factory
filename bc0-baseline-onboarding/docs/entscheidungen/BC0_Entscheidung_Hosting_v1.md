# BC0 — Entscheidungsvermerk Hosting

**Kontext:** BC0 (Reifegrad) · PG KI-CoE-KMU
**Autor:** Simeon Ehmer
**Datum:** 06.08.2026 · Version 1.0
**Status:** entschieden und umgesetzt

---

## 1. Entscheidung

Die BC0-Onboarding-App und ihre PostgreSQL-Datenbank werden auf **Supabase** betrieben.

- **Projekt:** `CoE_factory_BC0`
- **Project-ID:** `fcbvnwycopajmvdroitn`
- **Region:** `eu-west-1` — West EU (Irland)
- **Plan:** Free (Stand 06.08.2026)
- **Schema:** v1.1 (Projektstandard)

Die zuvor geprüfte Alternative **Hetzner self-managed** wird damit nicht weiterverfolgt.

## 2. Begründung

| Kriterium | Supabase | Hetzner self-managed |
|---|---|---|
| Postgres nativ | ✅ verwaltet, Schema v1.1 direkt einspielbar | ✅, aber Eigenbetrieb |
| Objektspeicher für Belege | ✅ Storage integriert (Bucket `belege`) | ⏳ zusätzlich einzurichten (MinIO o. ä.) |
| Betriebsaufwand | gering — Backups, Updates, TLS verwaltet | hoch — Patchen, Monitoring, Backups selbst |
| Kosten Projektlaufzeit | 0 € (Free-Tier ausreichend für BC0-Volumen) | ~5–10 €/Monat plus Zeit |
| Passung zum Projektrahmen | studentisches Projekt mit begrenzter Betriebskapazität | eher für Dauerbetrieb |

Ausschlaggebend war die Kombination aus **verwaltetem Postgres und integriertem Objektspeicher unter einem Dach** — die Beleg-Ingestion (Stufe 1–3) braucht beides, und die Trennung auf zwei Systeme hätte zusätzlichen Integrationsaufwand ohne fachlichen Gegenwert erzeugt.

## 3. Abweichung von der ursprünglichen Planung: Region

Die frühere Notiz nannte **Frankfurt (eu-central-1)** als Zielregion. Das bestehende Projekt wurde tatsächlich in **Irland (eu-west-1)** angelegt. Die Region ist bei Supabase nachträglich nicht änderbar.

**Bewertung:** Irland ist EU-Mitgliedstaat, die DSGVO gilt unmittelbar, es liegt **keine Drittlandsübermittlung** vor. Der datenschutzrechtliche Zweck der ursprünglichen Festlegung („EU-Region, kein US-Transfer") ist damit erfüllt. Latenz- und Kostenunterschiede sind für das BC0-Volumen nicht messbar.

**Entscheidung:** Region Irland wird beibehalten. Ein Neuaufbau in Frankfurt wäre reine Formtreue ohne Sachgewinn.

## 4. Offene Punkte

| Punkt | Frist |
|---|---|
| **7-Tage-Inaktivitätspause** des Free-Tiers durch Cron-Ping überbrücken — sonst erscheint die App externen Testern als defekt | vor externen Tests, KW 33 |
| **Datenschutz-Check** vor Aufnahme realer Mandantendaten: Supabase-AVV abschließen, EU-Region schriftlich bestätigen | vor produktivem Einsatz |
| **Fallback** dokumentiert: bei Engpass Upgrade auf Supabase Pro (25 $/Monat); ein Wechsel wäre über `migrate_sqlite_to_pg.py` und Schema v1.1 reproduzierbar | bei Bedarf |
| **`.env` nicht ins Repo** — enthält DB-Passwort im Klartext; `.gitignore` vor dem Code-Push prüfen | vor Push, KW 33 |

## 5. Umsetzungsnachweis (06.08.2026)

Migration von SQLite (`bc0.db`) nach Supabase-PostgreSQL ausgeführt und verifiziert:

- 3 Mandanten · 3 Profile · 18 Kernprozesse · 90 Teilprozesse · 600 Bitkom-Bewertungen
- NoroAI Consulting GmbH: **Reifegrad Ø 3.63 · 600 Bewertungen · Beleg-Quote 100 %** — identisch zum SQLite-Referenzlauf
- App-Endpunkt `/api/meta` meldet `"backend": "postgres"`

Die Migration ist idempotent (deterministische UUIDs via uuid5, Upserts) und damit wiederholbar.
