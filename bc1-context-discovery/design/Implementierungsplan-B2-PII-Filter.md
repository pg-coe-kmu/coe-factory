# B2 — PII-Filter vor LLM und Datenbank: Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) oder superpowers:subagent-driven-development — Tasks einzeln, **je Test EIN Edit**, nach jedem Test ein voller `.venv/bin/pytest -q -W error`-Lauf aus `bc1-context-discovery/` (tdd-guard). `*.py` ausschließlich über Edit/Write. Steps use checkbox (`- [ ]`) syntax for tracking.

**Ziel:** Kein personenbezogener Klartext verlässt den Code-Kern — weder zum LLM-Anbieter noch in `bc1.sessions`/`bc1.prozessprofil`. Ein reiner Textschritt `ersetze_pii` im Kern, unmittelbar vor dem ersten Speichern einer Nachricht; danach existiert kein Original mehr.

**Architektur:** Neues Modul `bc1_core/pii.py` (nur `re`, total, deterministisch, idempotent) mit einer öffentlichen Funktion. Einhängung an genau einer Stelle in `process_turn` (vor `raw_log.append`), damit API, CLI und Testprofil-Skripte gleich behandelt werden und der Crash-Resume-Pfad automatisch gefilterten Text abspielt. Die Systemprompts erklären dem LLM die Platzhalter. Eine Kennzahl (Testset) hält die gemessene Erkennung fest.

**Tech Stack:** Python 3.11+, `re`, pytest (`-W error`), tdd-guard. Kein neues Paket, kein Modell, kein Netz.

**Spec:** `design/Konzept-B2-PII-Filter.md` (Entscheidungen Richard 14.09.2026). Der Plan argumentiert aus dem Konzept; Ausführende lesen beides.

## Global Constraints

- **TDD mit tdd-guard:** Test zuerst, RED messen, dann Implementierung; `*.py` ausschließlich über Edit/Write (Bash-Schreibvorgänge sieht der Hook nicht — das wäre ein Bypass). **Je Edit genau EIN neuer Test** („Multiple test addition violation"), danach voller Lauf. Der Guard lässt nur die minimale Antwort auf den **aktuellen** Fehlschlag zu — wo der Plan einen größeren Codeblock zeigt, in Teilschritten bauen (Skill `tdd-guard`, Lessons). Return-Stubs statt `raise`-Stubs. Neue Impl-Datei erst NACH dem vollen Lauf anlegen, der den `ModuleNotFoundError` als RED registriert.
- **Volle Suite** nach jedem Test: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q -W error` aus `bc1-context-discovery/`. Ausgangslage 14.09.: **502 passed / 4 skipped** (Container `bc1-test-pg` läuft, colima an).
- **Platzhalterformat** `[Klasse KENNUNG]` mit Klasse ∈ {Person, E-Mail, Telefon, IBAN, Adresse}, Kennung A…Z, AA, AB, … — keine Ziffern, Kommas, Zeilenumbrüche (passiert `LISTE`, `_entferne_rand`, Zahl-Parser, S-NN-Regel unverändert; Konzept T3).
- **Hinweiswort bleibt stehen, Titel und Name werden ersetzt:** „Frau Dr. Erika Musterfrau" → „Frau [Person A]"; „Prof. Dr. Mustermann" → „[Person A]".
- **Abweichung vom Konzept, hier festgehalten:** „PLZ + Ort" wird **nur hinter einer Straße** erkannt („Musterstraße 12, 10115 Berlin"), nicht allein — fünfstellige Mengen („12000 Rechnungen") sind in Interviews häufig und wären Fehltreffer. Konzept-Tabelle in Task 5 nachziehen.
- **Bestehende Tests bleiben unverändert** (kein Testskript enthält PII-Muster, gemessen 14.09.). `raw_log`-Assertions wie `[("msg-1", "hallo")]` gelten weiter.
- **Keine realen Namen** in Code, Tests, Kommentaren — nur erfundene (Mustermann, Musterfrau, Beispiel), Domains `example.org/.com`, die dokumentierte Beispiel-IBAN `DE89 3704 0044 0532 0130 00`, erfundene Nummern.
- **Kein Push ohne OK von Richard.** Branch `bc1-b2-pii-konzept` ab `origin/bc1-db-profil-fundament` @ `f88f7d4` (bis PR #201 gemergt ist; danach Ziel `main`). Kein Worktree (tdd-guard hängt am Hauptcheckout).
- Sprache Deutsch. Commit-Stil `feat(bc1): …` / `test(bc1): …` / `docs(bc1): …` mit `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Alle Zahlen in Doku sind **gemessen**, nicht vermutet.

---

## Dateien

- Create: `bc1_core/pii.py` — Muster, Platzhaltervergabe, `ersetze_pii`
- Create: `tests/test_pii.py` — Verhalten je Muster, Vergabe, Idempotenz, Totalität
- Create: `tests/pii_testset.py` — Testset für die Kennzahl (POSITIV je Klasse, NEGATIV)
- Create: `tests/test_pii_kpi.py` — Kennzahl je Klasse = README, Fehltreffer = 0
- Modify: `bc1_core/core.py:131-135` — Filter vor `raw_log.append`
- Modify: `tests/test_core.py` — Integrationstest (Log + Fake-LLM sehen nur Platzhalter)
- Modify: `tests/test_feldtypen.py`, `tests/test_paket_feldtypen.py` — Round-Trip der Platzhalter
- Modify: `bc1_service/prompts.py` — `PII_HINWEIS` an beide Systemprompts
- Modify: `tests/test_prompts.py` — Hinweis gepinnt
- Modify: `README.md` — Abschnitt „PII-Filter" (vor „Setup und Start")
- Modify: `design/Konzept-B2-PII-Filter.md` — Adresse-Zeile (PLZ nur hinter Straße)
- Modify: `design/Abschlussplan-BC1.md` — B2-Zeile, Kleinpunkte

**Interfaces (Produces):**
- `bc1_core.pii.ersetze_pii(text: str) -> str` — total, deterministisch, idempotent
- `tests.pii_testset.POSITIV: list[tuple[str, str, str]]` = (Klasse, Eingabe, Erwartet); `tests.pii_testset.NEGATIV: list[str]`
- `bc1_service.prompts.PII_HINWEIS: str` — Satz, der an `SYSTEM_EXTRAKTION` und `SYSTEM_GESPRAECH` angehängt ist

---

## Reihenfolge

