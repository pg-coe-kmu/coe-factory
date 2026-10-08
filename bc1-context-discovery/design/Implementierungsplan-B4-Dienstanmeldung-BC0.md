# B4 Dienst-Anmeldung an BC0 — Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** BC1 meldet BC0 selbst „Interview läuft" (`im_interview`, beim Dienststart) und stößt nach jedem eingefrorenen Profil „Gate nachziehen" an — angemeldet mit dem Anwendungskonto.

**Architecture:** Ein neues, in sich geschlossenes Modul `bc1_service/bc0_meldungen.py` liest den Zugang, meldet sich je Meldung frisch an (`httpx`, Cookie) und übersetzt jede Absage in einen deutschen Satz. `main.py` baut den Melder vor den Pools und meldet nach `lade_kontext` (DB-Verbindung schon zurückgegeben); `api.py` hängt den Gate-Aufruf als FastAPI-Hintergrundaufgabe hinter die fertige Antwort. Keine DB-Änderung, kein Eingriff in Kern, Sitzung oder Fingerabdruck.

**Tech Stack:** Python 3.11, FastAPI 0.141.1 (`BackgroundTasks`), httpx 0.28.1 (`Client`, `MockTransport`), psycopg 3, pytest, uv, PostgreSQL 17 (Test-Container).

**Spec:** `bc1-context-discovery/design/Spec-B4-Dienstanmeldung-BC0.md` (abgenommen 06.10.2026, nach agy-Zweitmeinung überarbeitet).

**Zweitmeinung zum Plan (agy, 06.10., `Review-agy-Plan-B4-2026-10-06.md`) eingearbeitet:** C1 Start-Tests mit nicht startfähiger Fixture-Anfrage → `ANFRAGE_A` (+ `UPDATE` auf `im_interview`) · I1 `"gesetzt": null` → `or []` + Test · I2 Melder-Erwartung in `start.py` im Docstring benannt (kein `Protocol` — ein Aufrufer) · I3 401-nach-Login auch für das Gate · M1 Log-Assert ohne Tupel-Entpacken. **Nicht übernommen:** M2 (`anfrage_id or "unbekannt"` im Gate-Log) — im Betrieb ist `BC1_ANFRAGE_ID` Pflicht, `None` gibt es nur in Tests; ein Ersatztext wäre Fehlerbehandlung für einen unmöglichen Fall.

## Global Constraints

