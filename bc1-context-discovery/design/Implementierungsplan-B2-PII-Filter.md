# B2 — PII-Filter vor LLM und Datenbank: Implementierungsplan (Fassung 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) — Tasks einzeln, **je Test EIN Edit**, nach jedem Test ein voller `.venv/bin/pytest -q -W error`-Lauf aus `bc1-context-discovery/` (tdd-guard). `*.py` ausschließlich über Edit/Write. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Fassung 2 (14.09.2026):** nach unabhängiger Zweitmeinung (Codex, Plan-Review vor dem Bau; Adjudikation am Ende). Fassung 1 = Commit `a3be94c`.

**Ziel:** Kein personenbezogener Klartext verlässt den Code-Kern — weder zum LLM-Anbieter noch in `bc1.sessions`/`bc1.prozessprofil`. Ein reiner Textschritt `ersetze_pii` im Kern, unmittelbar vor dem ersten Speichern einer Nachricht; danach existiert kein Original mehr.

**Architektur:** Neues Modul `bc1_core/pii.py` (nur `re`, total, deterministisch, idempotent) mit einer öffentlichen Funktion. Einhängung an genau einer Stelle in `process_turn` (vor `raw_log.append`), damit API, CLI und Testprofil-Skripte gleich behandelt werden und der Crash-Resume-Pfad den gefilterten Log-Text abspielt. Die Systemprompts erklären dem LLM die Platzhalter. Eine Kennzahl (Testset, eine PII-Stelle je Fall) wird gegen die README-Tabelle gehalten.

**Tech Stack:** Python 3.11+, `re`, pytest (`-W error`), tdd-guard. Kein neues Paket, kein Modell, kein Netz.

**Spec:** `design/Konzept-B2-PII-Filter.md` (Entscheidungen Richard 14.09.2026; Nachträge aus dem Plan-Review sind dort eingearbeitet).

## Global Constraints

- **TDD mit tdd-guard:** Test zuerst, RED messen, dann Implementierung; `*.py` ausschließlich über Edit/Write. **Je Edit genau EIN neuer Test**, danach voller Lauf. Der Guard lässt nur die minimale Antwort auf den **aktuellen** Fehlschlag zu — die Steps unten sind so geschnitten (erst Literal, dann Vergabe, dann Buchstaben; erst Anrede + ein Wort, dann Titel, dann Mehrwortnamen). Return-Stubs statt `raise`-Stubs. Neue Impl-Datei erst NACH dem vollen Lauf anlegen, der den `ModuleNotFoundError` als RED registriert.
- **Volle Suite** nach jedem Test: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest -q -W error` aus `bc1-context-discovery/`. Ausgangslage 14.09.: **502 passed / 4 skipped**.
- **Platzhalterformat** `[Klasse KENNUNG]`, Klasse ∈ {Person, E-Mail, Telefon, IBAN, Adresse}, Kennung A…Z, AA, … — keine Ziffern, Kommas, Zeilenumbrüche. **Zusage präzisiert (Review M3):** alleinstehende Platzhalter und Platzhalter in Text-/Listenfeldern passieren die Normalisierer unverändert; in Zahlenfeldern gewinnt die Zahl (`ZAHL("30 pro Monat [Person A]")` → `"360"`), das ist gewollt.
- **Hinweiswort bleibt stehen, Titel und Name werden ersetzt:** „Frau Dr. med. Erika Musterfrau" → „Frau [Person A]"; „Prof. Dr. Mustermann" → „[Person A]". Kennungen folgen der **Textreihenfolge** (ein Person-Muster für Anrede und Titel; Review M1).
- **Namenswörter sind reine Buchstabenwörter** (Großbuchstabe + Kleinbuchstaben, Binnenbindestrich) — Kennungen wie `S-03`, `KP-06.TP-2` werden nie Teil eines Namens (Review I1). Hinweiswörter: Herr/Herrn/Frau/Hr./Fr./Kollege/Kollegin/„ich heiße"/„mein Name ist" — **kein** Plural „Kollegen" (nicht im Konzept; „Kollegen Sachbearbeitung Vertrieb" wäre ein Fehltreffer).
- **Adresse:** Straße/Allee/Gasse mit Hausnummer (Bereiche „12-14"), optional PLZ + Ort (ein- oder zweiteilig, nach Komma oder „in"); Weg/Platz/Ring/Damm/Ufer **nur mit PLZ + Ort** („Arbeitsplatz 3", „Datenweg 3" sind Prozessangaben; Review I3). Kein alleinstehendes PLZ + Ort (fünfstellige Mengen). Konzept ist entsprechend nachgezogen — **vor** dem Bau.
- **Telefon:** `+`/`0`-Präfix, geklammerte Vorwahl `(0)`, bis drei Trennzeichen zwischen Ziffern; nicht inmitten von Dezimalzahlen, nicht vor `:`/`.`+Ziffer; Datumsformen mit `.`, `/`, `-` bleiben (Review C1, I2). **IBAN:** Groß-/Kleinschreibung und geschützte Leerzeichen; Folgetext wird anhand der Soll-Länge je Land nicht verschluckt (Review C2). **E-Mail:** Unicode-Domains (Review C3).
- **Bekannte, akzeptierte Fehltreffer** (im Konzept): „Dr. Oetker", „Kollegin Buchhaltung", „Fr. Vormittag" → `[Person A]`; „Herrn Musters Freigabe" → beide Wörter. Übererkennung kostet Information, Untererkennung kostet Datenschutz.
- **Bestehende Tests bleiben unverändert** (kein Testskript enthält PII-Muster; Adapter-Tests vergleichen Konstanten, keine Prompt-Literale — Review, ausgeführt).
- **Keine realen Namen** — nur erfundene (Mustermann, Musterfrau, Beispiel, Muster), Domains `example.org/.com`, die dokumentierte Beispiel-IBAN `DE89 3704 0044 0532 0130 00`, erfundene Nummern.
- **Kein Push ohne OK von Richard.** Branch `bc1-b2-pii-konzept` ab `origin/bc1-db-profil-fundament` @ `f88f7d4` (Ziel `main`, sobald PR #201 gemergt ist). Kein Worktree.
- Sprache Deutsch. Commit-Stil `feat(bc1): …` / `test(bc1): …` / `docs(bc1): …` mit `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Alle Zahlen in Doku sind **gemessen**.

---

## Dateien

- Create: `bc1_core/pii.py` — Muster, Platzhaltervergabe, `ersetze_pii`
- Create: `tests/test_pii.py` — Verhalten je Muster, Vergabe, Reihenfolge, Idempotenz, Totalität
- Create: `tests/pii_testset.py` — Testset (POSITIV: eine PII-Stelle je Fall; NEGATIV)
- Create: `tests/test_pii_kpi.py` — Quote je Klasse = README-Tabelle, Fehltreffer = 0
- Modify: `bc1_core/core.py:6` (Import), `:131-135` — Filter vor `raw_log.append`
- Modify: `tests/test_core.py` — Spione für Store und LLM, Crash-Resume mit PII
- Modify: `tests/test_feldtypen.py`, `tests/test_paket_feldtypen.py` — Round-Trip der Platzhalter
- Modify: `bc1_service/prompts.py` — `PII_HINWEIS` an beide Systemprompts
- Modify: `tests/test_prompts.py` — Hinweis gepinnt
- Modify: `README.md` — Abschnitt „PII-Filter" (vor „Setup und Start")
- Modify: `design/Abschlussplan-BC1.md` — B2-Zeile, Kleinpunkte

**Interfaces (Produces):**
- `bc1_core.pii.ersetze_pii(text: str) -> str` — total, deterministisch, idempotent
- `tests.pii_testset.POSITIV: list[tuple[str, str, str]]` = (Klasse, Eingabe, Erwartet), genau eine PII-Stelle je Fall; `tests.pii_testset.NEGATIV: list[str]`
- `bc1_service.prompts.PII_HINWEIS: str`

---

## Reihenfolge

Task 0 → Task 1 (Muster-Klassen + Vergabe) → Task 2 (Namen, Reihenfolge, Idempotenz, Totalität) → Task 3 (Kern + Round-Trip) → Task 4 (Prompts) → Task 5 (Kennzahl + Doku) → Task 6 (Zweitmeinung Code) → Task 7 (Abschluss).

---

## Task 0: Plan-Commit und Basis