Task 0 (Plan-Commit, Basis messen) → Task 1 (Muster-Klassen + Vergabe) → Task 2 (Namen, Idempotenz, Totalität) → Task 3 (Einhängung im Kern + Round-Trip) → Task 4 (Prompts) → Task 5 (Kennzahl + Doku) → Task 6 (Zweitmeinung) → Task 7 (Abschluss, Push-Frage).

---

## Task 0: Plan-Commit und Basis

**Files:** dieser Plan.

- [ ] **Step 1:** Branch prüfen: `git status -sb` → `## bc1-b2-pii-konzept...origin/bc1-db-profil-fundament`, Arbeitsbaum sauber (Konzept-Commit `80aecb3` liegt darauf).
- [ ] **Step 2:** Container läuft? `docker ps --format '{{.Names}}'` → `bc1-test-pg`; sonst `docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:17`. Suite-Basis messen: erwartet **502 passed / 4 skipped**.
- [ ] **Step 3:** Commit `docs(bc1): Implementierungsplan B2 — PII-Filter vor LLM und Datenbank`.

---

## Task 1: Muster-Klassen (E-Mail, IBAN, Telefon, Adresse) und Platzhaltervergabe

**Files:**
- Create: `tests/test_pii.py`
- Create: `bc1_core/pii.py`

**Interfaces:**
- Produces: `ersetze_pii(text: str) -> str`; intern `_Vergabe` (Platzhalter je Klasse und Turn), `_buchstabe(n: int) -> str`, `_MUSTER` (Reihenfolge = Anwendungsreihenfolge).

Vorgehen je Test: Test per Edit anfügen (EIN Test) → voller Lauf → RED → minimal ergänzen → voller Lauf → GREEN. Der Guard darf kleinere Schritte verlangen als hier gezeigt (z. B. erst einen festen String, dann die Vergabe) — dann so bauen, die Zielform steht am Ende von Task 2.

- [ ] **Step 1: Erster Test — E-Mail** (`tests/test_pii.py` anlegen)

```python
"""PII-Filter (B2): personenbezogene Angaben werden VOR dem ersten Speichern
durch Platzhalter ersetzt. Erfundene Namen/Adressen/Nummern (Repo-Konvention);
was erkannt wird und was bewusst nicht: design/Konzept-B2-PII-Filter.md."""
from bc1_core.pii import ersetze_pii


def test_email_wird_platzhalter():
    assert (ersetze_pii("Rückfragen an erika.musterfrau@example.org bitte.")
            == "Rückfragen an [E-Mail A] bitte.")
```

- [ ] **Step 2:** Voller Lauf → RED (`ModuleNotFoundError: bc1_core.pii`). Erst jetzt `bc1_core/pii.py` anlegen:

```python
"""PII-Filter (B2): ersetzt personenbezogene Angaben durch Platzhalter, BEVOR der
Kern eine Nachricht speichert oder an einen Anbieter gibt.

Total (wirft nie), deterministisch, idempotent — nur Standardbibliothek.
Was erkannt wird, was bewusst nicht (nackte Nachnamen, Kartennummern,
Konsistenz über Turns) und warum: design/Konzept-B2-PII-Filter.md.
"""
from __future__ import annotations

import re

# Reihenfolge = Anwendungsreihenfolge: spezifisch vor allgemein.
_MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("E-Mail", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)


def _buchstabe(n: int) -> str:
    """0 → A, 25 → Z, 26 → AA (wie Tabellenspalten)."""
    kennung = ""
    n += 1
    while n:
        n, rest = divmod(n - 1, 26)
        kennung = chr(65 + rest) + kennung
    return kennung


class _Vergabe:
    """Platzhalter je Klasse und Turn: gleicher Wert → gleicher Buchstabe."""

    def __init__(self) -> None:
        self._kennung: dict[tuple[str, str], str] = {}
        self._belegt: dict[str, set[str]] = {}

    def platzhalter(self, klasse: str, wert: str) -> str:
        schluessel = (klasse, " ".join(wert.split()).lower())
        if schluessel not in self._kennung:
            belegt = self._belegt.setdefault(klasse, set())
            n = 0
            while _buchstabe(n) in belegt:
                n += 1
            belegt.add(_buchstabe(n))
            self._kennung[schluessel] = f"[{klasse} {_buchstabe(n)}]"
        return self._kennung[schluessel]


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[E-Mail A]"."""
    vergabe = _Vergabe()
    for klasse, muster in _MUSTER:
        text = muster.sub(lambda m, k=klasse: vergabe.platzhalter(k, m.group(0)),
                          text)
    return text
```

- [ ] **Step 3:** Voller Lauf → GREEN (503 passed). Commit `feat(bc1): PII-Filter — E-Mail-Muster und Platzhaltervergabe (B2, Task 1)`.

- [ ] **Step 4: Test — gleicher Wert, gleicher Platzhalter** (anfügen)

```python
def test_gleicher_wert_im_turn_bekommt_denselben_platzhalter():
    assert (ersetze_pii("erika@example.org und nochmal Erika@example.org")
            == "[E-Mail A] und nochmal [E-Mail A]")
```

Voller Lauf → GREEN bei Ankunft (die Vergabe normalisiert auf Kleinschreibung). Kein Commit nötig, weiter.

- [ ] **Step 5: Test — Buchstaben über Z hinaus** (anfügen)

```python
def test_buchstaben_laufen_ueber_z_hinaus():
    mails = " ".join(f"m{i}@example.org" for i in range(27))
    ergebnis = ersetze_pii(mails)
    assert "[E-Mail Z]" in ergebnis
    assert ergebnis.endswith("[E-Mail AA]")
```

Voller Lauf → GREEN bei Ankunft (`_buchstabe`). Commit `test(bc1): PII-Filter — Vergabe im Turn und Kennung über Z hinaus (B2, Task 1)`.

- [ ] **Step 6: Test — IBAN** (anfügen)

```python
def test_iban_wird_platzhalter():
    assert (ersetze_pii("Konto DE89 3704 0044 0532 0130 00 verwenden.")
            == "Konto [IBAN A] verwenden.")
    assert (ersetze_pii("IBAN DE89370400440532013000 ohne Leerzeichen")
            == "IBAN [IBAN A] ohne Leerzeichen")
```

- [ ] **Step 7:** Voller Lauf → RED. `_MUSTER` ergänzen (nach E-Mail):

```python
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2} ?(?:[A-Z0-9]{4} ?){2,7}[A-Z0-9]{1,4}\b")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — IBAN (B2, Task 1)`.

- [ ] **Step 8: Test — Telefon** (anfügen)

