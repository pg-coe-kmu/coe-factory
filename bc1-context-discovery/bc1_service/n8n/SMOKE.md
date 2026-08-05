# n8n-Chat-Anbindung — Aufbau & Smoke-Checkliste

> Übergangs-Chat-UI laut Bauplan B1 (n8n zustandslos, keine Fachlogik). Ziel-Nachweis P2:
> **echtes Interview im Chat gegen laufenden Dienst.**

## Aufbau

**1. Dienst starten** (aus `bc1-context-discovery/`):

```bash
export BC1_DB_DSN="postgresql://postgres:test@localhost:55432/postgres"   # oder Supabase-DSN
export ANTHROPIC_API_KEY="..."                                            # nie committen
.venv/bin/uvicorn bc1_service.main:app --port 8000
```

*Ohne Claude-Key (FakeLLM-Demo, so lief der Smoke am 05.08.2026):* statt `main:app` eine
lokale, NICHT committete Demo-Verdrahtung nutzen — Wegwerf-Datei `demo_fake.py` außerhalb
des Repos mit exakt diesem Inhalt, Start via
`PYTHONPATH="$PWD" .venv/bin/uvicorn demo_fake:app --app-dir <ordner-der-datei> --port 8000`:

```python
"""Demo-Verdrahtung OHNE echten LLM. BC1_DEMO_LLM=kaputt => absichtlich crashender LLM."""
import os

from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.package import TOY_PROZESS
from bc1_service.api import create_app
from bc1_service.postgres_store import PostgresStateStore
from bc1_service.snapshot import lade_snapshot


class KaputtesLLM(FakeLLM):
    def extract(self, message, package, state):
        raise RuntimeError("absichtlich kaputt (Smoke-Szenario 3)")


_SKRIPT = {
    "Der Prozess heißt Urlaubsantrag": [ExtractionCandidate("prozess_name", "Urlaubsantrag")],
    "Ausgelöst durch einen Antrag": [ExtractionCandidate("ausloeser", "Antrag")],
    "Etwa 100 mal pro Jahr": [ExtractionCandidate("haeufigkeit", "100 mal pro Jahr")],
}

_llm = KaputtesLLM() if os.environ.get("BC1_DEMO_LLM") == "kaputt" else FakeLLM(_SKRIPT)
_snapshot_pfad = os.environ.get("BC1_SNAPSHOT_PFAD")

app = create_app(
    PostgresStateStore(os.environ["BC1_DB_DSN"]),
    _llm,
    TOY_PROZESS,
    lade_snapshot(_snapshot_pfad) if _snapshot_pfad else None,
)
```

FakeLLM = geskriptetes Kern-Test-Double: NUR die drei Skript-Sätze oben führen zu
Extraktionen; die Fragen kommen wörtlich aus dem Use-Case-Paket.

**2. n8n starten:**

```bash
docker volume create n8n_data
docker run -d --rm --name n8n -p 5678:5678 \
  -e GENERIC_TIMEZONE="Europe/Berlin" -e TZ="Europe/Berlin" \
  -e N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true -e N8N_RUNNERS_ENABLED=true \
  -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

**3. Workflow:** `bc1-chat-workflow.json` in der n8n-UI importieren (oder Nodes von Hand).
Die Datei ist ein **einzelnes Workflow-Objekt** (`name`, `nodes`, `connections`, `settings`) —
genau das Format, das der UI-Import erwartet. Instanz-Daten (IDs, Zeitstempel, Projekt-/
Besitzer-Angaben) sind bewusst entfernt; n8n vergibt sie beim Import neu.

| Node | Einstellungen |
|---|---|
| Chat Trigger | Make Chat Publicly Available ✓ · Mode: Hosted Chat · Auth: None · Response Mode: **When Last Node Finishes** |
| HTTP Request | POST `http://host.docker.internal:8000/turn` (n8n läuft im Container → nicht `localhost`) · Body (JSON, Fields): `session_id` = `{{ $json.sessionId }}` · `message_id` = `exec-{{ $execution.id }}` (stabil bei Retries innerhalb einer Execution → Idempotenz) · `message` = `{{ $json.chatInput }}` · Options → Response → **Never Error** ✓ (409 erscheint als Text statt Workflow-Fehler) |
| Edit Fields (Set) | `output` (String) = `{{ $json.chat_text ?? $json.detail }}` |