- [x] **Step 1:** Branch `bc1-b2-pii-konzept`, Arbeitsbaum sauber. Container `bc1-test-pg` läuft. Suite-Basis **502 passed / 4 skipped** (14.09.).
- [x] **Step 2:** Commit `docs(bc1): Implementierungsplan B2 Fassung 2 + Konzept-Nachträge nach Codex-Review`.

---

## Task 1: Muster-Klassen (E-Mail, IBAN, Telefon, Adresse) und Platzhaltervergabe

**Files:** Create `tests/test_pii.py`, Create `bc1_core/pii.py`.

**Interfaces:** Produces `ersetze_pii(text) -> str`; intern `_MUSTER`, `_Vergabe`, `_buchstabe`, `_ersatz`, `_iban_ersatz`, `_DATUM`, `_IBAN_LAENGE`.

- [x] **Step 1: Test E-Mail** (`tests/test_pii.py` anlegen)

```python
"""PII-Filter (B2): personenbezogene Angaben werden VOR dem ersten Speichern
durch Platzhalter ersetzt. Erfundene Namen/Adressen/Nummern (Repo-Konvention);
was erkannt wird und was bewusst nicht: design/Konzept-B2-PII-Filter.md."""
from bc1_core.pii import ersetze_pii


def test_email_wird_platzhalter():
    assert (ersetze_pii("Rückfragen an erika.musterfrau@example.org bitte.")
            == "Rückfragen an [E-Mail A] bitte.")
```

- [x] **Step 2:** Voller Lauf → RED (`ModuleNotFoundError`). Dann `bc1_core/pii.py` minimal:

```python
"""PII-Filter (B2): ersetzt personenbezogene Angaben durch Platzhalter, BEVOR der
Kern eine Nachricht speichert oder an einen Anbieter gibt.

Total (wirft nie), deterministisch, idempotent — nur Standardbibliothek.
Was erkannt wird, was bewusst nicht (nackte Nachnamen, Kartennummern,
Konsistenz über Turns) und warum: design/Konzept-B2-PII-Filter.md.
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[E-Mail A]"."""
    return _EMAIL.sub("[E-Mail A]", text)
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — E-Mail (B2, Task 1)`.

- [x] **Step 3: Test — zwei Adressen, zwei Kennungen; gleicher Wert gleiche Kennung** (anfügen)

```python
def test_kennungen_je_wert_gleicher_wert_gleiche_kennung():
    assert (ersetze_pii("Kontakt max@example.org, info@example.org, Max@example.org")
            == "Kontakt [E-Mail A], [E-Mail B], [E-Mail A]")
```

- [x] **Step 4:** Voller Lauf → RED. Vergabe einführen:

```python
_MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("E-Mail", re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
)


class _Vergabe:
    """Platzhalter je Klasse und Turn: gleicher Wert → gleicher Buchstabe."""

    def __init__(self) -> None:
        self._kennung: dict[tuple[str, str], str] = {}
        self._belegt: dict[str, set[str]] = {}

    def platzhalter(self, klasse: str, wert: str) -> str:
        schluessel = (klasse, " ".join(wert.split()).lower())
        if schluessel not in self._kennung:
            belegt = self._belegt.setdefault(klasse, set())
            kennung = chr(65 + len(belegt))
            belegt.add(kennung)
            self._kennung[schluessel] = f"[{klasse} {kennung}]"
        return self._kennung[schluessel]


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[E-Mail A]"."""
    vergabe = _Vergabe()
    for klasse, muster in _MUSTER:
        text = muster.sub(lambda m, k=klasse: vergabe.platzhalter(k, m.group(0)), text)
    return text
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Platzhaltervergabe je Wert (B2, Task 1)`.

- [x] **Step 5: Test — Kennungen über Z hinaus** (anfügen)

```python
def test_kennungen_laufen_ueber_z_hinaus():
    ergebnis = ersetze_pii(" ".join(f"m{i}@example.org" for i in range(27)))
    assert "[E-Mail Z]" in ergebnis
    assert ergebnis.endswith("[E-Mail AA]")
```

- [x] **Step 6:** Voller Lauf → RED (`chr(91)` = `[`). `_buchstabe` einführen, in `platzhalter` `kennung = _buchstabe(len(belegt))`:

```python
def _buchstabe(n: int) -> str:
    """0 → A, 25 → Z, 26 → AA (wie Tabellenspalten)."""
    kennung = ""
    n += 1
    while n:
        n, rest = divmod(n - 1, 26)
        kennung = chr(65 + rest) + kennung
    return kennung
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Kennungen A..Z, AA.. (B2, Task 1)`.

- [x] **Step 7: Test — IBAN in drei Schreibweisen, Folgewort bleibt** (anfügen)

```python
def test_iban_wird_platzhalter_folgewort_bleibt():
    assert (ersetze_pii("Konto DE89 3704 0044 0532 0130 00 verwenden.")
            == "Konto [IBAN A] verwenden.")
    assert ersetze_pii("de89370400440532013000") == "[IBAN A]"
    assert ersetze_pii("DE89 3704 0044 0532 0130 00") == "[IBAN A]"
    assert ersetze_pii("AT61 1904 3002 3457 3201 SAP") == "[IBAN A] SAP"
```

- [x] **Step 8:** Voller Lauf → RED. IBAN-Muster (nach E-Mail) + Längentabelle + `_ersatz`:

```python
# Soll-Länge je Land (Zeichen ohne Leerzeichen): Folgetext wird nicht verschluckt.
_IBAN_LAENGE = {"AT": 20, "BE": 16, "CH": 21, "CZ": 24, "DE": 22, "DK": 18, "ES": 24,
                "FI": 18, "FR": 27, "GB": 22, "HU": 28, "IE": 22, "IT": 27, "LI": 21,
                "LU": 20, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "SE": 24, "SK": 24}

_MUSTER = (
    ("E-Mail", ...unverändert...),
    ("IBAN", re.compile(r"\b[a-z]{2}\d{2}(?:[  ]?[a-z0-9]{4}){2,7}(?:[  ]?[a-z0-9]{1,4})?\b",
                        re.IGNORECASE)),
)


def _iban_ersatz(treffer: str, vergabe: _Vergabe) -> str:
    laenge = _IBAN_LAENGE.get(treffer[:2].upper())
    if laenge is not None:
        gezaehlt = 0
        for i, zeichen in enumerate(treffer):
            gezaehlt += not zeichen.isspace()
            if gezaehlt == laenge:
                return vergabe.platzhalter("IBAN", treffer[:i + 1]) + treffer[i + 1:]
    return vergabe.platzhalter("IBAN", treffer)   # unbekanntes Land / kürzer: ganz ersetzen


def _ersatz(klasse: str, m: re.Match[str], vergabe: _Vergabe) -> str:
    if klasse == "IBAN":
        return _iban_ersatz(m.group(0), vergabe)
    return vergabe.platzhalter(klasse, m.group(0))


def ersetze_pii(text: str) -> str:
    vergabe = _Vergabe()
    for klasse, muster in _MUSTER:
        text = muster.sub(lambda m, k=klasse: _ersatz(k, m, vergabe), text)
    return text
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — IBAN mit Soll-Länge je Land (B2, Task 1)`.

- [x] **Step 9: Test — Telefon in üblichen Schreibweisen** (anfügen)

```python
def test_telefon_wird_platzhalter():
    assert (ersetze_pii("Erreichbar unter +49 30 1234567 oder 0151 12345678.")
            == "Erreichbar unter [Telefon A] oder [Telefon B].")
    assert ersetze_pii("Büro 030/1234567 oder 030 / 1234567") == "Büro [Telefon A] oder [Telefon B]"
    assert ersetze_pii("+49 (0)30 1234567") == "[Telefon A]"
```

- [x] **Step 10:** Voller Lauf → RED. Telefon-Muster (nach IBAN):

```python
    ("Telefon", re.compile(r"(?<![\d,.])(?:\+\d{1,3}(?:[ /-]*\(0\))?|\b0)[ /-]*\d"
                           r"(?:[ /-]{0,3}\d){6,13}\b(?![:.]\d)")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Telefon (B2, Task 1)`.

- [x] **Step 11: Test — Mengen, Daten, Dezimalzahlen, Uhrzeiten bleiben** (anfügen)