```python
def test_telefon_mit_vorwahl_wird_platzhalter():
    assert (ersetze_pii("Erreichbar unter +49 30 1234567 oder 0151 12345678.")
            == "Erreichbar unter [Telefon A] oder [Telefon B].")
    assert ersetze_pii("Büro 030/1234567") == "Büro [Telefon A]"
```

- [ ] **Step 9:** Voller Lauf → RED. `_MUSTER` ergänzen (nach IBAN — sonst frisst Telefon die Ziffern der IBAN):

```python
    ("Telefon", re.compile(r"(?:\+\d{1,3}[ /-]?|\b0)\d(?:[ /-]?\d){6,13}\b")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Telefon (B2, Task 1)`.

- [ ] **Step 10: Test — Mengen und Datumsangaben bleiben stehen** (anfügen)

```python
def test_mengen_und_daten_bleiben_stehen():
    for text in ("180 Fälle pro Jahr", "3 pro Woche", "45 Minuten",
                 "am 14.09.2026", "seit 2026-09-14", "12000 Rechnungen im Jahr",
                 "Termin 09/14/2026", "Rechnung Nr. 4711"):
        assert ersetze_pii(text) == text
```

- [ ] **Step 11:** Voller Lauf → RED an `09/14/2026` (Telefon-Muster greift). `ersetze_pii` bekommt die Datums-Ausnahme:

```python
_DATUM = re.compile(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2}")


def _ersatz(klasse: str, m: re.Match[str], vergabe: _Vergabe) -> str:
    if klasse == "Telefon" and _DATUM.fullmatch(m.group(0)):
        return m.group(0)
    return vergabe.platzhalter(klasse, m.group(0))


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[E-Mail A]"."""
    vergabe = _Vergabe()
    for klasse, muster in _MUSTER:
        text = muster.sub(lambda m, k=klasse: _ersatz(k, m, vergabe), text)
    return text
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Datumsformen sind keine Telefonnummern (B2, Task 1)`.

- [ ] **Step 12: Test — Adresse** (anfügen)

```python
def test_adresse_wird_platzhalter():
    assert (ersetze_pii("Sitz: Musterstraße 12, 10115 Berlin.")
            == "Sitz: [Adresse A].")
    assert ersetze_pii("Büro am Marktplatz 5") == "Büro am [Adresse A]"
    assert ersetze_pii("Beispielweg 3a") == "[Adresse A]"
```

- [ ] **Step 13:** Voller Lauf → RED. `_MUSTER` ergänzen (nach Telefon):

```python
    ("Adresse", re.compile(
        r"\b[A-ZÄÖÜ][\wäöüß-]*(?:straße|strasse|str\.|weg|allee|gasse|platz)"
        r"\s+\d+[a-zA-Z]?(?:,?\s+\d{5}\s+[A-ZÄÖÜ][\wäöüß-]+)?\b")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Adresse (Straße mit Hausnummer, PLZ nur dahinter) (B2, Task 1)`.

---

## Task 2: Namen mit Hinweiswort, Idempotenz, Totalität

**Files:**
- Modify: `tests/test_pii.py`
- Modify: `bc1_core/pii.py`

**Interfaces:**
- Consumes: `_MUSTER`, `_Vergabe`, `_ersatz` aus Task 1.
- Produces: Zielform von `bc1_core/pii.py` (vollständig am Ende dieses Tasks).

- [ ] **Step 1: Test — Anrede** (anfügen)

```python
def test_anrede_verraet_den_namen_hinweiswort_bleibt():
    assert (ersetze_pii("Herr Mustermann prüft die Rechnung.")
            == "Herr [Person A] prüft die Rechnung.")
    assert (ersetze_pii("mit Herrn Beispiel und Frau Musterfrau")
            == "mit Herrn [Person A] und Frau [Person B]")
    assert (ersetze_pii("Bitte an Hr. Mustermann und Fr. Musterfrau.")
            == "Bitte an Hr. [Person A] und Fr. [Person B].")
```

- [ ] **Step 2:** Voller Lauf → RED. Person-Muster (Anrede) ans Ende von `_MUSTER`, `_ersatz` erweitern:

```python
# Ein Wort mit großem Anfangsbuchstaben (Umlaute, Bindestrich erlaubt).
_WORT = r"[A-ZÄÖÜ][\wäöüß-]+"
_TITEL = r"(?:(?:Dr|Prof)\.\s+)"
_NAME = _TITEL + r"*" + _WORT + r"(?:\s+" + _WORT + r"){0,2}"

_MUSTER = (
    ... E-Mail, IBAN, Telefon, Adresse wie in Task 1 ...
    # Hinweiswort bleibt stehen (Gruppe "hinweis"), Titel + Name werden ersetzt.
    ("Person", re.compile(
        r"(?P<hinweis>\b(?:Herrn?|Frau|Hr\.|Fr\.|Kolleg(?:e|in|en)"
        r"|[Ii]ch heiße|[Mm]ein Name ist)\s+)"
        r"(?P<name>" + _NAME + r")")),
)


def _ersatz(klasse: str, m: re.Match[str], vergabe: _Vergabe) -> str:
    if klasse == "Person":
        return m.group("hinweis") + vergabe.platzhalter(klasse, m.group("name"))
    if klasse == "Telefon" and _DATUM.fullmatch(m.group(0)):
        return m.group(0)
    return vergabe.platzhalter(klasse, m.group(0))
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Namen hinter Anrede (B2, Task 2)`.

- [ ] **Step 3: Test — Titel und mehrteilige Namen sind EIN Platzhalter** (anfügen)

```python
def test_titel_und_mehrteilige_namen_werden_ein_platzhalter():
    assert (ersetze_pii("Frau Dr. Erika Musterfrau leitet das.")
            == "Frau [Person A] leitet das.")
    assert (ersetze_pii("Kollegin Anna Maria Muster übernimmt.")
            == "Kollegin [Person A] übernimmt.")
    assert ersetze_pii("Prof. Dr. Mustermann entscheidet.") == "[Person A] entscheidet."
    assert ersetze_pii("Dr. Beispiel ruft zurück.") == "[Person A] ruft zurück."
```

- [ ] **Step 4:** Voller Lauf → RED an `Prof. Dr. Mustermann` (Titel ohne Anrede). Zweites Person-Muster **nach** dem ersten anfügen (Hinweis-Gruppe leer, damit `_ersatz` unverändert bleibt):

```python
    ("Person", re.compile(r"(?P<hinweis>\b)(?P<name>" + _TITEL + r"+" + _WORT
                          + r"(?:\s+" + _WORT + r"){0,2})")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Titel ohne Anrede, mehrteilige Namen (B2, Task 2)`.

- [ ] **Step 5: Test — Selbstvorstellung und Kollege** (anfügen)

