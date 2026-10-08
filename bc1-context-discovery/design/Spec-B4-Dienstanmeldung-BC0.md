# Spec B4 — Dienst-Anmeldung an BC0 (BC1 meldet „Interview läuft" und stößt das Gate an)

> Stand 06.10.2026. Entschieden von der BC1-Projektleitung in fünf Schritten (Umfang schlank,
> Meldung beim Start, Fehlerverhalten, Pflicht mit Aus-Schalter, Ablauf und Technik abgenommen;
> dabei die Selbstheilung beim Start nach eigenem Befund wieder gestrichen). Quelle der
> Anforderung: Abschlussplan B4, #206 (Durchstich „ohne Eingriff von Hand"), BC0-Endpunkte in
> `bc0-baseline-onboarding/app/app.py` (v3.12) und `bc0_auth/routen.py`, nachgelesen 06.10.
> Überarbeitet nach Zweitmeinung (agy, 06.10., `Review-agy-Spec-B4-2026-10-06.md`): fehlender
> Mandant = 404 statt 403 · DB-Verbindung vor dem BC0-Aufruf zurückgeben · Adressprüfung über
> den Hostnamen · Admin-Konto in der Probe · keine Ausnahmeverkettung aus `httpx` · Antworten
> ohne JSON · Mindestwartezeit 1 Minute · kein eigener „Aus-Melder" (Aus = `None`).
> **Ergänzt 08.10.2026 (Entscheidung BC1-Projektleitung, „B"):** Der Start prüft den Zugang
> **immer** (Anmeldung + eigenes Konto lesen), nicht nur bei `zugeordnet` — sonst fiel ein
> falscher Zugang bei einer Anfrage im Stand `im_interview` erst nach dem Interview auf.
> Nächster Schritt nach Abnahme dieser Spec: Implementierungsplan.

## Big Picture

**Ziel.** Im Durchstich (#206) soll niemand bei BC0 von Hand nachhelfen. BC1 meldet dafür zwei
Dinge selbst an BC0:

1. **„Interview läuft"** — die Anfrage geht von `zugeordnet` auf `im_interview`.
2. **„Interview fertig, bitte ans Gate"** — nach jedem abgeschlossenen Profil ruft BC1 bei BC0
   „Gate nachziehen" auf. Ob die Anfrage auf `am_gate` geht, entscheidet **BC0** (alle
   Teilprozesse der Anfrage fertig?), nicht BC1.

Dafür meldet sich BC1 mit dem Anwendungskonto bei BC0 an, wie ein Benutzer im Browser.

**Was sich ändert (Klartext).**

1. **Start.** Der Dienst braucht zusätzlich die BC0-Adresse und den Zugang des
   Anwendungskontos. Fehlt etwas, startet er nicht und sagt, was fehlt — außer, man schaltet die
   Meldungen bewusst ab (`BC1_BC0_MELDUNGEN=aus`, z. B. für lokale Testläufe ohne echtes BC0;
   dann steht beim Start eine deutliche Warnzeile im Log).
2. **„Interview läuft"** wird **beim Start** gemeldet — eine Dienstinstanz ist seit B5 für genau
   eine Anfrage gestartet, der Start heißt also „jetzt wird interviewt". Gemeldet wird nur, wenn
   die Anfrage noch auf `zugeordnet` steht; bei `im_interview` passiert nichts (sonst würde BC0s
   „seit wann" bei jedem Neustart überschrieben). **Vorher prüft der Start in jedem Fall den
   Zugang** (Ergänzung 08.10.): BC1 meldet sich an und liest das eigene Konto — darf es
   schreiben, sieht es den Mandanten? Das ändert bei BC0 nichts. Klappt das oder die Meldung
   nicht (BC0 nicht erreichbar, Passwort falsch, Konto ohne Schreibrecht oder ohne diesen
   Mandanten), **bricht der Start mit einem klaren Satz ab** — auch bei einer Anfrage, die schon
   auf `im_interview` steht.
3. **Nach dem Abschluss** stößt BC1 „Gate nachziehen" an — **nach** dem Versand der Antwort, im
   Hintergrund. Der Chat scheitert daran **nie**: das Profil ist schon fest gespeichert, die
   befragte Person bekommt ihr „Danke". Schlägt der Aufruf fehl, steht im Log eine deutliche
   Zeile mit Handlungsanweisung (Gate bei BC0 von Hand nachziehen — der benannte Rückfall).
4. **Nichts sonst.** Keine Datenbankänderung, keine neue Spalte, nichts am Gesprächsablauf, an der
   Sitzung oder am Fingerabdruck.

**Was bewusst NICHT gebaut wird.**

| Punkt | Warum nicht | Wohin |
|---|---|---|
| `PUT …/zuordnung` (stand im Plan) | Seit B5 interviewt BC1 nur bereits zugeordnete Anfragen. Der Aufruf würde den Hauptbezug ersetzen — mit einem einzelnen Teilprozess fielen die übrigen Teilprozesse aus der Anfrage. Schaden statt Nutzen. | entfällt; Klärpunkt an BC0 (s. u.) |
| Gate-Aufruf auch beim Start („Selbstheilung") | BC0s Gate-Funktion verknüpft nur über den Teilprozess (B5-Rückstellung 9): eine neue Anfrage auf einen Teilprozess mit altem fertigem Profil ginge beim Start sofort ans Gate, der Start bräche ab, **bevor** interviewt wurde. | Rückstellung — einbauen, sobald BC0 über `anfrage_id` prüft |
| Snapshot-Modus durch DB-Lesepfad ablösen · Zugangsprüfung `GET /prozesse` (B3 d) | Für den Durchstich nicht nötig; berührt die Prozessauswahl. | eigener Punkt im Abschlussplan, nach C4 (b) |
| Wiederholung / Warteschlange für fehlgeschlagene Gate-Aufrufe | Rückfall von Hand reicht für den Durchstich; Gate nachziehen ist beliebig wiederholbar. | C4, nur auf konkreten Anlass |
| Sitzung bei BC0 aufbewahren | Eine BC0-Anmeldung gilt 8 Stunden; zwischen Start und Abschluss können Stunden liegen. Frische Anmeldung je Meldung = höchstens zwei Anmeldungen je Teilprozess, kein abgelaufenes Cookie. | — |

**Was bleibt (BC0-seitig, nicht durch BC1 lösbar).** Die Gate-Funktion prüft weiter nur über
den Teilprozess und läuft für den ganzen Mandanten: ein Abschluss kann eine Anfrage mit mehreren
Teilprozessen, deren übrige Teilprozesse alte fertige Profile tragen, zu früh ans Gate schieben —
auch *andere* Anfragen desselben Mandanten. Bis BC0 das korrigiert: im Durchstich Teilprozesse
ohne fertiges Profil wählen (wie seit B5). Mit B4 stößt BC1 die Funktion selbst an — der
Klärpunkt an BC0 wird dringlicher.

**Erfolg.** Ein Interview zu einer Anfrage im Stand `zugeordnet` bringt sie ohne Handgriff auf
`im_interview` (Start) und — wenn alle ihre Teilprozesse fertig sind — auf `am_gate`
(Abschluss). Vorher bestätigt eine Live-Probe (nur lesend), dass das Konto schreiben darf und
den Mandanten sieht.

## Technischer Teil

### 1. BC0-Schnittstelle (nachgelesen 06.10., `app.py` v3.12, `bc0_auth`)

| Aufruf | Rumpf | Recht | Antworten, die BC1 behandelt |
|---|---|---|---|
| `POST /api/auth/login` | `{"email", "passwort"}` | — | 200 + Cookie `bc0_sitzung` (HttpOnly, Secure, 8 h) · 401 „E-Mail-Adresse oder Passwort ist falsch." · 429 mit `Retry-After` (Sekunden) |
| `PUT /api/companies/{cid}/anfragen/{anfrage_id}/status` | `{"status": "im_interview"}` | `schreibender_benutzer` + Mandant | 200 `{status_alt, status}` · 400 (kein Prozessbezug, Rückschritt) · 401 · 403 (kein Schreibrecht) · 404 („Mandant unbekannt." oder „Unbekannte Anfrage: …") |
| `POST /api/companies/{cid}/anfragen/gate_nachziehen` | — | `schreibender_benutzer` + Mandant | 200 `{geprueft, gesetzt[], anfragen[]}` · 401 · 403 (kein Schreibrecht) · 404 („Mandant unbekannt.") · 501 (BC0 ohne Postgres) |
| `GET /api/auth/me` (Start-Prüfung und Live-Probe) | — | angemeldet | 200 `{rolle, ist_admin, darf_schreiben, mandanten[], …}` |

**Rechte bei BC0 (`bc0_auth`):** 403 kommt nur bei fehlendem Schreibrecht (`darf_schreiben` =
Rolle `benutzer` oder `admin`). Ein Konto, dem der Mandant nicht zugewiesen ist, bekommt
**bewusst 404 „Mandant unbekannt."** (`pruefe_mandant`, verbirgt fremde Mandanten). Ein Admin
sieht alle Mandanten, auch mit leerer `mandanten`-Liste (`darf_mandanten_sehen`).

`cid` = `BC1_COMPANY_ID` (dieselbe ID, über die BC1 schon BC0s Sichten liest). Gemessen mit dem
installierten `httpx` 0.28.1: ein Cookie mit `Secure` wird über `http://localhost` **nicht**
zurückgeschickt — ein lokales BC0 braucht deshalb `BC0_COOKIE_UNSICHER=1` (BC0-Schalter).
`httpx.Client` folgt Weiterleitungen standardmäßig nicht (gemessen: `follow_redirects=False`).

### 2. Neues Modul `bc1_service/bc0_meldungen.py`

- **`Bc0Zugang`** (frozen dataclass): `url`, `email`, `passwort` — `passwort` mit `repr=False`,
  damit es in keinem `repr`/Traceback auftaucht.
- **`lies_bc0_zugang(umgebung) -> Bc0Zugang | None`** — `None` heißt „aus":
  - `BC1_BC0_MELDUNGEN` gesetzt: Wert `aus` → `None`; jeder andere nicht leere Wert → Abbruch
    (Tippfehler schaltet nicht still ab).
  - sonst Pflicht: `BC1_BC0_URL`, `BC1_BC0_KONTO_EMAIL`, `BC1_BC0_KONTO_PASSWORT`; **eine**
    Meldung nennt alle fehlenden Namen.
  - `BC1_BC0_URL` geprüft über `urllib.parse.urlsplit`: Schema `https`, oder Schema `http` mit
    Hostname genau `localhost` / `127.0.0.1` (kein Präfixvergleich — `http://localhost.example.org`
    ist abzuweisen). Abschließender `/` wird entfernt.
- **`Bc0Melder(zugang, company_id, *, transport=None)`** — `transport` nur für Tests
  (`httpx.MockTransport`). Je Meldung: neuer `httpx.Client(base_url=…, timeout=10,
  transport=…)` → Login → Aufruf → schließen.
  - `melde_interview_laeuft(anfrage_id) -> None`
  - `ziehe_gate_nach() -> list[str]` (die von BC0 gemeldeten `gesetzt`)
  - Fehler → **`Bc0MeldungFehler(RuntimeError)`** mit einem der Sätze aus Abschnitt 5.
  - **Keine Verkettung mit `httpx`-Ausnahmen** (`raise … from None`): eine `httpx`-Ausnahme trägt
    die Anfrage samt Rumpf (`e.request.content` — beim Login also das Passwort; gemessen 06.10.).
    `str()`/`repr()` der Ausnahme enthalten es nicht, ein Traceback-Werkzeug, das Objekte
    aufschlüsselt, aber schon. Ausnahmeobjekte von `httpx` werden nie geloggt.
- **`baue_melder(umgebung, company_id) -> Bc0Melder | None`** — `None` beim „aus" (dann schreibt
  es die Warnzeile; Logger `bc1_service.bc0_meldungen`, Stufe WARNING). **Kein eigener
  Aus-Melder:** Start und `api.py` prüfen auf `None` — so entsteht beim „aus" auch keine
  irreführende Log-Zeile nach jedem Abschluss.
- **Live-Probe** `python -m bc1_service.bc0_meldungen --probe` (liest dieselben Variablen +
  `BC1_COMPANY_ID`): Login + `GET /api/auth/me`, gibt Rolle, `darf_schreiben` und „Mandant
  sichtbar: ja/nein" aus (`ist_admin` **oder** `company_id` in `mandanten` — wie BC0s
  `darf_mandanten_sehen`). Ändert nichts bei BC0. Exit-Code ≠ 0, wenn Schreibrecht oder Mandant
  fehlt.
- **Ergänzung 08.10.:** `Bc0Melder.pruefe_konto() -> None` — Login + `GET /api/auth/me`, wirft
  `Bc0MeldungFehler` mit einem der beiden neuen Sätze (Abschnitt 5), wenn Schreibrecht oder
  Mandant fehlt. Die Bewertung „bereit?" steht an **einer** Stelle (`_konto_bereit(konto,
  company_id) -> (schreiben, mandant)`), die Start-Prüfung und Live-Probe gemeinsam nutzen;
  `"mandanten": null` gilt als leere Liste.
- Abhängigkeit: `httpx` zusätzlich in die Gruppe `service` (`pyproject.toml`, `uv.lock`; ist als
  Dev-Abhängigkeit schon 0.28.1 gepinnt).

### 3. Start (`main.py`, `start.py`)

Reihenfolge in `main.py`:

1. wie heute: `BC1_DB_DSN`, `lies_company_id`, `lies_anfrage_id`
2. **neu:** `_melder = baue_melder(os.environ, _company_id)` — **vor** dem Öffnen der Pools, damit
   ein Konfigurationsfehler ohne offene Verbindungen abbricht
3. wie heute: Pools öffnen, im `with _profil_pool.connection()`-Block `lade_kontext(...)`
   (B5-Prüfungen unverändert); **neu, im selben Block:** `_status =
   bc0_lesepfade.anfrage_status(...)`
4. **neu, nach dem `with`-Block, aber im selben `try`** (die DB-Verbindung ist schon zurück im
   Pool und wartet nicht bis zu 10 s auf BC0; beim Abbruch werden die Pools weiter geschlossen):
   `melde_interview_beginn(_melder, _anfrage_id, _status)` in `start.py` — bei `_melder is not
   None` **zuerst immer `pruefe_konto()`** (Ergänzung 08.10.), dann `melde_interview_laeuft` nur
   bei `_status == "zugeordnet"`. `Bc0MeldungFehler` geht als Startabbruch durch.

Der Status kommt **nicht** in `Bc0Kontext`: der Kontext geht in den Fingerabdruck ein, und der
Wechsel `zugeordnet` → `im_interview` darf laufende Sitzungen nicht in `paket_konflikt` stürzen.

### 4. Abschluss (`api.py`)

- `create_app(..., melder=None)`; `main.py` übergibt `_melder` (`None` beim „aus" und in Tests).
- `turn(req, hintergrund: BackgroundTasks)`: **nach** erfolgreichem `writer.reconcile` und nur
  bei `antwort["status"] == "fertig"` und `melder is not None` →
  `hintergrund.add_task(_gate_im_hintergrund, melder, anfrage_id)`. Ohne Writer kein Aufruf
  (dann wurde nichts eingefroren).
- `_gate_im_hintergrund` fängt **jede** Ausnahme und schreibt die Log-Zeile (Abschnitt 5); bei
  Erfolg INFO mit `gesetzt`.
- Gemessen (FastAPI 0.141.1, Starlette-`TestClient`): eine Hintergrundaufgabe in einem `def`-
  Endpunkt läuft nach der Antwort im Worker-Thread; eine Ausnahme darin ändert die Antwort (200)
  nicht. Doku: „background tasks to be run *after* returning a response".
- Wiederholung derselben `message_id` nach `fertig` (Replay) stößt erneut an — harmlos, BC0s
  Funktion ist wiederholbar.

### 5. Wortlaut (wird in Tests festgenagelt; `{…}` = `str.format`)

| Fall | Satz |
|---|---|
| Zugang unvollständig | „BC0-Zugang unvollständig: {namen} fehlt. Ohne Zugang meldet BC1 weder 'im_interview' noch das Gate. Entweder setzen oder bewusst BC1_BC0_MELDUNGEN=aus." |
| Schalter unbekannt | „BC1_BC0_MELDUNGEN='{wert}' ist unbekannt. Erlaubt ist nur 'aus' — oder die Variable weglassen." |
| keine https-Adresse | „BC1_BC0_URL='{url}' ist keine https-Adresse. Das Passwort geht nur verschlüsselt über das Netz (Ausnahme: localhost)." |
| Warnung „aus" | „Meldungen an BC0 sind ausgeschaltet (BC1_BC0_MELDUNGEN=aus) — 'im_interview' und das Gate setzt BC0 von Hand." |
| 401 beim Login | „BC0 lehnt die Anmeldung ab (E-Mail oder Passwort falsch). BC1_BC0_KONTO_EMAIL und BC1_BC0_KONTO_PASSWORT prüfen." |
| 429 beim Login | „BC0 sperrt die Anmeldung nach zu vielen Fehlversuchen noch {minuten} Minute(n). Erst den Zugang prüfen, dann warten." |
| 401 nach geglückter Anmeldung (Cookie nicht angenommen, z. B. lokales BC0 ohne https) | „BC0 nimmt die Anmeldung bei '{aktion}' nicht an (401), obwohl sie geklappt hat. Bei einem lokalen BC0 ohne https muss dort BC0_COOKIE_UNSICHER=1 gesetzt sein." |
| 403 | „BC0 verweigert '{aktion}' (403): {detail} Das Anwendungskonto braucht Schreibrecht (Rolle 'benutzer' oder 'admin')." |
| 404 „Mandant unbekannt." | „BC0 kennt den Mandanten {company_id} für dieses Anwendungskonto nicht (404). Das Konto braucht den Mandanten zugewiesen." |
| andere HTTP-Antwort | „BC0 antwortet auf '{aktion}' mit {code}: {detail}" |
| nicht erreichbar / Zeitlimit | „BC0 unter {url} ist nicht erreichbar ({art}). Läuft BC0, stimmt BC1_BC0_URL?" |
| Start-Prüfung: Konto ohne Schreibrecht (Ergänzung 08.10.) | „Das BC0-Anwendungskonto darf nicht schreiben (Rolle '{rolle}'). Es braucht die Rolle 'benutzer' oder 'admin'." |
| Start-Prüfung: Mandant nicht sichtbar (Ergänzung 08.10.) | „Das BC0-Anwendungskonto sieht den Mandanten {company_id} nicht. Das Konto braucht den Mandanten zugewiesen." |
| Gate im Hintergrund fehlgeschlagen (WARNING) | „Gate nachziehen bei BC0 fehlgeschlagen: {grund} — Anfrage {anfrage_id} bitte bei BC0 von Hand nachziehen (POST /api/companies/{company_id}/anfragen/gate_nachziehen)." |

`{detail}` = BC0s `detail`-Text; ist die Antwort kein JSON oder ohne `detail` (z. B. 502 vom
vorgeschalteten Proxy), der Antworttext — beides auf 200 Zeichen gekürzt. `{minuten}` =
`max(1, round(Retry-After / 60))`, fehlt oder ist der Kopf unlesbar: 1 (wie BC0 selbst rechnet).
`{art}` = Name der Ausnahmeklasse (nicht deren Text). **Das Passwort steht in keinem Satz,
keinem Log und keinem `repr`.**
`{aktion}` ∈ {`Anmeldung`, `Status im_interview`, `Gate nachziehen`, `Konto lesen`}.

### 6. Tests (TDD, tdd-guard)

- **Neu `tests/test_bc0_meldungen.py`** (ohne Netz, `httpx.MockTransport` als nachgebautes BC0):
  Login-Rumpf · Cookie geht in den Folgeaufruf · `PUT …/status` mit `{"status":"im_interview"}`
  an der richtigen Adresse · `POST …/gate_nachziehen` → `gesetzt` · je Fehlerfall der Satz aus
  Abschnitt 5 (401, 429 mit `Retry-After` / ohne / unter 30 s, 403, 404 „Mandant unbekannt.",
  404 sonst, 400, 500, 502 ohne JSON, `ConnectError`, `TimeoutException`, Weiterleitung 302) ·
  das Passwort steht in keiner Meldung und nicht im `repr(Bc0Zugang)` · `Bc0MeldungFehler` hat
  weder `__cause__` noch einen nicht unterdrückten `__context__` · `lies_bc0_zugang`:
  vollständig, je ein Name fehlt, alle fehlen, `aus`, unbekannter Schalter, `http://` fremd,
  `http://localhost.example.org` abgewiesen, `http://localhost` und `http://127.0.0.1` erlaubt,
  Schrägstrich am Ende · `baue_melder` beim „aus" → `None` + Warnzeile · Live-Probe gegen den
  Fake (Benutzer mit Mandant, Admin ohne Mandantenliste, Leser, Benutzer ohne Mandant —
  Ausgabe und Exit-Code).
- **`tests/test_start.py`** (erweitern): `melde_interview_beginn` ruft bei `zugeordnet` genau
  einmal, bei `im_interview` nie, mit `None` nie; `Bc0MeldungFehler` geht durch.
- **`tests/test_api.py`** (erweitern): `fertig` mit Writer → genau ein Gate-Aufruf; Zwischenstand → keiner;
  ohne Writer → keiner; ohne Melder (`None`) → keiner und keine Log-Zeile; Melder wirft →
  Antwort unverändert 200, WARNING-Zeile mit Handlungsanweisung; Replay `fertig` → erneuter
  Aufruf.
- **`tests/test_postgres_init.py`**: Startabbruch bei fehlendem Zugang (ohne `aus`), wie die
  bestehenden Abbruchtests. **`tests/test_api_profil.py`** (importiert `main`) setzt
  `BC1_BC0_MELDUNGEN=aus`.
- **Ergänzung 08.10.:** `pruefe_konto` gegen den Fake (bereit; Admin ohne Liste; Leser;
  Benutzer ohne Mandant; `"mandanten": null`; BC0-Absage geht durch; nur Login + `GET /me`) ·
  `melde_interview_beginn` prüft bei `zugeordnet` UND `im_interview` genau einmal, meldet nach
  der Prüfung, meldet nicht bei gescheiterter Prüfung · `main`: Start bricht auch bei
  `im_interview` ab, wenn die Prüfung scheitert (Pools geschlossen) · Live-Probe nutzt dieselbe
  Bewertung.
- Abschluss: volle Suite mit Container (PG 17), `-W error`.

### 7. Prüfung, Live, Mitteilungen

- Zweitmeinung **agy** für Spec und Plan; Befunde nach Schwere adjudiziert, der
  BC1-Projektleitung vorgelegt.
- Lokal auf `bc1-b4-dienstanmeldung`; Push/PR nur nach OK der BC1-Projektleitung mit
  Vorab-Prüfung, was öffentlich wird.
- Live nach Merge, ausgeführt von der BC1-Projektleitung: (1) Live-Probe gegen
  `https://bc0.perspektivwechsel.ai` (nur lesend); (2) im Durchstich der echte Start zu einer
  Anfrage im Stand `zugeordnet`. Keine Datenbank-Einspielung nötig.
- Doku: README und `n8n/SMOKE.md` (neue Variablen, Übernahme aus der lokalen Zugangsdatei per
  `export BC1_BC0_KONTO_EMAIL="$BC0_APP_KONTO_EMAIL"` usw., Startabbrüche).
- Abschlussplan: B4 nachziehen; neuer Punkt „Snapshot ablösen + `/prozesse`-Zugang" (nach
  C4 (b)); Rückstellungen „Selbstheilung beim Start" (Auslöser: BC0-Gate über `anfrage_id`) und
  „Wiederholung Gate-Aufruf" (C4); `…/zuordnung` entfällt mit Begründung.
- Sammelliste an BC0 (Runde 2, lokal, verschickt die BC1-Projektleitung): (a) BC1 interviewt nur
  bereits zugeordnete Anfragen — der in `PUT …/zuordnung` beschriebene Weg „der Bezug entsteht
  im Interview" wird von BC1 nicht bedient, BC0 ordnet vorher zu; (b) Punkt 4 (Gate-Funktion
  über `anfrage_id`) wird durch B4 dringlicher — BC1 stößt die Funktion jetzt selbst an, und
  sie wirkt mandantenweit.