```python
def test_mengen_daten_dezimalzahlen_bleiben_stehen():
    for text in ("180 Fälle pro Jahr", "3 pro Woche", "45 Minuten", "60%", "80 %",
                 "am 14.09.2026", "seit 2026-09-14", "Termin 01-02-2026",
                 "Termin 01/02/2026 09:30", "Termin am Freitag um 09:30",
                 "0,01234567 %", "12000 Rechnungen im Jahr", "Rechnung Nr. 4711"):
        assert ersetze_pii(text) == text
```

- [x] **Step 12:** Voller Lauf → RED (`01-02-2026`, `01/02/2026` treffen als Telefon). Datums-Ausnahme:

```python
_DATUM = re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}")


def _ersatz(klasse, m, vergabe):
    if klasse == "IBAN":
        return _iban_ersatz(m.group(0), vergabe)
    if klasse == "Telefon" and _DATUM.fullmatch(m.group(0)):
        return m.group(0)
    return vergabe.platzhalter(klasse, m.group(0))
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Datumsformen sind keine Telefonnummern (B2, Task 1)`.

- [x] **Step 13: Test — Adresse mit Straße** (anfügen)

```python
def test_adresse_mit_strasse_wird_platzhalter():
    assert ersetze_pii("Sitz: Musterstraße 12, 10115 Berlin.") == "Sitz: [Adresse A]."
    assert ersetze_pii("Musterstraße 12-14, 10115 Berlin") == "[Adresse A]"
    assert ersetze_pii("Musterstraße 12, 01234 Bad Beispielstadt") == "[Adresse A]"
    assert ersetze_pii("Hauptstr. 5 in 10115 Berlin") == "[Adresse A]"
    assert ersetze_pii("Karl-Marx-Straße 1") == "[Adresse A]"
```

- [x] **Step 14:** Voller Lauf → RED. Adresse-Muster (nach Telefon):

```python
_STRASSE = r"[A-ZÄÖÜ][a-zäöüß]*(?:-[A-ZÄÖÜ][a-zäöüß]*)*-?"
_HAUSNR = r"\d+[a-zA-Z]?(?:\s*[-–/]\s*\d+[a-zA-Z]?)?"
_ORT = r"[A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+)?"
_PLZ_ORT = r"(?:(?:,|\s+in)?\s+\d{5}\s+" + _ORT + r")"

    ("Adresse", re.compile(r"\b" + _STRASSE + r"(?:[Ss]traße|[Ss]trasse|[Ss]tr\.|[Aa]llee|[Gg]asse)\s+"
                           + _HAUSNR + _PLZ_ORT + r"?\b")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Adresse mit Straße, Bereich, PLZ + Ort (B2, Task 1)`.

- [x] **Step 15: Test — Weg/Platz nur mit PLZ + Ort** (anfügen)

```python
def test_weg_und_platz_nur_als_volle_adresse():
    assert ersetze_pii("Marktplatz 5, 10115 Berlin") == "[Adresse A]"
    for text in ("Der Arbeitsplatz 3 nutzt S-03.", "System Datenweg 3 verarbeitet 60%.",
                 "Büro am Marktplatz 5", "Beispielweg 3a"):
        assert ersetze_pii(text) == text
```

- [x] **Step 16:** Voller Lauf → RED. Zweites Adresse-Muster (nach dem ersten):

```python
    ("Adresse", re.compile(r"\b" + _STRASSE + r"(?:[Ww]eg|[Pp]latz|[Rr]ing|[Dd]amm|[Uu]fer)\s+"
                           + _HAUSNR + _PLZ_ORT + r"\b")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Weg/Platz nur mit PLZ + Ort (B2, Task 1)`.

---

## Task 2: Namen mit Hinweiswort, Textreihenfolge, Idempotenz, Totalität

**Files:** Modify `tests/test_pii.py`, `bc1_core/pii.py`.

- [x] **Step 1: Test — Anrede, ein Namenswort** (anfügen)

```python
def test_anrede_verraet_den_namen_hinweiswort_bleibt():
    assert (ersetze_pii("Herr Mustermann prüft die Rechnung.")
            == "Herr [Person A] prüft die Rechnung.")
    assert (ersetze_pii("mit Herrn Beispiel und Frau Musterfrau")
            == "mit Herrn [Person A] und Frau [Person B]")
    assert (ersetze_pii("Bitte an Hr. Mustermann und Fr. Musterfrau.")
            == "Bitte an Hr. [Person A] und Fr. [Person B].")
```

- [x] **Step 2:** Voller Lauf → RED. Person-Muster (ans Ende von `_MUSTER`) und `_ersatz`-Zweig:

```python
# Ein Namenswort: Großbuchstabe + Kleinbuchstaben, Binnenbindestrich erlaubt
# ("Müller-Lüdenscheid"); keine Ziffern — sonst frisst das Muster S-03/KP-06.
_WORT = r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)*"
_ANREDE = r"(?:Herrn?|Frau|Hr\.|Fr\.|Kolleg(?:e|in)|[Ii]ch heiße|[Mm]ein Name ist)"

    # Hinweiswort bleibt stehen (Gruppe "hinweis"), der Name wird ersetzt.
    ("Person", re.compile(r"(?P<hinweis>\b" + _ANREDE + r"\s+)(?P<name>" + _WORT + r")")),


def _ersatz(klasse, m, vergabe):
    if klasse == "Person":
        return m.group("hinweis") + vergabe.platzhalter(klasse, m.group("name"))
    if klasse == "IBAN":
        ...
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Namen hinter Anrede (B2, Task 2)`.

- [x] **Step 3: Test — Titel und bis zu drei Namensteile, ein Platzhalter** (anfügen)

```python
def test_titel_und_mehrteilige_namen_werden_ein_platzhalter():
    assert ersetze_pii("Frau Dr. Erika Musterfrau leitet das.") == "Frau [Person A] leitet das."
    assert ersetze_pii("Frau Dr. med. Muster prüft") == "Frau [Person A] prüft"
    assert ersetze_pii("Kollegin Anna Maria Muster übernimmt.") == "Kollegin [Person A] übernimmt."
    assert ersetze_pii("Herr Müller-Lüdenscheid kommt.") == "Herr [Person A] kommt."
```

- [x] **Step 4:** Voller Lauf → RED. Titel und Mehrwortnamen in die Namensgruppe:

```python
_TITEL = r"(?:(?:Dr|Prof)\.\s+(?:(?:med|jur|phil|ing|rer\.\s?nat|h\.\s?c)\.\s+)?)"

    ("Person", re.compile(r"(?P<hinweis>\b" + _ANREDE + r"\s+)"
                          r"(?P<name>" + _TITEL + r"*" + _WORT + r"(?:\s+" + _WORT + r"){0,2})")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Titel und mehrteilige Namen (B2, Task 2)`.

- [x] **Step 5: Test — Titel ohne Anrede, Kennungen in Textreihenfolge** (anfügen)

```python
def test_titel_ohne_anrede_und_kennungen_in_textreihenfolge():
    assert ersetze_pii("Prof. Dr. Mustermann entscheidet.") == "[Person A] entscheidet."
    assert (ersetze_pii("Dr. Muster prüft und Frau Beispiel genehmigt.")
            == "[Person A] prüft und Frau [Person B] genehmigt.")
```

- [x] **Step 6:** Voller Lauf → RED. Hinweis-Gruppe um den Titel-Einstieg erweitern (EIN Muster, links nach rechts):

```python
    ("Person", re.compile(r"(?P<hinweis>\b" + _ANREDE + r"\s+|\b(?=(?:Dr|Prof)\.\s))"
                          r"(?P<name>" + _TITEL + r"*" + _WORT + r"(?:\s+" + _WORT + r"){0,2})")),
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Titel ohne Anrede, Kennungen in Textreihenfolge (B2, Task 2)`.

- [x] **Step 7: Test — Selbstvorstellung, Kollege, Kennungen neben Namen** (anfügen)

```python
def test_selbstvorstellung_kollege_und_kennungen_neben_namen():
    assert ersetze_pii("Mein Name ist Max Mustermann.") == "Mein Name ist [Person A]."
    assert ersetze_pii("Ich heiße Erika Musterfrau.") == "Ich heiße [Person A]."
    assert ersetze_pii("Kollege Muster übernimmt.") == "Kollege [Person A] übernimmt."
    assert ersetze_pii("Frau Muster S-03 prüft.") == "Frau [Person A] S-03 prüft."
    assert ersetze_pii("Frau Muster KP-06.TP-2 prüft.") == "Frau [Person A] KP-06.TP-2 prüft."
```

