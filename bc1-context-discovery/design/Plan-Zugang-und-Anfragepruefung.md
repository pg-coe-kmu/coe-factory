# Plan — Zugangsschlüssel und Anfrage-Prüfung (Schritt 1 des Einbaus in BC0)

> Stand 27.10.2026 · Go der BC1-Projektleitung am 27.10. · Zweig `bc1-zugang-anfrage`
> Herkunft: Abschlussplan B3 Teil 2 („Zugangsprüfung für Dienst, alle Endpunkte“) und die
> Entscheidung, BC1 auf BC0s Server hinter BC0s Backend zu betreiben (BC0 reicht `/turn` weiter).

## Big Picture

BC1 läuft künftig als Container neben BC0s Anwendung. Erreichen soll ihn nur BC0s Backend.
Heute hat der Dienst keine Zugangsprüfung, und er ignoriert unbekannte Felder im Aufruf still.
Schickt BC0 also eine falsche Anfrage-Nummer mit, interviewt BC1 trotzdem zur eingestellten
Anfrage, und niemand merkt es. Schritt 1 schließt beides:

1. **Zugangsschlüssel.** Jeder Aufruf braucht den Header `X-BC1-Zugang` mit dem Wert aus
   `BC1_ZUGANG`. Sonst antwortet der Dienst mit 401, ohne Inhalt. Das gilt für alle Endpunkte.
2. **Anfrage und Mandant im Aufruf.** `/turn` verlangt `anfrage_id` und `company_id`. Passen
   sie nicht zu Anfrage und Mandant des Dienstes, kommt 409 `anfrage_passt_nicht` mit
   lesbarem Text. Dabei wird nichts geschrieben, und die KI wird nicht aufgerufen.
3. **Anrede.** Der letzte feste Text mit „du“ (Antwort bei `fehler_fortsetzbar`) wird auf
   „Sie“ umgestellt.

Diese Zusagen stehen im Brief an BC0 vom 27.10.

**Nicht in Schritt 1:** „Anfrage je Gespräch“ (Schritt 2, nach der Vorführung) und die
Bindung „Anfrage gehört Person“ (vor echten Nutzern, mit BC0).

## Technischer Teil

### Entscheidungen

| # | Frage | Festlegung | Begründung |
|---|---|---|---|
| Z1 | Wie heißt der Header? | `X-BC1-Zugang` | im Brief an BC0 so genannt |
| Z2 | Welche Endpunkte? | **alle** (Middleware): `/turn`, `/gesundheit`, `/docs`, `/redoc`, `/openapi.json` | B3 Teil 2 verlangt alle; im Compose-Netz braucht niemand Zugriff ohne Schlüssel |
| Z3 | Antwort bei fehlendem oder falschem Schlüssel | 401 **ohne Inhalt** | so im Brief; verrät nichts |
| Z4 | Vergleich | `hmac.compare_digest` auf Bytes | zeitkonstant |
| Z5 | `BC1_ZUGANG` beim Start | **Pflicht**, mindestens 32 Zeichen, sonst Startabbruch. Die Meldung nennt den Wert nie. | ein schwacher oder vergessener Schlüssel soll laut scheitern; `secrets.token_urlsafe(32)` liefert 43 Zeichen |
| Z6 | `create_app(zugang=None)` | `None` = keine Prüfung, nur für Tests. `main.py` übergibt den Schlüssel immer; ein Test hält die Verdrahtung fest. | dasselbe Muster wie `anfrage_id`, `writer`, `melder` |
| Z7 | Protokoll bei 401 | eine Zeile WARNING `zugang_verweigert pfad=… grund=fehlt|falsch`, nie der Header-Wert | Fehlkonfiguration bei BC0 soll im Log auffallen |
| Z8 | `anfrage_id`, `company_id` im `TurnRequest` | **Pflicht**. Form `A-JJJJ-NN` bzw. UUID, sonst 422. | eine vergessene Angabe soll sofort auffallen (Zweitmeinung 27.10.) |
| Z9 | Abweichung | 409 `anfrage_passt_nicht` mit `chat_text`, **vor** Sitzungs-Lock und Laden; ein Schlüssel für Anfrage und Mandant | so im Brief; kein Schreiben, kein KI-Aufruf |
| Z10 | `create_app(anfrage_id=None)` | Dann prüft der Dienst nur den Mandanten. Nur Tests ohne BC0-Kontext; `main.py` setzt die Anfrage immer. | vorhandenes Muster |
| Z11 | `company_id` im Vergleich | als UUID normalisiert (Kleinschreibung), wie `lies_company_id` | dieselbe UUID in Großbuchstaben ist derselbe Mandant |