Dann **Publish**; Chat-URL steht im Chat-Trigger-Node.

## Smoke-Checkliste (durchgeführt 05.08.2026, FakeLLM-Verdrahtung, Postgres 16 im Container)

1. ☑ **Normales Interview bis fertig:** Drei Skript-Antworten im Hosted Chat →
   „Danke! Das Interview ist abgeschlossen (Vollständigkeit: 100%)." DB-Nachweis:
   `SELECT session_id, version, state->>'status' FROM bc1.sessions;` → Chat-Session
   `fertig`, 3 Einträge im raw_log.
2. ☑ **Gleiche message_id doppelt (Idempotenz):** identischer `/turn`-Body zweimal per curl →
   semantisch identische Antwort (Hinweis: JSONB gibt Keys umsortiert zurück — mit `jq -S`
   vergleichen), `rounds` bleibt 1.
3. ☑ **LLM absichtlich kaputt:** Dienst mit `BC1_DEMO_LLM=kaputt` (bzw. ungültigem Key) neu
   gestartet → Chat zeigt die freundliche `fehler_fortsetzbar`-Erklärung, kein 500; per curl:
   `{"status":"fehler_fortsetzbar","payload":{"grund":"verarbeitung_fehlgeschlagen"},...}`.
4. ☑ **Danach Resume:** Dienst wieder heil gestartet, **gleiche message_id** erneut gesendet →
   Turn wird verarbeitet (Crash-Resume-Pfad), nächste Frage kommt, `rounds` ohne Inflation;
   im Chat: Nachricht erneut gesendet → Interview läuft an der richtigen Stelle weiter.

Bonus (Transport-Gate live): Nachricht in die abgeschlossene Chat-Session → Chat zeigt
`session_abgeschlossen` (409-Detail; bewusst roher Text — hübschere Formulierung wäre
API-Kosmetik, siehe Roadmap-Notiz im Ledger).

## Baseline-Nachweis (BC0-Snapshot)

5. ☑ **`GET /prozesse` liefert die Baseline:** Dienst mit gesetztem `BC1_SNAPSHOT_PFAD`
   gestartet → `curl http://localhost:8000/prozesse` gibt die **10 Kernprozess-Einträge**
   des BC0-Snapshots zurück (am 05.08.2026 per curl verifiziert). Ohne gesetzten Pfad
   antwortet der Endpunkt mit 404 `kein_snapshot_konfiguriert` (im Test gepinnt).
   Der Snapshot selbst bleibt lokal — nie ins Repo (siehe Vertraulichkeits-Regel).

## Wiederholung mit echtem Claude — OFFENER ABNAHME-PUNKT

> ⚠️ **Dieser Punkt ist noch NICHT abgehakt.** Die Checkliste oben lief bewusst gegen die
> FakeLLM-Verdrahtung (Richard-Entscheidung: FakeLLM-first, damit der Smoke ohne Key und
> ohne Kosten deterministisch läuft). Der Nachweis „echtes Interview gegen echten Claude"
> steht damit aus — P2 ist an dieser Stelle noch nicht vollständig abgenommen.

Sobald `ANTHROPIC_API_KEY` (Platform) da ist: Dienst regulär über `bc1_service.main:app`
starten und Checkliste erneut durchgehen — dann mit frei formulierten Antworten statt der
Skript-Sätze. Erst danach gilt die Bauplan-B3-Zeile als erfüllt. (Nachgehalten im Ledger.)