Voller Lauf → GREEN bei Ankunft (Buchstabenwörter). Weiter.

- [x] **Step 8: Test — kein Treffer ohne Hinweiswort, bei kleingeschriebenem Folgewort, beim Plural** (anfügen)

```python
def test_kein_treffer_ohne_hinweiswort_und_bei_kleingeschriebenem_folgewort():
    for text in ("Mustermann prüft das.", "die Frau des Kunden ruft an",
                 "Kollegen aus dem Vertrieb", "Kollegen Sachbearbeitung Vertrieb prüfen.",
                 "ich bin Sachbearbeiter", "Herr der Lage",
                 "Anfrage eines Kollegen oder Kunden"):
        assert ersetze_pii(text) == text
```

Voller Lauf → GREEN bei Ankunft. Commit `test(bc1): PII-Filter — Selbstvorstellung, Kennungen neben Namen, Negativfälle (B2, Task 2)`.

- [x] **Step 9: Test — vorhandene Platzhalter bleiben, Kennungen kollidieren nicht** (anfügen)

```python
def test_vorhandene_platzhalter_bleiben_und_kollidieren_nicht():
    assert ersetze_pii("Frau [Person A] und Herr Muster") == "Frau [Person A] und Herr [Person B]"
```

- [x] **Step 10:** Voller Lauf → RED (`[Person A]` doppelt). Kennungen vorhandener Platzhalter vorab belegen — **keine** Segmentierung (kein Muster trifft den Wortlaut eines Platzhalters; Review-Guard-Hinweis):

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
        schluessel = (klasse, " ".join(wert.split()).lower())
        if schluessel not in self._kennung:
            belegt = self._belegt.setdefault(klasse, set())
            n = 0
            while _buchstabe(n) in belegt:
                n += 1
            belegt.add(_buchstabe(n))
            self._kennung[schluessel] = f"[{klasse} {_buchstabe(n)}]"
        return self._kennung[schluessel]
```

und in `ersetze_pii`: `vergabe = _Vergabe(text)`. Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter — Kennungen vorhandener Platzhalter bleiben belegt (B2, Task 2)`.

- [x] **Step 11: Test — idempotent und deterministisch** (anfügen)

```python
def test_idempotent_und_deterministisch():
    text = "Herr Muster (muster@example.org, 0151 12345678), Musterstraße 1"
    einmal = ersetze_pii(text)
    assert einmal == "Herr [Person A] ([E-Mail A], [Telefon A]), [Adresse A]"
    assert ersetze_pii(einmal) == einmal
    assert ersetze_pii(text) == einmal
```

Voller Lauf → GREEN bei Ankunft. Weiter.

- [x] **Step 12: Test — leer und beliebiger Text ohne Ausnahme** (anfügen)

```python
def test_leer_und_beliebiger_text_ohne_ausnahme():
    assert ersetze_pii("") == ""
    for text in ("[", "]]", "@", "+", "Dr.", "Herr ", "\n\t", "S-03, S-04",
                 "0" * 40, "[Person ]", "[Person A", "DE00"):
        assert isinstance(ersetze_pii(text), str)   # darf nie werfen
```

Voller Lauf → GREEN bei Ankunft. Commit `test(bc1): PII-Filter — Idempotenz, Determinismus, Totalität (B2, Task 2)`.

- [x] **Step 13: Zielform prüfen.** `bc1_core/pii.py` muss jetzt genau dies sein (Reihenfolge `_MUSTER`: E-Mail, IBAN, Telefon, Adresse/Straße, Adresse/Weg, Person) — gegen diese Fassung wurden **alle** Erwartungen aus Task 1–2 und dem Testset am 14.09. als Wegwerf-Skript gemessen (0 Abweichungen):

```python
"""PII-Filter (B2): ersetzt personenbezogene Angaben durch Platzhalter, BEVOR der
Kern eine Nachricht speichert oder an einen Anbieter gibt.

Total (wirft nie), deterministisch, idempotent — nur Standardbibliothek.
Was erkannt wird, was bewusst nicht (nackte Nachnamen, Kartennummern,
Konsistenz über Turns) und warum: design/Konzept-B2-PII-Filter.md.
"""
from __future__ import annotations

import re

# Ein Namenswort: Großbuchstabe + Kleinbuchstaben, Binnenbindestrich erlaubt
# ("Müller-Lüdenscheid"); keine Ziffern — sonst frisst das Muster S-03/KP-06.
_WORT = r"[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)*"
_TITEL = r"(?:(?:Dr|Prof)\.\s+(?:(?:med|jur|phil|ing|rer\.\s?nat|h\.\s?c)\.\s+)?)"
_ANREDE = r"(?:Herrn?|Frau|Hr\.|Fr\.|Kolleg(?:e|in)|[Ii]ch heiße|[Mm]ein Name ist)"
_STRASSE = r"[A-ZÄÖÜ][a-zäöüß]*(?:-[A-ZÄÖÜ][a-zäöüß]*)*-?"
_HAUSNR = r"\d+[a-zA-Z]?(?:\s*[-–/]\s*\d+[a-zA-Z]?)?"
_ORT = r"[A-ZÄÖÜ][a-zäöüß-]+(?:\s+[A-ZÄÖÜ][a-zäöüß-]+)?"
_PLZ_ORT = r"(?:(?:,|\s+in)?\s+\d{5}\s+" + _ORT + r")"

# Reihenfolge = Anwendungsreihenfolge: spezifisch vor allgemein (IBAN vor Telefon).
_MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("E-Mail", re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
    ("IBAN", re.compile(r"\b[a-z]{2}\d{2}(?:[  ]?[a-z0-9]{4}){2,7}(?:[  ]?[a-z0-9]{1,4})?\b",
                        re.IGNORECASE)),
    ("Telefon", re.compile(r"(?<![\d,.])(?:\+\d{1,3}(?:[ /-]*\(0\))?|\b0)[ /-]*\d"
                           r"(?:[ /-]{0,3}\d){6,13}\b(?![:.]\d)")),
    # Straße/Allee/Gasse mit Hausnummer, optional PLZ + Ort; Weg/Platz/Ring/
    # Damm/Ufer NUR mit PLZ + Ort ("Arbeitsplatz 3" ist keine Adresse).
    ("Adresse", re.compile(r"\b" + _STRASSE + r"(?:[Ss]traße|[Ss]trasse|[Ss]tr\.|[Aa]llee|[Gg]asse)\s+"
                           + _HAUSNR + _PLZ_ORT + r"?\b")),
    ("Adresse", re.compile(r"\b" + _STRASSE + r"(?:[Ww]eg|[Pp]latz|[Rr]ing|[Dd]amm|[Uu]fer)\s+"
                           + _HAUSNR + _PLZ_ORT + r"\b")),
    # Hinweiswort bleibt stehen (Gruppe "hinweis"), Titel + Name werden ersetzt.
    # EIN Muster für Anrede und Titel, damit die Kennungen der Textreihenfolge folgen.
    ("Person", re.compile(r"(?P<hinweis>\b" + _ANREDE + r"\s+|\b(?=(?:Dr|Prof)\.\s))"
                          r"(?P<name>" + _TITEL + r"*" + _WORT + r"(?:\s+" + _WORT + r"){0,2})")),
)
_DATUM = re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}-\d{2}-\d{2}")
_PLATZHALTER = re.compile(
    r"\[(?P<klasse>Person|E-Mail|Telefon|IBAN|Adresse) (?P<kennung>[A-Z]+)\]")
# Soll-Länge je Land (Zeichen ohne Leerzeichen): Folgetext wird nicht verschluckt.
_IBAN_LAENGE = {"AT": 20, "BE": 16, "CH": 21, "CZ": 24, "DE": 22, "DK": 18, "ES": 24,
                "FI": 18, "FR": 27, "GB": 22, "HU": 28, "IE": 22, "IT": 27, "LI": 21,
                "LU": 20, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "SE": 24, "SK": 24}


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


def _iban_ersatz(treffer: str, vergabe: _Vergabe) -> str:
    laenge = _IBAN_LAENGE.get(treffer[:2].upper())
    if laenge is not None:
        gezaehlt = 0
        for i, zeichen in enumerate(treffer):
            gezaehlt += not zeichen.isspace()
            if gezaehlt == laenge:
                return vergabe.platzhalter("IBAN", treffer[:i + 1]) + treffer[i + 1:]
    return vergabe.platzhalter("IBAN", treffer)   # unbekanntes Land / kürzer: ganz ersetzen


def _ersatz(klasse: str, m: re.Match[str], vergabe: _Vergabe) -> str:
    if klasse == "Person":
        return m.group("hinweis") + vergabe.platzhalter(klasse, m.group("name"))
    if klasse == "IBAN":
        return _iban_ersatz(m.group(0), vergabe)
    if klasse == "Telefon" and _DATUM.fullmatch(m.group(0)):
        return m.group(0)
    return vergabe.platzhalter(klasse, m.group(0))


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[Person A]".

    Total, deterministisch, idempotent: vorhandene Platzhalter bleiben stehen
    (kein Muster trifft ihren Wortlaut, ihre Kennungen werden nicht neu vergeben).
    """
    vergabe = _Vergabe(text)
    for klasse, muster in _MUSTER:
        text = muster.sub(lambda m, k=klasse: _ersatz(k, m, vergabe), text)
    return text
```

