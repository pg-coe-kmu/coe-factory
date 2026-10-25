# Härtung vor dem Betrieb — Spec und Implementierungsplan

> Stand 25.10.2026, Fassung 2. Go der BC1-Projektleitung am 25.10. („Go für das Härtungspaket als Erstes. Erst Plan, dann bauen").
> Quellen: Abschlussplan „Neu 23.10." (3), (6), (7) und „Neu 08.10. — aus B4" (3).
> Klein (S): drei Stellen, je ein TDD-Zyklus. Spec und Plan stehen deshalb in einem Dokument.
> **Geprüft:** unabhängiger Prüfer (25.10.), „bereit mit Korrekturen", 0 Critical, 1 Important, 8 Minor. Alles eingearbeitet; ein Minor ist mit Ziel zurückgestellt (Abschnitt „Befundverbleib").
> **Gebaut 25.10.** auf Zweig `bc1-haertung-vor-betrieb`, alle Tasks unter dem tdd-guard. Gesamtprüfung: „merge-fähig", 0 Critical, 0 Important, 9 Minor. Eingearbeitet: Kommentare und README-Wortlaut (m1, m2), Test für genau 64 Zeichen mit Gegenprobe (m4), Verweis (m8), Go-Zeile im Abschlussplan (m7). Begründet weggelassen: T5 auf alle Stufen (m3; der geänderte Aufruf protokolliert nur auf ERROR, der Guard ließe es nur als fast doppelten Test zu) und 422 im angepassten P5-Test (m5; T1 prüft die 422, siehe M3). Mit Ziel im Abschlussplan („Neu 23.10." (6)): kaputte Adresse ohne `@` (m6) → B7 Teil 2; wachsende Sitzungs-Wörterbücher → B3 Teil 2. Commit-Titel ohne Umlaute (m9): der Squash-Titel trägt sie. Suite: mit DB 837/4, ohne DB 571/270.

## Big Picture

Bevor der Dienst irgendwo außerhalb des eigenen Rechners erreichbar ist, schließen wir drei Lücken. Bei allen dreien landen Dinge im Protokoll, die dort nicht hingehören.

1. **Gefälschte Protokollzeilen:** Die Sitzungskennung kommt vom Browser. Die n8n-Chat-Oberfläche erzeugt sie als UUID und legt sie im `localStorage` ab, der Nutzer kann sie also ändern. Heute nimmt der Dienst jede nicht-leere Zeichenkette an. Eine Kennung mit Zeilenumbruch erzeugt im Protokoll eine zweite, gefälschte Zeile, denn Profil-Writer und Dienstschicht schreiben die Kennung roh. **Neu:** Sitzungs- und Nachrichtenkennung müssen einem festen Muster entsprechen, sonst lehnt der Dienst ab.
2. **Passwort in der Adresse:** Steht in `BC1_BC0_URL` ein `user:passwort@`, landet es in jeder Protokollzeile von `httpx` und in der Meldung „nicht erreichbar". **Neu:** Der Dienst startet mit so einer Adresse nicht und sagt warum, ohne die Adresse zu wiederholen.
3. **Datenbank-Details im Protokoll:** Scheitert das Aufräumen eines Entwurfs, protokolliert der Writer die ganze Ausnahme (`%r`). Postgres hängt eine DETAIL-Zeile mit einem Ausschnitt der Zeile an, und dort steht Profiltext. **Neu:** Es werden nur Fehlerklasse und erste Zeile protokolliert, wie an der Nachbarstelle schon heute (`_fehlergrund`).