```python
def test_selbstvorstellung_und_kollege():
    assert ersetze_pii("Mein Name ist Max Mustermann.") == "Mein Name ist [Person A]."
    assert ersetze_pii("Ich heiße Erika Musterfrau.") == "Ich heiße [Person A]."
    assert ersetze_pii("Kollege Muster übernimmt.") == "Kollege [Person A] übernimmt."
```

Voller Lauf → GREEN bei Ankunft (Hinweiswörter stehen schon im Muster). Weiter ohne Commit.

- [ ] **Step 6: Test — kein Treffer ohne Hinweiswort / bei kleingeschriebenem Folgewort** (anfügen)

```python
def test_kein_treffer_ohne_hinweiswort_und_bei_kleingeschriebenem_folgewort():
    for text in ("Mustermann prüft das.", "die Frau des Kunden ruft an",
                 "Kollegen aus dem Vertrieb", "ich bin Sachbearbeiter",
                 "Herr der Lage", "Anfrage eines Kollegen oder Kunden"):
        assert ersetze_pii(text) == text
```

Voller Lauf → GREEN bei Ankunft. Commit `test(bc1): PII-Filter — Selbstvorstellung, Kollege, Negativfälle (B2, Task 2)`.

- [ ] **Step 7: Test — vorhandene Platzhalter bleiben, Kennungen kollidieren nicht** (anfügen)

```python
def test_vorhandene_platzhalter_bleiben_und_kollidieren_nicht():
    assert (ersetze_pii("Frau [Person A] und Herr Muster")
            == "Frau [Person A] und Herr [Person B]")
```

- [ ] **Step 8:** Voller Lauf → RED (heute `[Person A]` doppelt). Platzhalter-Schutz: vorhandene Platzhalter werden als Abschnittsgrenzen behandelt und ihre Kennungen vorab als belegt markiert:

```python
_PLATZHALTER = re.compile(
    r"\[(?P<klasse>Person|E-Mail|Telefon|IBAN|Adresse) (?P<kennung>[A-Z]+)\]")


class _Vergabe:
    """Platzhalter je Klasse und Turn: gleicher Wert → gleicher Buchstabe.
    Schon vorhandene Platzhalter (Idempotenz, eingefügter Text) behalten ihre
    Kennung; sie wird nicht neu vergeben."""

    def __init__(self, text: str) -> None:
        self._kennung: dict[tuple[str, str], str] = {}
        self._belegt: dict[str, set[str]] = {}
        for m in _PLATZHALTER.finditer(text):
            self._belegt.setdefault(m.group("klasse"), set()).add(m.group("kennung"))

    def platzhalter(self, klasse: str, wert: str) -> str:
        ...  # unverändert aus Task 1


def _ersetze_abschnitt(abschnitt: str, vergabe: _Vergabe) -> str:
    for klasse, muster in _MUSTER:
        abschnitt = muster.sub(lambda m, k=klasse: _ersatz(k, m, vergabe), abschnitt)
    return abschnitt


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[Person A]".

    Total, deterministisch, idempotent: vorhandene Platzhalter bleiben stehen,
    die Muster laufen nur über den Text dazwischen.
    """
    vergabe = _Vergabe(text)
    teile: list[str] = []
    pos = 0
    for m in _PLATZHALTER.finditer(text):
        teile.append(_ersetze_abschnitt(text[pos:m.start()], vergabe))
        teile.append(m.group(0))
        pos = m.end()
    teile.append(_ersetze_abschnitt(text[pos:], vergabe))
    return "".join(teile)
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — vorhandene Platzhalter geschützt, Kennungen kollisionsfrei (B2, Task 2)`.

- [ ] **Step 9: Test — idempotent und deterministisch** (anfügen)

```python
def test_idempotent_und_deterministisch():
    text = "Herr Muster (muster@example.org, 0151 12345678), Musterstraße 1"
    einmal = ersetze_pii(text)
    assert einmal == "Herr [Person A] ([E-Mail A], [Telefon A]), [Adresse A]"
    assert ersetze_pii(einmal) == einmal
    assert ersetze_pii(text) == einmal
```

Voller Lauf → GREEN bei Ankunft. Weiter.

- [ ] **Step 10: Test — leer und beliebiger Text ohne Ausnahme** (anfügen)

```python
def test_leer_und_beliebiger_text_ohne_ausnahme():
    assert ersetze_pii("") == ""
    for text in ("[", "]]", "@", "+", "Dr.", "Herr ", "\n\t", "S-03, S-04",
                 "0" * 40, "[Person ]", "[Person A"):
        ersetze_pii(text)   # darf nie werfen; Rückgabe ist ein str
```

Voller Lauf → GREEN bei Ankunft. Commit `test(bc1): PII-Filter — Idempotenz, Determinismus, Totalität (B2, Task 2)`.

- [ ] **Step 11: Zielform prüfen.** `bc1_core/pii.py` muss jetzt genau diese Bausteine enthalten (Reihenfolge in `_MUSTER`: E-Mail, IBAN, Telefon, Adresse, Person/Anrede, Person/Titel):