---

## Task 3: Einhängung im Kern (mit Spionen) und Round-Trip durch die Feldtypen

**Files:** Modify `bc1_core/core.py`, `tests/test_core.py` (nutzt vorhandene `_turn`, `CrashtBeimZweitenSave`, `InMemoryStateStore`, `FakeLLM`, `ExtractionCandidate`, `TOY_PROZESS`), `tests/test_feldtypen.py`, `tests/test_paket_feldtypen.py`.

- [x] **Step 1: Spione + Integrationstest** (`tests/test_core.py`, anfügen — Helferklassen sind kein Test, der EINE neue Test ist die Funktion)

```python
class _ProtokollStore(InMemoryStateStore):
    """Zeichnet bei JEDEM save den raw_log auf — beweist, dass nie Klartext gespeichert wird."""
    def __init__(self):
        super().__init__()
        self.gespeicherte_logs = []

    def save(self, state):
        self.gespeicherte_logs.append(list(state.raw_log))
        super().save(state)


class _ProtokollLLM(FakeLLM):
    """Zeichnet auf, was BEIDE Anbieter-Eingänge zu sehen bekommen."""
    def __init__(self, extractions=None):
        super().__init__(extractions)
        self.extract_texte = []
        self.antwort_texte = []

    def extract(self, message, package, state):
        self.extract_texte.append(message)
        return super().extract(message, package, state)

    def antworte(self, kontext):
        self.antwort_texte.append(kontext.nutzer_nachricht)
        return super().antworte(kontext)


def test_pii_wird_vor_dem_ersten_save_ersetzt_und_beide_llm_eingaenge_sehen_nur_platzhalter():
    store = _ProtokollStore()
    gefiltert = "Frau [Person A] startet den Prozess, Rückfragen an [E-Mail A]."
    llm = _ProtokollLLM({gefiltert: [ExtractionCandidate("prozess_name", "Freigabe")]})
    roh = "Frau Musterfrau startet den Prozess, Rückfragen an erika@example.org."
    _turn(store, llm, TOY_PROZESS, "s1", "msg-1", roh)
    assert store.gespeicherte_logs                       # mindestens ein save
    assert all(log == [("msg-1", gefiltert)] for log in store.gespeicherte_logs)
    assert llm.extract_texte == [gefiltert]
    assert llm.antwort_texte == [gefiltert]
    assert store.load("s1").values["prozess_name"].value == "Freigabe"
```

- [x] **Step 2:** Voller Lauf → RED. `bc1_core/core.py`: Import `from bc1_core.pii import ersetze_pii` (nach `from bc1_core.llm import LLMClient`), und im `else`-Zweig:

```python
    else:
        # PII-Filter VOR dem ersten Speichern (B2): ab hier existiert kein
        # Original mehr — weder in raw_log noch beim Anbieter. Der
        # Crash-Resume-Pfad oben liest raw_log, also den gefilterten Text
        # (gilt für Turns, die unter B2 geloggt wurden).
        message = ersetze_pii(message)
        # Rohnachricht zuerst sichern (vor jedem LLM-Aufruf).
        state.raw_log.append((message_id, message))
        state.processed_message_ids.add(message_id)
        store.save(state)
```

Voller Lauf → GREEN. Commit `feat(bc1): PII-Filter im Kern vor dem ersten Speichern (B2, Task 3)`.

- [x] **Step 3: Crash-Resume mit PII und abweichendem Retry-Body** (anfügen)

```python
def test_crash_resume_spielt_den_gefilterten_logtext_ab_nicht_den_retry_body():
    store = CrashtBeimZweitenSave()
    gefiltert = "Herr [Person A] startet."
    llm = _ProtokollLLM({gefiltert: [ExtractionCandidate("prozess_name", "Freigabe")]})
    _turn(store, llm, TOY_PROZESS, "s1", "m1", "eins")
    store.scharf = True
    try:
        _turn(store, llm, TOY_PROZESS, "s1", "m2", "Herr Muster startet.")
    except RuntimeError:
        pass                                    # m2 geloggt, unbeantwortet
    store.scharf = False
    _turn(store, llm, TOY_PROZESS, "s1", "m2", "Herr Beispiel startet.")   # anderer Body
    assert store.load("s1").raw_log == [("m1", "eins"), ("m2", gefiltert)]
    assert llm.extract_texte[-1] == gefiltert
    assert "Muster" not in "".join(llm.extract_texte + llm.antwort_texte)
    assert "Beispiel" not in "".join(llm.extract_texte + llm.antwort_texte)
```

Voller Lauf → GREEN bei Ankunft (Replay-Pfad liest `raw_log`). Commit `test(bc1): Crash-Resume spielt gefilterten Logtext ab (B2, Task 3)`.

- [x] **Step 4: Round-Trip Feldtypen** (`tests/test_feldtypen.py`, anfügen)

```python
def test_pii_platzhalter_passieren_text_und_listenfelder_unveraendert():
    assert FREITEXT.normalisiere("[Person A]") == "[Person A]"
    assert LISTE.normalisiere("[Person A], [Person B]") == "[Person A], [Person B]"
    assert ZAHL.normalisiere("[Telefon A]") == "[Telefon A]"
    assert JA_NEIN.normalisiere("[Person A]") == "[Person A]"
    # In Zahlenfeldern gewinnt die Zahl — gewollt (Konzept T3, Review M3).
    assert ZAHL.normalisiere("30 pro Monat [Person A]") == "360"
```

Voller Lauf → GREEN bei Ankunft. Weiter.

- [x] **Step 5: Round-Trip Systemfeld** (`tests/test_paket_feldtypen.py`, anfügen)

```python
def test_pii_platzhalter_bleibt_im_systemfeld_stehen():
    typ = baue_system_typ(frozenset({"S-01"}))
    assert typ.normalisiere("S-01, [Person A]") == "S-01, [Person A]"
    # Freitext ohne S-NN-Kennung ist im Systemfeld erlaubt (Review I5) — die
    # Bewertung "Platzhalter als Wert" ist im Konzept ausdrücklich vertagt.
    assert typ.validator("[Person A]") is True
```

Voller Lauf → GREEN bei Ankunft. Commit `test(bc1): PII-Platzhalter passieren Feldtypen und Systemfeld (B2, Task 3)`.

---

## Task 4: Prompts erklären die Platzhalter

**Files:** Modify `bc1_service/prompts.py:31-49`, `tests/test_prompts.py`.

- [x] **Step 1: Test** (anfügen)

```python
def test_system_prompts_erklaeren_die_pii_platzhalter():
    # B2: der Anbieter sieht nur Platzhalter — wörtlich übernehmen, nie auflösen, nie raten.
    for prompt in (SYSTEM_EXTRAKTION, SYSTEM_GESPRAECH):
        assert "[Person A]" in prompt
        assert "wörtlich" in prompt
        assert "nie auf" in prompt
```