- Arbeitsverzeichnis für alle Befehle: `coe-factory/bc1-context-discovery/`; Zweig `bc1-b4-dienstanmeldung`.
- Tests: `uv run pytest …`; DB-Tests brauchen `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres"` (Container: `colima start && docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:17`), sonst skippen sie. Abschluss immer mit `-W error`.
- **TDD-Guard aktiv, NIE umgehen** (kein `tdd-guard off`, kein Settings-Bypass, keine Datei-Änderung per Bash an `*.py`). Bei einem Block das Skill `tdd-guard` aufrufen; jeden neu gelösten Block dort in die Lessons-Tabelle eintragen.
- **Ein neuer Test je Edit** (Guard-Regel „Multiple test addition"): Testblöcke eines Steps einzeln einfügen, jeweils RED laufen lassen, dann die Implementierung für genau diesen RED. Die Code-Blöcke unten zeigen den **Endstand** eines Steps, nicht einen einzigen Edit.
- **Kein Netz in Tests.** BC0 wird ausschließlich über `httpx.MockTransport` nachgebaut.
- **Das Passwort steht in keiner Meldung, keinem Log, keinem `repr`.** `httpx`-Ausnahmen werden nie verkettet und nie geloggt (sie tragen den Anmelderumpf, gemessen 06.10.).
- Umgebungsvariablen (exakt): `BC1_BC0_URL`, `BC1_BC0_KONTO_EMAIL`, `BC1_BC0_KONTO_PASSWORT`, `BC1_BC0_MELDUNGEN` (einziger erlaubter Wert `aus`).
- Adresse: Schema `https`, oder `http` mit Hostname genau `localhost`/`127.0.0.1`; Prüfung über `urllib.parse.urlsplit`, nie per Präfix.
- Zeitlimit je Aufruf 10 s; Weiterleitungen werden nicht befolgt (httpx-Standard `follow_redirects=False`).
- „Interview läuft" nur aus Status `zugeordnet`; bei `im_interview` kein Aufruf.
- **Kein** `PUT …/zuordnung`, **kein** Gate-Aufruf beim Start, **kein** Status in `Bc0Kontext`.
- Meldungstexte wörtlich aus Spec Abschnitt 5; deutsche Anführungszeichen („ ") nie in Python-String-Literale, im Text `'…'`.
- Kein Push, kein PR, kein Posten auf GitHub ohne OK der BC1-Projektleitung. Live-Probe und Live-Start führt die BC1-Projektleitung aus; Claude meldet sich nie mit dem echten Passwort an und liest `ZUGAENGE-LOKAL.env` nicht.
- **Pause nach jedem Task:** Zwischenstand an die BC1-Projektleitung, dann auf Go warten. Review je Task und Gesamtreview per **agy**.
- Commit-Nachrichten enden mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Lokales BC0 ohne https** (`http://localhost`, BC0 setzt das Cookie mit `Secure`) → die Anmeldung klappt, der Folgeaufruf bekommt 401 → erwartet der eigene Satz mit dem Hinweis `BC0_COOKIE_UNSICHER=1`, nicht „Passwort falsch". *Test in Task 2.*
2. **Passwort mit Leerzeichen am Rand oder Sonderzeichen** (`' pa"ss\\wört '`) → wird unverändert an BC0 geschickt (nicht beschnitten), steht trotzdem in keiner Meldung. *Tests in Task 1 und Task 2.*
3. **`BC1_BC0_URL` mit Schrägstrich am Ende oder ohne Rechnernamen** (`https://bc0.example.org/`, `https://`) → kein doppelter Schrägstrich im Pfad; ohne Rechnernamen Startabbruch. *Test in Task 1.*
4. **BC0 (oder ein Proxy davor) antwortet ohne JSON** — 502 mit HTML-Seite, oder 200 mit HTML → verständlicher Satz mit gekürztem Antworttext, kein `JSONDecodeError`. *Tests in Task 2.*
5. **Unerwartete Ausnahme im Hintergrund-Gate-Aufruf** (Programmfehler, nicht `Bc0MeldungFehler`) → WARNING mit nur dem Klassennamen, Antwort unverändert, keine Ausnahme nach außen. *Test in Task 5.*

---

## Dateistruktur

| Datei | Änderung | Verantwortung |
|---|---|---|
| `bc1_service/bc0_meldungen.py` | **neu** | Zugang lesen, Melder (Login + zwei Meldungen), Fehlersätze, Live-Probe |
| `tests/test_bc0_meldungen.py` | **neu** | Nachgebautes BC0 (`MockTransport`), alle Fälle des Moduls |
| `pyproject.toml`, `uv.lock` | ändern | `httpx` in die Gruppe `service` |
| `bc1_service/start.py` | ändern | `melde_interview_beginn(melder, anfrage_id, status)` |
| `bc1_service/main.py` | ändern | Melder bauen (vor den Pools), Status lesen, melden (nach dem `with`) |
| `bc1_service/api.py` | ändern | `create_app(…, melder=None)`, Hintergrundaufgabe nach `fertig` |
| `tests/test_start.py`, `tests/test_api.py`, `tests/test_api_profil.py`, `tests/test_postgres_init.py` | erweitern | Nachweise Start, Abschluss, Verdrahtung |
| `README.md`, `bc1_service/n8n/SMOKE.md` | ändern | Betrieb: neue Variablen, Startabbrüche, Live-Probe |
| `design/Abschlussplan-BC1.md` | ändern | B4 gebaut, Rückstellungen mit Ziel |

---

### Task 1: Zugang lesen — `lies_bc0_zugang`, `Bc0Zugang` (Pflicht mit Aus-Schalter)

**Files:**
- Create: `bc1_service/bc0_meldungen.py`
- Create: `tests/test_bc0_meldungen.py`
- Modify: `pyproject.toml` (Gruppe `service`), `uv.lock`

**Interfaces:**
- Consumes: —
- Produces:
  - `Bc0Zugang(url: str, email: str, passwort: str)` — frozen dataclass, `passwort` mit `repr=False`
  - `lies_bc0_zugang(umgebung: Mapping[str, str]) -> Bc0Zugang | None` (`None` = „aus"; Fehler = `RuntimeError` mit Spec-Satz)
  - Konstanten `MELDUNG_ZUGANG_UNVOLLSTAENDIG`, `MELDUNG_SCHALTER_UNBEKANNT`, `MELDUNG_KEIN_HTTPS`
  - (`baue_melder` und `MELDUNG_AUS` entstehen in Task 2 zusammen mit `Bc0Melder` — so gibt es in Task 1 keinen ungetesteten Zweig.)

- [ ] **Step 1: Abhängigkeit** — in `pyproject.toml` die Gruppe `service` um `"httpx",` ergänzen (nach `"jsonschema",`), dann `uv lock` und `uv sync --all-groups`. Prüfen: `git diff uv.lock` zeigt nur die Gruppenzugehörigkeit, keine neue Version (httpx bleibt 0.28.1).

- [ ] **Step 2: Tests schreiben (einzeln, je RED)** — `tests/test_bc0_meldungen.py`:

```python
"""B4: Meldungen an BC0 — Zugang, Melder, Fehlersätze, Live-Probe.

Kein Netz: BC0 wird mit httpx.MockTransport nachgebaut (Endpunkte und Antworten wie
bc0_auth/routen.py und app.py v3.12, nachgelesen 06.10.2026).
"""
import pytest

from bc1_service.bc0_meldungen import (
    MELDUNG_KEIN_HTTPS,
    MELDUNG_SCHALTER_UNBEKANNT,
    MELDUNG_ZUGANG_UNVOLLSTAENDIG,
    Bc0Zugang,
    lies_bc0_zugang,
)

MANDANT = "11111111-1111-1111-1111-111111111111"
PASSWORT = ' pa"ss\\wört '            # Rand-Leerzeichen und Sonderzeichen: bleibt unverändert
VOLL = {
    "BC1_BC0_URL": "https://bc0.example.org",
    "BC1_BC0_KONTO_EMAIL": "dienst@example.org",
    "BC1_BC0_KONTO_PASSWORT": PASSWORT,
}


def test_vollstaendiger_zugang_wird_gelesen_und_das_passwort_nicht_beschnitten():
    zugang = lies_bc0_zugang(VOLL)
    assert zugang == Bc0Zugang("https://bc0.example.org", "dienst@example.org", PASSWORT)


def test_passwort_steht_nicht_im_repr():
    assert PASSWORT not in repr(lies_bc0_zugang(VOLL))


@pytest.mark.parametrize("fehlt", sorted(VOLL))
def test_ein_fehlender_name_bricht_ab_und_wird_genannt(fehlt):
    umgebung = {k: v for k, v in VOLL.items() if k != fehlt}
    with pytest.raises(RuntimeError) as fehler:
        lies_bc0_zugang(umgebung)
    assert str(fehler.value) == MELDUNG_ZUGANG_UNVOLLSTAENDIG.format(namen=fehlt)


def test_alle_fehlenden_namen_stehen_in_einer_meldung():
    with pytest.raises(RuntimeError) as fehler:
        lies_bc0_zugang({"BC1_BC0_KONTO_PASSWORT": "   "})   # nur Leerzeichen = fehlt
    assert str(fehler.value) == MELDUNG_ZUGANG_UNVOLLSTAENDIG.format(
        namen="BC1_BC0_URL, BC1_BC0_KONTO_EMAIL, BC1_BC0_KONTO_PASSWORT")


def test_aus_schalter_liefert_none_auch_ohne_zugang():
    assert lies_bc0_zugang({"BC1_BC0_MELDUNGEN": "aus"}) is None


def test_aus_schalter_gewinnt_auch_bei_vollstaendigem_zugang():
    assert lies_bc0_zugang({**VOLL, "BC1_BC0_MELDUNGEN": " aus "}) is None


@pytest.mark.parametrize("wert", ["AUS", "off", "nein", "0"])
def test_unbekannter_schalter_bricht_ab(wert):
    with pytest.raises(RuntimeError) as fehler:
        lies_bc0_zugang({**VOLL, "BC1_BC0_MELDUNGEN": wert})
    assert str(fehler.value) == MELDUNG_SCHALTER_UNBEKANNT.format(wert=wert)


@pytest.mark.parametrize("url", [
    "http://bc0.example.org",
    "http://localhost.example.org",        # Präfix-Falle: kein localhost
    "ftp://bc0.example.org",
    "https://",                             # kein Rechnername
    "bc0.example.org",
])
def test_unsichere_oder_unvollstaendige_adresse_bricht_ab(url):
    with pytest.raises(RuntimeError) as fehler:
        lies_bc0_zugang({**VOLL, "BC1_BC0_URL": url})
    assert str(fehler.value) == MELDUNG_KEIN_HTTPS.format(url=url)


@pytest.mark.parametrize("url, erwartet", [
    ("http://localhost:8000", "http://localhost:8000"),
    ("http://127.0.0.1:8000/", "http://127.0.0.1:8000"),
    ("https://bc0.example.org/", "https://bc0.example.org"),
    (" https://bc0.example.org ", "https://bc0.example.org"),
])
def test_erlaubte_adressen_werden_ohne_schraegstrich_am_ende_uebernommen(url, erwartet):
    assert lies_bc0_zugang({**VOLL, "BC1_BC0_URL": url}).url == erwartet
```

- [ ] **Step 3: Implementierung (je RED minimal)** — `bc1_service/bc0_meldungen.py`, Endstand nach Task 1:

```python
"""Meldungen von BC1 an BC0 (B4): 'Interview laeuft' und 'Gate nachziehen'.

BC1 meldet sich dafuer mit dem Anwendungskonto an (POST /api/auth/login, Cookie
bc0_sitzung). Je Meldung eine frische Anmeldung: eine BC0-Sitzung gilt 8 Stunden,
zwischen Start und Abschluss koennen Stunden liegen.

Sicherheit: Das Passwort steht in keiner Meldung, keinem Log, keinem repr. Ausnahmen
von httpx werden nie verkettet und nie geloggt — sie tragen die Anfrage samt Rumpf,
beim Login also das Passwort (gemessen 06.10.2026: e.request.content).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

_PFLICHT = ("BC1_BC0_URL", "BC1_BC0_KONTO_EMAIL", "BC1_BC0_KONTO_PASSWORT")
_ERLAUBTE_HTTP_HOSTS = ("localhost", "127.0.0.1")   # lokales BC0, sonst nur https

# Wortlaut aus der Spec B4, Abschnitt 5 — in Tests festgenagelt.
MELDUNG_ZUGANG_UNVOLLSTAENDIG = (
    "BC0-Zugang unvollständig: {namen} fehlt. Ohne Zugang meldet BC1 weder "
    "'im_interview' noch das Gate. Entweder setzen oder bewusst BC1_BC0_MELDUNGEN=aus.")
MELDUNG_SCHALTER_UNBEKANNT = (
    "BC1_BC0_MELDUNGEN='{wert}' ist unbekannt. Erlaubt ist nur 'aus' — oder die "
    "Variable weglassen.")
MELDUNG_KEIN_HTTPS = (
    "BC1_BC0_URL='{url}' ist keine https-Adresse. Das Passwort geht nur verschlüsselt "
    "über das Netz (Ausnahme: localhost).")


@dataclass(frozen=True)
class Bc0Zugang:
    url: str
    email: str
    passwort: str = field(repr=False)


def lies_bc0_zugang(umgebung: Mapping[str, str]) -> Bc0Zugang | None:
    """None heisst: Meldungen bewusst aus. Ein Tippfehler im Schalter schaltet nicht ab."""
    schalter = umgebung.get("BC1_BC0_MELDUNGEN", "").strip()
    if schalter:
        if schalter == "aus":
            return None
        raise RuntimeError(MELDUNG_SCHALTER_UNBEKANNT.format(wert=schalter))
    roh = {name: umgebung.get(name, "") for name in _PFLICHT}
    fehlend = [name for name in _PFLICHT if not roh[name].strip()]
    if fehlend:
        raise RuntimeError(MELDUNG_ZUGANG_UNVOLLSTAENDIG.format(namen=", ".join(fehlend)))
    url_roh = roh["BC1_BC0_URL"].strip()
    teile = urlsplit(url_roh)
    sicher = teile.scheme == "https" or (
        teile.scheme == "http" and teile.hostname in _ERLAUBTE_HTTP_HOSTS)
    if not (sicher and teile.hostname):
        raise RuntimeError(MELDUNG_KEIN_HTTPS.format(url=url_roh))
    # Das Passwort wird NICHT beschnitten — Leerzeichen koennen dazugehoeren.
    return Bc0Zugang(url=url_roh.rstrip("/"), email=roh["BC1_BC0_KONTO_EMAIL"].strip(),
                     passwort=roh["BC1_BC0_KONTO_PASSWORT"])
```

Hinweis: Die Meldung für `"https://"` nennt den Rohwert; `teile.hostname` ist dort `None` → abgewiesen. `" https://bc0.example.org "` wird vor der Prüfung beschnitten (die Adresse, nicht das Passwort).

- [ ] **Step 4: Grün** — `uv run pytest tests/test_bc0_meldungen.py -v` → alle PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock bc1_service/bc0_meldungen.py tests/test_bc0_meldungen.py
git commit -m "BC1 B4: BC0-Zugang lesen (Pflicht mit Aus-Schalter, nur https)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: Pause** — agy-Review des Task-Diffs, Zwischenstand an die BC1-Projektleitung, auf Go warten.

---

### Task 2: Melder — Anmeldung, „Interview läuft", „Gate nachziehen", Fehlersätze, `baue_melder`

**Files:**
- Modify: `bc1_service/bc0_meldungen.py`
- Modify: `tests/test_bc0_meldungen.py`

**Interfaces:**
- Consumes: `Bc0Zugang`, `lies_bc0_zugang` (Task 1)
- Produces:
  - `baue_melder(umgebung: Mapping[str, str], company_id: str) -> Bc0Melder | None` — `None` beim „aus" (dann WARNING `MELDUNG_AUS` auf Logger `bc1_service.bc0_meldungen`); Konfigurationsfehler = `RuntimeError` aus `lies_bc0_zugang`
  - `class Bc0MeldungFehler(RuntimeError)`
  - `Bc0Melder(zugang: Bc0Zugang, company_id: str, *, transport: httpx.BaseTransport | None = None)`
    - `.melde_interview_laeuft(anfrage_id: str) -> None` — `PUT /api/companies/{company_id}/anfragen/{anfrage_id}/status`, Rumpf `{"status": "im_interview"}`
    - `.ziehe_gate_nach() -> list[str]` — `POST /api/companies/{company_id}/anfragen/gate_nachziehen`, gibt `gesetzt` zurück
    - `.lies_konto() -> dict` — `GET /api/auth/me` (nur Live-Probe, Task 3)
  - Konstanten `ZEITLIMIT_SEKUNDEN = 10`, `MELDUNG_AUS`, `MELDUNG_ANMELDUNG_ABGELEHNT`, `MELDUNG_GESPERRT`, `MELDUNG_SITZUNG_NICHT_ANGENOMMEN`, `MELDUNG_KEIN_SCHREIBRECHT`, `MELDUNG_MANDANT_UNBEKANNT`, `MELDUNG_ANTWORT`, `MELDUNG_NICHT_ERREICHBAR`

- [ ] **Step 1: Nachgebautes BC0 + Tests (einzeln, je RED)** — in `tests/test_bc0_meldungen.py` ergänzen (Imports oben zusammenführen):

```python
import json
import logging

import httpx

from bc1_service.bc0_meldungen import (
    MELDUNG_ANMELDUNG_ABGELEHNT,
    MELDUNG_ANTWORT,
    MELDUNG_AUS,
    MELDUNG_GESPERRT,
    MELDUNG_KEIN_SCHREIBRECHT,
    MELDUNG_MANDANT_UNBEKANNT,
    MELDUNG_NICHT_ERREICHBAR,
    MELDUNG_SITZUNG_NICHT_ANGENOMMEN,
    ZEITLIMIT_SEKUNDEN,
    Bc0MeldungFehler,
    Bc0Melder,
    baue_melder,
)

ANFRAGE = "A-2026-01"


def _eigene(caplog, logger="bc1_service.bc0_meldungen"):
    return [r.getMessage() for r in caplog.records if r.name == logger]


def test_baue_melder_beim_aus_liefert_none_und_warnt(caplog):
    with caplog.at_level(logging.WARNING, logger="bc1_service.bc0_meldungen"):
        assert baue_melder({"BC1_BC0_MELDUNGEN": "aus"}, MANDANT) is None
    assert _eigene(caplog) == [MELDUNG_AUS]


def test_baue_melder_mit_zugang_liefert_einen_melder_ohne_warnung(caplog):
    with caplog.at_level(logging.WARNING, logger="bc1_service.bc0_meldungen"):
        assert isinstance(baue_melder(VOLL, MANDANT), Bc0Melder)
    assert _eigene(caplog) == []


def test_baue_melder_reicht_konfigurationsfehler_durch():
    with pytest.raises(RuntimeError, match="BC0-Zugang unvollständig"):
        baue_melder({}, MANDANT)
COOKIE = "bc0_sitzung=schluessel-1; HttpOnly; Secure; Path=/; SameSite=lax"


class FakeBc0:
    """BC0 im Kleinen: Login setzt das Cookie, die Fachaufrufe verlangen es.

    `login` / `aktion` ersetzen die Antwort des jeweiligen Schritts (Funktion
    request -> Response, darf auch eine httpx-Ausnahme werfen)."""

    def __init__(self, *, login=None, aktion=None, konto=None):
        self.anfragen: list[httpx.Request] = []
        self._login = login
        self._aktion = aktion
        self.konto = konto or {"rolle": "benutzer", "ist_admin": False,
                               "darf_schreiben": True, "mandanten": [MANDANT]}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.anfragen.append(request)
        if request.url.path == "/api/auth/login":
            if self._login is not None:
                return self._login(request)
            return httpx.Response(200, json={"ok": True}, headers={"set-cookie": COOKIE})
        if self._aktion is not None:
            return self._aktion(request)
        if request.headers.get("cookie") != "bc0_sitzung=schluessel-1":
            return httpx.Response(401, json={"detail": "Nicht angemeldet."})
        if request.url.path.endswith("/gate_nachziehen"):
            return httpx.Response(200, json={"geprueft": 2, "gesetzt": [ANFRAGE],
                                             "anfragen": []})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"ok": True, "anfrage_id": ANFRAGE,
                                             "status_alt": "zugeordnet",
                                             "status": "im_interview"})
        if request.url.path == "/api/auth/me":
            return httpx.Response(200, json=self.konto)
        return httpx.Response(404, json={"detail": "Not Found"})


def _melder(bc0, url="https://bc0.example.org"):
    zugang = lies_bc0_zugang({**VOLL, "BC1_BC0_URL": url})
    return Bc0Melder(zugang, MANDANT, transport=httpx.MockTransport(bc0))


def test_anmeldung_schickt_email_und_passwort_unveraendert():
    bc0 = FakeBc0()
    _melder(bc0).melde_interview_laeuft(ANFRAGE)
    login = bc0.anfragen[0]
    assert login.method == "POST" and login.url.path == "/api/auth/login"
    assert json.loads(login.content) == {"email": "dienst@example.org", "passwort": PASSWORT}


def test_interview_laeuft_setzt_den_status_mit_cookie():
    bc0 = FakeBc0()
    _melder(bc0).melde_interview_laeuft(ANFRAGE)
    status = bc0.anfragen[1]
    assert status.method == "PUT"
    assert status.url.path == f"/api/companies/{MANDANT}/anfragen/{ANFRAGE}/status"
    assert json.loads(status.content) == {"status": "im_interview"}
    assert status.headers["cookie"] == "bc0_sitzung=schluessel-1"


def test_gate_nachziehen_liefert_die_gesetzten_anfragen():
    bc0 = FakeBc0()
    assert _melder(bc0).ziehe_gate_nach() == [ANFRAGE]
    gate = bc0.anfragen[1]
    assert gate.method == "POST"
    assert gate.url.path == f"/api/companies/{MANDANT}/anfragen/gate_nachziehen"


def test_gate_ohne_gesetzte_anfragen_auch_bei_null():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(
        200, json={"geprueft": 0, "gesetzt": None, "anfragen": []}))
    assert _melder(bc0).ziehe_gate_nach() == []


def test_jede_meldung_meldet_sich_frisch_an():
    bc0 = FakeBc0()
    melder = _melder(bc0)
    melder.melde_interview_laeuft(ANFRAGE)
    melder.ziehe_gate_nach()
    pfade = [a.url.path for a in bc0.anfragen]
    assert pfade.count("/api/auth/login") == 2


def test_zeitlimit_ist_zehn_sekunden():
    bc0 = FakeBc0()
    _melder(bc0).ziehe_gate_nach()
    assert ZEITLIMIT_SEKUNDEN == 10
    assert bc0.anfragen[0].extensions["timeout"] == {
        "connect": 10, "read": 10, "write": 10, "pool": 10}


def _fehler(bc0, aufruf="gate", url="https://bc0.example.org") -> Bc0MeldungFehler:
    melder = _melder(bc0, url)
    with pytest.raises(Bc0MeldungFehler) as fehler:
        if aufruf == "gate":
            melder.ziehe_gate_nach()
        else:
            melder.melde_interview_laeuft(ANFRAGE)
    assert PASSWORT not in str(fehler.value)
    return fehler.value


def test_falsches_passwort():
    bc0 = FakeBc0(login=lambda r: httpx.Response(
        401, json={"detail": "E-Mail-Adresse oder Passwort ist falsch."}))
    assert str(_fehler(bc0)) == MELDUNG_ANMELDUNG_ABGELEHNT


@pytest.mark.parametrize("kopf, minuten", [("600", 10), ("20", 1), (None, 1), ("bald", 1)])
def test_gesperrte_anmeldung_nennt_die_wartezeit(kopf, minuten):
    headers = {"Retry-After": kopf} if kopf is not None else {}
    bc0 = FakeBc0(login=lambda r: httpx.Response(
        429, json={"detail": "Zu viele fehlgeschlagene Anmeldeversuche."}, headers=headers))
    assert str(_fehler(bc0)) == MELDUNG_GESPERRT.format(minuten=minuten)


@pytest.mark.parametrize("aufruf, aktion", [
    ("status", "Status im_interview"), ("gate", "Gate nachziehen")])
def test_lokales_bc0_ohne_https_nimmt_das_sichere_cookie_nicht_zurueck(aufruf, aktion):
    # Gemessen 06.10.: httpx schickt ein Secure-Cookie nicht ueber http://localhost.
    bc0 = FakeBc0()
    fehler = _fehler(bc0, aufruf=aufruf, url="http://localhost:8000")
    assert str(fehler) == MELDUNG_SITZUNG_NICHT_ANGENOMMEN.format(aktion=aktion)


def test_kein_schreibrecht():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(
        403, json={"detail": "Nur lesender Zugang."}))
    assert str(_fehler(bc0)) == MELDUNG_KEIN_SCHREIBRECHT.format(
        aktion="Gate nachziehen", detail="Nur lesender Zugang.")


def test_mandant_nicht_zugewiesen_kommt_als_404():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(404, json={"detail": "Mandant unbekannt."}))
    assert str(_fehler(bc0, aufruf="status")) == MELDUNG_MANDANT_UNBEKANNT.format(
        company_id=MANDANT)


@pytest.mark.parametrize("code, detail", [
    (404, "Unbekannte Anfrage: A-2026-01"),
    (400, "Rueckschritt von 'am_gate' auf 'im_interview' ist nicht vorgesehen."),
    (500, "Interner Fehler"),
])
def test_andere_absagen_nennen_code_und_detail(code, detail):
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(code, json={"detail": detail}))
    assert str(_fehler(bc0, aufruf="status")) == MELDUNG_ANTWORT.format(
        aktion="Status im_interview", code=code, detail=detail)


def test_antwort_ohne_json_nennt_den_gekuerzten_text():
    seite = "<html>" + "x" * 500 + "</html>"
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(502, text=seite))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Gate nachziehen", code=502, detail=seite[:200])


def test_erfolg_ohne_json_ist_ebenfalls_ein_fehler():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(200, text="<html>Wartung</html>"))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Gate nachziehen", code=200, detail="<html>Wartung</html>")


def test_weiterleitung_wird_nicht_befolgt():
    bc0 = FakeBc0(aktion=lambda r: httpx.Response(
        302, headers={"location": "https://anderswo.example.org/"}))
    assert str(_fehler(bc0)) == MELDUNG_ANTWORT.format(
        aktion="Gate nachziehen", code=302, detail="")
    assert len(bc0.anfragen) == 2                      # Login + Aufruf, kein Folgen


def _wirft(ausnahme_klasse):
    def antwort(request):
        raise ausnahme_klasse("kaputt", request=request)
    return antwort


@pytest.mark.parametrize("klasse", [httpx.ConnectError, httpx.ReadTimeout])
def test_nicht_erreichbar_beim_login_ohne_verkettung(klasse):
    fehler = _fehler(FakeBc0(login=_wirft(klasse)))
    assert str(fehler) == MELDUNG_NICHT_ERREICHBAR.format(
        url="https://bc0.example.org", art=klasse.__name__)
    # Die httpx-Ausnahme traegt den Login-Rumpf mit dem Passwort — sie darf an der
    # BC1-Ausnahme nicht haengen, weder als Ursache noch als Kontext.
    assert fehler.__cause__ is None and fehler.__context__ is None


def test_nicht_erreichbar_beim_fachaufruf():
    fehler = _fehler(FakeBc0(aktion=_wirft(httpx.ConnectError)))
    assert str(fehler) == MELDUNG_NICHT_ERREICHBAR.format(
        url="https://bc0.example.org", art="ConnectError")
```

(Die Imports oben in der Testdatei mit denen aus Task 1 zusammenführen.)

Hinweis zu `test_zeitlimit_ist_zehn_sekunden`: `httpx` 0.28.1 legt das Zeitlimit je Anfrage in `request.extensions["timeout"]` ab — gemessen 06.10. mit `MockTransport`: `{'connect': 10, 'read': 10, 'write': 10, 'pool': 10}`.

- [ ] **Step 2: Implementierung (je RED minimal)** — `bc1_service/bc0_meldungen.py`, Endstand nach Task 2 (Task-1-Teil bleibt; oben `import logging`, `import httpx` und `log = logging.getLogger(__name__)` ergänzen):

```python
import logging

import httpx

log = logging.getLogger(__name__)

ZEITLIMIT_SEKUNDEN = 10

MELDUNG_AUS = (
    "Meldungen an BC0 sind ausgeschaltet (BC1_BC0_MELDUNGEN=aus) — 'im_interview' und "
    "das Gate setzt BC0 von Hand.")

MELDUNG_ANMELDUNG_ABGELEHNT = (
    "BC0 lehnt die Anmeldung ab (E-Mail oder Passwort falsch). BC1_BC0_KONTO_EMAIL "
    "und BC1_BC0_KONTO_PASSWORT prüfen.")
MELDUNG_GESPERRT = (
    "BC0 sperrt die Anmeldung nach zu vielen Fehlversuchen noch {minuten} Minute(n). "
    "Erst den Zugang prüfen, dann warten.")
MELDUNG_SITZUNG_NICHT_ANGENOMMEN = (
    "BC0 nimmt die Anmeldung bei '{aktion}' nicht an (401), obwohl sie geklappt hat. "
    "Bei einem lokalen BC0 ohne https muss dort BC0_COOKIE_UNSICHER=1 gesetzt sein.")
MELDUNG_KEIN_SCHREIBRECHT = (
    "BC0 verweigert '{aktion}' (403): {detail} Das Anwendungskonto braucht "
    "Schreibrecht (Rolle 'benutzer' oder 'admin').")
MELDUNG_MANDANT_UNBEKANNT = (
    "BC0 kennt den Mandanten {company_id} für dieses Anwendungskonto nicht (404). "
    "Das Konto braucht den Mandanten zugewiesen.")
MELDUNG_ANTWORT = "BC0 antwortet auf '{aktion}' mit {code}: {detail}"
MELDUNG_NICHT_ERREICHBAR = (
    "BC0 unter {url} ist nicht erreichbar ({art}). Läuft BC0, stimmt BC1_BC0_URL?")

_ANMELDUNG = "Anmeldung"
_MANDANT_UNBEKANNT_DETAIL = "Mandant unbekannt."   # bc0_auth.abhaengigkeiten.pruefe_mandant


class Bc0MeldungFehler(RuntimeError):
    """Eine Meldung an BC0 ist gescheitert; der Text ist fuer Menschen gedacht."""


def _detail(antwort: httpx.Response) -> str:
    """BC0s detail-Text; ohne JSON (Proxy-Seite) der Antworttext. Auf 200 Zeichen."""
    try:
        daten = antwort.json()
    except ValueError:
        daten = None
    detail = daten.get("detail") if isinstance(daten, dict) else None
    if not isinstance(detail, str):
        detail = antwort.text
    return detail[:200]


def _minuten(antwort: httpx.Response) -> int:
    """Wie BC0 selbst: max(1, round(Sekunden / 60)); unlesbar oder fehlend = 1."""
    try:
        sekunden = int(antwort.headers.get("Retry-After", ""))
    except ValueError:
        return 1
    return max(1, round(sekunden / 60))


class Bc0Melder:
    """Je Meldung: frischer Client -> Login -> Aufruf -> schliessen."""

    def __init__(self, zugang: Bc0Zugang, company_id: str, *,
                 transport: httpx.BaseTransport | None = None) -> None:
        self._zugang = zugang
        self._company_id = company_id
        self._transport = transport             # nur Tests (httpx.MockTransport)

    def melde_interview_laeuft(self, anfrage_id: str) -> None:
        self._melden("Status im_interview", "PUT",
                     f"/api/companies/{self._company_id}/anfragen/{anfrage_id}/status",
                     {"status": "im_interview"})

    def ziehe_gate_nach(self) -> list[str]:
        daten = self._melden(
            "Gate nachziehen", "POST",
            f"/api/companies/{self._company_id}/anfragen/gate_nachziehen")
        return list(daten.get("gesetzt") or [])          # auch bei "gesetzt": null

    def lies_konto(self) -> dict:
        return self._melden("Konto lesen", "GET", "/api/auth/me")

    def _melden(self, aktion: str, methode: str, pfad: str, rumpf: dict | None = None) -> dict:
        art = None
        try:
            with httpx.Client(base_url=self._zugang.url, timeout=ZEITLIMIT_SEKUNDEN,
                              transport=self._transport) as client:
                self._pruefe(client.post("/api/auth/login", json={
                    "email": self._zugang.email, "passwort": self._zugang.passwort}),
                    _ANMELDUNG)
                antwort = client.request(methode, pfad, json=rumpf)
                self._pruefe(antwort, aktion)
                return self._json(antwort, aktion)
        except httpx.RequestError as fehler:
            art = type(fehler).__name__
        # Bewusst AUSSERHALB des except-Blocks: so haengt die httpx-Ausnahme (mit dem
        # Login-Rumpf) weder als __cause__ noch als __context__ an der BC1-Ausnahme.
        raise Bc0MeldungFehler(MELDUNG_NICHT_ERREICHBAR.format(url=self._zugang.url, art=art))

    def _pruefe(self, antwort: httpx.Response, aktion: str) -> None:
        code = antwort.status_code
        if 200 <= code < 300:
            return
        detail = _detail(antwort)
        if aktion == _ANMELDUNG and code == 401:
            raise Bc0MeldungFehler(MELDUNG_ANMELDUNG_ABGELEHNT)
        if aktion == _ANMELDUNG and code == 429:
            raise Bc0MeldungFehler(MELDUNG_GESPERRT.format(minuten=_minuten(antwort)))
        if code == 401:
            raise Bc0MeldungFehler(MELDUNG_SITZUNG_NICHT_ANGENOMMEN.format(aktion=aktion))
        if code == 403:
            raise Bc0MeldungFehler(MELDUNG_KEIN_SCHREIBRECHT.format(aktion=aktion, detail=detail))
        if code == 404 and detail == _MANDANT_UNBEKANNT_DETAIL:
            raise Bc0MeldungFehler(MELDUNG_MANDANT_UNBEKANNT.format(company_id=self._company_id))
        raise Bc0MeldungFehler(MELDUNG_ANTWORT.format(aktion=aktion, code=code, detail=detail))

    @staticmethod
    def _json(antwort: httpx.Response, aktion: str) -> dict:
        try:
            daten = antwort.json()
        except ValueError:
            daten = None
        if not isinstance(daten, dict):
            raise Bc0MeldungFehler(MELDUNG_ANTWORT.format(
                aktion=aktion, code=antwort.status_code, detail=antwort.text[:200]))
        return daten


def baue_melder(umgebung: Mapping[str, str], company_id: str) -> Bc0Melder | None:
    """None = Meldungen bewusst aus; dann steht es einmal deutlich im Log."""
    zugang = lies_bc0_zugang(umgebung)
    if zugang is None:
        log.warning(MELDUNG_AUS)
        return None
    return Bc0Melder(zugang, company_id)
```

Prüfpunkte für den Implementer: `_pruefe` und `_json` werfen im `try`, aber **nicht** im `except` — ihre Ausnahmen haben keinen Kontext. `httpx.RequestError` ist die Basisklasse von `ConnectError` und `TimeoutException`. Der Login-Rumpf wird nur im `client.post` gebaut, nirgends sonst.

- [ ] **Step 3: Grün** — `uv run pytest tests/test_bc0_meldungen.py -v` → alle PASS.

- [ ] **Step 4: Commit**

```bash
git add bc1_service/bc0_meldungen.py tests/test_bc0_meldungen.py
git commit -m "BC1 B4: Melder an BC0 (Anmeldung, im_interview, Gate nachziehen, Fehlersaetze)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Pause** — agy-Review des Task-Diffs, Zwischenstand, auf Go warten.

---

### Task 3: Live-Probe (nur lesend)

**Files:**
- Modify: `bc1_service/bc0_meldungen.py`
- Modify: `tests/test_bc0_meldungen.py`

**Interfaces:**
- Consumes: `lies_bc0_zugang`, `Bc0Melder.lies_konto`, `Bc0MeldungFehler` (Task 1/2); `bc1_service.start.lies_company_id`
- Produces: `probe(umgebung: Mapping[str, str], *, transport=None, ausgabe=print) -> int` (Exit-Code: 0 = Schreibrecht und Mandant da, 1 = fehlt etwas oder BC0-Fehler, 2 = Konfiguration); Aufruf `python -m bc1_service.bc0_meldungen --probe`

- [ ] **Step 1: Tests (einzeln, je RED)**

```python
from bc1_service.bc0_meldungen import probe


def _probe(konto=None, login=None, umgebung=None):
    zeilen: list[str] = []
    bc0 = FakeBc0(konto=konto, login=login)
    code = probe(umgebung or {**VOLL, "BC1_COMPANY_ID": MANDANT},
                 transport=httpx.MockTransport(bc0), ausgabe=zeilen.append)
    return code, zeilen, bc0


def test_probe_benutzer_mit_mandant_ist_bereit_und_aendert_nichts():
    code, zeilen, bc0 = _probe()
    assert code == 0
    assert zeilen == ["Rolle: benutzer", "Schreibrecht: ja",
                      f"Mandant {MANDANT} sichtbar: ja"]
    assert [a.method for a in bc0.anfragen] == ["POST", "GET"]   # Login + /me, sonst nichts


def test_probe_admin_ohne_mandantenliste_sieht_den_mandanten():
    code, zeilen, _ = _probe(konto={"rolle": "admin", "ist_admin": True,
                                    "darf_schreiben": True, "mandanten": []})
    assert code == 0 and zeilen[2] == f"Mandant {MANDANT} sichtbar: ja"


def test_probe_leser_ist_nicht_bereit():
    code, zeilen, _ = _probe(konto={"rolle": "leser", "ist_admin": False,
                                    "darf_schreiben": False, "mandanten": [MANDANT]})
    assert code == 1 and zeilen[1] == "Schreibrecht: nein"


def test_probe_benutzer_ohne_mandant_ist_nicht_bereit():
    code, zeilen, _ = _probe(konto={"rolle": "benutzer", "ist_admin": False,
                                    "darf_schreiben": True, "mandanten": []})
    assert code == 1 and zeilen[2] == f"Mandant {MANDANT} sichtbar: nein"


def test_probe_mit_falschem_passwort_meldet_den_satz():
    code, zeilen, _ = _probe(login=lambda r: httpx.Response(401, json={"detail": "x"}))
    assert code == 1 and zeilen == [MELDUNG_ANMELDUNG_ABGELEHNT]


def test_probe_ohne_mandant_oder_mit_aus_ist_ein_konfigurationsfehler():
    code, zeilen, _ = _probe(umgebung=dict(VOLL))
    assert code == 2 and "BC1_COMPANY_ID" in zeilen[0]
    code, zeilen, _ = _probe(umgebung={"BC1_BC0_MELDUNGEN": "aus", "BC1_COMPANY_ID": MANDANT})
    assert code == 2 and zeilen == ["BC1_BC0_MELDUNGEN=aus — nichts zu prüfen."]
```

- [ ] **Step 2: Implementierung** — ans Ende von `bc0_meldungen.py` (`import os`, `import sys` oben ergänzen):

```python
from bc1_service.start import lies_company_id


def probe(umgebung: Mapping[str, str], *, transport=None, ausgabe=print) -> int:
    """Live-Probe (nur lesend): darf das Konto schreiben, sieht es den Mandanten?

    Mandant sichtbar wie bei BC0 (darf_mandanten_sehen): Admin sieht alle, sonst
    nur die zugewiesenen. Aendert nichts bei BC0."""
    try:
        company_id = lies_company_id(umgebung)
        zugang = lies_bc0_zugang(umgebung)
    except RuntimeError as fehler:
        ausgabe(str(fehler))
        return 2
    if zugang is None:
        ausgabe("BC1_BC0_MELDUNGEN=aus — nichts zu prüfen.")
        return 2
    try:
        konto = Bc0Melder(zugang, company_id, transport=transport).lies_konto()
    except Bc0MeldungFehler as fehler:
        ausgabe(str(fehler))
        return 1
    schreiben = konto.get("darf_schreiben") is True
    mandant = konto.get("ist_admin") is True or company_id in konto.get("mandanten", [])
    ausgabe(f"Rolle: {konto.get('rolle')}")
    ausgabe(f"Schreibrecht: {'ja' if schreiben else 'nein'}")
    ausgabe(f"Mandant {company_id} sichtbar: {'ja' if mandant else 'nein'}")
    return 0 if schreiben and mandant else 1


if __name__ == "__main__":
    if sys.argv[1:] != ["--probe"]:
        print("Aufruf: python -m bc1_service.bc0_meldungen --probe")
        sys.exit(2)
    sys.exit(probe(os.environ))
```

Import-Hinweis: `start.py` importiert `bc0_meldungen` **nicht** (Task 4 nimmt den Melder nur als Objekt entgegen) — kein Zirkelimport. Den Import oben zu den anderen stellen.

- [ ] **Step 3: Grün** — `uv run pytest tests/test_bc0_meldungen.py -v`; zusätzlich von Hand ohne Netz: `BC1_BC0_MELDUNGEN=aus BC1_COMPANY_ID=11111111-1111-1111-1111-111111111111 uv run python -m bc1_service.bc0_meldungen --probe; echo $?` → Ausgabe „…nichts zu prüfen.", Exit 2.

- [ ] **Step 4: Commit** — `"BC1 B4: Live-Probe fuer das Anwendungskonto (nur lesend)"` (+ Trailer).

- [ ] **Step 5: Pause** — agy-Review, Zwischenstand, auf Go warten.

---

### Task 4: Start — „Interview läuft" melden, Verdrahtung in `main.py`

**Files:**
- Modify: `bc1_service/start.py`, `bc1_service/main.py`
- Modify: `tests/test_start.py`, `tests/test_postgres_init.py`, `tests/test_api_profil.py`

**Interfaces:**
- Consumes: `baue_melder`, `Bc0MeldungFehler` (Task 1/2); `bc0_lesepfade.anfrage_status(conn, company_id, anfrage_id) -> str | None` (besteht)
- Produces:
  - `start.melde_interview_beginn(melder, anfrage_id: str, status: str | None) -> None`
  - `main._melder` (Modulattribut, `Bc0Melder | None`); `create_app(..., melder=_melder)` — der Parameter selbst entsteht in Task 5, bis dahin übergibt `main.py` ihn **noch nicht** (siehe Step 4)

- [ ] **Step 1: Tests `test_start.py` (einzeln, je RED)** — ohne DB:

```python
from bc1_service.bc0_meldungen import Bc0MeldungFehler
from bc1_service.start import melde_interview_beginn


class _Melder:
    def __init__(self, fehler=None):
        self.gemeldet: list[str] = []
        self._fehler = fehler

    def melde_interview_laeuft(self, anfrage_id):
        self.gemeldet.append(anfrage_id)
        if self._fehler:
            raise self._fehler


def test_zugeordnete_anfrage_wird_einmal_als_im_interview_gemeldet():
    melder = _Melder()
    melde_interview_beginn(melder, "A-2026-01", "zugeordnet")
    assert melder.gemeldet == ["A-2026-01"]


def test_anfrage_schon_im_interview_wird_nicht_erneut_gemeldet():
    # Sonst ueberschriebe jeder Neustart BC0s status_seit.
    melder = _Melder()
    melde_interview_beginn(melder, "A-2026-01", "im_interview")
    assert melder.gemeldet == []


def test_ohne_melder_wird_nichts_gemeldet():
    melde_interview_beginn(None, "A-2026-01", "zugeordnet")     # darf nicht werfen


def test_fehler_der_meldung_geht_als_startabbruch_durch():
    with pytest.raises(Bc0MeldungFehler, match="kaputt"):
        melde_interview_beginn(_Melder(Bc0MeldungFehler("kaputt")), "A-2026-01", "zugeordnet")
```

- [ ] **Step 2: Implementierung `start.py`** — am Ende ergänzen; den Modul-Docstring um einen Satz erweitern („Seit B4 meldet der Start BC0 'im_interview' — nur aus 'zugeordnet'."):

```python
def melde_interview_beginn(melder, anfrage_id: str, status: str | None) -> None:
    """B4: BC0 erfaehrt, dass interviewt wird. Nur aus 'zugeordnet' — bei 'im_interview'
    nicht erneut, sonst ueberschriebe jeder Neustart BC0s status_seit. melder None =
    Meldungen bewusst aus (BC1_BC0_MELDUNGEN=aus). Ein Bc0MeldungFehler bricht den Start ab.

    melder: bc0_meldungen.Bc0Melder oder Ersatz mit melde_interview_laeuft(anfrage_id) —
    bewusst ohne Import (start.py bleibt frei von der HTTP-Seite)."""
    if melder is not None and status == "zugeordnet":
        melder.melde_interview_laeuft(anfrage_id)
```

- [ ] **Step 3: Tests Verdrahtung (einzeln, je RED)**

`tests/test_postgres_init.py` — neuer Abbruchtest nach dem `BC1_ANFRAGE_ID`-Test:

```python
# B4: ohne BC0-Zugang (und ohne bewusstes 'aus') startet der Dienst nicht — und zwar
# bevor eine Datenbankverbindung entsteht (die DSN hier ist absichtlich unerreichbar).
def test_main_ohne_bc0_zugang_meldet_die_fehlenden_variablen(monkeypatch):
    import importlib
    import sys

    monkeypatch.setenv("BC1_DB_DSN", "postgresql://egal/egal")
    monkeypatch.setenv("BC1_COMPANY_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("BC1_ANFRAGE_ID", "A-2026-01")
    for name in ("BC1_BC0_MELDUNGEN", "BC1_BC0_URL", "BC1_BC0_KONTO_EMAIL",
                 "BC1_BC0_KONTO_PASSWORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delitem(sys.modules, "bc1_service.main", raising=False)
    with pytest.raises(RuntimeError, match="BC0-Zugang unvollständig"):
        importlib.import_module("bc1_service.main")
```

`tests/test_api_profil.py` — im bestehenden `test_main_verdrahtet_den_profil_writer` vor dem Import `monkeypatch.setenv("BC1_BC0_MELDUNGEN", "aus")` ergänzen und nach den bestehenden Asserts `assert main._melder is None` (die Übergabe an `create_app` prüft Task 5). Zwei neue Tests dahinter:

```python
class _StartMelder:
    def __init__(self):
        self.gemeldet: list[str] = []

    def melde_interview_laeuft(self, anfrage_id):
        self.gemeldet.append(anfrage_id)


def _main_mit_melder(monkeypatch, anfrage_id, melder, gesehen=None):
    import importlib
    import sys

    from bc1_service import api as api_modul
    from bc1_service import bc0_meldungen

    def _stub_create_app(*a, **kw):
        if gesehen is not None:
            gesehen.update(kw)
        return "app"

    monkeypatch.setattr(api_modul, "create_app", _stub_create_app)
    monkeypatch.setattr(bc0_meldungen, "baue_melder", lambda umgebung, cid: melder)
    monkeypatch.setenv("BC1_DB_DSN", DSN)
    monkeypatch.setenv("BC1_COMPANY_ID", MANDANT_A)
    monkeypatch.setenv("BC1_ANFRAGE_ID", anfrage_id)
    monkeypatch.setenv("BC1_LLM", "ollama")
    monkeypatch.delitem(sys.modules, "bc1_service.main", raising=False)
    return importlib.import_module("bc1_service.main")


def test_main_meldet_eine_zugeordnete_anfrage_beim_start(umgebung, monkeypatch):
    import sys

    melder = _StartMelder()
    main = _main_mit_melder(monkeypatch, ANFRAGE_A, melder)        # Fixture: 'zugeordnet'
    try:
        assert melder.gemeldet == [ANFRAGE_A]
        assert main._melder is melder
    finally:
        main._store.close()
        main._profil_pool.close()
        sys.modules.pop("bc1_service.main", None)


def test_main_meldet_eine_anfrage_im_interview_nicht_erneut(umgebung, monkeypatch):
    import sys

    # ANFRAGE_A (startfaehig: alle TPs bewertet) auf 'im_interview' stellen — die
    # Fixture-Anfrage im Stand 'im_interview' (A-2026-02, ganzer KP-01) bricht schon an
    # der B5-Pruefung ab (KP-01.TP-3 unbewertet, test_start.py).
    with verbindung(DSN, None) as conn:
        conn.execute("UPDATE ref_anfragen SET status = 'im_interview' "
                     "WHERE company_id = %s AND anfrage_id = %s", (MANDANT_A, ANFRAGE_A))
        conn.commit()
    melder = _StartMelder()
    main = _main_mit_melder(monkeypatch, ANFRAGE_A, melder)
    try:
        assert melder.gemeldet == []
    finally:
        main._store.close()
        main._profil_pool.close()
        sys.modules.pop("bc1_service.main", None)
```

(Fixture-Stand laut `tests/db_fixture.py` Z. 248: `ANFRAGE_A` = `zugeordnet`, alle Teilprozesse bewertet — die einzige startfähige Anfrage von Mandant A. Die `umgebung`-Fixture spielt die DB je Test frisch ein, das `UPDATE` wirkt nur im eigenen Test. agy-Befund C1, 06.10.)

Dazu ein Test, dass ein Fehler der Meldung die Pools schließt:

```python
def test_main_schliesst_die_pools_wenn_die_meldung_scheitert(umgebung, monkeypatch):
    from bc1_service.bc0_meldungen import Bc0MeldungFehler
    from psycopg_pool import ConnectionPool

    geschlossen: list[str] = []
    original = ConnectionPool.close

    def _close(self, *a, **kw):
        geschlossen.append("pool")
        return original(self, *a, **kw)

    class _Kaputt(_StartMelder):
        def melde_interview_laeuft(self, anfrage_id):
            raise Bc0MeldungFehler("BC0 unter https://x ist nicht erreichbar (ConnectError).")

    monkeypatch.setattr(ConnectionPool, "close", _close)
    with pytest.raises(Bc0MeldungFehler, match="nicht erreichbar"):
        _main_mit_melder(monkeypatch, ANFRAGE_A, _Kaputt())
    assert len(geschlossen) >= 2          # Session-Store-Pool + Profil-Pool
```

(`PostgresStateStore` hält intern ebenfalls einen `psycopg_pool.ConnectionPool` — `postgres_store.py:36`, nachgesehen 06.10. —, deshalb mindestens zwei `close`-Aufrufe.)

- [ ] **Step 4: Implementierung `main.py`**

Docstring: in der Pflicht-Zeile ergänzen „seit B4 außerdem `BC1_BC0_URL`, `BC1_BC0_KONTO_EMAIL`, `BC1_BC0_KONTO_PASSWORT` — oder bewusst `BC1_BC0_MELDUNGEN=aus`". Imports:

```python
from bc1_service import bc0_lesepfade, bc0_meldungen
from bc1_service.start import (lade_kontext, lies_anfrage_id, lies_company_id,
                               melde_interview_beginn)
```

(`bc0_meldungen` als Modul importieren und `bc0_meldungen.baue_melder(...)` aufrufen — so greift das `monkeypatch.setattr` der Tests.)

Nach `_anfrage_id = lies_anfrage_id(os.environ)`:

```python
# B4: vor den Pools — ein Konfigurationsfehler bricht ohne offene Verbindungen ab.
_melder = bc0_meldungen.baue_melder(os.environ, _company_id)
```

Der Start-Block wird zu:

```python
try:
    with _profil_pool.connection() as _conn:
        _kontext = lade_kontext(_conn, _company_id, _anfrage_id)
        _status = bc0_lesepfade.anfrage_status(_conn, _company_id, _anfrage_id)
    # Nach dem with: die Verbindung ist zurueck im Pool und wartet nicht bis zu
    # 10 s auf BC0. Im try: scheitert die Meldung, schliessen beide Pools.
    melde_interview_beginn(_melder, _anfrage_id, _status)
except Exception:
    # (bestehender Kommentar bleibt)
    _profil_pool.close()
    _store.close()
    raise
```

`create_app(...)` bleibt in Task 4 unverändert (der Parameter `melder` kommt in Task 5).

- [ ] **Step 5: Grün** — mit Container: `BC1_TEST_DB_DSN=… uv run pytest tests/test_start.py tests/test_postgres_init.py tests/test_api_profil.py -v -W error` → alle PASS.

- [ ] **Step 6: Commit** — `"BC1 B4: Start meldet BC0 'im_interview' (nur aus 'zugeordnet'), Zugang Pflicht"` (+ Trailer).

- [ ] **Step 7: Pause** — agy-Review, Zwischenstand, auf Go warten.

---

### Task 5: Abschluss — „Gate nachziehen" im Hintergrund

**Files:**
- Modify: `bc1_service/api.py`, `bc1_service/main.py`
- Modify: `tests/test_api.py`, `tests/test_api_profil.py`

**Interfaces:**
- Consumes: `Bc0MeldungFehler` (Task 2), `main._melder` (Task 4); Melder-Protokoll `ziehe_gate_nach() -> list[str]`
- Produces: `create_app(store, llm, package, snapshot=None, lifespan=None, *, company_id, anfrage_id=None, writer=None, melder=None)`; `api.MELDUNG_GATE_FEHLGESCHLAGEN`; Logger `bc1_service.api`

- [ ] **Step 1: Tests `test_api.py` (einzeln, je RED)** — ohne DB, mit Writer-Ersatz; **ans Ende der Datei** (dort ist `ANFRAGE = "A-2026-01"` schon definiert):

```python
import logging

from bc1_service.api import MELDUNG_GATE_FEHLGESCHLAGEN
from bc1_service.bc0_meldungen import Bc0MeldungFehler


class _WriterOhneDb:
    """Der Gate-Anstoss haengt nur an 'Writer verdrahtet + fertig' — die DB-Seite
    prueft test_api_profil.py."""

    def reconcile(self, state, antwort):
        return None


class _GateMelder:
    def __init__(self, fehler=None):
        self.aufrufe = 0
        self._fehler = fehler

    def ziehe_gate_nach(self):
        self.aufrufe += 1
        if self._fehler is not None:
            raise self._fehler
        return [ANFRAGE]


def _gate_client(melder, writer=_WriterOhneDb()):
    return TestClient(create_app(InMemoryStateStore(), _fake_llm(), TOY_PROZESS,
                                 company_id=MANDANT, anfrage_id=ANFRAGE,
                                 writer=writer, melder=melder))


def _bis_fertig(client):
    _turn(client, "m1", "Der Prozess heißt Urlaubsantrag")
    _turn(client, "m2", "Ausgelöst durch einen Antrag")
    return _turn(client, "m3", "Etwa 100 mal pro Jahr")


def _api_log(caplog):
    return [r for r in caplog.records if r.name == "bc1_service.api"]


def test_fertig_mit_writer_zieht_das_gate_genau_einmal_nach():
    melder = _GateMelder()
    antwort = _bis_fertig(_gate_client(melder))
    assert antwort.json()["status"] == "fertig"
    assert melder.aufrufe == 1


def test_zwischenstand_zieht_das_gate_nicht_nach():
    melder = _GateMelder()
    _turn(_gate_client(melder), "m1", "Der Prozess heißt Urlaubsantrag")
    assert melder.aufrufe == 0


def test_ohne_writer_wird_nichts_eingefroren_und_nichts_nachgezogen():
    melder = _GateMelder()
    _bis_fertig(_gate_client(melder, writer=None))
    assert melder.aufrufe == 0


def test_ohne_melder_kein_aufruf_und_keine_logzeile(caplog):
    with caplog.at_level(logging.INFO, logger="bc1_service.api"):
        antwort = _bis_fertig(_gate_client(None))
    assert antwort.json()["status"] == "fertig"
    assert _api_log(caplog) == []


def test_gescheitertes_gate_laesst_die_antwort_unberuehrt_und_warnt(caplog):
    melder = _GateMelder(Bc0MeldungFehler("BC0 antwortet auf 'Gate nachziehen' mit 500: x"))
    with caplog.at_level(logging.WARNING, logger="bc1_service.api"):
        antwort = _bis_fertig(_gate_client(melder))
    assert antwort.status_code == 200 and antwort.json()["status"] == "fertig"
    assert [r.getMessage() for r in _api_log(caplog)] == [MELDUNG_GATE_FEHLGESCHLAGEN.format(
        grund="BC0 antwortet auf 'Gate nachziehen' mit 500: x",
        anfrage_id=ANFRAGE, company_id=MANDANT)]


def test_unerwartete_ausnahme_im_hintergrund_nennt_nur_die_klasse(caplog):
    melder = _GateMelder(AttributeError("interna mit geheimnis"))
    with caplog.at_level(logging.WARNING, logger="bc1_service.api"):
        antwort = _bis_fertig(_gate_client(melder))
    assert antwort.status_code == 200
    eintraege = _api_log(caplog)
    assert len(eintraege) == 1
    assert "AttributeError" in eintraege[0].getMessage()
    assert "geheimnis" not in eintraege[0].getMessage()


def test_replay_des_abschlusses_zieht_erneut_nach():
    melder = _GateMelder()
    client = _gate_client(melder)
    _bis_fertig(client)
    assert _turn(client, "m3", "Etwa 100 mal pro Jahr").status_code == 200
    assert melder.aufrufe == 2
```

Hinweis: Starlettes `TestClient` führt Hintergrundaufgaben aus, bevor `post()` zurückkehrt (gemessen 06.10.) — die Zähler sind deshalb direkt nach dem Aufruf verlässlich.

- [ ] **Step 2: Implementierung `api.py`**

Imports und Konstante:

```python
import logging
import threading

from fastapi import BackgroundTasks, FastAPI, HTTPException
...
from bc1_service.bc0_meldungen import Bc0MeldungFehler

log = logging.getLogger(__name__)

# B4 (Spec Abschnitt 5): der Rueckfall von Hand, wenn BC0 nicht mitspielt.
MELDUNG_GATE_FEHLGESCHLAGEN = (
    "Gate nachziehen bei BC0 fehlgeschlagen: {grund} — Anfrage {anfrage_id} bitte bei "
    "BC0 von Hand nachziehen (POST /api/companies/{company_id}/anfragen/gate_nachziehen).")
```

`create_app`: neuer Schlüsselwortparameter nach `writer`:

```python
    writer: ProfilWriter | None = None,
    # B4: None beim bewussten 'aus' (BC1_BC0_MELDUNGEN) und in Tests.
    melder=None,
```

`turn` bekommt `hintergrund: BackgroundTasks` (`def turn(req: TurnRequest, hintergrund: BackgroundTasks) -> dict:`); im `if writer is not None:`-Block **nach** dem Overlay:

```python
                if melder is not None and antwort["status"] == "fertig":
                    # Nach der Antwort, im Hintergrund: das Profil ist eingefroren,
                    # der Chat darf an BC0 nie scheitern (Spec B4, Abschnitt 4).
                    hintergrund.add_task(_gate_im_hintergrund, melder, company_id,
                                         anfrage_id)
```

Neue Modulfunktion (unterhalb von `create_app`):

```python
def _gate_im_hintergrund(melder, company_id: str, anfrage_id: str | None) -> None:
    try:
        gesetzt = melder.ziehe_gate_nach()
    except Exception as fehler:                            # noqa: BLE001 — Hintergrund
        # Nie das Ausnahmeobjekt loggen: eine fremde Ausnahme koennte Interna tragen.
        grund = str(fehler) if isinstance(fehler, Bc0MeldungFehler) else type(fehler).__name__
        log.warning(MELDUNG_GATE_FEHLGESCHLAGEN.format(
            grund=grund, anfrage_id=anfrage_id, company_id=company_id))
        return
    log.info("Gate bei BC0 nachgezogen (Anfrage %s): auf am_gate gesetzt: %s",
             anfrage_id, ", ".join(gesetzt) or "keine")
```

Modul-Docstring von `api.py` um einen Satz ergänzen: „Seit B4 stößt der Dienst nach einem eingefrorenen Profil BC0s 'Gate nachziehen' an — nach der Antwort, im Hintergrund."

- [ ] **Step 3: Verdrahtung `main.py`** — `create_app(..., writer=ProfilWriter(...), melder=_melder)`. Tests dazu in `test_api_profil.py` (einzeln, je RED): im bestehenden `test_main_verdrahtet_den_profil_writer` nach den Asserts `assert gesehen["melder"] is None` ergänzen (dort ist `aus` gesetzt), und neu:

```python
def test_main_reicht_den_melder_an_die_app_durch(umgebung, monkeypatch):
    import sys

    melder = _StartMelder()
    gesehen: dict = {}
    main = _main_mit_melder(monkeypatch, ANFRAGE_A, melder, gesehen)
    try:
        assert gesehen["melder"] is melder
    finally:
        main._store.close()
        main._profil_pool.close()
        sys.modules.pop("bc1_service.main", None)
```

- [ ] **Step 4: Test mit echtem Freeze (`test_api_profil.py`, DB)**

```python
class _GateZaehler:
    def __init__(self):
        self.aufrufe = 0

    def ziehe_gate_nach(self):
        self.aufrufe += 1
        return [ANFRAGE_A]


def test_eingefrorenes_profil_stoesst_das_gate_einmal_an(umgebung):
    pool, paket = umgebung
    melder = _GateZaehler()
    client = TestClient(create_app(
        InMemoryStateStore(), _llm(), paket, company_id=MANDANT_A, anfrage_id=ANFRAGE_A,
        writer=ProfilWriter(pool, MANDANT_A, paket), melder=melder))
    antwort = _turn(client, "m1", "alles")
    assert antwort.json()["status"] == "fertig"
    assert melder.aufrufe == 1
    with verbindung(DSN) as conn:
        assert conn.execute("SELECT status FROM bc1.prozessprofil").fetchone()[0] == "fertig"
```

- [ ] **Step 5: Grün** — `BC1_TEST_DB_DSN=… uv run pytest tests/test_api.py tests/test_api_profil.py -v -W error` → alle PASS.

- [ ] **Step 6: Commit** — `"BC1 B4: nach dem Abschluss Gate bei BC0 nachziehen (Hintergrund, Rueckfall von Hand)"` (+ Trailer).

- [ ] **Step 7: Pause** — agy-Review, Zwischenstand, auf Go warten.

---

### Task 6: Betrieb — README und SMOKE

**Files:**
- Modify: `README.md` (Abschnitt „Dienst starten"), `bc1_service/n8n/SMOKE.md` (Aufbau Schritt 1, Startabbrüche)

- [ ] **Step 1: README** — Pflicht-Satz ergänzen um „seit B4 der BC0-Zugang (`BC1_BC0_URL`, `BC1_BC0_KONTO_EMAIL`, `BC1_BC0_KONTO_PASSWORT`) — lokal ohne echtes BC0 bewusst `BC1_BC0_MELDUNGEN=aus`". Im Beispielblock nach `BC1_ANFRAGE_ID`:

```bash
export BC1_BC0_MELDUNGEN=aus               # lokal ohne BC0; im Betrieb stattdessen:
# export BC1_BC0_URL="https://bc0.perspektivwechsel.ai"
# export BC1_BC0_KONTO_EMAIL="$BC0_APP_KONTO_EMAIL"      # aus der lokalen Zugangsdatei
# export BC1_BC0_KONTO_PASSWORT="$BC0_APP_KONTO_PASSWORT"
```

Ein Absatz danach: was der Dienst bei BC0 tut (beim Start `im_interview` aus `zugeordnet`; nach jedem Abschluss Gate nachziehen; scheitert das, WARNING mit Handlungsanweisung) und die Live-Probe `uv run python -m bc1_service.bc0_meldungen --probe` (nur lesend; Exit 0 = bereit).

- [ ] **Step 2: SMOKE.md** — in „1. Dienst starten" dieselben Zeilen (Test-Container: `BC1_BC0_MELDUNGEN=aus`, weil der Container kein BC0 hat). Startabbrüche: neue Tabelle „Seit B4 (BC0-Meldungen)" mit Verweis auf die Konstanten in `bc1_service/bc0_meldungen.py`:

| Meldung beginnt mit | Bedeutung | Was tun |
|---|---|---|
| „BC0-Zugang unvollständig" | Variable fehlt | setzen oder bewusst `BC1_BC0_MELDUNGEN=aus` |
| „BC1_BC0_MELDUNGEN='…' ist unbekannt" | Tippfehler im Schalter | nur `aus` oder weglassen |
| „BC1_BC0_URL='…' ist keine https-Adresse" | http zu fremdem Rechner | https-Adresse eintragen |
| „BC0 lehnt die Anmeldung ab" | E-Mail/Passwort falsch | Zugang prüfen |
| „BC0 sperrt die Anmeldung" | zu viele Fehlversuche | Zugang prüfen, warten |
| „BC0 nimmt die Anmeldung … nicht an (401)" | lokales BC0 ohne https | dort `BC0_COOKIE_UNSICHER=1` |
| „BC0 verweigert …(403)" | Konto ohne Schreibrecht | bei BC0 Rolle `benutzer` erbitten |
| „BC0 kennt den Mandanten … nicht (404)" | Mandant dem Konto nicht zugewiesen | bei BC0 zuweisen lassen |
| „BC0 unter … ist nicht erreichbar" | Netz/Adresse/BC0 aus | Adresse prüfen, BC0 erreichbar? |

Plus der Satz: Im Log nach einem Abschluss bedeutet „Gate nachziehen bei BC0 fehlgeschlagen" — das Profil ist gespeichert, die Anfrage bei BC0 von Hand nachziehen.

- [ ] **Step 3: Kontrolle** — `git grep -n "BC1_BC0_" README.md bc1_service/n8n/SMOKE.md` zeigt die neuen Stellen; kein Passwort, keine echte E-Mail-Adresse im Text.

- [ ] **Step 4: Commit** — `"BC1 B4: README und Smoke um BC0-Zugang, Startabbrueche und Live-Probe"` (+ Trailer).

- [ ] **Step 5: Pause** — Zwischenstand, auf Go warten.

---

### Task 6b: Start prüft den Zugang immer (Ergänzung 08.10., Entscheidung „B")

**Anlass:** Bei einer Anfrage im Stand `im_interview` rief der Start BC0 gar nicht an — ein falscher Zugang fiel erst nach dem Interview als Gate-WARNING auf (Befund des Task-6-Implementers). Spec-Ergänzung 08.10. (Abschnitte Big Picture 2, 1, 2, 3, 5, 6).

**Files:**
- Modify: `bc1_service/bc0_meldungen.py`, `bc1_service/start.py`
- Modify: `tests/test_bc0_meldungen.py`, `tests/test_start.py`, `tests/test_api_profil.py`
- Modify: `README.md`, `bc1_service/n8n/SMOKE.md`

**Interfaces:**
- Consumes: `Bc0Melder.lies_konto()`, `Bc0MeldungFehler`, `probe` (Tasks 2/3); `melde_interview_beginn` (Task 4); Test-Fakes `FakeBc0` (test_bc0_meldungen), `_Melder` (test_start), `_StartMelder`/`_main_mit_melder`/`_Kaputt` (test_api_profil)
- Produces:
  - `MELDUNG_KONTO_OHNE_SCHREIBRECHT`, `MELDUNG_KONTO_OHNE_MANDANT` (Wortlaut Spec Abschnitt 5)
  - `_konto_bereit(konto: dict, company_id: str) -> tuple[bool, bool]` (schreiben, mandant) — einzige Stelle der Bewertung, `"mandanten": null` = leer
  - `Bc0Melder.pruefe_konto() -> None` (wirft `Bc0MeldungFehler`)
  - `melde_interview_beginn`: bei Melder **zuerst immer** `pruefe_konto()`, dann `melde_interview_laeuft` nur bei `zugeordnet`

- [ ] **Step 1: Tests `test_bc0_meldungen.py` (einzeln, je RED)** — Imports um `MELDUNG_KONTO_OHNE_MANDANT`, `MELDUNG_KONTO_OHNE_SCHREIBRECHT` ergänzen:

```python
def _konto_melder(konto):
    bc0 = FakeBc0(konto=konto)
    return _melder(bc0), bc0


def test_pruefe_konto_bereit_liest_nur_das_eigene_konto():
    melder, bc0 = _konto_melder(None)                     # Benutzer mit Mandant (Standard)
    melder.pruefe_konto()
    assert [(a.method, a.url.path) for a in bc0.anfragen] == [
        ("POST", "/api/auth/login"), ("GET", "/api/auth/me")]


def test_pruefe_konto_admin_ohne_mandantenliste_ist_bereit():
    melder, _ = _konto_melder({"rolle": "admin", "ist_admin": True,
                               "darf_schreiben": True, "mandanten": []})
    melder.pruefe_konto()


def test_pruefe_konto_leser_bricht_ab():
    melder, _ = _konto_melder({"rolle": "leser", "ist_admin": False,
                               "darf_schreiben": False, "mandanten": [MANDANT]})
    with pytest.raises(Bc0MeldungFehler) as fehler:
        melder.pruefe_konto()
    assert str(fehler.value) == MELDUNG_KONTO_OHNE_SCHREIBRECHT.format(rolle="leser")


@pytest.mark.parametrize("mandanten", [[], None, ["99999999-9999-9999-9999-999999999999"]])
def test_pruefe_konto_ohne_sichtbaren_mandanten_bricht_ab(mandanten):
    melder, _ = _konto_melder({"rolle": "benutzer", "ist_admin": False,
                               "darf_schreiben": True, "mandanten": mandanten})
    with pytest.raises(Bc0MeldungFehler) as fehler:
        melder.pruefe_konto()
    assert str(fehler.value) == MELDUNG_KONTO_OHNE_MANDANT.format(company_id=MANDANT)


def test_pruefe_konto_reicht_bc0_absage_durch():
    bc0 = FakeBc0(login=lambda r: httpx.Response(401, json={"detail": "x"}))
    with pytest.raises(Bc0MeldungFehler) as fehler:
        _melder(bc0).pruefe_konto()
    assert str(fehler.value) == MELDUNG_ANMELDUNG_ABGELEHNT


def test_probe_mit_mandantenliste_null_meldet_nicht_sichtbar():
    code, zeilen, _ = _probe(konto={"rolle": "benutzer", "ist_admin": False,
                                    "darf_schreiben": True, "mandanten": None})
    assert code == 1 and zeilen[2] == f"Mandant {MANDANT} sichtbar: nein"
```

- [ ] **Step 2: Implementierung `bc0_meldungen.py`** (Aufrufer zuerst, dann Definitionen — tdd-guard-Lesson):

```python
MELDUNG_KONTO_OHNE_SCHREIBRECHT = (
    "Das BC0-Anwendungskonto darf nicht schreiben (Rolle '{rolle}'). Es braucht die Rolle "
    "'benutzer' oder 'admin'.")
MELDUNG_KONTO_OHNE_MANDANT = (
    "Das BC0-Anwendungskonto sieht den Mandanten {company_id} nicht. Das Konto braucht den "
    "Mandanten zugewiesen.")


def _konto_bereit(konto: dict, company_id: str) -> tuple[bool, bool]:
    """(darf schreiben, sieht den Mandanten) — wie BC0s darf_schreiben/darf_mandanten_sehen:
    Admin sieht alle Mandanten. "mandanten": null gilt als leer."""
    schreiben = konto.get("darf_schreiben") is True
    mandant = konto.get("ist_admin") is True or company_id in (konto.get("mandanten") or [])
    return schreiben, mandant
```

In `Bc0Melder`:

```python
    def pruefe_konto(self) -> None:
        """Start-Pruefung (Ergaenzung 08.10.): Anmeldung + eigenes Konto lesen, aendert nichts."""
        konto = self.lies_konto()
        schreiben, mandant = _konto_bereit(konto, self._company_id)
        if not schreiben:
            raise Bc0MeldungFehler(MELDUNG_KONTO_OHNE_SCHREIBRECHT.format(rolle=konto.get("rolle")))
        if not mandant:
            raise Bc0MeldungFehler(MELDUNG_KONTO_OHNE_MANDANT.format(company_id=self._company_id))
```

`probe` (bei grüner Suite, Refactoring): die zwei Bewertungszeilen durch `schreiben, mandant = _konto_bereit(konto, company_id)` ersetzen.

- [ ] **Step 3: Tests `test_start.py`** — den Bestands-Fake `_Melder` um die Prüfung erweitern (Aufruf/Setup und Erwartungen in getrennten Schritten, tdd-guard-Lesson „Bestandstest"):

```python
class _Melder:
    def __init__(self, fehler=None, pruef_fehler=None):
        self.gemeldet: list[str] = []
        self.aufrufe: list[str] = []
        self._fehler = fehler
        self._pruef_fehler = pruef_fehler

    def pruefe_konto(self):
        self.aufrufe.append("pruefe")
        if self._pruef_fehler:
            raise self._pruef_fehler

    def melde_interview_laeuft(self, anfrage_id):
        self.aufrufe.append("melde")
        self.gemeldet.append(anfrage_id)
        if self._fehler:
            raise self._fehler
```

Neue Tests (einzeln, je RED):

```python
def test_zugeordnet_prueft_zuerst_und_meldet_dann():
    melder = _Melder()
    melde_interview_beginn(melder, "A-2026-01", "zugeordnet")
    assert melder.aufrufe == ["pruefe", "melde"]


def test_im_interview_prueft_den_zugang_trotzdem():
    melder = _Melder()
    melde_interview_beginn(melder, "A-2026-01", "im_interview")
    assert melder.aufrufe == ["pruefe"]


def test_gescheiterte_pruefung_bricht_ab_und_meldet_nicht():
    melder = _Melder(pruef_fehler=Bc0MeldungFehler("Konto kaputt"))
    with pytest.raises(Bc0MeldungFehler, match="Konto kaputt"):
        melde_interview_beginn(melder, "A-2026-01", "zugeordnet")
    assert melder.aufrufe == ["pruefe"]
```

- [ ] **Step 4: Implementierung `start.py`**

```python
def melde_interview_beginn(melder, anfrage_id: str, status: str | None) -> None:
    """B4: Zuerst immer den Zugang pruefen (Ergaenzung 08.10.: sonst fiele ein falscher
    Zugang bei 'im_interview' erst nach dem Interview auf), dann BC0 melden, dass interviewt
    wird — nur aus 'zugeordnet'; bei 'im_interview' nicht erneut, sonst ueberschriebe jeder
    Neustart BC0s status_seit. melder None = Meldungen bewusst aus (BC1_BC0_MELDUNGEN=aus).
    Ein Bc0MeldungFehler bricht den Start ab.

    melder: bc0_meldungen.Bc0Melder oder Ersatz mit pruefe_konto() und
    melde_interview_laeuft(anfrage_id) — bewusst ohne Import (start.py bleibt frei von der
    HTTP-Seite)."""
    if melder is None:
        return
    melder.pruefe_konto()
    if status == "zugeordnet":
        melder.melde_interview_laeuft(anfrage_id)
```

- [ ] **Step 5: Tests `test_api_profil.py`** — `_StartMelder` um `pruefe_konto` (zählt `self.geprueft += 1`, Start `0`) erweitern; in `test_main_meldet_eine_anfrage_im_interview_nicht_erneut` zusätzlich `assert melder.geprueft == 1`; neuer Test (DB):

```python
def test_main_bricht_bei_im_interview_ab_wenn_die_kontopruefung_scheitert(umgebung, monkeypatch):
    from bc1_service.bc0_meldungen import Bc0MeldungFehler

    with verbindung(DSN, None) as conn:
        conn.execute("UPDATE ref_anfragen SET status = 'im_interview' "
                     "WHERE company_id = %s AND anfrage_id = %s", (MANDANT_A, ANFRAGE_A))
        conn.commit()

    class _KontoKaputt(_StartMelder):
        def pruefe_konto(self):
            raise Bc0MeldungFehler("Das BC0-Anwendungskonto darf nicht schreiben (Rolle 'leser').")

    melder = _KontoKaputt()
    with pytest.raises(Bc0MeldungFehler, match="darf nicht schreiben"):
        _main_mit_melder(monkeypatch, ANFRAGE_A, melder)
    assert melder.gemeldet == []
```

- [ ] **Step 6: Doku** — README (Absatz „Was der Dienst bei BC0 tut") und SMOKE: den Hinweis „bei `im_interview` startet der Dienst ohne Anruf bei BC0 …" durch „Beim Start prüft der Dienst immer den Zugang (Anmeldung + eigenes Konto, ändert nichts) und bricht bei einem Mangel ab — auch bei `im_interview`" ersetzen; SMOKE-Tabelle um zwei Zeilen: „Das BC0-Anwendungskonto darf nicht schreiben" → Rolle bei BC0 erbitten · „Das BC0-Anwendungskonto sieht den Mandanten" → bei BC0 zuweisen lassen. Wortanfänge gegen die Konstanten prüfen.

- [ ] **Step 7: Grün + Commit** — `BC1_TEST_DB_DSN=… uv run pytest -q -W error`; Commit `"BC1 B4: Start prueft den BC0-Zugang immer (auch bei im_interview)"` (+ Trailer).

- [ ] **Step 8: Pause** — agy-Review, Zwischenstand, auf Go warten.

---

### Task 7: Abschluss — volle Suite, Gesamtreview, Abschlussplan, Sammelliste

**Files:**
- Modify: `bc1-context-discovery/design/Abschlussplan-BC1.md`
- Modify (lokal, Projektwurzel, NICHT im Repo): die lokale Sammelliste an BC0 (Runde 2)

- [ ] **Step 1: Volle Suite mit Container** — `BC1_TEST_DB_DSN=… uv run pytest -q -W error`; Ergebnis (passed/skipped) wörtlich in den Zwischenbericht (Ausgang vor B4: 597 passed / 4 skipped). Kein „grün" ohne diese Ausgabe.

- [ ] **Step 2: Gesamtreview per agy** — Diff `git diff main...bc1-b4-dienstanmeldung` als Datei, `agy --mode plan --effort high -p "…"` (nur lesend, `git status` vor/nach vergleichen); Befunde nach Schwere adjudizieren (Critical/Important fixen mit Test, Minor fixen oder mit Ziel vertagen), Ergebnis der BC1-Projektleitung vorlegen.

- [ ] **Step 3: Abschlussplan**
  - B4-Zeile: „Gebaut am Tag des Merges (Zweig `bc1-b4-dienstanmeldung`, Spec/Plan `design/…-B4-…`): `im_interview` beim Start aus `zugeordnet`, Gate nachziehen nach jedem eingefrorenen Profil (Hintergrund, Rückfall von Hand), Zugang Pflicht mit `BC1_BC0_MELDUNGEN=aus`, Live-Probe. `PUT …/zuordnung` entfällt (würde Teilprozesse aus der Anfrage löschen; seit B5 nur zugeordnete Anfragen)." Nächster Schritt: Live-Probe (BC1-Projektleitung), dann Durchstich.
  - **Neue Zeile B8 — „Snapshot-Modus durch DB-Lesepfad ablösen + Zugangsprüfung `GET /prozesse`"** (aus B4 ausgelagert, Entscheidung 06.10.): Ziel nach C4 (b); Verweis aus B3 (d) und aus dem Kleinpunkt „Snapshot-Modus filtert `aktiv` nicht" von „B4" auf „B8" umstellen.
  - Kleinpunkte „Neu 06.10. — aus B4 vertagt": (1) **Selbstheilung beim Start** (Gate nachziehen auch beim Start) → einbauen, sobald BC0 die Gate-Funktion über `anfrage_id` prüft (Sammelliste Runde 2, Punkt 4); (2) **Wiederholung/Warteschlange für fehlgeschlagene Gate-Aufrufe** → C4, nur auf konkreten Anlass; (3) Minor-Befunde der Reviews mit Ziel.
  - Entscheidungen: „Nächstes Go" → C4 (b) (danach B7/C1a).
  - B5-Rückstellung (2) „Status `im_interview` + `gate_nachziehen`" als erledigt markieren.
  - Commit `"BC1 B4: Abschlussplan nachgezogen"` (+ Trailer).

- [ ] **Step 4: Sammelliste Runde 2 (lokal, nicht posten)** — zwei Punkte ergänzen: (a) BC1 interviewt nur bereits zugeordnete Anfragen; der in `PUT …/zuordnung` beschriebene Weg „der Bezug entsteht im Interview" wird von BC1 nicht bedient — BC0 ordnet vorher zu (bitte bestätigen); (b) Punkt 4 (Gate-Funktion über `anfrage_id`) wird durch B4 dringlicher: BC1 stößt `gate_nachziehen` jetzt nach jedem Abschluss selbst an, und die Funktion wirkt mandantenweit.

- [ ] **Step 5: Zwischenbericht an die BC1-Projektleitung und auf Go warten** — Suite-Ergebnis, Review-Adjudikation, Vertraulichkeits-Check des Diffs (was öffentlich würde: keine Zugangsdaten, keine echte Konto-E-Mail, keine Klarnamen in neuen Texten), Push/PR nur nach OK; danach Live-Probe durch die BC1-Projektleitung:

```bash
export BC1_COMPANY_ID="<echte company_id>"
export BC1_BC0_URL="https://bc0.perspektivwechsel.ai"
export BC1_BC0_KONTO_EMAIL="$BC0_APP_KONTO_EMAIL"
export BC1_BC0_KONTO_PASSWORT="$BC0_APP_KONTO_PASSWORT"
uv run python -m bc1_service.bc0_meldungen --probe
```

Erwartet: „Schreibrecht: ja", „Mandant … sichtbar: ja", Exit 0. Weicht etwas ab → Ergebnis melden, nicht im Code „passend machen".

---

### Task 8: Gate je Anfrage + Selbstheilung beim Start (Ergänzung 2, 08.10., nach BC0 v3.13)

**Anlass:** BC0 v3.13 (#281) zählt nur noch Profile mit derselben `anfrage_id` und nimmt optional `POST …/gate_nachziehen?anfrage_id=…` (Bitte von BC0 in #280). Damit fällt der Grund für die Rückstellung „Selbstheilung beim Start" weg. Spec: Stellen „Ergänzung 2". Eigener Zweig `bc1-b4-gate-je-anfrage` ab `main` (enthält B4 und BC0 v3.13).

**Files:**
- Modify: `bc1_service/bc0_meldungen.py`, `bc1_service/start.py`, `bc1_service/main.py`, `bc1_service/api.py`
- Modify: `tests/test_bc0_meldungen.py`, `tests/test_start.py`, `tests/test_api.py`, `tests/test_api_profil.py`
- Modify: `README.md`, `bc1_service/n8n/SMOKE.md`, `design/Abschlussplan-BC1.md`

**Interfaces:**
- Consumes: `Bc0Melder._melden`, `pruefe_konto`, `melde_interview_laeuft`; `api._gate_im_hintergrund(melder, company_id, anfrage_id)`; Test-Fakes `FakeBc0`, `_Melder` (test_start), `_GateMelder` (test_api), `_StartMelder`/`_GateZaehler`/`_main_mit_melder` (test_api_profil)
- Produces:
  - `Bc0Melder.ziehe_gate_nach(anfrage_id: str) -> list[str]` — schickt Query-Parameter `anfrage_id`
  - `Bc0Melder._melden(aktion, methode, pfad, rumpf=None, params=None)`
  - `start.pruefe_bc0_vor_dem_start(melder, anfrage_id: str) -> None` — bei Melder: `pruefe_konto()`, dann `ziehe_gate_nach(anfrage_id)`; `None` → nichts
  - `start.melde_interview_beginn(melder, anfrage_id, status)` — nur noch die Meldung bei `zugeordnet` (keine Kontoprüfung mehr)
  - `main.py`: `pruefe_bc0_vor_dem_start` im `try` vor dem `with`-Block; `melde_interview_beginn` wie bisher danach
  - `api._gate_im_hintergrund` ruft `melder.ziehe_gate_nach(anfrage_id)`

- [ ] **Step 1: Melder (`test_bc0_meldungen.py`, je RED)** — zuerst alle Bestandsaufrufe `ziehe_gate_nach()` auf `ziehe_gate_nach(ANFRAGE)` umstellen (Signaturänderung: erst die Aufrufe, dann die Implementierung — tdd-guard-Lesson), dann neu:

```python
def test_gate_schickt_die_eigene_anfrage_als_parameter():
    bc0 = FakeBc0()
    _melder(bc0).ziehe_gate_nach(ANFRAGE)
    gate = bc0.anfragen[1]
    assert gate.url.path == f"/api/companies/{MANDANT}/anfragen/gate_nachziehen"
    assert dict(gate.url.params) == {"anfrage_id": ANFRAGE}
```

Implementierung:

```python
    def ziehe_gate_nach(self, anfrage_id: str) -> list[str]:
        """Gate je Anfrage (BC0 v3.13): BC0 prueft nur diese Anfrage statt des ganzen Mandanten."""
        daten = self._melden(
            "Gate nachziehen", "POST",
            f"/api/companies/{self._company_id}/anfragen/gate_nachziehen",
            params={"anfrage_id": anfrage_id})
        return list(daten.get("gesetzt") or [])          # auch bei "gesetzt": null
```

`_melden(..., rumpf: dict | None = None, params: dict | None = None)` und `client.request(methode, pfad, json=rumpf, params=params)`.

- [ ] **Step 2: Hintergrund (`test_api.py`, `test_api_profil.py`)** — `_GateMelder.ziehe_gate_nach(self, anfrage_id)` und `_GateZaehler.ziehe_gate_nach(self, anfrage_id)` merken sich `anfrage_id` (`self.anfragen.append(anfrage_id)`); neuer Test in `test_api.py`:

```python
def test_gate_im_hintergrund_reicht_die_eigene_anfrage_durch():
    melder = _GateMelder()
    _bis_fertig(_gate_client(melder))
    assert melder.anfragen == [ANFRAGE]
```

Implementierung `api._gate_im_hintergrund`: `gesetzt = melder.ziehe_gate_nach(anfrage_id)`.

- [ ] **Step 3: Start (`test_start.py`)** — Fake `_Melder` um `ziehe_gate_nach(self, anfrage_id)` erweitern (`self.aufrufe.append("gate")`, optional `gate_fehler`). Die drei Tests, die heute `pruefe` in `melde_interview_beginn` erwarten (`test_zugeordnet_prueft_zuerst_und_meldet_dann`, `test_im_interview_prueft_den_zugang_trotzdem`, `test_gescheiterte_pruefung_bricht_ab_und_meldet_nicht`), wandern zur neuen Funktion — Bestandstests in getrennten Schritten anpassen (tdd-guard-Lesson); neu:

```python
def test_vor_dem_start_erst_pruefen_dann_gate():
    melder = _Melder()
    pruefe_bc0_vor_dem_start(melder, "A-2026-01")
    assert melder.aufrufe == ["pruefe", "gate"]


def test_vor_dem_start_ohne_melder_nichts():
    pruefe_bc0_vor_dem_start(None, "A-2026-01")            # darf nicht werfen


def test_gescheiterte_pruefung_zieht_kein_gate_nach():
    melder = _Melder(pruef_fehler=Bc0MeldungFehler("Konto kaputt"))
    with pytest.raises(Bc0MeldungFehler, match="Konto kaputt"):
        pruefe_bc0_vor_dem_start(melder, "A-2026-01")
    assert melder.aufrufe == ["pruefe"]


def test_melde_interview_beginn_meldet_nur_noch():
    melder = _Melder()
    melde_interview_beginn(melder, "A-2026-01", "zugeordnet")
    assert melder.aufrufe == ["melde"]
```

Implementierung `start.py`:

```python
def pruefe_bc0_vor_dem_start(melder, anfrage_id: str) -> None:
    """B4 (Ergaenzung 2, 08.10.): vor dem Lesen aus der DB — Zugang pruefen, dann das Gate fuer
    die eigene Anfrage nachziehen (Selbstheilung: holt einen frueher gescheiterten Gate-Aufruf
    nach; seit BC0 v3.13 zaehlen nur Profile derselben Anfrage). Steht die Anfrage danach auf
    am_gate, bricht lade_kontext mit der B5-Meldung ab — kein ueberfluessiges Interview.
    melder None = Meldungen bewusst aus. Ein Bc0MeldungFehler bricht den Start ab."""
    if melder is None:
        return
    melder.pruefe_konto()
    melder.ziehe_gate_nach(anfrage_id)


def melde_interview_beginn(melder, anfrage_id: str, status: str | None) -> None:
    """B4: BC0 melden, dass interviewt wird — nur aus 'zugeordnet'; bei 'im_interview' nicht
    erneut, sonst ueberschriebe jeder Neustart BC0s status_seit. Die Kontopruefung laeuft vorher
    in pruefe_bc0_vor_dem_start. melder None = Meldungen bewusst aus."""
    if melder is not None and status == "zugeordnet":
        melder.melde_interview_laeuft(anfrage_id)
```

Modul-Docstring von `start.py` entsprechend anpassen.

- [ ] **Step 4: `main.py` + Verdrahtungstests (`test_api_profil.py`, DB)** — `_StartMelder` um `ziehe_gate_nach(self, anfrage_id)` erweitern (`self.gate.append(anfrage_id)`, Start `[]`); neue Tests (einzeln, je RED):

```python
def test_main_zieht_beim_start_das_gate_fuer_die_eigene_anfrage_nach(umgebung, monkeypatch):
    import sys

    melder = _StartMelder()
    main = _main_mit_melder(monkeypatch, ANFRAGE_A, melder)
    try:
        assert melder.gate == [ANFRAGE_A]
        assert melder.gemeldet == [ANFRAGE_A]
    finally:
        main._store.close()
        main._profil_pool.close()
        sys.modules.pop("bc1_service.main", None)


def test_main_bricht_ab_wenn_das_gate_die_anfrage_schon_abschliesst(umgebung, monkeypatch):
    class _GateSchliesstAb(_StartMelder):
        def ziehe_gate_nach(self, anfrage_id):
            super().ziehe_gate_nach(anfrage_id)
            # So wirkt BC0, wenn alle Teilprozesse der Anfrage fertig sind (v3.13).
            with verbindung(DSN, None) as conn:
                conn.execute("UPDATE ref_anfragen SET status = 'am_gate' "
                             "WHERE company_id = %s AND anfrage_id = %s", (MANDANT_A, anfrage_id))
                conn.commit()

    melder = _GateSchliesstAb()
    with pytest.raises(RuntimeError, match="steht auf 'am_gate'"):
        _main_mit_melder(monkeypatch, ANFRAGE_A, melder)
    assert melder.gemeldet == []


def test_main_schliesst_die_pools_wenn_das_gate_beim_start_scheitert(umgebung, monkeypatch):
    from bc1_service.bc0_meldungen import Bc0MeldungFehler
    from psycopg_pool import ConnectionPool

    geschlossen: list[str] = []
    original = ConnectionPool.close

    def _close(self, *a, **kw):
        geschlossen.append("pool")
        return original(self, *a, **kw)

    class _GateKaputt(_StartMelder):
        def ziehe_gate_nach(self, anfrage_id):
            raise Bc0MeldungFehler("BC0 antwortet auf 'Gate nachziehen' mit 500: x")

    monkeypatch.setattr(ConnectionPool, "close", _close)
    with pytest.raises(Bc0MeldungFehler, match="Gate nachziehen"):
        _main_mit_melder(monkeypatch, ANFRAGE_A, _GateKaputt())
    assert len(geschlossen) >= 2
```

Implementierung `main.py` (Import um `pruefe_bc0_vor_dem_start` ergänzen):

```python
try:
    # Ergaenzung 2: vor dem Lesen aus der DB — Zugang pruefen, Gate fuer die eigene Anfrage
    # nachziehen. Hat ein frueherer Lauf das Gate verpasst, steht die Anfrage danach auf
    # am_gate und lade_kontext bricht mit der B5-Meldung ab.
    pruefe_bc0_vor_dem_start(_melder, _anfrage_id)
    with _profil_pool.connection() as _conn:
        _kontext = lade_kontext(_conn, _company_id, _anfrage_id)
        _status = bc0_lesepfade.anfrage_status(_conn, _company_id, _anfrage_id)
    melde_interview_beginn(_melder, _anfrage_id, _status)
except Exception:
    ...  # unverändert: beide Pools schließen, re-raise
```

- [ ] **Step 5: Doku**
  - `SMOKE.md`: den B5-Hinweis „**Für den Durchstich** einen Teilprozess wählen, zu dem es noch kein fertiges BC1-Profil gibt …" ersetzen durch „Seit BC0 v3.13 (08.10.) zählt die Gate-Funktion nur Profile derselben Anfrage — im Durchstich ist jeder Teilprozess wählbar." Im BC0-Absatz ergänzen: beim Start zieht der Dienst nach der Kontoprüfung das Gate für die eigene Anfrage nach; ist die Anfrage danach schon `am_gate`, endet der Start mit „steht auf 'am_gate'".
  - `README.md` (Absatz „Was der Dienst bei BC0 tut"): dieselbe Ergänzung in einem Satz; Gate-Aufrufe tragen `?anfrage_id=`.
  - `Abschlussplan-BC1.md`: Stand-Zeile; B4-Zeile „gebaut; Live offen" → „live: Probe 08.10. bestanden" und den Hinweis „Teilprozess ohne fertiges Profil" streichen, Ergänzung 2 nennen; Kleinpunkt „Neu 08.10." (1) Selbstheilung → *erledigt 08.10. (Ergänzung 2)*; Kleinpunkt „Neu 06.10." (9) BC0-Gate-Funktion über `anfrage_id` → *erledigt durch BC0 v3.13 (#281)*.
  - Kontrolle: `git grep -n "ohne fertiges\|kein fertiges" README.md bc1_service/n8n/SMOKE.md design/Abschlussplan-BC1.md` findet nur noch erledigte/historische Stellen.

- [ ] **Step 6: Grün + Commit** — `BC1_TEST_DB_DSN=… uv run pytest -q -W error`; Commit `"BC1 B4: Gate je Anfrage (?anfrage_id) und Selbstheilung beim Start (BC0 v3.13)"` (+ Trailer).

- [ ] **Step 7: Pause** — agy-Review, Zwischenstand, Push/PR nur nach OK der BC1-Projektleitung.