```python
"""PII-Filter (B2): ersetzt personenbezogene Angaben durch Platzhalter, BEVOR der
Kern eine Nachricht speichert oder an einen Anbieter gibt.

Total (wirft nie), deterministisch, idempotent — nur Standardbibliothek.
Was erkannt wird, was bewusst nicht (nackte Nachnamen, Kartennummern,
Konsistenz über Turns) und warum: design/Konzept-B2-PII-Filter.md.
"""
from __future__ import annotations

import re

# Ein Wort mit großem Anfangsbuchstaben (Umlaute, Bindestrich erlaubt).
_WORT = r"[A-ZÄÖÜ][\wäöüß-]+"
_TITEL = r"(?:(?:Dr|Prof)\.\s+)"
_NAME = _TITEL + r"*" + _WORT + r"(?:\s+" + _WORT + r"){0,2}"

# Reihenfolge = Anwendungsreihenfolge: spezifisch vor allgemein (IBAN vor
# Telefon, Anrede+Titel+Name als EIN Treffer vor dem Titel-Muster).
_MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("E-Mail", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2} ?(?:[A-Z0-9]{4} ?){2,7}[A-Z0-9]{1,4}\b")),
    ("Telefon", re.compile(r"(?:\+\d{1,3}[ /-]?|\b0)\d(?:[ /-]?\d){6,13}\b")),
    ("Adresse", re.compile(
        r"\b[A-ZÄÖÜ][\wäöüß-]*(?:straße|strasse|str\.|weg|allee|gasse|platz)"
        r"\s+\d+[a-zA-Z]?(?:,?\s+\d{5}\s+[A-ZÄÖÜ][\wäöüß-]+)?\b")),
    # Hinweiswort bleibt stehen (Gruppe "hinweis"), Titel + Name werden ersetzt.
    ("Person", re.compile(
        r"(?P<hinweis>\b(?:Herrn?|Frau|Hr\.|Fr\.|Kolleg(?:e|in|en)"
        r"|[Ii]ch heiße|[Mm]ein Name ist)\s+)"
        r"(?P<name>" + _NAME + r")")),
    ("Person", re.compile(r"(?P<hinweis>\b)(?P<name>" + _TITEL + r"+" + _WORT
                          + r"(?:\s+" + _WORT + r"){0,2})")),
)
_DATUM = re.compile(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2}")
_PLATZHALTER = re.compile(
    r"\[(?P<klasse>Person|E-Mail|Telefon|IBAN|Adresse) (?P<kennung>[A-Z]+)\]")


def _buchstabe(n: int) -> str:
    """0 → A, 25 → Z, 26 → AA (wie Tabellenspalten)."""
    kennung = ""
    n += 1
    while n:
        n, rest = divmod(n - 1, 26)
        kennung = chr(65 + rest) + kennung
    return kennung


class _Vergabe:
    """Platzhalter je Klasse und Turn: gleicher Wert → gleicher Buchstabe.
    Schon vorhandene Platzhalter (Idempotenz, eingefügter Text) behalten ihre
    Kennung; sie wird nicht neu vergeben."""

    def __init__(self, text: str) -> None:
        self._kennung: dict[tuple[str, str], str] = {}
        self._belegt: dict[str, set[str]] = {}
        for m in _PLATZHALTER.finditer(text):
            self._belegt.setdefault(m.group("klasse"), set()).add(m.group("kennung"))

    def platzhalter(self, klasse: str, wert: str) -> str:
        schluessel = (klasse, " ".join(wert.split()).lower())
        if schluessel not in self._kennung:
            belegt = self._belegt.setdefault(klasse, set())
            n = 0
            while _buchstabe(n) in belegt:
                n += 1
            belegt.add(_buchstabe(n))
            self._kennung[schluessel] = f"[{klasse} {_buchstabe(n)}]"
        return self._kennung[schluessel]


def _ersatz(klasse: str, m: re.Match[str], vergabe: _Vergabe) -> str:
    if klasse == "Person":
        return m.group("hinweis") + vergabe.platzhalter(klasse, m.group("name"))
    if klasse == "Telefon" and _DATUM.fullmatch(m.group(0)):
        return m.group(0)
    return vergabe.platzhalter(klasse, m.group(0))


def _ersetze_abschnitt(abschnitt: str, vergabe: _Vergabe) -> str:
    for klasse, muster in _MUSTER:
        abschnitt = muster.sub(lambda m, k=klasse: _ersatz(k, m, vergabe), abschnitt)
    return abschnitt


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[Person A]".

    Total, deterministisch, idempotent: vorhandene Platzhalter bleiben stehen,
    die Muster laufen nur über den Text dazwischen.
    """
    vergabe = _Vergabe(text)
    teile: list[str] = []
    pos = 0
    for m in _PLATZHALTER.finditer(text):
        teile.append(_ersetze_abschnitt(text[pos:m.start()], vergabe))
        teile.append(m.group(0))
        pos = m.end()
    teile.append(_ersetze_abschnitt(text[pos:], vergabe))
    return "".join(teile)
```

Bekannte, akzeptierte Grenzen (im README, Task 5): „Dr. Oetker" wird `[Person A]`; „Dr. med. Muster" bleibt teilweise stehen (kleingeschriebener Titelzusatz); „Fr. Vormittag" wird ersetzt. Übererkennung kostet Information, Untererkennung kostet Datenschutz.

---

## Task 3: Einhängung im Kern und Round-Trip durch die Feldtypen

**Files:**
- Modify: `bc1_core/core.py:6` (Import) und `:131-135` (vor `raw_log.append`)
- Modify: `tests/test_core.py` (Integrationstest)
- Modify: `tests/test_feldtypen.py`, `tests/test_paket_feldtypen.py`

**Interfaces:**
- Consumes: `bc1_core.pii.ersetze_pii`.
- Produces: `process_turn` speichert und verarbeitet ausschließlich gefilterten Text; Signatur unverändert.

- [ ] **Step 1: Integrationstest** (`tests/test_core.py`, anfügen; Import `from bc1_core.serialize import state_to_dict` oben ergänzen — vorhandene Imports: `json`, `InMemoryStateStore`, `FakeLLM`, `ExtractionCandidate`, `TOY_PROZESS`, `_turn`)

```python
def test_pii_wird_vor_dem_speichern_ersetzt_und_das_llm_sieht_nur_platzhalter():
    store = InMemoryStateStore()
    gefiltert = "Frau [Person A] startet den Prozess, Rückfragen an [E-Mail A]."
    # Skript auf den GEFILTERTEN Text geschlüsselt: greift es, hat der LLM-Client
    # nie den Rohtext gesehen.
    llm = FakeLLM({gefiltert: [ExtractionCandidate("prozess_name", "Freigabe")]})
    roh = "Frau Musterfrau startet den Prozess, Rückfragen an erika@example.org."
    _turn(store, llm, TOY_PROZESS, "s1", "msg-1", roh)
    st = store.load("s1")
    assert st.raw_log == [("msg-1", gefiltert)]
    assert st.values["prozess_name"].value == "Freigabe"
    gespeichert = json.dumps(state_to_dict(st), ensure_ascii=False)
    assert "Musterfrau" not in gespeichert and "example.org" not in gespeichert
```

- [ ] **Step 2:** Voller Lauf → RED (`raw_log` trägt den Rohtext, Skript greift nicht). `bc1_core/core.py`: Import `from bc1_core.pii import ersetze_pii` (nach `from bc1_core.llm import LLMClient`), und im `else`-Zweig von `process_turn`:

```python
    else:
        # PII-Filter VOR dem ersten Speichern (B2): ab hier existiert kein
        # Original mehr — weder in raw_log noch beim Anbieter. Der
        # Crash-Resume-Pfad oben liest raw_log und ist damit automatisch gefiltert.
        message = ersetze_pii(message)
        # Rohnachricht zuerst sichern (vor jedem LLM-Aufruf).
        state.raw_log.append((message_id, message))
        state.processed_message_ids.add(message_id)
        store.save(state)
```