- [x] **Step 2:** Voller Lauf → RED. `bc1_service/prompts.py`:

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
    ...bestehender Wortlaut unverändert bis "Sätze, OHNE Frage."
) + PII_HINWEIS
```

Voller Lauf → GREEN (Adapter-Tests vergleichen gegen die Konstanten — Review, ausgeführt). Commit `feat(bc1): Systemprompts erklären die PII-Platzhalter (B2, Task 4)`.

---

## Task 5: Kennzahl `pii_erkennung`, README, Abschlussplan

**Files:** Create `tests/pii_testset.py`, `tests/test_pii_kpi.py`; Modify `README.md`, `design/Abschlussplan-BC1.md`.

- [x] **Step 1: Testset** (`tests/pii_testset.py` — Daten, kein Test; **genau eine PII-Stelle je POSITIV-Fall**, damit die Quote PII-Stellen zählt, Review I6)

```python
"""Testset für die Kennzahl pii_erkennung (Issue #50).

POSITIV: (Klasse, Eingabe, Erwartet) mit GENAU EINER PII-Stelle je Fall — die
Quote je Klasse = erkannte Stellen / vorhandene Stellen. Erfundene Namen,
Beispiel-Domains, die dokumentierte Beispiel-IBAN, erfundene Nummern. Die Klasse
"Name ohne Hinweiswort" ist die dokumentierte Lücke aus dem Konzept (heute 0 %);
ändert sich ihre Quote, muss die README-Tabelle mit.
NEGATIV: Interviewsätze ohne PII (alle Skript-Sätze der Demo-Durchläufe +
Grenzfälle), müssen unverändert bleiben (Fehltreffer = 0)."""
POSITIV = [
    ("E-Mail", "Rückfragen an erika.musterfrau@example.org.", "Rückfragen an [E-Mail A]."),
    ("E-Mail", "Sammelpostfach: rechnungen@example.com", "Sammelpostfach: [E-Mail A]"),
    ("E-Mail", "Kontakt max+test@sub.example.org bitte", "Kontakt [E-Mail A] bitte"),
    ("E-Mail", "Postfach muster@büro.example.org", "Postfach [E-Mail A]"),
    ("Telefon", "Erreichbar unter +49 30 1234567.", "Erreichbar unter [Telefon A]."),
    ("Telefon", "Handy 0151 12345678", "Handy [Telefon A]"),
    ("Telefon", "Büro 030 / 1234567", "Büro [Telefon A]"),
    ("Telefon", "Zentrale +49 (0)30 1234567", "Zentrale [Telefon A]"),
    ("Telefon", "Tel. +43 1 234 56 78", "Tel. [Telefon A]"),
    ("IBAN", "Überweisung auf DE89 3704 0044 0532 0130 00.", "Überweisung auf [IBAN A]."),
    ("IBAN", "IBAN de89370400440532013000 ohne Leerzeichen", "IBAN [IBAN A] ohne Leerzeichen"),
    ("IBAN", "Konto AT61 1904 3002 3457 3201 SAP", "Konto [IBAN A] SAP"),
    ("Adresse", "Lieferung an Musterstraße 12, 10115 Berlin.", "Lieferung an [Adresse A]."),
    ("Adresse", "Sitz Musterstraße 12-14, 01234 Bad Beispielstadt", "Sitz [Adresse A]"),
    ("Adresse", "Hauptstr. 5 in 10115 Berlin", "[Adresse A]"),
    ("Adresse", "Karl-Marx-Straße 1", "[Adresse A]"),
    ("Adresse", "Marktplatz 5, 10115 Berlin", "[Adresse A]"),
    ("Name mit Hinweiswort", "Herr Mustermann prüft die Rechnung.", "Herr [Person A] prüft die Rechnung."),
    ("Name mit Hinweiswort", "Frau Dr. Erika Musterfrau gibt frei.", "Frau [Person A] gibt frei."),
    ("Name mit Hinweiswort", "Frau Dr. med. Muster prüft.", "Frau [Person A] prüft."),
    ("Name mit Hinweiswort", "Kollegin Musterfrau übernimmt.", "Kollegin [Person A] übernimmt."),
    ("Name mit Hinweiswort", "Kollege Mustermann prüft.", "Kollege [Person A] prüft."),
    ("Name mit Hinweiswort", "Mein Name ist Max Mustermann.", "Mein Name ist [Person A]."),
    ("Name mit Hinweiswort", "Ich heiße Erika Musterfrau.", "Ich heiße [Person A]."),
    ("Name mit Hinweiswort", "Prof. Dr. Mustermann entscheidet.", "[Person A] entscheidet."),
    ("Name mit Hinweiswort", "Bitte an Hr. Mustermann.", "Bitte an Hr. [Person A]."),
    ("Name mit Hinweiswort", "Bitte an Fr. Musterfrau.", "Bitte an Fr. [Person A]."),
    ("Name mit Hinweiswort", "Herr Müller-Lüdenscheid kommt.", "Herr [Person A] kommt."),
    ("Name mit Hinweiswort", "Frau Muster S-03 prüft.", "Frau [Person A] S-03 prüft."),
    ("Name ohne Hinweiswort", "Mustermann prüft das.", "[Person A] prüft das."),
    ("Name ohne Hinweiswort", "Das macht Erika Musterfrau.", "Das macht [Person A]."),
    ("Name ohne Hinweiswort", "Freigabe durch Mustermann.", "Freigabe durch [Person A]."),
]

NEGATIV = [
    # Alle Skript-Sätze der drei Demo-Durchläufe (test_demo_durchlaeufe.py)
    "Wir wollen die Reisebuchung automatisieren — es geht um den ganzen Prozess, Ziel ist Zeit sparen.",
    "Wir wollen Antworten aus unserer Wissensbasis automatisieren — es geht um den ganzen Prozess, Ziel ist Zeit sparen.",
    "Wir wollen das Consultant-Staffing beschleunigen — es geht um den ganzen Prozess, Ziel ist Zeit sparen.",
    "Verantwortlich und Ablauf.", "Auslöser, Eingang und Ergebnis.", "Mengen und Dauer.",
    "Der anstrengendste Schritt.", "Beteiligte und Systeme.", "Voraussetzungen.",
    # Werte der Demo-Durchläufe
    "Office Management, Mitarbeiter", "Mail, Buchungsportal, Excel", "Fachexperten, Support",
    "Sharepoint, Mail, Wiki", "Staffing, Vertrieb", "CRM, Skill-Datenbank, Excel",
    "Mitarbeiter plant eine Dienstreise", "Anfrage eines Kollegen oder Kunden",
    "Kundenanfrage nach einem Consultant",
    "Anfrage erfassen, Profile suchen, Matching, Vorschlag versenden",
    "30 pro Monat", "20 pro Woche", "300 pro Jahr", "3 Stunden", "45 Minuten", "60%", "80 %",
    # Grenzfälle: Mengen, Daten, Kennungen, Rollen, Prozessangaben, kleingeschriebene Folgewörter
    "180 Fälle pro Jahr", "12000 Rechnungen im Jahr", "Rechnung Nr. 4711 vom 14.09.2026",
    "seit 2026-09-14", "Termin 01-02-2026", "Termin 01/02/2026 09:30", "Termin am Freitag um 09:30",
    "0,01234567 %", "S-03, S-04", "KP-06.TP-2", "Frau des Kunden ruft an", "Kollegen aus dem Vertrieb",
    "Kollegen Sachbearbeitung Vertrieb prüfen.", "ich bin Sachbearbeiter in der Buchhaltung",
    "Herr der Lage", "Der Arbeitsplatz 3 nutzt S-03.", "System Datenweg 3 verarbeitet 60%.",
    "Büro am Marktplatz 5", "Arbeitsschritt 3 dauert 20 Minuten",
]
```

- [x] **Step 2: KPI-Test — Quote je Klasse gegen die README-Tabelle** (`tests/test_pii_kpi.py`, EIN Test)

```python
"""Kennzahl pii_erkennung (Issue #50): Quote je Klasse auf dem Testset — gemessen,
und gegen die README-Tabelle „PII-Filter" gehalten: weicht eine Quote ab, muss
das README mit (auch nach oben — die Lücke darf kleiner werden)."""
import re
from collections import defaultdict
from pathlib import Path

from bc1_core.pii import ersetze_pii
from tests.pii_testset import NEGATIV, POSITIV

README = Path(__file__).resolve().parent.parent / "README.md"


def _quoten_gemessen() -> dict[str, int]:
    treffer: dict[str, int] = defaultdict(int)
    gesamt: dict[str, int] = defaultdict(int)
    for klasse, eingabe, erwartet in POSITIV:
        gesamt[klasse] += 1
        treffer[klasse] += ersetze_pii(eingabe) == erwartet
    return {klasse: round(100 * treffer[klasse] / gesamt[klasse]) for klasse in gesamt}


