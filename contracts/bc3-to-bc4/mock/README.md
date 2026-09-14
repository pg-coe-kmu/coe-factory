# Aurelia — Mock-Lieferung

**Setting:** Aurelia Krankenkasse, Antragsbearbeitung Krankentagegeld (KP-07)
**Lieferungs-ID:** `del-aurelia-2026-06-07-002`
**Schema:** v3.4


## Was hier drin liegt

| Datei | Was es ist | Für wen |
|---|---|---|
| `tickets.json` | 1 Epic mit 4 Stories — die Hauptlieferung | BC4 (parsen + bauen) |
| `architecture.md` | Mermaid-Bauplan + Komponenten + Plattform-Standards | BC4 + Mensch |
| `openapi.yaml` | OpenAPI 3.0 mit Endpunkten je Story | BC4 |
| `compliance-audit.json` | Compliance-Vorprüfung (Pflichten + ID-Reservierungen) | Audit-Spur — BC4 ignoriert |

## So liest BC4 das Ganze

1. Diese Datei
2. `tickets.json` parsen — gegen `../tickets.schema.json` validieren
3. `architecture.md` überfliegen für Worker-Routing
4. `openapi.yaml` als Endpunkt-Vorgabe
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

## Über die openapi.yaml

`openapi.yaml` beschreibt die REST-Endpunkte des Aurelia-Systems — was rein kommt, was zurück kommt, welche Datenobjekte (Request + Response). Sie ist der **Vertrag**: BC4 baut Services, die genau das anbieten.

**Endpunkte im Überblick:**

| Endpunkt | Methode | Story | Was er macht |
|---|---|---|---|
| `/antrag` | POST | `st-...-1` | Antrag aufnehmen + Duplikat-Prüfung |
| `/antrag/{id}/extraktion` | POST | `st-...-2` | OCR + LLM-Extraktion der 12 Pflichtfelder |
| `/antrag/{id}/sap-anlage` | POST | `st-...-3` | In SAP anlegen + DMS-Ablage + Bestätigung |
| `/hitl-queue` | GET | `st-...-4` | Liste unsicherer Anträge (mit Pagination) |
| `/hitl/{id}/freigabe` | POST | `st-...-4` | Sachbearbeiter gibt einen Eintrag frei |
| `/health` | GET | — | Healthcheck (kein Token nötig) |

**Verknüpfung zu tickets.json:** Jeder Endpunkt hat ein `x-story-id`-Feld. Damit weiß ein KI-Agent maschinen-lesbar, welcher Endpunkt zu welcher Story gehört.

**Was die openapi.yaml mitliefert:**

- **OAuth2-Sicherheit** mit 3 Scopes (`antrag.lesen`, `antrag.schreiben`, `hitl.bearbeiten`). Konkreter Identity-Provider wird mit Platform-Team festgelegt.
- **Pagination** auf `/hitl-queue` (limit, offset) — wichtig bei ~300 Anträgen/Woche.
- **Webhook** `antragEingangsbestaetigung` — asynchron nach SAP-Anlage. Receiver-URL kommt aus Konfiguration. Retry-Strategie: 5 Versuche mit Exponential-Backoff.
- **Beispiel-Payloads** auf den meisten Endpoints — sowohl hoch-konfident als auch niedrig-konfident.
- **Error-Catalog** mit 15 strukturierten Fehlercodes (`E-AUTH-401`, `E-OCR-101`, `E-LLM-202`, `E-SAP-501` …) — gruppiert nach Domäne.

**Versionierungs-Regel:** Breaking Changes → `/api/v2/...`, Backward-kompatible Erweiterungen → Minor-Bump in `info.version`.

---

*Stand 12.06.2026 · Sabrina + Svetlana*