### Tasks (je Test zuerst, dann Code)

1. **`lies_zugang`** in `start.py`: fehlt → Abbruch; kürzer als 32 → Abbruch; die Meldung enthält den Wert nicht; gültig → Wert (getrimmt).
2. **Verdrahtung in `main.py`**: `main_laden` setzt `BC1_ZUGANG`; der Test prüft `gesehen["zugang"]`. Ein zweiter Test: Ohne `BC1_ZUGANG` bricht der Start ab.
3. **Middleware** in `create_app` (neue Testdatei `tests/test_zugang.py`):
   - ohne Header → 401 ohne Inhalt; falscher Header → 401;
   - richtiger Header → `/gesundheit` 200, `/turn` 200;
   - `/docs` und `/openapi.json` ohne Header → 401;
   - `zugang=None` → keine Prüfung;
   - Protokollzeile `zugang_verweigert` ohne Header-Wert.
4. **Pflichtfelder**: erst die Test-Helfer (`_turn` in `test_api.py`, `test_api_profil.py`, `test_protokoll.py`, direkter Aufruf in `test_api.py`) auf die neuen Felder umstellen (bleibt grün, weil sie heute ignoriert werden). Dann Tests für 422 bei fehlendem oder falsch geformtem Feld (rot), dann das Modell (grün).
5. **409 `anfrage_passt_nicht`**:
   - fremde Anfrage → 409 mit `chat_text`, Store leer, kein KI-Aufruf;
   - fremder Mandant → 409;
   - `anfrage_id=None` am Dienst → nur der Mandant zählt;
   - UUID in Großbuchstaben → kein 409;
   - die Turn-Zeile trägt `status=anfrage_passt_nicht`.
6. **Anrede**: Test auf den Text bei `fehler_fortsetzbar` (rot), dann `api.py`.
7. **Doku**:
   - README: Pflichtvariable, Header, Felder, 401/409, Docker-Aufruf.
   - `main.py`-Docstring.
   - `SMOKE.md`: n8n sendet Header und Felder.
   - `bc1-chat-workflow.json`: Header mit Platzhalter, die zwei Felder mit Platzhaltern.
8. **Suite mit Test-DB**, dann unabhängige Prüfung, Befunde nach Schwere einarbeiten.

### Unabhängige Prüfung (27.10.) — wie eingearbeitet

0 Critical, 0 Important, 8 Minor; Urteil „merge-fähig“. Mutationsproben: 9 von 12 Mutanten
waren gefangen. Die drei überlebenden haben jetzt je einen Test, und jeder davon ist per
Mutation belegt.
- (1) Ein Satz im Brief an BC0 zum Fehlen von `BC1_ZUGANG` war falsch → im Brief berichtigt (BC1 startet dann nicht).
- (2) Kein Test hielt „Prüfung vor dem Laden“ fest → Test mit gespeicherter Sitzung einer fremden Anfrage.
- (3) Nicht-ASCII im Header und Pfad-Maskierung ohne Test → je ein Test.
- (4) `BC1_ZUGANG` nahm Nicht-ASCII an → Startabbruch, nur druckbares ASCII.
- (5) Eine 422 spiegelte die Eingabe samt Nachrichtentext zurück → eigener Handler, nur Ort und Art.
- (6) und (7) README, Dockerfile, SMOKE und ein Testkommentar → nachgezogen.
- (8) zurückgestellt, siehe unten.

### Zurückgestellt (mit Ziel)

- **`request.url.path` statt `request.scope["path"]` in der Middleware:** Ein ungültiges UTF-8 im Query-String ergibt über rohes ASGI 500 statt 401. Über uvicorn mit httptools ist das nicht erreichbar (gemessen von der Prüfung); bei h11 ist es eine Einschätzung. Ziel: beim nächsten Anfassen der Middleware, mit einem Test über rohes ASGI.
- **WebSocket-Routen** wären von der Middleware nicht erfasst; heute gibt es keine. Ziel: Wer eine WebSocket-Route anlegt, schützt sie mit.

### Folgen für Bestehendes

- `anfrage_konflikt` und `mandant_konflikt` (Sitzung gehört woandershin) bleiben. Sie greifen, wenn Aufruf und Dienst zusammenpassen, die Sitzung aber zu einer anderen Anfrage oder einem anderen Mandanten gehört.
- Der lokale n8n-Chat braucht nach dem Umbau Header und Felder. Ohne sie antwortet der Dienst mit 401 bzw. 422; `SMOKE.md` sagt, wo sie einzutragen sind.
- Das Testprofil-Werkzeug ruft `process_turn` direkt auf, nicht `/turn`, und ist nicht betroffen.