**Wen es betrifft:** niemanden im Normalbetrieb. n8n schickt eine UUID als Sitzungskennung und `exec-<Nummer>` als Nachrichtenkennung; beide passen. Vertrag, Datenbank und BC0 bleiben unberührt. Die Form der n8n-Kennung ist **recherchiert** (Quelltext `@n8n/chat`: `uuid` v4), **nicht gemessen**; die Live-Prüfung erfolgt beim Durchstich (#206). Gespeicherte Sitzungen mit abweichender Kennung gibt es live nicht: `bc1.sessions` war bei der Messung am 25.10. leer (Messpunkt M1 der Messung vor dem Live-Lauf).

**Nicht in diesem Paket (bleibt, wo es im Abschlussplan steht):**
- Die `bc1*`-Logger ausdrücklich auf INFO setzen. Das schützt vor einer fremden Logging-Konfiguration, und die entsteht erst auf dem Server → **B3 Teil 2**.
- Der Traceback, den uvicorn bei einer *unerwarteten* Ausnahme schreibt → **B7 Teil 2**.

## Entscheidungen (Claude, 25.10.)

| # | Entscheidung | Warum |
|---|---|---|
| E1 | Muster für `session_id` und `message_id`: `^[A-Za-z0-9_-]{1,64}$` | Lässt die UUID der n8n-Chat-Oberfläche (36 Zeichen), `exec-<Nummer>`, die Testprofil-Kennungen (längste 36 Zeichen) und alle Test-Kennungen durch. Schließt Leerzeichen, Zeilenumbrüche, Steuerzeichen, Anführungszeichen und `\|` aus. Der Writer baut aus `\|` einen Schlüssel (`profil_writer.py`, `f"{session_id}\|{focus_step_id}"`). 64 Zeichen passen zur vorhandenen Maskierung der Dienstzeile (`_protokollwert` kürzt auf 64), so stehen in allen Protokollzeilen dieselben Kennungen. |
| E2 | Abweisung über das Standard-422 von FastAPI, ohne eigenen `chat_text` | Ein regulärer Browser schickt nie eine andere Kennung; die Abweisung trifft nur manipulierte Anfragen. Die leere Kennung wird schon heute so abgewiesen. FastAPIs 422-Behandlung protokolliert nichts. |
| E3 | Jedes `@` in `BC1_BC0_URL` abweisen, geprüft direkt nach dem `strip()`, **vor** `urlsplit` und der https-Prüfung | Ein Passwort mit `/`, `?` oder `#` (oder ein Tippfehler wie `https:///…`) entgeht einer Prüfung auf `netloc`, denn `urlsplit` schneidet vorher ab (gemessen vom Prüfer). Eine BC0-Basisadresse braucht kein `@`; BC1 hängt nur `/api/...` an. Die https-Meldung wiederholt die Adresse, deshalb muss diese Prüfung vorher kommen. |
| E4 | Writer: `_draft_aufraeumen` nutzt den vorhandenen `_fehlergrund` | Wiederverwenden statt neu bauen. Klasse und erste Zeile reichen zur Diagnose (Tabelle, Constraint, Meldung). |
| E5 | Die Maskierung `_protokollwert` in `api.py` bleibt und bekommt einen eigenen kleinen Test | Sie ist Verteidigung in der Tiefe, falls das Muster je fällt. Ihr bisheriger Test prüft nach der Änderung nur noch „keine Zeile"; ohne eigenen Test wäre sie ungeschützt. |

## Global Constraints

- TDD unter dem tdd-guard, nie umgangen. `*.py` unter `coe-factory/` nur mit Edit/Write/MultiEdit; Bash nur für pytest, git und Messungen. Ein neuer Test je Edit (ein parametrisierter Test zählt als einer). Jeder Zwischenschritt mit eigenem vollen pytest-Lauf.
- pytest aus `bc1-context-discovery/`: `BC1_TEST_DB_DSN=postgresql://postgres:test@localhost:55432/postgres .venv/bin/pytest -q -W error`.
- Wortlaut neu: `MELDUNG_URL_MIT_ZUGANGSDATEN = ("BC1_BC0_URL enthält ein @ — dort gehören keine Zugangsdaten hin. Das Passwort gehört nach BC1_BC0_KONTO_PASSWORT; in der Adresse stünde es in jeder Protokollzeile.")` in `bc1_service/bc0_meldungen.py`.
- Musterkonstante: `KENNUNG_MUSTER = r"^[A-Za-z0-9_-]{1,64}$"` in `bc1_service/api.py`.
- Commits auf Zweig `bc1-haertung-vor-betrieb`, Deutsch, Schluss `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Kein Push ohne OK.

## Review Focus

1. **Zeilenumbruch am Ende** (`"s1\n"`): Pythons `re` lässt `$` vor einem abschließenden Zeilenumbruch zu, die Rust-Regex von pydantic-core nicht (gemessen: mit `regex_engine="python-re"` ginge `"s1\n"` durch). Der Test deckt genau diesen Fall ab.
2. **Bestehende Aufrufer:** Alle Tests, die `/turn` mit eigenen Kennungen aufrufen, bleiben grün; gemessen wird genau ein Bestandstest rot (Task 1).
3. **Passwort mit `/`, `?`, `#`** und Tippfehler `https:///…` werden abgewiesen, ohne die Adresse auszugeben.

## Testmatrix

| Fall | Erwartung | Test |
|---|---|---|
| `session_id` mit `\n`, mit Leerzeichen, mit `\|`, mit 65 Zeichen; `message_id` mit `\n` | 422 | T1 (parametrisiert) |
| UUID als `session_id`, `exec-4711` als `message_id` | 200 | T2 |
| `_protokollwert("x status=fertig\nturn")` | `"x?status?fertig?turn"` | T6 |
| `BC1_BC0_URL` mit `user:pw@`, nur `user@`, `@` ohne Benutzer, lokales http mit `user:pw@`, Passwort mit `/` (https und http), Tippfehler `https:///user:pw@…` | `RuntimeError` mit genau `MELDUNG_URL_MIT_ZUGANGSDATEN` | T3 (parametrisiert) |
| Aufräumen scheitert mit DETAIL-Zeile | Protokoll enthält `draft_aufraeumen_fehlgeschlagen` und die erste Zeile, nicht die DETAIL-Zeile | T5 (DB) |

## Tasks

### Task 1 — Kennungsmuster im `TurnRequest`

Dateien: `bc1_service/api.py`, `tests/test_api.py`, `tests/test_protokoll.py`.

- [ ] T1 in `tests/test_api.py` (neben `test_leere_message_id_wird_abgewiesen`): `test_kennung_ausserhalb_des_musters_wird_abgewiesen(session, mid)`, parametrisiert über `("s1\n","m1")`, `("s 1","m1")`, `("s1|x","m1")`, `("x"*65,"m1")`, `("s1","m1\nturn korrelation=x")`. Erwartet: `_turn(_client(), mid, "Hallo", session=session).status_code == 422`.
- [ ] Volle Suite → RED (heute 200, Assertion-RED).
- [ ] `session_id`/`message_id` auf `Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")` umstellen (Literal; die Konstante kommt erst bei Grün).
- [ ] Volle Suite. Erwartet rot ist dann genau `tests/test_protokoll.py::test_fremd_gewaehlte_ids_koennen_keine_felder_faelschen` (Error-RED an der ersten Erwartungszeile, `IndexError`): Er schickt `session="x status=fertig\nturn"`, `message_id="m1 http=200"`; die Anfrage kommt nicht mehr an (422), es entsteht keine Dienstzeile.
- [ ] Nur die **Erwartungszeilen** dieses Tests ersetzen, die Aufrufzeile bleibt unverändert: `assert _zeilen(caplog) == []`. Die 422 selbst prüft T1.
- [ ] Volle Suite → GREEN.
- [ ] Refactoring bei Grün: das Literal in `KENNUNG_MUSTER` ziehen (beide Felder). Volle Suite.
- [ ] T2 `test_uuid_und_exec_kennung_werden_angenommen` (grün bei Ankunft, eigener Edit): Sitzung `"3f2b8c1e-9a4d-4e6f-8b7a-1c2d3e4f5a6b"`, Nachricht `"exec-4711"` → 200. Volle Suite.
- [ ] T6 `test_protokollwert_maskiert_fremde_zeichen` in `tests/test_protokoll.py` (grün bei Ankunft, eigener Edit): `_protokollwert("x status=fertig\nturn") == "x?status?fertig?turn"`. Volle Suite.
- [ ] Commit `fix(bc1): Sitzungs- und Nachrichtenkennung auf ein festes Muster (Härtung)`.

### Task 2 — Keine Zugangsdaten in `BC1_BC0_URL`

Dateien: `bc1_service/bc0_meldungen.py`, `tests/test_bc0_meldungen.py`.

- [ ] T3 `test_adresse_mit_at_zeichen_bricht_ab_ohne_sie_zu_wiederholen(url)` plus Import von `MELDUNG_URL_MIT_ZUGANGSDATEN` (zwei Edits: erst die Testfunktion, dann der Import), parametrisiert über `"https://bc1:geheim@bc0.example.org"`, `"https://bc1@bc0.example.org"`, `"https://@bc0.example.org"`, `"http://bc1:geheim@localhost:8000"`, `"https://bc1:ge/heim@bc0.example.org"`, `"http://bc1:ge/heim@bc0.example.org"`, `"https:///bc1:geheim@bc0.example.org"`. Erwartet: `RuntimeError` mit `str(...) == MELDUNG_URL_MIT_ZUGANGSDATEN`.
- [ ] Volle Suite → RED (Sammelfehler: Import fehlt).
- [ ] Nur die Konstante anlegen. Volle Suite → RED (`DID NOT RAISE` bzw. falsche Meldung).
- [ ] Die Prüfung in `lies_bc0_zugang` direkt nach dem `strip()` der Adresse, vor `urlsplit`. Volle Suite → GREEN.
- [ ] Commit `fix(bc1): Zugangsdaten in BC1_BC0_URL abweisen (Härtung)`.

### Task 3 — Writer protokolliert beim Aufräumen keine Nutzdaten

Dateien: `bc1_service/profil_writer.py`, `tests/test_profil_writer.py`.

- [ ] T5 `test_fehlgeschlagenes_aufraeumen_protokolliert_keine_detailzeile` (DB), nach dem Muster von `test_fehlgeschlagenes_aufraeumen_am_draft_liefert_trotzdem_aus` mit Trigger, aber `RAISE EXCEPTION 'Aufraeumen blockiert' USING DETAIL = 'PROFILTEXT_DARF_NICHT_INS_LOG'`. Erwartet: `"draft_aufraeumen_fehlgeschlagen"` und `"Aufraeumen blockiert"` im Protokoll, `"PROFILTEXT_DARF_NICHT_INS_LOG"` nicht.
- [ ] Volle Suite → RED.
- [ ] `grund=%r` → `grund=%s` mit `_fehlergrund(fehler)`.
- [ ] Volle Suite → GREEN.
- [ ] Commit `fix(bc1): Aufräumfehler ohne DETAIL-Zeile protokollieren (Härtung)`.

### Task 4 — Doku und Abschluss

- [ ] README, Abschnitt „Betriebsprotokoll": ein Satz zum Kennungsmuster (Abweisung mit 422) und dass `BC1_BC0_URL` kein `@` enthalten darf.
- [ ] Abschlussplan: „Neu 23.10." (3) und (7), „Neu 08.10. — aus B4" (3) (Userinfo) und der Writer-Teil von (6) erledigt; Logger-Stufe bleibt B3 Teil 2, uvicorn-Traceback B7 Teil 2; dazu der zurückgestellte Befund unten unter B7 Teil 2.
- [ ] Gegenprobe für T2 (nie rot gewesen): Kopie-Verfahren im Scratchpad, Muster ohne `-` → T2 muss rot werden. T1, T3, T5 waren im eigenen Zyklus rot.
- [ ] Gesamtprüfung durch einen unabhängigen Prüfer, volle Suite mit und ohne DB.
- [ ] Commit `docs(bc1): Härtung vor dem Betrieb — README und Abschlussplan`.

## Befundverbleib (Prüfung 25.10.)

| Befund | Schwere | Verbleib |
|---|---|---|
| I1 `"@" in netloc` übersieht Passwörter mit `/ ? #` und Tippfehler | Important | eingearbeitet (E3, T3, T4 gestrichen) |
| M1 Funktionsname `_protokollwert`, Begründung, Test fehlt | Minor | eingearbeitet (E5, T6) |
| M2 Länge 128 gegen Maskierung 64 | Minor | eingearbeitet (E1, `{1,64}`) |
| M3 Bestandstest: nur Erwartungszeilen, Konstante erst bei Grün | Minor | eingearbeitet (Task 1) |
| M4 Task 2 in Guard-Schritte schneiden | Minor | eingearbeitet (Task 2) |
| M5 Matrix und T1 widersprechen sich | Minor | eingearbeitet (Matrix „422") |
| M6 Gegenproben auf die falschen Tests | Minor | eingearbeitet (Gegenprobe T2) |
| M7 n8n-Kennung recherchiert statt gemessen; Bestand | Minor | eingearbeitet (Big Picture) |
| M8 `ProfilWriteError` trägt die DETAIL-Zeile im Text (heute nicht protokolliert) | Minor | **zurückgestellt → B7 Teil 2** (nächstes Paket am 25.10.): beim Anfassen auf `_fehlergrund` umstellen |