def _quoten_readme() -> dict[str, int]:
    abschnitt = README.read_text(encoding="utf-8").split("## PII-Filter", 1)[1].split("\n## ", 1)[0]
    zeilen = re.findall(r"^\| ([^|]+?) \|.*\| (\d+) % \|$", abschnitt, flags=re.M)
    return {klasse: int(prozent) for klasse, prozent in zeilen}


def test_quote_je_klasse_entspricht_der_readme_tabelle():
    assert _quoten_gemessen() == _quoten_readme()
```

- [x] **Step 3:** Voller Lauf → RED (README-Abschnitt fehlt). README-Abschnitt vor `## Setup und Start` einfügen (Prozentwerte = Messung; erwartet 100/100/100/100/100/0):

```markdown
## PII-Filter

Jede Nachricht wird im Kern gefiltert, **bevor** sie gespeichert oder an einen
LLM-Anbieter gegeben wird (`bc1_core/pii.py`, Einhängung in `process_turn`).
Ein Original gibt es danach nicht — weder in `bc1.sessions` noch im Profil.
Strategie: **maskieren**, kein Mapping-Tresor (kein Konsument für eine Rückersetzung).

| Klasse | Erkennung | Platzhalter | Quote Testset |
|---|---|---|---|
| E-Mail | Muster, auch Unicode-Domains | `[E-Mail A]` | 100 % |
| Telefon | Muster: `+`/`0`-Präfix, `(0)`, 7–14 Ziffern, Trenner; Datums-, Uhrzeit- und Dezimalformen ausgenommen | `[Telefon A]` | 100 % |
| IBAN | Muster, Groß-/Kleinschreibung, Soll-Länge je Land | `[IBAN A]` | 100 % |
| Adresse | Straße/Allee/Gasse mit Hausnummer, optional PLZ + Ort; Weg/Platz nur mit PLZ + Ort | `[Adresse A]` | 100 % |
| Name mit Hinweiswort | Anrede (Herr/Herrn/Frau/Hr./Fr.), Titel (Dr./Prof., auch „Dr. med."), Kollege/Kollegin, „ich heiße", „mein Name ist"; Hinweiswort bleibt stehen | `[Person A]` | 100 % |
| Name ohne Hinweiswort | **nicht erkannt** (dokumentierte Lücke, braucht NER) | — | 0 % |

Quote = erkannte PII-Stellen / vorhandene Stellen im Testset (`tests/pii_testset.py`,
eine Stelle je Fall); `tests/test_pii_kpi.py` hält diese Tabelle gegen die Messung.
Fehltreffer auf den PII-freien Interviewsätzen des Testsets: 0. Kennungen laufen
je Klasse und Turn (A, B, …, AA) in Textreihenfolge; gleicher Wert im selben Turn
→ gleicher Platzhalter; über Turns hinweg keine Konsistenz.

Bekannte Grenzen: nackte Nachnamen („Mustermann prüft"), „ich bin X", Kartennummern,
Straßen ohne Straßenwort („Am Alten Markt 3"). Übererkennung ist akzeptiert („Dr. Oetker",
„Fr. Vormittag" werden `[Person A]`). NER folgt erst bei gemessenem Bedarf. Außerhalb
von BC1: n8n speichert Ausführungsdaten mit der Chat-Eingabe, bevor der Dienst sie
sieht — Hosting-Thema (B3). Konzept: `design/Konzept-B2-PII-Filter.md`.
```

Voller Lauf → GREEN. Dann zweiten Test anfügen:

```python
def test_keine_fehltreffer_auf_pii_freien_interviewsaetzen():
    fehltreffer = [satz for satz in NEGATIV if ersetze_pii(satz) != satz]
    assert fehltreffer == []
```

Voller Lauf → GREEN. Commit `test(bc1): Kennzahl pii_erkennung gegen README-Tabelle, null Fehltreffer (B2, Task 5)` (README im selben Commit).

- [x] **Step 4: Abschlussplan** — B2-Zeile: Stand „GEBAUT (Konzept + Plan Fassung 2): Filter im Kern vor dem ersten Speichern, Muster + Hinweiswörter, Kennzahl gegen README-Tabelle; keine Namensliste aus BC0 (ADR-004 R5); Zweitmeinung Codex vor dem Bau (Plan) und nach dem Bau (Code)"; nächster Schritt „PR; BC0 informieren; dann B7-Logging". Kleinpunkte: NER-Auslöser; „Platzhalter als Wert = ungültig" (C2-Nähe); n8n-Ausführungsdaten (B3); Straßen ohne Straßenwort. Commit `docs(bc1): Abschlussplan — B2 gebaut (B2, Task 5)`.

---

## Task 6: Zweitmeinung (Code)

Zweitmeinung 1 (Plan, Codex, 14.09.) ist erledigt — Adjudikation unten. Zweitmeinung 2 nach dem Bau: `codex:codex-rescue` über `git diff origin/bc1-db-profil-fundament...HEAD` mit Auftrag „Abweichungen Bau vs. Plan Fassung 2, Restlücken der Muster, Testabdeckung, Guard-Spuren (Code ohne Test)". Codex hat keinen Container — Befunde per rotem Test nachmessen.

- [x] **Step 1:** Review anstoßen; Befunde unter „Adjudikation Zweitmeinung 2" eintragen.
- [x] **Step 2:** Critical/Important fixen (Test zuerst); Minor begründet fixen oder mit Ziel in den Abschlussplan.
- [x] **Step 3:** Voller Lauf, Zahl notieren.

---

## Task 7: Abschluss

- [ ] **Step 1:** Volle Suite final messen, Zahl im Abschlussplan eintragen.
- [x] **Step 2:** Vertraulichkeits-Check: `git diff --name-only origin/bc1-db-profil-fundament...HEAD` → `git grep -n -i -E "passw|secret|supabase\.co|@gmail|sk-ant|AIza" -- <Dateien>` → nur Beispiel-Domains/Testwerte. Befund Richard vorlegen; **Push nur nach OK**.
- [x] **Step 3:** PR: Ziel `main`, falls PR #201 gemergt ist, sonst `bc1-db-profil-fundament`. PR-Text: Big Picture, Prüfung (Suite, Kennzahl), Abweichung von #50 (kein Mapping-Tresor), Zweitmeinungen.
- [x] **Step 4:** Kommentar in Issue #50 (öffentlich, nach OK): Stand, Kennzahl, Abweichung, Lücken mit Auslöser.
- [ ] **Step 5 (Richard):** BC0 informieren über den bestehenden Kanal zu BC0: BC1 liest keine Personennamen; das direkte SELECT-Recht von `bc1_role` auf `prozess_personen` ist für BC1 unnötig.
- [ ] **Step 6:** `SESSION-HANDOFF.md` (lokal): B2-Stand, nächstes Paket B7.

---

## Adjudikation Zweitmeinung 1 (Codex, Plan-Review 14.09.2026)

Codex hat die Zielform aus Fassung 1 im Arbeitsspeicher ausgeführt (kein Container, kein Guard). Jeder Befund wurde hier mit einem eigenen Wegwerf-Skript nachgemessen; die korrigierte Zielform (Task 2, Step 13) besteht alle Regressionsfälle (0 Abweichungen).