Voller Lauf → GREEN (alle bestehenden `raw_log`-Assertions halten: kein Testskript enthält PII). Commit `feat(bc1): PII-Filter im Kern vor dem ersten Speichern (B2, Task 3)`.

- [ ] **Step 3: Round-Trip Feldtypen** (`tests/test_feldtypen.py`, anfügen)

```python
def test_pii_platzhalter_passieren_die_normalisierer_unveraendert():
    assert FREITEXT.normalisiere("[Person A]") == "[Person A]"
    assert LISTE.normalisiere("[Person A], [Person B]") == "[Person A], [Person B]"
    assert ZAHL.normalisiere("[Telefon A]") == "[Telefon A]"
    assert JA_NEIN.normalisiere("[Person A]") == "[Person A]"
```

Voller Lauf → GREEN bei Ankunft (pinnt die Konzept-Aussage T3). Weiter.

- [ ] **Step 4: Round-Trip Systemfeld** (`tests/test_paket_feldtypen.py`, anfügen; `baue_system_typ` ist dort schon importiert)

```python
def test_pii_platzhalter_bleibt_im_systemfeld_stehen_und_ist_kein_system():
    typ = baue_system_typ(frozenset({"S-01"}))
    assert typ.normalisiere("S-01, [Person A]") == "S-01, [Person A]"
    assert typ.validator("[Person A]") is False   # eine Person ist kein System
```

Voller Lauf → GREEN bei Ankunft. Commit `test(bc1): PII-Platzhalter passieren Feldtypen und Systemfeld unverändert (B2, Task 3)`.

---

## Task 4: Prompts erklären die Platzhalter

**Files:**
- Modify: `bc1_service/prompts.py:31-49`
- Modify: `tests/test_prompts.py`

**Interfaces:**
- Produces: `PII_HINWEIS: str`, angehängt an `SYSTEM_EXTRAKTION` und `SYSTEM_GESPRAECH` (alle drei Adapter importieren diese Konstanten).

- [ ] **Step 1: Test** (`tests/test_prompts.py`, anfügen)

```python
def test_system_prompts_erklaeren_die_pii_platzhalter():
    # B2: der Anbieter sieht nur Platzhalter — er soll sie wörtlich übernehmen,
    # nie auflösen, nie raten.
    for prompt in (SYSTEM_EXTRAKTION, SYSTEM_GESPRAECH):
        assert "[Person A]" in prompt
        assert "wörtlich" in prompt
        assert "nie auf" in prompt
```

- [ ] **Step 2:** Voller Lauf → RED. `bc1_service/prompts.py`:

```python
PII_HINWEIS = (
    " Ausdrücke in eckigen Klammern wie [Person A], [E-Mail A] oder "
    "[Telefon A] sind Platzhalter für entfernte personenbezogene Angaben: "
    "übernimm sie wörtlich, löse sie nie auf und rate nicht, wer gemeint ist."
)

SYSTEM_EXTRAKTION = (
    "Du extrahierst Fakten aus einer Interview-Antwort für ein Prozessprofil. "
    "Extrahiere NUR, was die Nachricht wirklich belegt — nichts erfinden, "
    "nichts aus Vorwissen ergänzen. Werte wörtlich bzw. minimal normalisiert."
) + PII_HINWEIS

SYSTEM_GESPRAECH = (
    ... bestehender Text unverändert ...
    "Sätze, OHNE Frage."
) + PII_HINWEIS
```

Voller Lauf → GREEN (Adapter-Stub-Tests vergleichen gegen die Konstanten, nicht gegen Literale — falls doch einer rot wird: Literal auf die Konstante umstellen, nicht den Hinweis kürzen). Commit `feat(bc1): Systemprompts erklären die PII-Platzhalter (B2, Task 4)`.

---

## Task 5: Kennzahl `pii_erkennung`, README, Konzept, Abschlussplan

