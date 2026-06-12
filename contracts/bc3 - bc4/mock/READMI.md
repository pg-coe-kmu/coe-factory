# Aurelia — Mock-Lieferung

**Setting:** Aurelia Krankenkasse, Antragsbearbeitung Krankentagegeld (KP-07)
**Lieferungs-ID:** `del-aurelia-2026-06-07-002`
**Schema:** v3.4


## Was hier drin liegt

| Datei | Was es ist | Für wen |
|---|---|---|
| `tickets.json` | 1 Epic mit 4 Stories — die Hauptlieferung | BC4 (parsen + bauen) |
| `architecture.md` | Mermaid-Bauplan + Komponenten + Plattform-Standards | BC4 + Mensch |
| `api/openapi.yaml` | OpenAPI 3.0 mit Endpunkten je Story | BC4 |
| `compliance-audit.json` | Compliance-Vorprüfung (Pflichten + ID-Reservierungen) | Audit-Spur — BC4 ignoriert |

## So liest BC4 das Ganze

1. Diese Datei (1 Minute)
2. `tickets.json` parsen — gegen `../tickets.schema.json` validieren
3. `architecture.md` überfliegen für Worker-Routing
4. `api/openapi.yaml` als Endpunkt-Vorgabe
5. Pro Story:
   - `beschreibung` ist Prompt-Kontext für Claude
   - `akzeptanzkriterien[].text` werden zu Test-Cases
   - `akzeptanzkriterien[].messverfahren` sagt, wie der Test gebaut wird
   - Worker-Routing kommt aus Epic-`kategorien[]` — alle Stories des Epics gehen an dieselben Worker
6. **Build erst nach** `gate2.status === "approved"`

## Hochrisiko-Hinweis (wichtig)

Aurelia ist nach AI-Act Anhang III 5(a) **Hochrisiko-KI** (Sozialleistungen). In `compliance-audit.json` steht:
- `ai_act_klasse: "high"`
- `menschliche_pruefung_noetig: true`
- `risiko_ampel: "yellow"` (durch Mitigationen wie HitL gesenkt)

→ Vor BC4-Build muss DSB-Freigabe gesetzt sein (`dsb_freigabe.status: "approved"` in compliance-audit.json). (Muss noch geklärt wie)

## Das Epic

`ep-1111-1111-1111-111111111111` — Automatisierte Antragserfassung via OCR + LLM-Extraktion (aus BC2 UC-1)

**4 Stories:**
- `st-...-1` — Antragseingang aus 3 Kanälen + Duplikat-Prüfung
- `st-...-2` — OCR + LLM-Extraktion von 12 Pflichtfeldern
- `st-...-3` — SAP-Anlage + DMS-Ablage + Eingangsbestätigung
- `st-...-4` — HitL-Prüfschritt bei Konfidenz < 0,8 *(entstanden aus Compliance-Pflicht p1 in compliance-audit.json)*

PII-Filter, Audit-Log, Löschungs-Cron, Verschlüsselung sind **Plattform-Standards** — keine eigenen Stories, sondern Infrastruktur (Pflichten p2-p6 in compliance-audit.json mit `reservierte_ticket_id: null`).

---

*Stand 12.06.2026 · Sabrina + Svetlana*
