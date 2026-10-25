# Härtung vor dem Betrieb — Spec und Implementierungsplan

> Stand 25.10.2026, Fassung 1. Go der BC1-Projektleitung am 25.10. („Go für das Härtungspaket als Erstes. Erst Plan, dann bauen").
> Quellen: Abschlussplan „Neu 23.10." (3), (6), (7) und „Neu 08.10. — aus B4" (3).
> Klein (S): drei Stellen, je ein TDD-Zyklus. Spec und Plan stehen deshalb in einem Dokument.

## Big Picture

Bevor der Dienst irgendwo außerhalb des eigenen Rechners erreichbar ist, schließen wir drei Lücken. Bei allen dreien landen Dinge im Protokoll, die dort nicht hingehören.

1. **Gefälschte Protokollzeilen:** Die Sitzungskennung kommt vom Browser (die n8n-Chat-Oberfläche erzeugt sie als UUID und legt sie im `localStorage` ab, der Nutzer kann sie ändern). Heute nimmt der Dienst jede nicht-leere Zeichenkette an. Eine Kennung mit Zeilenumbruch erzeugt im Protokoll eine zweite, gefälschte Zeile, denn Profil-Writer und Dienstschicht schreiben die Kennung roh. **Neu:** Sitzungs- und Nachrichtenkennung müssen einem festen Muster entsprechen, sonst lehnt der Dienst ab.
2. **Passwort in der Adresse:** Steht in `BC1_BC0_URL` ein `user:passwort@`, landet es in jeder Protokollzeile von `httpx` und in der Meldung „nicht erreichbar". **Neu:** Der Dienst startet mit so einer Adresse nicht und sagt warum, ohne die Adresse zu wiederholen.
3. **Datenbank-Details im Protokoll:** Scheitert das Aufräumen eines Entwurfs, protokolliert der Writer die ganze Ausnahme (`%r`). Postgres hängt eine DETAIL-Zeile mit einem Ausschnitt der Zeile an, und dort steht Profiltext. **Neu:** Es werden nur Fehlerklasse und erste Zeile protokolliert, wie an der Nachbarstelle schon heute (`_fehlergrund`).

**Wen es betrifft:** niemanden im Normalbetrieb. n8n schickt eine UUID als Sitzungskennung und `exec-<Nummer>` als Nachrichtenkennung; beide passen. Vertrag, Datenbank und BC0 bleiben unberührt.

**Nicht in diesem Paket (bleibt, wo es im Abschlussplan steht):**
- Die `bc1*`-Logger ausdrücklich auf INFO setzen. Das schützt vor einer fremden Logging-Konfiguration, und die entsteht erst auf dem Server → **B3 Teil 2**.
- Der Traceback, den uvicorn bei einer *unerwarteten* Ausnahme schreibt → **B7 Teil 2**.

## Entscheidungen (Claude, 25.10.)

| # | Entscheidung | Warum |
|---|---|---|
| E1 | Muster für `session_id` und `message_id`: `^[A-Za-z0-9_-]{1,128}$` | Lässt die UUID der n8n-Chat-Oberfläche, `exec-<Nummer>`, die Testprofil-Kennungen (`uc1-reisebuchung-testdaten-v3`) und alle Test-Kennungen durch. Schließt Leerzeichen, Zeilenumbrüche, Steuerzeichen, Anführungszeichen und `\|` aus. Der Writer baut aus `\|` einen Schlüssel (`profil_writer.py`, `f"{session_id}\|{focus_step_id}"`). 128 Zeichen sind reichlich für eine UUID (36). |
| E2 | Abweisung über das Standard-422 von FastAPI, ohne eigenen `chat_text` | Ein regulärer Browser schickt nie eine andere Kennung; die Abweisung trifft nur manipulierte Anfragen. Die leere Kennung wird schon heute so abgewiesen. |
| E3 | Prüfung auf Zugangsdaten in `lies_bc0_zugang` **vor** der https-Prüfung, Kriterium `"@" in netloc` | Die https-Meldung wiederholt die Adresse; sie darf nie eine Adresse mit Passwort ausgeben. `"@" in netloc` fängt auch `https://@host` und den Fall nur mit Benutzername. |
| E4 | Writer: `_draft_aufraeumen` nutzt den vorhandenen `_fehlergrund` | Wiederverwenden statt neu bauen. Klasse und erste Zeile reichen zur Diagnose (Tabelle, Constraint, Meldung). |

## Global Constraints

- TDD unter dem tdd-guard, nie umgangen. `*.py` unter `coe-factory/` nur mit Edit/Write/MultiEdit; Bash nur für pytest, git und Messungen. Ein neuer Test je Edit (ein parametrisierter Test zählt als einer).
- pytest aus `bc1-context-discovery/`: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`.
- Wortlaut neu: `MELDUNG_URL_MIT_ZUGANGSDATEN = ("BC1_BC0_URL enthält Zugangsdaten (Benutzer oder Passwort vor einem @). Das Passwort gehört nach BC1_BC0_KONTO_PASSWORT; in der Adresse stünde es in jeder Protokollzeile.")` in `bc1_service/bc0_meldungen.py`.
- Musterkonstante: `KENNUNG_MUSTER = r"^[A-Za-z0-9_-]{1,128}$"` in `bc1_service/api.py`.
- Commits auf Zweig `bc1-haertung-vor-betrieb`, Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Kein Push ohne OK.

## Review Focus

1. **Zeilenumbruch am Ende** (`"s1\n"`): Pythons `re` lässt `$` vor einem abschließenden Zeilenumbruch zu, die Rust-Regex von pydantic-core nicht. Der Test muss genau diesen Fall abdecken, damit das Muster unabhängig von der Regex-Maschine hält.
2. **Bestehende Aufrufer:** Alle Tests, die `/turn` mit eigenen Kennungen aufrufen, bleiben grün (volle Suite).
3. **Adresse mit `@` im Pfad oder in der Abfrage** (`https://bc0.example.org/a@b`) ist keine Zugangsangabe und muss weiter angenommen werden — deshalb `netloc`, nicht die ganze Adresse.

## Testmatrix

| Fall | Erwartung | Test |
|---|---|---|
| `session_id` mit `\n`, mit Leerzeichen, mit `\|`, mit 129 Zeichen; `message_id` mit `\n` | 422, keine Sitzung im Store | T1 (parametrisiert) |
| UUID als `session_id`, `exec-4711` als `message_id` | 200 | T2 |
| `BC1_BC0_URL` mit `user:pw@`, nur `user@`, `@` ohne Benutzer, lokales http mit `user:pw@` | `RuntimeError` mit genau `MELDUNG_URL_MIT_ZUGANGSDATEN`; Passwort nicht in der Meldung | T3 (parametrisiert) |
| `@` nur im Pfad | wird angenommen | T4 |
| Aufräumen scheitert mit DETAIL-Zeile | Protokoll enthält `draft_aufraeumen_fehlgeschlagen` und die erste Zeile, nicht die DETAIL-Zeile | T5 (DB) |

## Tasks

### Task 1 — Kennungsmuster im `TurnRequest`

Dateien: `bc1_service/api.py`, `tests/test_api.py`, `tests/test_protokoll.py` (nur eine Erwartung).

- [ ] T1 in `tests/test_api.py` (neben `test_leere_message_id_wird_abgewiesen`): `test_kennung_ausserhalb_des_musters_wird_abgewiesen(session, mid)`, parametrisiert über `("s1\n","m1")`, `("s 1","m1")`, `("s1|x","m1")`, `("x"*129,"m1")`, `("s1","m1\nturn korrelation=x")`. Erwartet: `_turn(client, mid, "Hallo", session=session).status_code == 422`.
- [ ] Volle Suite → RED (heute 200).
- [ ] `KENNUNG_MUSTER` anlegen und `session_id`/`message_id` auf `Field(pattern=KENNUNG_MUSTER)` umstellen (Aufrufer vor Konstante: erst Literal im `Field`, dann bei Grün in die Konstante ziehen, siehe Guard-Lessons).
- [ ] Volle Suite. Erwartet rot ist dann genau ein Bestandstest: `tests/test_protokoll.py::test_fremd_gewaehlte_ids_koennen_keine_felder_faelschen` schickt `session="x status=fertig\nturn"`, `message_id="m1 http=200"` und erwartet eine maskierte Dienstzeile. Mit dem Muster kommt die Anfrage nicht mehr an (422), es entsteht keine Dienstzeile (README: 422 steht nur im Zugriffslog von uvicorn).
- [ ] Nur die **Erwartung** dieses Tests anpassen, der Aufruf bleibt: Status 422 und `_zeilen(caplog) == []`. Der Testname bleibt wahr. Die Maskierung `_feld` in `api.py` bleibt unverändert: Sie schützt weiter die Korrelationskennung aus dem Header, und auch die Kennungen, falls das Muster je fällt.
- [ ] Volle Suite → GREEN.
- [ ] T2 `test_uuid_und_exec_kennung_werden_angenommen` (grün bei Ankunft, eigener Edit): Sitzung `"3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b"`, Nachricht `"exec-4711"` → 200.
- [ ] Commit `fix(bc1): Sitzungs- und Nachrichtenkennung auf ein festes Muster (Härtung)`.

### Task 2 — Keine Zugangsdaten in `BC1_BC0_URL`

Dateien: `bc1_service/bc0_meldungen.py`, `tests/test_bc0_meldungen.py`.

- [ ] T3 `test_adresse_mit_zugangsdaten_bricht_ab_ohne_sie_zu_wiederholen(url)`, parametrisiert über `"https://bc1:geheim@bc0.example.org"`, `"https://bc1@bc0.example.org"`, `"https://@bc0.example.org"`, `"http://bc1:geheim@localhost:8000"`. Erwartet: `RuntimeError`, `str(...) == MELDUNG_URL_MIT_ZUGANGSDATEN`, `"geheim" not in str(...)`.
- [ ] Volle Suite → RED (Import- bzw. Assertion-Fehler).
- [ ] Konstante und Prüfung in `lies_bc0_zugang` direkt nach `urlsplit`, vor der https-Prüfung.
- [ ] Volle Suite → GREEN.
- [ ] T4 `test_at_zeichen_im_pfad_ist_keine_zugangsangabe` (grün bei Ankunft): `"https://bc0.example.org/a@b"` wird zu `Bc0Zugang(url="https://bc0.example.org/a@b", …)`.
- [ ] Commit `fix(bc1): Zugangsdaten in BC1_BC0_URL abweisen (Härtung)`.

### Task 3 — Writer protokolliert beim Aufräumen keine Nutzdaten

Dateien: `bc1_service/profil_writer.py`, `tests/test_profil_writer.py`.

- [ ] T5 `test_fehlgeschlagenes_aufraeumen_protokolliert_keine_detailzeile` (DB), nach dem Muster von `test_fehlgeschlagenes_aufraeumen…` mit Trigger, aber `RAISE EXCEPTION 'Aufraeumen blockiert' USING DETAIL = 'PROFILTEXT_DARF_NICHT_INS_LOG'`. Erwartet: `"draft_aufraeumen_fehlgeschlagen"` und `"Aufraeumen blockiert"` im Protokoll, `"PROFILTEXT_DARF_NICHT_INS_LOG"` nicht.
- [ ] Volle Suite → RED.
- [ ] `grund=%r` → `grund=%s` mit `_fehlergrund(fehler)`.
- [ ] Volle Suite → GREEN.
- [ ] Commit `fix(bc1): Aufräumfehler ohne DETAIL-Zeile protokollieren (Härtung)`.

### Task 4 — Doku und Abschluss

- [ ] README, Abschnitt „Betriebsprotokoll": ein Satz zum Kennungsmuster (Abweisung mit 422) und dass `BC1_BC0_URL` keine Zugangsdaten enthalten darf.
- [ ] Abschlussplan: „Neu 23.10." (3) und (7), „Neu 08.10. — aus B4" (3) (Userinfo) und der Writer-Teil von (6) erledigt; Logger-Stufe bleibt B3 Teil 2, uvicorn-Traceback B7 Teil 2.
- [ ] Gegenproben ohne Projektdatei anzufassen (Plugin im Scratchpad): Muster ausgehebelt → T1 rot; Zugangsprüfung ausgehebelt → T3 rot; `%r` zurück → T5 rot.
- [ ] Gesamtprüfung durch einen unabhängigen Prüfer, volle Suite mit und ohne DB.
- [ ] Commit `docs(bc1): Härtung vor dem Betrieb — README und Abschlussplan`.