**Files:**
- Create: `tests/pii_testset.py`
- Create: `tests/test_pii_kpi.py`
- Modify: `README.md` (neuer Abschnitt vor „Setup und Start")
- Modify: `design/Konzept-B2-PII-Filter.md` (Adresse-Zeile)
- Modify: `design/Abschlussplan-BC1.md` (B2-Zeile)

**Interfaces:**
- Produces: `tests.pii_testset.POSITIV`, `tests.pii_testset.NEGATIV`; README-Zahlen = `DOKUMENTIERT` im KPI-Test.

- [ ] **Step 1: Testset anlegen** (`tests/pii_testset.py` — Daten, kein Test; darf per Write angelegt werden, enthält keine `test_`-Funktion)

```python
"""Testset für die Kennzahl pii_erkennung (Issue #50).

POSITIV: (Klasse, Eingabe, Erwartet) — erfundene Namen, Beispiel-Domains, die
dokumentierte Beispiel-IBAN, erfundene Nummern. Die Klasse "Name ohne
Hinweiswort" ist die bewusste Lücke aus dem Konzept: ihre Quote MUSS 0 %
bleiben, bis NER kommt — steigt sie, hat sich der Filter verändert.
NEGATIV: Interviewsätze ohne PII (Sätze der Demo-Durchläufe + Grenzfälle),
müssen unverändert bleiben (Fehltreffer = 0).
"""
POSITIV = [
    ("E-Mail", "Rückfragen an erika.musterfrau@example.org.",
     "Rückfragen an [E-Mail A]."),
    ("E-Mail", "Sammelpostfach: rechnungen@example.com",
     "Sammelpostfach: [E-Mail A]"),
    ("E-Mail", "Kontakt max+test@sub.example.org oder info@example.org",
     "Kontakt [E-Mail A] oder [E-Mail B]"),
    ("Telefon", "Erreichbar unter +49 30 1234567.", "Erreichbar unter [Telefon A]."),
    ("Telefon", "Handy 0151 12345678, Büro 030/1234567",
     "Handy [Telefon A], Büro [Telefon B]"),
    ("Telefon", "Tel. +43 1 234 56 78", "Tel. [Telefon A]"),
    ("IBAN", "Überweisung auf DE89 3704 0044 0532 0130 00.",
     "Überweisung auf [IBAN A]."),
    ("IBAN", "IBAN DE89370400440532013000 ohne Leerzeichen",
     "IBAN [IBAN A] ohne Leerzeichen"),
    ("Adresse", "Lieferung an Musterstraße 12, 10115 Berlin.",
     "Lieferung an [Adresse A]."),
    ("Adresse", "Büro am Marktplatz 5", "Büro am [Adresse A]"),
    ("Adresse", "Beispielweg 3a", "[Adresse A]"),
    ("Name mit Hinweiswort", "Herr Mustermann prüft die Rechnung.",
     "Herr [Person A] prüft die Rechnung."),
    ("Name mit Hinweiswort", "Frau Dr. Erika Musterfrau gibt frei.",
     "Frau [Person A] gibt frei."),
    ("Name mit Hinweiswort",
     "Kollegin Musterfrau übernimmt, Kollege Mustermann prüft.",
     "Kollegin [Person A] übernimmt, Kollege [Person B] prüft."),
    ("Name mit Hinweiswort", "Mein Name ist Max Mustermann.",
     "Mein Name ist [Person A]."),
    ("Name mit Hinweiswort", "Ich heiße Erika Musterfrau.", "Ich heiße [Person A]."),
    ("Name mit Hinweiswort", "Prof. Dr. Mustermann entscheidet.",
     "[Person A] entscheidet."),
    ("Name mit Hinweiswort", "Bitte an Hr. Mustermann und Fr. Musterfrau.",
     "Bitte an Hr. [Person A] und Fr. [Person B]."),
    ("Name ohne Hinweiswort", "Mustermann prüft das.", "[Person A] prüft das."),
    ("Name ohne Hinweiswort", "Das macht Erika Musterfrau.", "Das macht [Person A]."),
    ("Name ohne Hinweiswort", "Freigabe durch Mustermann und Musterfrau.",
     "Freigabe durch [Person A] und [Person B]."),
]

NEGATIV = [
    # Sätze der drei Demo-Durchläufe (test_demo_durchlaeufe.py)
    "Wir wollen die Reisebuchung automatisieren — es geht um den ganzen Prozess, Ziel ist Zeit sparen.",
    "Verantwortlich und Ablauf.", "Auslöser, Eingang und Ergebnis.", "Mengen und Dauer.",
    "Der anstrengendste Schritt.", "Beteiligte und Systeme.", "Voraussetzungen.",
    "Office Management, Mitarbeiter", "Mail, Buchungsportal, Excel",
    "Mitarbeiter plant eine Dienstreise", "Anfrage eines Kollegen oder Kunden",
    "Kundenanfrage nach einem Consultant", "CRM, Skill-Datenbank, Excel",
    "Anfrage erfassen, Profile suchen, Matching, Vorschlag versenden",
    "30 pro Monat", "20 pro Woche", "300 pro Jahr", "3 Stunden", "45 Minuten", "60%", "80 %",
    # Grenzfälle: Mengen, Daten, IDs, Rollen, kleingeschriebene Folgewörter
    "180 Fälle pro Jahr", "12000 Rechnungen im Jahr", "Rechnung Nr. 4711 vom 14.09.2026",
    "seit 2026-09-14", "Termin am Freitag um 09:30", "S-03, S-04", "KP-06.TP-2",
    "die Frau des Kunden ruft an", "Kollegen aus dem Vertrieb",
    "ich bin Sachbearbeiter in der Buchhaltung", "Herr der Lage",
    "Arbeitsschritt 3 dauert 20 Minuten",
]
```

- [ ] **Step 2: KPI-Test** (`tests/test_pii_kpi.py` anlegen, EIN Test)

```python
"""Kennzahl pii_erkennung (Issue #50): Trefferquote je Klasse auf dem Testset.
Die Zahlen stehen im README (Abschnitt „PII-Filter"); dieser Test hält sie fest —
ändert sich eine Quote, muss das README mit. Gemessen, nicht gewünscht."""
from collections import defaultdict

from bc1_core.pii import ersetze_pii
from tests.pii_testset import NEGATIV, POSITIV

DOKUMENTIERT = {
    "E-Mail": 1.0,
    "Telefon": 1.0,
    "IBAN": 1.0,
    "Adresse": 1.0,
    "Name mit Hinweiswort": 1.0,
    "Name ohne Hinweiswort": 0.0,   # bewusste Lücke (Konzept), NER-Auslöser
}


def _quoten() -> dict[str, float]:
    treffer: dict[str, int] = defaultdict(int)
    gesamt: dict[str, int] = defaultdict(int)
    for klasse, eingabe, erwartet in POSITIV:
        gesamt[klasse] += 1
        treffer[klasse] += ersetze_pii(eingabe) == erwartet
    return {klasse: treffer[klasse] / gesamt[klasse] for klasse in gesamt}


def test_trefferquote_je_klasse_entspricht_dem_readme():
    assert _quoten() == DOKUMENTIERT
```

- [ ] **Step 3:** Voller Lauf. Erwartet GREEN — wenn eine Quote abweicht, ist entweder das Testset falsch erwartet oder ein Muster hat eine Lücke: **Lücke fixen (Task-1/2-Zyklus), nicht die Zahl anpassen**; nur bewusst akzeptierte Grenzen (Task 2, Step 11) dürfen die Erwartung im Testset ändern. Danach zweiten Test anfügen:

```python
def test_keine_fehltreffer_auf_pii_freien_interviewsaetzen():
    fehltreffer = [satz for satz in NEGATIV if ersetze_pii(satz) != satz]
    assert fehltreffer == []
```

Voller Lauf → GREEN. Commit `test(bc1): Kennzahl pii_erkennung — Testset, Quote je Klasse, null Fehltreffer (B2, Task 5)`.

- [ ] **Step 4: README** — neuer Abschnitt vor `## Setup und Start`:

```markdown
## PII-Filter

Jede Nachricht wird im Kern gefiltert, **bevor** sie gespeichert oder an einen
LLM-Anbieter gegeben wird (`bc1_core/pii.py`, Einhängung in `process_turn`).
Ein Original gibt es danach nicht — weder in `bc1.sessions` noch im Profil.
Strategie: **maskieren**, kein Mapping-Tresor (kein Konsument für eine Rückersetzung).

| Klasse | Erkennung | Platzhalter | Quote Testset |
|---|---|---|---|
| E-Mail | Muster | `[E-Mail A]` | 100 % |
| Telefon | Muster (`+`/`0`-Präfix, 7–14 Ziffern; Datumsformen ausgenommen) | `[Telefon A]` | 100 % |
| IBAN | Muster | `[IBAN A]` | 100 % |
| Adresse | Straße mit Hausnummer, optional PLZ + Ort dahinter | `[Adresse A]` | 100 % |
| Name mit Hinweiswort | Anrede (Herr/Herrn/Frau/Hr./Fr.), Titel (Dr./Prof.), Kollege/Kollegin, „ich heiße", „mein Name ist"; Hinweiswort bleibt stehen | `[Person A]` | 100 % |
| Name ohne Hinweiswort | **nicht erkannt** (bewusste Lücke, braucht NER) | — | 0 % |

Kennungen laufen je Klasse und Turn (A, B, …, AA); gleicher Wert im selben Turn
→ gleicher Platzhalter; über Turns hinweg keine Konsistenz. Fehltreffer auf den
PII-freien Interviewsätzen des Testsets: 0. Testset und Zahlen:
`tests/pii_testset.py`, `tests/test_pii_kpi.py` — der Test hält die Tabelle fest.

Bekannte Grenzen: nackte Nachnamen („Mustermann prüft"), „ich bin X",
kleingeschriebene Titelzusätze („Dr. med."), Kartennummern. Übererkennung ist
akzeptiert („Dr. Oetker" wird `[Person A]`). NER folgt erst bei gemessenem Bedarf.
Außerhalb von BC1: n8n speichert Ausführungsdaten mit der Chat-Eingabe, bevor
der Dienst sie sieht — Hosting-Thema (B3). Konzept: `design/Konzept-B2-PII-Filter.md`.
```

- [ ] **Step 5: Konzept nachziehen** — in `design/Konzept-B2-PII-Filter.md` die Adresse-Zeile der Tabelle „Was erkannt wird" auf: `Straßenwort (…) mit Hausnummer, optional PLZ (5 Ziffern) mit Ort dahinter — nicht allein, weil fünfstellige Mengen („12000 Rechnungen") sonst Fehltreffer wären (Plan, 14.09.)`; in T3 Punkt 5 entsprechend `Adresse (Straße + Hausnummer, optional PLZ + Ort dahinter)`.

- [ ] **Step 6: Abschlussplan** — B2-Zeile: Stand „GEBAUT (Plan `design/Implementierungsplan-B2-PII-Filter.md`, Konzept `design/Konzept-B2-PII-Filter.md`): Filter im Kern vor dem ersten Speichern, Muster + Hinweiswörter, Kennzahl im README; keine Namensliste aus BC0 (ADR-004 R5)"; nächster Schritt „Zweitmeinung, PR"; Kleinpunkte: NER-Auslöser, „Platzhalter als Wert = ungültig" (C2-Nähe), n8n-Ausführungsdaten (B3).

- [ ] **Step 7:** Commit `docs(bc1): README PII-Filter mit Kennzahlen, Konzept-Nachtrag Adresse, Abschlussplan B2 (B2, Task 5)`.

---

## Task 6: Zweitmeinung

Pflicht (CLAUDE.md: Kern-Datenfluss = Tragweite). Wie bei B1: `codex:codex-rescue` als Review über `git diff origin/bc1-db-profil-fundament...HEAD` mit Auftrag „Lücken der Muster (Fehltreffer/Untererkennung im Deutschen), Idempotenz-/Replay-Risiken im Kern, Prompt-Wirkung, Testabdeckung". Codex hat keinen Container — Befunde sind Codeableitungen, jeden übernommenen Befund per rotem Test nachmessen.

- [ ] **Step 1:** Review anstoßen, Befunde in diesen Plan unter „Adjudikation Task 6" eintragen (Nr., Schwere, Entscheidung, Nachweis).
- [ ] **Step 2:** Critical/Important fixen (Test zuerst), Minor begründet fixen oder mit Ziel in den Abschlussplan (Kleinpunkte).
- [ ] **Step 3:** Voller Lauf, Zahl notieren. Commit je Fix `fix(bc1): … (B2, Review N)`.

---

## Task 7: Abschluss

- [ ] **Step 1:** Volle Suite final messen, Zahl in Abschlussplan/README eintragen (README-Tabelle muss `DOKUMENTIERT` entsprechen — der KPI-Test erzwingt es).
- [ ] **Step 2:** Vertraulichkeits-Check: `git diff --name-only origin/bc1-db-profil-fundament...HEAD` → `git grep -n -i -E "passw|secret|supabase\.co|@gmail|sk-ant|AIza" -- <Dateien>` → nur Beispiel-Domains/Testwerte. Befund Richard vorlegen; **Push nur nach OK**.
- [ ] **Step 3:** PR: Ziel `main`, falls PR #201 gemergt ist, sonst `bc1-db-profil-fundament`. PR-Text: Big Picture (was, warum, Entscheidungen), Prüfung (Suite, Kennzahl), Abweichung von #50 (kein Mapping-Tresor).
- [ ] **Step 4:** Kommentar in Issue #50 (öffentlich, nach OK): Stand, Kennzahl, Abweichung, Lücken mit Auslöser.
- [ ] **Step 5:** `SESSION-HANDOFF.md` (lokal): B2-Stand, offene Punkte (BC0 informieren: keine Namen; B7 als nächstes).

---

## Selbstprüfung des Plans (14.09.2026)

- **Spec-Abdeckung:** Konzept T1 (Modul, total/deterministisch/idempotent) → Task 1–2 · T2 (Einhängung, Replay) → Task 3 · T3 (Muster, Reihenfolge, Grenzen, Platzhalterformat) → Task 1–2, Round-Trip Task 3 · T4 (Prompts) → Task 4 · T5 (Tests, KPI) → Task 1–5 · T6 (Doku, Abschlussplan, BC0 informieren, Issue #50) → Task 5, 7 · T7 (Branch, PR) → Task 0, 7. Abweichung „PLZ nur hinter Straße" ist in den Global Constraints und in Task 5 Step 5 nachgehalten.
- **Platzhalter:** keine („…" steht nur für unveränderten Bestandstext, dessen Wortlaut in Task 2 Step 11 bzw. `prompts.py` vollständig sichtbar ist).
- **Typkonsistenz:** `ersetze_pii(text: str) -> str` überall; `_Vergabe(text)` ab Task 2 Step 8 (Task 1 zeigt die frühere Form `_Vergabe()` — Zielform in Step 11 gilt); `_ersatz(klasse, m, vergabe)`; `PII_HINWEIS`; `POSITIV`/`NEGATIV`/`DOKUMENTIERT` mit identischen Klassennamen („E-Mail", „Telefon", „IBAN", „Adresse", „Name mit Hinweiswort", „Name ohne Hinweiswort").
- **Ehrlich offen:** (1) Der Guard kann kleinere Schritte erzwingen als gezeigt; die Zielform (Task 2 Step 11) ist der Maßstab. (2) Die 100-%-Quoten gelten auf einem selbst geschriebenen Testset — sie belegen, dass die Muster tun, was das Konzept sagt, nicht, dass echte Interviews lückenlos gefiltert werden; die 0 % der Lücken-Klasse machen das sichtbar. (3) Ob ein Adapter-Test den Systemprompt als Literal vergleicht, zeigt erst der Lauf in Task 4.
