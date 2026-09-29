# Entscheidungsvorlage — DB / Single Source of Truth

**PostgreSQL (self-managed) vs. Supabase (managed) · inkl. Vektor-Layer (pgvector vs. Qdrant)**

*Ersteller: Simeon Ehmer | Version v1.0 | Stand 21.06.2026 | Bezug: Tracker #5 (Hoch, blockiert BC1) + #6 (Mittel)*

---

## 1. Empfehlung (TL;DR)

> **SSoT-Engine: PostgreSQL, self-managed auf EU-/DE-Hosting (z. B. Hetzner) — mit pgvector.**
> Maximale Datenhoheit (DSGVO/öffentliches Projekt), eine Datenbank, deckt den Vektor-Layer direkt mit ab.
>
> **Supabase** ist die schnellere, komfortablere Alternative (managed, pgvector + Auth + Storage out of the box) — aber **US-Mutterkonzern** (CLOUD Act / Schrems II) selbst in der Frankfurt-Region. Falls Managed-Komfort gewünscht ist: **Supabase self-hosted** auf EU-Infrastruktur als Kompromiss.
>
> **Vektor-Layer (#6): pgvector** — für unsere Datenmenge mehr als ausreichend. **Qdrant** erst bei zweistelligen Millionen Vektoren. → #6 fällt mit der Postgres-Entscheidung praktisch weg.

**Wichtig zur Einordnung:** Die DB-Engine ist **BC0-intern**. Was BC1 wirklich braucht, ist der **stabile Schnittstellen-Vertrag** (Snapshot/`/api/v1` + stabile IDs) — und der ist bereits geliefert. BC1 kann **heute** gegen den Snapshot entwickeln; die Engine-Wahl legt nur die **Zielrichtung** für den späteren Server fest.

---

## 2. Kontext

- BC0 ist Single Source of Truth; aktuell lokal mit **SQLite** (läuft, NoroAI vollständig).
- Verarbeitet werden **fremde KMU-/Mandantendaten** → DSGVO + Datenhoheit haben Gewicht (Hochschul-/Fördervorhaben).
- Skala ist klein (wenige Mandanten, 600 Bewertungen je Mandant) — keine Hyperscale-Anforderung.
- Entscheidung legt fest, wohin der spätere **gemeinsame Server** läuft; BC1 wünscht Klarheit.

---

## 3. Option A — PostgreSQL, self-managed (EU/DE-Host)

| Pro | Contra |
|---|---|
| Volle **Datenhoheit**, keine US-Konzern-Bindung (DSGVO sauber) | Betrieb/Wartung selbst (Backups, Updates, Monitoring) |
| Eine DB für alles; Schema-Entwurf liegt bereits vor (`BC0_Onboarding_DB_Schema.sql`) | Auth/Storage muss selbst ergänzt werden (z. B. MinIO) |
| **pgvector** inklusive → Vektor-Layer abgedeckt | Etwas mehr Initial-Setup als ein Klick-Managed-Dienst |
| Günstig (Hetzner-VM ~10 €/Mon.); volle Kontrolle, portabel | |
| Migration SQLite → Postgres ist 1:1 (gleiches Schema) | |

## 4. Option B — Supabase (managed)

| Pro | Contra |
|---|---|
| **Sehr schnell startklar**: managed Postgres + **pgvector** + Auth + Storage + REST/Realtime out of the box | **US-Mutterkonzern** → CLOUD Act / Schrems II selbst bei Region Frankfurt — heikel für öffentliches Projekt |
| Wenig Betriebsaufwand, automatische Backups | Anbieter-Abhängigkeit (Lock-in bei Auth/Realtime-Features) |
| Free-Tier zum Testen; Pro ab **$25/Monat** | Kostentreiber bei Wachstum (Egress/MAU-Overage) |
| Open Source → **self-hostbar** auf eigener EU-Infra (Kompromiss) | Self-hosting nimmt den Managed-Vorteil wieder weg |

---

## 5. Vergleich auf einen Blick

| Kriterium | PostgreSQL self-managed | Supabase (managed) |
|---|---|---|
| Datenhoheit / DSGVO | ★★★ (volle Kontrolle, EU/DE) | ★ (US-Konzern, CLOUD Act) |
| Time-to-BC1 | ★★ (Setup nötig) | ★★★ (sofort) |
| Betriebsaufwand | ★ (selbst) | ★★★ (managed) |
| Auth/Storage inkl. | nein (MinIO etc. ergänzen) | ja |
| Vektor-Layer (pgvector) | ja | ja |
| Kosten (klein) | ~10 €/Mon. (VM) | ab ~$25/Mon. (Pro) |
| Lock-in | gering | mittel–hoch |

---

## 6. Vektor-Layer (#6) — pgvector vs. Qdrant

| | pgvector | Qdrant |
|---|---|---|
| Architektur | im Postgres integriert (eine DB) | separater Dienst (zweite DB + Sync) |
| Gut bis | ~5–10 Mio. Vektoren | zweistellige Mio. / horizontale Skalierung |
| Aufwand | minimal | höher (Betrieb + Synchronisation) |
| Für unseren Fall | **ausreichend** | überdimensioniert |

**Empfehlung #6: pgvector.** Bei Postgres/Supabase ist es ohnehin inklusive. Qdrant nur, falls BC1/BC2 später echte Vektor-Skalierung (>10 Mio.) brauchen — dann als bewusster Folgeschritt nachrüstbar.

---

## 7. Empfehlung & nächste Schritte

1. **Richtungsbeschluss:** SSoT-Engine = **PostgreSQL (self-managed, EU/DE)** mit **pgvector**. Supabase als Fallback notieren (Managed-Komfort), bei Bedarf **self-hosted**.
2. **Jetzt nichts umbauen:** BC0 bleibt vorerst bei SQLite (läuft); BC1 entwickelt gegen den **Snapshot** weiter.
3. **#6 schließen:** mit der Postgres-Richtung erledigt (pgvector), kein eigener Vektor-Dienst nötig.
4. **Migration planen** (kein Sofort-Task): Schema steht (`BC0_Onboarding_DB_Schema.sql`), Umzug = Schema anlegen + Snapshot/Daten einspielen.

> **Kernaussage fürs Meeting:** Die Engine-Wahl ist eine *Richtungsentscheidung*, kein Blocker für den Start — BC1 ist über den stabilen Vertrag bereits entkoppelt und arbeitsfähig.