| Nr. | Schwere | Befund | Entscheidung | Nachweis |
|---|---|---|---|---|
| C1 | Critical | Telefon mit `(0)` oder „ / " bleibt Klartext | **Gefixt:** geklammerte Vorwahl, bis 3 Trennzeichen | Task 1 Step 9 |
| C2 | Critical | IBAN klein geschrieben / geschützte Leerzeichen bleiben; Folgewort „SAP" verschluckt | **Gefixt:** `IGNORECASE`, ` `, Soll-Länge je Land | Task 1 Step 7 |
| C3 | Critical | E-Mail mit Umlaut-Domain bleibt | **Gefixt:** `\w` (Unicode) | Task 5 Testset |
| I1 | Important | Namensmuster frisst `S-03`/`KP-06`, Plural „Kollegen" frisst Rollen | **Gefixt:** Buchstabenwörter, kein Plural | Task 2 Step 7/8 |
| I2 | Important | Datums-Ausnahme greift nicht bei `01/02/2026 09:30`, `01-02-2026`, Dezimalzahlen | **Gefixt:** Lookbehind/-ahead, `-` im Datum | Task 1 Step 11/12 |
| I3 | Important | „Arbeitsplatz 3", „Datenweg 3" werden Adressen; Bereiche/zweiteilige Orte teilweise | **Gefixt:** Weg/Platz nur mit PLZ + Ort; Bereiche; Ort zweiteilig; „in" | Task 1 Step 13–16; bewusst kein Treffer mehr für „Marktplatz 5" allein |
| I4 | Important | Integrationstest beweist weder jeden save noch beide LLM-Eingänge | **Gefixt:** Spione, Crash-Resume mit abweichendem Body | Task 3 Step 1/3 |
| I5 | Important | `validator("[Person A]") is False` ist falsch (Freitext erlaubt) | **Gefixt:** Erwartung `True`, Test umbenannt | Task 3 Step 5 |
| I6 | Important | KPI zählt Sätze statt Stellen; README nicht wirklich gehalten; zwei Demo-Sätze fehlen | **Gefixt:** eine Stelle je Fall, Test liest README-Tabelle, alle Demo-Sätze | Task 5 |
| M1 | Minor | Personenkennungen folgen der Musterreihenfolge | **Gefixt:** ein Person-Muster | Task 2 Step 5/6 |
| M2 | Minor | „Crash-Resume automatisch gefiltert" gilt nur für B2-Turns | **Gefixt (Wortlaut)** in Kommentar und Plan | Task 3 Step 2 |
| M3 | Minor | Platzhalter in gemischten Zahlenwerten gehen unter | **Zusage präzisiert**, Verhalten getestet (gewollt) | Task 3 Step 4 |
| — | Important | PLZ/Ort-Entscheidung stand erst nach dem Bau an | **Gefixt:** Konzept vor dem Bau nachgezogen | Konzept |
| — | Important | Neue akzeptierte Fehltreffer nicht im Konzept; „Dr. med." leckte | **Gefixt:** Titelzusätze erkannt; Fehltreffer-Liste im Konzept | Konzept, Task 2 Step 3 |
| — | Minor | BC0 informieren nur als Handoff-Punkt | **Gefixt:** Task 7 Step 5 mit Verantwortlichem | Task 7 |
| — | Minor | Lückenquote „MUSS 0 %" verbietet Verbesserung | **Gefixt:** README-Tabelle ist die Wahrheit, Abweichung in beide Richtungen → README nachziehen | Task 5 |
| — | Important | Guard: Steps zu groß (Task 1 Step 2, Task 2 Step 2, Task 2 Step 8) | **Gefixt:** Literal → Vergabe → Buchstaben; Anrede → Titel → Mehrwort → Textreihenfolge; keine Segmentierung (unnötig) | Task 1/2 |

## Adjudikation Zweitmeinung 2 (Codex, Code-Review 14.09.2026)

Codex hat das gebaute Modul im Arbeitsspeicher gegen eigene Sätze ausgeführt (kein Container, kein Guard). Jeder Befund wurde hier per rotem Test nachgestellt und gefixt; Bau ≙ Zielform war laut Codex verhaltensgleich.

| Nr. | Schwere | Befund | Entscheidung | Nachweis |
|---|---|---|---|---|
| 1 | Critical | Zwei IBANs nebeneinander: die zweite bleibt im ersten Lauf offen (Idempotenz verletzt) | **Gefixt:** Gruppe, die wie ein IBAN-Anfang aussieht, beendet die IBAN; nur bekannte Ländercodes | `test_zwei_ibans_nebeneinander…` |
| 2 | Critical | „René", „van Muster", „von Muster", „Dr.-Ing." bleiben ganz/teilweise offen | **Gefixt:** Buchstabenklassen Latin-1 + Latin Extended-A (per `chr`), Partikel, zusammengesetzte Titel; „der" allein kein Partikel | `test_namen_mit_akzenten…` |
| 3 | Important | Telefon mit geschütztem Leerzeichen / „(030)" bleibt offen | **Gefixt:** Trennerklasse U+00A0/U+202F, geklammerte Vorwahl | `test_telefon_mit_geschuetztem…` |
| 4 | Important | IBAN mit Doppel-Leerzeichen leckt; „Ticket AB12 3456 7890" wird IBAN | **Gefixt:** beliebige Leerzeichen, nur Länder aus der Tabelle | `test_iban_nur_bekannte_laender…` |
| 5 | Important | Unicode-/Punycode-Endungen bei E-Mail | **Gefixt** | `test_email_mit_unicode…` |
| 6 | Important | Datumsfolgen mit weiteren Zahlen werden Telefon | **Gefixt:** Lookahead/Lookbehind statt `fullmatch`; `_DATUM` entfällt | `test_telefon_mit_geschuetztem…` |
| 7 | Important | „Musterweg 3,12345" leckt; „Fertigungsstraße 3" wird Adresse; Ort über Zeilenumbruch | **Gefixt:** Komma ohne Abstand, Ort nur in derselben Zeile, Prozessbegriffe ausgenommen | `test_adresse_komma_ohne_abstand…` |
| 8 | Important | Literal U+00A0 in Modul und Test kann gemeinsam still normalisiert werden | **Gefixt:** `chr(160)` in Modul und Test, kein Zeichen im Quelltext | `test_geschuetztes_leerzeichen_in_iban_per_chr160` |
| 9 | Important | Anbieter-Ausgaben (Extraktionswerte, Antworttext) laufen am Filter vorbei | **Gefixt:** `ersetze_pii` auf `cand.value` (Extraktor) und auf `llm.antworte(...)` (Kern). Hinweis: je String eigene Kennungen — ein halluzinierter Name im Antworttext bekommt nicht zwingend dieselbe Kennung wie in der Eingabe | `test_anbieter_ausgaben_werden_ebenfalls_gefiltert` |
| 10 | Important | Crash-Resume-Test beweist keinen Resume | **Gefixt:** `pytest.raises`, Zwischenzustand geprüft, Aufrufzähler | `test_crash_resume_spielt…` |
| 11 | Minor | Adresskennungen folgen der Musterreihenfolge | **Gefixt:** ein Adresse-Muster | `test_adresskennungen_folgen…` |
| 12 | Minor | README-Parsing hängt an exakten Leerzeichen | **Gefixt:** Zellen zerlegen, `(\d+)\s*%`, Dopplung abgewiesen | `test_pii_kpi.py` |
| 13 | Minor | Erweiterungen ohne erzwingenden Test; unerreichbarer Datumszweig | **Gefixt:** `test_zugesagte_erweiterungen…`; `_DATUM` entfernt | `test_pii.py` |
| — | Hinweis | Alt-Logs würden ungefiltert abgespielt | Akzeptiert: live nur Testprofile, Migration bewusst vertagt (Konzept) | — |
| — | Hinweis | BC0-Benachrichtigung offen | Task 7 Step 5 (Richard) | — |

## Selbstprüfung des Plans (Fassung 2)

- **Spec-Abdeckung:** Konzept T1 → Task 1–2 · T2 → Task 3 · T3 → Task 1–3 · T4 → Task 4 · T5 → Task 1–5 · T6 → Task 5, 7 · T7 → Task 0, 7. Konzept-Nachträge (Adresse, Fehltreffer, Titelzusätze, Kennungsreihenfolge) sind eingearbeitet.
- **Platzhalter:** keine („…unverändert…" verweist auf sichtbaren Bestandstext).
- **Typkonsistenz:** `ersetze_pii(text: str) -> str`; `_Vergabe()` (Task 1) → `_Vergabe(text)` (ab Task 2 Step 10; Zielform Step 13 gilt); `_ersatz(klasse, m, vergabe)`; `_iban_ersatz(treffer, vergabe)`; `PII_HINWEIS`; Klassennamen identisch in Testset, README-Tabelle und Modul.
- **Ehrlich offen:** (1) Die Quoten gelten auf einem selbst geschriebenen Testset — sie belegen, dass die Muster tun, was das Konzept sagt, nicht, dass echte Interviews lückenlos gefiltert werden. (2) Der Guard kann noch kleinere Schritte erzwingen; die Zielform ist der Maßstab. (3) Codex konnte den Guard nicht messen; die Step-Schnitte sind Ableitung.
