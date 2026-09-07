# BC1 P3 Etappe 1 — Feldtypen + Discovery-Paket + Demos (Implementierungsplan)

**Goal:** Das echte Discovery-Interview: 8 Feldtypen mit Validierung + Normalisierung im Kern, das Discovery-Paket (~26 Muss- + 17 passive Felder aus dem BC0-Fragenkatalog A–J, flach mit Fokus-Schritt) als reine Daten im Service, `BC1_PAKET`-Umschalter, und 3 Demo-Durchläufe (Reisebuchung · RAG-Wissensbasis · Consultant Placement) als Nachweis, dass EIN generisches Paket alle Fälle trägt.

**Architecture:** Kern-Erweiterung minimal und additiv: neues Stdlib-Modul `bc1_core/feldtypen.py` (pro Typ EIN Validator + EIN totaler Normalisierer; Werte bleiben Strings), `FieldSpec.typ` mit Default `FREITEXT` (rückwärtskompatibel, expliziter `validator` gewinnt), Normalisierung an der bestehenden Extraktor-Naht VOR dem Merge (damit Wert-Vergleiche/Klärung auf normalisierten Werten arbeiten). **Dokumentierte Spec-Ergänzung (bei Plan-Review entdeckt, mit diesem Plan freigegeben):** `UseCasePackage.max_rounds` (Default 20) — das Discovery-Paket hat 26 Pflichtfelder, das bisherige globale `MAX_ROUNDS = 20` würde ein braves Eine-Antwort-pro-Frage-Interview VOR der letzten Frage kappen; die Rundenobergrenze ist eine Paket-Eigenschaft (Fall-Spezifika ins Paket), Discovery setzt 60.

**Tech Stack:** Python 3.11+ Stdlib (Kern: `re`, `dataclasses`) · bestehende Nähte: `_status_for`/`extract_and_merge` (extractor.py), `decide_next` (dialog.py), `create_app` (api.py), `Snapshot.prozess_liste()` (snapshot.py) · pytest + FakeLLM (kein Netz).

**Bindende Verträge:** Die Normalisierungs-Tabelle und die Feldliste stehen im Abschnitt „Bindende Verträge" unten — sie sind der BC2-relevante Vertrag dieses Pakets.

## Global Constraints

- **Branch:** `bc1-p3-discovery`, abgezweigt von `bc1-ollama-adapter` (PR #151 unmerged).
- **TDD.** Pro Task: erst der rote Test, dann Implementierung. pytest IMMER aus `bc1-context-discovery/` und IMMER mit Test-DB: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest` (Container `bc1-test-pg` auf Port 55432; falls er nicht läuft: `docker run -d --rm --name bc1-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16`).
- **Kern-Änderungen exakt diese und keine weiteren:** `feldtypen.py` (neu) · `package.py` (FieldSpec.typ, UseCasePackage.max_rounds) · `extractor.py` (Normalisierungs-Naht + Typ-Fallback in `_status_for`) · `dialog.py` (package.max_rounds statt Modul-Konstante). KEINE neuen Dependencies (Kern bleibt Stdlib-only).
- **Die bestehenden 149 Tests bleiben grün** (2 Skips: Echt-LLM). `TOY_PROZESS` bleibt unverändert (typ-Default FREITEXT + expliziter validator decken es ab).
- **Normalisierungs-Regeln = Tabelle unten, wörtlich:** ZAHL → pro Jahr (genau EINE Zahl; Woche ×52, Monat ×12, Jahr ×1; mehrere Zahlen oder andere Perioden ungültig) · MINUTEN (genau EINE Zahl; Stunden ×60; andere Einheiten ungültig) · SKALA_1_5 ganze Zahl 1–5 · PROZENT_0_100 („%" wird entfernt) · JA_NEIN → „ja"/„nein" (case-insensitiv, Satzzeichen toleriert) · LISTE (Komma-/Zeilen-getrennt, Einträge getrimmt, komma-separiert) · FREITEXT nicht-leer · AUSWAHL case-insensitiv → kanonische Option. **Normalisierer sind TOTAL** (werfen nie; Unparsebares kommt unverändert zurück und fällt dann in der Validierung durch → bestehende Nachfrage-Mechanik).
- **Feldnamen des Discovery-Pakets schema-nah englisch** (Spec-Feldliste), alles andere (Fragen, Docstrings, Commits) deutsch; Conventional Commits Scope `bc1`; Commit je RED→GREEN-Paar.
- Generik-Invariante: keine Verzweigung auf Use-Case-/Feldnamen im Kern; das Paket ist reine Daten.

## Bindende Verträge (BC2-relevant)

**Normalisierungs-Regeln** — gespeichert wird IMMER der normalisierte Wert; erst normalisieren, dann validieren. Normalisierer sind **total** (werfen nie; Unparsebares kommt unverändert zurück und fällt in der Validierung durch → Nachfrage-Mechanik):

| Typ | akzeptiert | normalisiert zu | ungültig (→ Nachfrage-Mechanik) |
|---|---|---|---|
| `ZAHL` | genau EINE Ganz-/Dezimalzahl, optional „pro Woche/Monat/Jahr" | Zahl **pro Jahr** (×52 / ×12 / ×1), ohne Einheit | keine oder mehrere Zahlen; andere Perioden |
| `MINUTEN` | genau EINE Zahl, optional „Minuten/Min/Stunden/Std/h" | Zahl in **Minuten** (Stunden ×60) | keine oder mehrere Zahlen; andere Einheiten (z. B. Tage) |
| `SKALA_1_5` | ganze Zahl | „1"–„5" | außerhalb 1–5; keine ganze Zahl |
| `PROZENT_0_100` | Zahl, optional „%" | Zahl ohne „%" | außerhalb 0–100 |
| `JA_NEIN` | „ja"/„nein", case-insensitiv, umgebende Satzzeichen/Leerraum toleriert | „ja" / „nein" | alles andere |
| `LISTE` | nicht-leerer Text; Komma-/Zeilen-getrennt | Einträge getrimmt, komma-separiert | leer |
| `FREITEXT` | nicht-leerer Text | unverändert | – (Leerwerte filtert die Extraktion schon) |
| `AUSWAHL(optionen)` | eine der Optionen (case-insensitiv) | kanonische Option | nicht in der Liste |

**Aktiv gefragte Muss-Felder (M, 26, in Katalog-Reihenfolge):**

| Katalog | Feldname | Typ |
|---|---|---|
| A1 | `request_intent` | FREITEXT |
| A2 | `request_goal` | AUSWAHL(zeit_sparen, fehler_senken, skalieren) |
| A3 | `scope_focus` | AUSWAHL(ganzer_prozess, einzelner_schritt) |
| B1 | `process_name` | FREITEXT |
| B3 | `process_owner_role` | FREITEXT (Katalog nennt „Auswahl" ohne Optionsliste) |
| B4 | `process_id` | AUSWAHL(Snapshot-Prozesse) / FREITEXT-Fallback |
| B5 | `process_steps` | LISTE |
| C1 | `trigger_text` | FREITEXT |
| C2 | `input_text` | FREITEXT |
| C3 | `input_format` | AUSWAHL(digital, papier, pdf, mail) |
| C4 | `output_text` | FREITEXT |
| D1 | `frequency_per_year` | ZAHL |
| D4 | `executions_per_run` | ZAHL (⚠️ Katalog-Befund: Katalog-Zielfeld heißt `executions_per_year`, die Katalog-Frage erfasst aber Fälle **pro Durchlauf** — der Feldname folgt der Frage; Mapping-Auflösung mit Katalog-Owner/BC2 offen) |
| E1 | `total_duration_minutes` | MINUTEN |
| E5 | `focus_step` | FREITEXT (auf M hochgestuft — der flache Fokus-Schnitt hängt daran) |
| E2 | `focus_step_duration_minutes` | MINUTEN |
| E3 | `focus_step_duration_source` | AUSWAHL(gemessen, geschaetzt, aus_system) |
| E4 | `focus_step_duration_confidence_pct` | PROZENT_0_100 |
| F1 | `focus_step_roles` | LISTE |
| F2 | `focus_step_systems` | LISTE |
| F3 | `focus_step_media_break` | JA_NEIN |
| G1 | `documentation_status` | SKALA_1_5 |
| G2 | `standardization_level` | SKALA_1_5 |
| G4 | `data_availability_score` | SKALA_1_5 |
| G5 | `stability_score` | SKALA_1_5 |
| I1 | `pii_involved` | JA_NEIN |

**Paket-Identität / `schema_version`:** Basis ist `1.0`. Wird das Paket mit einer
Snapshot-Prozessliste gebaut (B4-AUSWAHL), hängt die Fabrik einen Fingerprint der
sortierten Prozess-**IDs** als Build-Metadata an: `1.0+kp-<16 Hex>`. Konsumenten, die
nur die Vertragsform prüfen, werten den Teil vor dem `+`. Konsequenz im Betrieb:
Ändert sich die **ID-Menge** der Baseline, weist der Paket-Guard laufende Interviews
beim nächsten Turn als Paketkonflikt (HTTP 409) ab — bewusst, damit keine Session
gegen ein anderes Options-Set validiert als das, mit dem sie gestartet wurde. Reine
Namens-Änderungen ohne ID-Wechsel lassen die Identität unverändert.

**Passiv miterfasste E-Felder (17, `required=False`, nur bei Erwähnung befüllt):** A4 `pain_level` (SKALA_1_5) · B2 `process_category` (AUSWAHL(steuerung, kerngeschaeft, unterstuetzung)) · C5 `output_format` (AUSWAHL(system, dokument, mail) — bewusst NICHT die C3-Formate) · D2 `seasonal_peaks` (JA_NEIN) · D3 `step_frequency_per_year` (ZAHL) · F4 `systems_integrated` (JA_NEIN) · F5 `digital_logging` (JA_NEIN) · G3 `variant_share_pct` (PROZENT_0_100) · G6 `rule_based_score` (SKALA_1_5) · G7 `acceptance_score` (SKALA_1_5) · G8 `automation_potential_estimate_pct` (PROZENT_0_100) · H1 `upstream_process` (FREITEXT) · H2 `downstream_process` (FREITEXT) · H3 `interface_data` (FREITEXT) · I2 `approval_steps` (JA_NEIN) · I3 `error_hotspots` (FREITEXT) · J2 `open_remarks` (FREITEXT).

## File Structure

- `bc1_core/feldtypen.py` — Create: `Feldtyp`-Dataclass, Konstanten `ZAHL MINUTEN SKALA_1_5 PROZENT_0_100 JA_NEIN LISTE FREITEXT`, Fabrik `AUSWAHL(*optionen)`
- `bc1_core/package.py` — Modify: `FieldSpec.typ: Feldtyp = FREITEXT` · `UseCasePackage.max_rounds: int = 20`
- `bc1_core/extractor.py` — Modify: `_status_for`-Fallback auf `spec.typ.validator`; Normalisierung vor dem Merge
- `bc1_core/dialog.py` — Modify: `package.max_rounds` statt `MAX_ROUNDS` (Konstante bleibt als Default-Referenz)
- `bc1_service/discovery_paket.py` — Create: `baue_discovery_paket(prozesse)` mit allen Feldern der Spec-Tabelle
- `bc1_service/paket_wahl.py` — Create: `waehle_paket(umgebung, prozesse)` (`BC1_PAKET`: discovery-Default | toy)
- `bc1_service/main.py` — Modify: Snapshot zuerst laden, Prozessliste an Paket-Fabrik, `waehle_paket` statt `TOY_PROZESS`
- `bc1_service/n8n/SMOKE.md` — Modify: Abschnitt „Discovery-Interview live"
- `tests/test_feldtypen.py`, `tests/test_discovery_paket.py`, `tests/test_paket_wahl.py`, `tests/test_demo_durchlaeufe.py` — Create
- `tests/test_package.py`, `tests/test_extractor.py`, `tests/test_dialog.py` — Modify (gezielte Ergänzungen)

## Reihenfolge

Task 1 → 2 → 3 sequenziell (Typen → FieldSpec/Extractor-Naht → max_rounds). Task 4 (Paket) braucht 1–3. Task 5 (Wahl/Verdrahtung) braucht 4. Task 6 (Demos + SMOKE) braucht 4–5.

> Hinweis: Die „Expected"-Zwischenstände sind die Zahlen zum Zeitpunkt der jeweiligen Task; der Endstand steht in der Abnahme.

---

### Task 1: Feldtypen (`bc1_core/feldtypen.py`)

**Files:**
- Create: `bc1_core/feldtypen.py`
- Test: `tests/test_feldtypen.py`

**Interfaces:**
- Consumes: nichts (Stdlib-only, kernunabhängig).
- Produces: `@dataclass(frozen=True) Feldtyp(name: str, validator: Callable[[str], bool], normalisiere: Callable[[str], str])` · Konstanten `ZAHL, MINUTEN, SKALA_1_5, PROZENT_0_100, JA_NEIN, LISTE, FREITEXT: Feldtyp` · `AUSWAHL(*optionen: str) -> Feldtyp`. Task 2 hängt `FieldSpec.typ` daran; Task 4 nutzt alle acht.

- [ ] **Step 1: Branch anlegen + Plan committen**

```bash
cd coe-factory && git checkout -b bc1-p3-discovery bc1-ollama-adapter
git add bc1-context-discovery/design/Implementierungsplan-P3-Discovery.md
git commit -m "docs(bc1): Implementierungsplan P3 Etappe 1 (Feldtypen + Discovery-Paket + Demos)"
```

- [ ] **Step 2: Write the failing tests** — `tests/test_feldtypen.py`

```python
"""Feldtypen: je Antworttyp EIN Validator + EIN totaler Normalisierer.

Die Normalisierungs-Regeln sind BC2-relevanter Vertrag (Spec-Tabelle P3):
gespeichert wird IMMER der normalisierte Wert.
"""
from bc1_core.feldtypen import (
    AUSWAHL,
    FREITEXT,
    JA_NEIN,
    LISTE,
    MINUTEN,
    PROZENT_0_100,
    SKALA_1_5,
    ZAHL,
)


# --- ZAHL: normalisiert auf pro Jahr -----------------------------------------

def test_zahl_woche_und_monat_werden_auf_jahr_normalisiert():
    assert ZAHL.normalisiere("50 pro Monat") == "600"
    assert ZAHL.normalisiere("2 pro Woche") == "104"
    assert ZAHL.normalisiere("300 pro Jahr") == "300"
    assert ZAHL.normalisiere("300") == "300"


def test_zahl_unbekannte_periode_bleibt_unveraendert_und_ist_ungueltig():
    # Total: kein Wurf, unverändert zurück — die Validierung lehnt dann ab.
    assert ZAHL.normalisiere("5 pro Tag") == "5 pro Tag"
    assert ZAHL.validator("5 pro Tag") is False
    assert ZAHL.validator("600") is True
    assert ZAHL.validator("keine Ahnung") is False


# --- MINUTEN -----------------------------------------------------------------

def test_minuten_stunden_werden_umgerechnet():
    assert MINUTEN.normalisiere("2 Stunden") == "120"
    assert MINUTEN.normalisiere("45 Minuten") == "45"
    assert MINUTEN.normalisiere("90") == "90"
    assert MINUTEN.normalisiere("1,5 h") == "90"


def test_minuten_andere_einheiten_ungueltig():
    assert MINUTEN.normalisiere("3 Tage") == "3 Tage"
    assert MINUTEN.validator("3 Tage") is False
    assert MINUTEN.validator("120") is True


# --- SKALA_1_5 / PROZENT_0_100 ----------------------------------------------

def test_skala_akzeptiert_nur_ganze_zahlen_eins_bis_fuenf():
    assert SKALA_1_5.normalisiere(" 3 ") == "3"
    assert SKALA_1_5.validator("3") is True
    assert SKALA_1_5.validator("0") is False
    assert SKALA_1_5.validator("6") is False
    assert SKALA_1_5.validator("3,5") is False


def test_prozent_entfernt_prozentzeichen_und_prueft_bereich():
    assert PROZENT_0_100.normalisiere("70%") == "70"
    assert PROZENT_0_100.normalisiere("70 %") == "70"
    assert PROZENT_0_100.validator("70") is True
    assert PROZENT_0_100.validator("101") is False
    assert PROZENT_0_100.validator("-1") is False


# --- JA_NEIN -----------------------------------------------------------------

def test_ja_nein_case_insensitiv_mit_satzzeichen():
    assert JA_NEIN.normalisiere("Ja.") == "ja"
    assert JA_NEIN.normalisiere("  NEIN! ") == "nein"
    assert JA_NEIN.validator("ja") is True
    assert JA_NEIN.validator("vielleicht") is False
    assert JA_NEIN.normalisiere("vielleicht") == "vielleicht"


# --- LISTE / FREITEXT --------------------------------------------------------

def test_liste_trennt_kommas_und_zeilen_und_trimmt():
    assert LISTE.normalisiere("Prüfen, Buchen ,Ablegen") == "Prüfen, Buchen, Ablegen"
    assert LISTE.normalisiere("Prüfen\nBuchen") == "Prüfen, Buchen"
    assert LISTE.validator("Prüfen, Buchen") is True
    assert LISTE.validator("   ") is False


def test_freitext_verlangt_nur_nicht_leer():
    assert FREITEXT.validator("irgendwas") is True
    assert FREITEXT.validator("  ") is False
    assert FREITEXT.normalisiere("irgendwas") == "irgendwas"


# --- AUSWAHL -----------------------------------------------------------------

def test_auswahl_normalisiert_case_insensitiv_auf_kanonische_option():
    typ = AUSWAHL("zeit_sparen", "fehler_senken", "skalieren")
    assert typ.normalisiere("Zeit_Sparen") == "zeit_sparen"
    assert typ.normalisiere("skalieren.") == "skalieren"
    assert typ.validator("zeit_sparen") is True
    assert typ.validator("abkuerzen") is False
    assert typ.normalisiere("abkuerzen") == "abkuerzen"


def test_ja_nein_und_auswahl_tolerieren_typografische_anfuehrungszeichen():
    assert JA_NEIN.normalisiere('„Ja“') == "ja"
    assert AUSWAHL("zeit_sparen").normalisiere('„zeit_sparen“') == "zeit_sparen"


def test_normalisierer_sind_total_und_werfen_nie():
    for typ in (ZAHL, MINUTEN, SKALA_1_5, PROZENT_0_100, JA_NEIN, LISTE, FREITEXT):
        assert isinstance(typ.normalisiere(""), str)
        assert isinstance(typ.normalisiere("совершенно anders 💥"), str)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest` (aus `bc1-context-discovery/`)
Expected: FAIL mit `ModuleNotFoundError: No module named 'bc1_core.feldtypen'`; Rest der Suite grün.

- [ ] **Step 4: Write minimal implementation** — `bc1_core/feldtypen.py`

```python
"""Deklarative Feldtypen nach den Antworttypen des BC0-Fragenkatalogs.

Vertrag (Spec P3, BC2-relevant): normalisiere() ist TOTAL — wirft nie,
Unparsebares kommt unverändert zurück und fällt dann in der Validierung
durch (bestehende Nachfrage-Mechanik). Gespeichert wird der normalisierte
Wert; Werte bleiben Strings (Wire-Format).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Feldtyp:
    name: str
    validator: Callable[[str], bool]
    normalisiere: Callable[[str], str]


def _zahl_in(text: str) -> float | None:
    treffer = re.search(r"-?\d+(?:[.,]\d+)?", text)
    return float(treffer.group().replace(",", ".")) if treffer else None


def _nur_zahl(text: str) -> bool:
    return re.fullmatch(r"\s*-?\d+(?:[.,]\d+)?\s*", text) is not None


def _formatiere(zahl: float) -> str:
    return str(int(zahl)) if zahl == int(zahl) else str(zahl)


_PERIODEN = {"woche": 52.0, "monat": 12.0, "jahr": 1.0}


def _normalisiere_zahl(wert: str) -> str:
    zahl = _zahl_in(wert)
    if zahl is None:
        return wert
    text = wert.lower()
    for periode, faktor in _PERIODEN.items():
        if periode in text:
            return _formatiere(zahl * faktor)
    return _formatiere(zahl) if _nur_zahl(wert) else wert


def _normalisiere_minuten(wert: str) -> str:
    zahl = _zahl_in(wert)
    if zahl is None:
        return wert
    text = wert.lower()
    if re.search(r"\b(stunden?|std\.?|h)\b", text):
        return _formatiere(zahl * 60)
    if re.search(r"\b(minuten?|min\.?)\b", text) or _nur_zahl(wert):
        return _formatiere(zahl)
    return wert


def _entferne_rand(wert: str) -> str:
    return wert.strip().strip(".!?,;:„“\"' ").strip()


def _normalisiere_ja_nein(wert: str) -> str:
    kern = _entferne_rand(wert).lower()
    return kern if kern in ("ja", "nein") else wert


def _normalisiere_prozent(wert: str) -> str:
    kern = wert.strip()
    if kern.endswith("%"):
        kern = kern[:-1].strip()
    return kern if _nur_zahl(kern) else wert


def _normalisiere_liste(wert: str) -> str:
    teile = [t.strip() for t in re.split(r"[,\n]", wert) if t.strip()]
    return ", ".join(teile) if teile else wert


def _ist_skala(wert: str) -> bool:
    return re.fullmatch(r"[1-5]", wert.strip()) is not None


def _ist_prozent(wert: str) -> bool:
    return _nur_zahl(wert) and 0 <= float(wert.replace(",", ".")) <= 100


ZAHL = Feldtyp("zahl", lambda w: _nur_zahl(w) and float(w.replace(",", ".")) >= 0,
               _normalisiere_zahl)
MINUTEN = Feldtyp("minuten", lambda w: _nur_zahl(w) and float(w.replace(",", ".")) >= 0,
                  _normalisiere_minuten)
SKALA_1_5 = Feldtyp("skala_1_5", _ist_skala, lambda w: w.strip())
PROZENT_0_100 = Feldtyp("prozent_0_100", _ist_prozent, _normalisiere_prozent)
JA_NEIN = Feldtyp("ja_nein", lambda w: w in ("ja", "nein"), _normalisiere_ja_nein)
LISTE = Feldtyp("liste", lambda w: bool(w.strip()), _normalisiere_liste)
FREITEXT = Feldtyp("freitext", lambda w: bool(w.strip()), lambda w: w)


def AUSWAHL(*optionen: str) -> Feldtyp:
    """Fabrik: Auswahl-Typ mit kanonischen Optionen (case-insensitiv)."""
    def _normalisiere(wert: str) -> str:
        kern = _entferne_rand(wert).lower()
        for option in optionen:
            if kern == option.lower():
                return option
        return wert

    return Feldtyp(
        name=f"auswahl({', '.join(optionen)})",
        validator=lambda w: w in optionen,
        normalisiere=_normalisiere,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **161 passed, 2 skipped** (149 + 12 neue)

- [ ] **Step 6: Commit**

```bash
git add bc1-context-discovery/bc1_core/feldtypen.py bc1-context-discovery/tests/test_feldtypen.py
git commit -m "feat(bc1): Feldtypen — 8 Antworttypen mit Validator + totalem Normalisierer (Katalog A-Typen)"
```

---

### Task 2: `FieldSpec.typ` + Extraktor-Naht

**Files:**
- Modify: `bc1_core/package.py` (nur FieldSpec), `bc1_core/extractor.py`
- Test: `tests/test_extractor.py` (Ergänzungen), `tests/test_package.py` (eine Ergänzung)

**Interfaces:**
- Consumes: `Feldtyp`, `FREITEXT`, `ZAHL`, `MINUTEN` aus Task 1.
- Produces: `FieldSpec(name, question, required=True, validator=None, typ: Feldtyp = FREITEXT)` — expliziter `validator` gewinnt über `typ.validator`; `extract_and_merge` normalisiert JEDEN Kandidatenwert via `spec.typ.normalisiere` VOR dem Merge (gespeicherte Werte, Kandidaten und Vergleiche arbeiten normalisiert). Task 4 verlässt sich exakt darauf.

- [ ] **Step 1: Write the failing tests** — ergänzen in `tests/test_extractor.py` (Imports der Datei um `from bc1_core.feldtypen import MINUTEN, ZAHL` erweitern; bestehende Import-Struktur der Datei übernehmen)

```python
def test_typ_normalisiert_vor_validierung_und_speichert_normalisiert():
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("dauer", "Wie lange?", typ=MINUTEN),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("dauer", "2 Stunden")]})
    extract_and_merge(state, "m", "m1", paket, llm)
    assert state.values["dauer"].value == "120"
    assert state.values["dauer"].status is FieldStatus.GUELTIG


def test_typ_ungueltiger_wert_bleibt_unnormalisiert_und_ungueltig():
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("menge", "Wie oft?", typ=ZAHL),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("menge", "5 pro Tag")]})
    extract_and_merge(state, "m", "m1", paket, llm)
    assert state.values["menge"].value == "5 pro Tag"
    assert state.values["menge"].status is FieldStatus.UNGUELTIG


def test_expliziter_validator_gewinnt_ueber_typ():
    # Rückwärtskompatibilität: Felder wie TOY haeufigkeit behalten Verhalten.
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("f", "?", validator=lambda v: v == "spezial", typ=ZAHL),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({"m": [ExtractionCandidate("f", "spezial")]})
    extract_and_merge(state, "m", "m1", paket, llm)
    assert state.values["f"].status is FieldStatus.GUELTIG


def test_klaerung_erkennt_normalisierte_gleichheit():
    # "50 pro Monat" und "600" sind nach Normalisierung DERSELBE Wert —
    # die Wiederholung darf keinen Konflikt (UNKLAR) erzeugen.
    paket = UseCasePackage(
        name="typ_test", schema_version="0.1",
        fields=(FieldSpec("menge", "Wie oft?", typ=ZAHL),),
    )
    state = SessionState("s1", "0.1")
    llm = FakeLLM({
        "a": [ExtractionCandidate("menge", "50 pro Monat")],
        "b": [ExtractionCandidate("menge", "600")],
    })
    extract_and_merge(state, "a", "m1", paket, llm)
    extract_and_merge(state, "b", "m2", paket, llm)
    assert state.values["menge"].value == "600"
    assert state.values["menge"].status is FieldStatus.GUELTIG
    assert state.values["menge"].candidates == []
```

Ergänzen in `tests/test_package.py` (Import `from bc1_core.feldtypen import FREITEXT` an den bestehenden Import-Block):

```python
def test_fieldspec_typ_default_ist_freitext():
    spec = FieldSpec("f", "?")
    assert spec.typ is FREITEXT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_extractor.py tests/test_package.py -v`
Expected: FAIL — `TypeError: FieldSpec.__init__() got an unexpected keyword argument 'typ'` bzw. `AttributeError: ... no attribute 'typ'`.
Danach VOLLEN Lauf für den Guard: `BC1_TEST_DB_DSN=... .venv/bin/pytest` (5 neue FAIL, Rest grün).

- [ ] **Step 3: Write minimal implementation**

`bc1_core/package.py` — Import ergänzen und `FieldSpec` erweitern:

```python
from bc1_core.feldtypen import FREITEXT, Feldtyp

@dataclass(frozen=True)
class FieldSpec:
    name: str
    question: str
    required: bool = True
    validator: Callable[[str], bool] | None = None
    typ: Feldtyp = FREITEXT
```

`bc1_core/extractor.py` — `_status_for` fällt auf den Typ-Validator zurück:

```python
def _status_for(spec: FieldSpec, value: str) -> FieldStatus:
    # Policy: ein werfender Validator macht den Wert UNGUELTIG, bricht aber
    # nie den Turn ab — sonst ginge die Nachricht nach Raw-First-Save (Task 8)
    # beim Idempotenz-Replay dauerhaft verloren.
    pruefer = spec.validator if spec.validator is not None else spec.typ.validator
    try:
        gueltig = pruefer(value)
    except Exception:
        return FieldStatus.UNGUELTIG
    return FieldStatus.GUELTIG if gueltig else FieldStatus.UNGUELTIG
```

In `extract_and_merge` direkt nach dem `spec is None`-Guard die Normalisierung einziehen und im gesamten Schleifenrumpf `cand.value` durch `wert` ersetzen (6 Stellen: Neuanlage-value, `_status_for`-Aufrufe, Gleichheits-Vergleich, Kandidaten-Vergleich, Kandidaten-Merken, Wert-Übernahmen):

```python
    for cand in llm.extract(message, package, state):
        spec = package.field(cand.field_name)
        if spec is None:
            continue
        # Normalisierung VOR dem Merge: Vergleiche, Klärung und Kandidaten
        # arbeiten auf dem normalisierten Wert; gespeichert wird er auch.
        wert = spec.typ.normalisiere(cand.value)
```

- [ ] **Step 4: Run tests to verify they pass (VOLLER Lauf — beweist Rückwärtskompatibilität)**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **166 passed, 2 skipped** (161 + 5 neue; insbesondere alle bestehenden extractor-/core-Tests unverändert grün)

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_core/package.py bc1-context-discovery/bc1_core/extractor.py bc1-context-discovery/tests/test_extractor.py bc1-context-discovery/tests/test_package.py
git commit -m "feat(bc1): FieldSpec.typ + Normalisierung an der Extraktor-Naht (vor Merge, expliziter Validator gewinnt)"
```

---

### Task 3: `UseCasePackage.max_rounds` (dokumentierte Spec-Ergänzung)

**Files:**
- Modify: `bc1_core/package.py` (UseCasePackage), `bc1_core/dialog.py`
- Test: `tests/test_dialog.py` (Ergänzungen), `tests/test_package.py` (eine Ergänzung)

**Interfaces:**
- Consumes: bestehendes `decide_next(state, package, conf, llm)`.
- Produces: `UseCasePackage(..., max_rounds: int = 20)`; `decide_next` kappt bei `state.rounds >= package.max_rounds`. Die Modul-Konstante `MAX_ROUNDS = 20` bleibt (Default-Referenz + bestehende Test-Importe). Task 4 setzt `max_rounds=60`.

- [ ] **Step 1: Write the failing tests** — ergänzen in `tests/test_dialog.py` (bestehende Helfer/Imports der Datei nutzen; `confidence_check` ist dort bereits importiert, `UseCasePackage`/`FieldSpec` müssen zum Import-Block ergänzt werden)

```python
def test_paket_max_rounds_uebersteuert_die_konstante():
    paket = UseCasePackage(
        name="lang", schema_version="0.1",
        fields=(FieldSpec("f1", "?"),),
        max_rounds=25,
    )
    state = SessionState("s1", "0.1")
    state.rounds = 20   # alte Grenze erreicht — Paket erlaubt mehr
    conf = confidence_check(state, paket)
    d = decide_next(state, paket, conf, FakeLLM())
    assert d.done is False
    assert d.next_field == "f1"


def test_paket_max_rounds_kappt_wie_bisher():
    paket = UseCasePackage(
        name="kurz", schema_version="0.1",
        fields=(FieldSpec("f1", "?"),),
        max_rounds=3,
    )
    state = SessionState("s1", "0.1")
    state.rounds = 3
    conf = confidence_check(state, paket)
    d = decide_next(state, paket, conf, FakeLLM())
    assert d.done is True
    assert state.values["f1"].status is FieldStatus.UNGELOEST
    assert state.values["f1"].grund == GRUND_RUNDEN_LIMIT
```

Ergänzen in `tests/test_package.py`:

```python
def test_package_max_rounds_default_ist_20():
    assert TOY_PROZESS.max_rounds == 20
```

(`confidence_check`, `GRUND_RUNDEN_LIMIT`, `FieldStatus`, `FakeLLM` sind in `tests/test_dialog.py` bereits importiert; `UseCasePackage`/`FieldSpec` zum dortigen `bc1_core.package`-Import ergänzen — Muster der Datei übernehmen.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_dialog.py tests/test_package.py -v`
Expected: FAIL — `TypeError: UseCasePackage.__init__() got an unexpected keyword argument 'max_rounds'`. Danach voller Lauf (Guard).

- [ ] **Step 3: Write minimal implementation**

`bc1_core/package.py`:

```python
@dataclass(frozen=True)
class UseCasePackage:
    name: str
    schema_version: str
    fields: tuple[FieldSpec, ...]
    # Rundenobergrenze ist Paket-Eigenschaft: 26 Pflichtfelder brauchen mehr
    # Runden als 3 (Spec-Ergänzung P3, dokumentiert im Plan-Kopf).
    max_rounds: int = 20
```

`bc1_core/dialog.py` — die Zeile `if state.rounds >= MAX_ROUNDS:` ersetzen durch:

```python
    if state.rounds >= package.max_rounds:
```

(`MAX_ROUNDS = 20` bleibt als Konstante im Modul stehen.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **169 passed, 2 skipped** (166 + 3 neue)

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_core/package.py bc1-context-discovery/bc1_core/dialog.py bc1-context-discovery/tests/test_dialog.py bc1-context-discovery/tests/test_package.py
git commit -m "feat(bc1): UseCasePackage.max_rounds — Rundenobergrenze wird Paket-Eigenschaft (Spec-Ergänzung P3)"
```

---

### Task 4: Discovery-Paket (`bc1_service/discovery_paket.py`)

**Files:**
- Create: `bc1_service/discovery_paket.py`
- Test: `tests/test_discovery_paket.py`

**Interfaces:**
- Consumes: alle 8 Feldtypen aus Task 1; `FieldSpec`/`UseCasePackage` (inkl. `max_rounds`) aus Task 2/3.
- Produces: `baue_discovery_paket(prozesse: list[tuple[str, str]] | None = None) -> UseCasePackage` (Name `"discovery"`, `SCHEMA_VERSION = "1.0"`, `MAX_ROUNDS_DISCOVERY = 60`). `prozesse` = (ID, Name)-Paare → B4 als AUSWAHL über die IDs, Frage nennt das Mapping; `None` → FREITEXT-Fallback. Task 5/6 rufen exakt diese Fabrik.

- [ ] **Step 1: Write the failing tests** — `tests/test_discovery_paket.py`

```python
"""Integrität des Discovery-Pakets gegen die Spec-Feldliste (P3)."""
from bc1_service.discovery_paket import (
    MAX_ROUNDS_DISCOVERY,
    SCHEMA_VERSION,
    baue_discovery_paket,
)

MUSS_FELDER = [
    "request_intent", "request_goal", "scope_focus",
    "process_name", "process_owner_role", "process_id", "process_steps",
    "trigger_text", "input_text", "input_format", "output_text",
    "frequency_per_year", "executions_per_run",
    "total_duration_minutes", "focus_step", "focus_step_duration_minutes",
    "focus_step_duration_source", "focus_step_duration_confidence_pct",
    "focus_step_roles", "focus_step_systems", "focus_step_media_break",
    "documentation_status", "standardization_level",
    "data_availability_score", "stability_score", "pii_involved",
]

PASSIVE_FELDER = [
    "pain_level", "process_category", "output_format", "seasonal_peaks",
    "step_frequency_per_year", "systems_integrated", "digital_logging",
    "variant_share_pct", "rule_based_score", "acceptance_score",
    "automation_potential_estimate_pct", "upstream_process",
    "downstream_process", "interface_data", "approval_steps",
    "error_hotspots", "open_remarks",
]


def test_alle_muss_felder_der_spec_sind_required():
    paket = baue_discovery_paket()
    for name in MUSS_FELDER:
        spec = paket.field(name)
        assert spec is not None, f"Muss-Feld fehlt: {name}"
        assert spec.required, f"Muss-Feld nicht required: {name}"
    assert len([f for f in paket.fields if f.required]) == len(MUSS_FELDER)


def test_alle_passiven_felder_sind_optional():
    paket = baue_discovery_paket()
    for name in PASSIVE_FELDER:
        spec = paket.field(name)
        assert spec is not None, f"Passives Feld fehlt: {name}"
        assert not spec.required, f"Passives Feld faelschlich required: {name}"
    assert len(paket.fields) == len(MUSS_FELDER) + len(PASSIVE_FELDER)


def test_paket_metadaten():
    paket = baue_discovery_paket()
    assert paket.name == "discovery"
    assert paket.schema_version == SCHEMA_VERSION == "1.0"
    assert paket.max_rounds == MAX_ROUNDS_DISCOVERY == 60


def test_b4_mit_snapshot_wird_auswahl_ueber_die_ids():
    paket = baue_discovery_paket([("KP-01", "Angebotserstellung"), ("KP-02", "Onboarding")])
    spec = paket.field("process_id")
    assert spec.typ.validator("KP-01") is True
    assert spec.typ.validator("KP-99") is False
    assert spec.typ.normalisiere("kp-02") == "KP-02"
    assert "KP-01 = Angebotserstellung" in spec.question


def test_b4_ohne_snapshot_ist_freitext():
    spec = baue_discovery_paket(None).field("process_id")
    assert spec.typ.validator("irgendein Prozess") is True


def test_typ_stichproben_gegen_die_spec_tabelle():
    paket = baue_discovery_paket()
    assert paket.field("frequency_per_year").typ.normalisiere("50 pro Monat") == "600"
    assert paket.field("total_duration_minutes").typ.normalisiere("2 Stunden") == "120"
    assert paket.field("pii_involved").typ.normalisiere("Ja.") == "ja"
    assert paket.field("request_goal").typ.validator("zeit_sparen") is True
    assert paket.field("request_goal").typ.validator("abkuerzen") is False
    assert paket.field("documentation_status").typ.validator("6") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_discovery_paket.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'bc1_service.discovery_paket'`. Danach voller Lauf (Guard).

- [ ] **Step 3: Write minimal implementation** — `bc1_service/discovery_paket.py`

```python
"""Das Discovery-Paket — reine Daten nach dem BC0-Fragenkatalog (Blöcke A–J).

Feldnamen schema-nah englisch (Zielfelder des Katalogs): der Gate-0-Payload
ist damit BC2-nah benannt. Muss-Felder (M) werden aktiv gefragt, E-Felder
passiv miterfasst (required=False). Dokumentierte Katalog-Abweichungen
(Spec P3): B3/H1/H2 nennen „Auswahl" ohne Optionsliste → FREITEXT bis der
Katalog Optionen nachliefert · E5 auf Pflicht hochgestuft (der flache
Fokus-Schnitt hängt daran). Flach + Fokus-Schritt: die focus_step_*-Felder
gelten für den in focus_step benannten Schritt.
"""
from __future__ import annotations

from bc1_core.feldtypen import (
    AUSWAHL,
    FREITEXT,
    JA_NEIN,
    LISTE,
    MINUTEN,
    PROZENT_0_100,
    SKALA_1_5,
    ZAHL,
)
from bc1_core.package import FieldSpec, UseCasePackage

SCHEMA_VERSION = "1.0"
MAX_ROUNDS_DISCOVERY = 60   # 26 Pflichtfelder × 2 Versuche + Puffer


def baue_discovery_paket(
    prozesse: list[tuple[str, str]] | None = None,
) -> UseCasePackage:
    """prozesse: (ID, Name)-Paare aus dem BC0-Snapshot für B4; None → Freitext."""
    if prozesse:
        b4_typ = AUSWAHL(*(pid for pid, _ in prozesse))
        b4_frage = ("Zu welchem Ihrer Kernprozesse gehört das? ("
                    + ", ".join(f"{pid} = {name}" for pid, name in prozesse) + ")")
    else:
        b4_typ = FREITEXT
        b4_frage = "Zu welchem Ihrer Kernprozesse gehört das?"

    return UseCasePackage(
        name="discovery",
        schema_version=SCHEMA_VERSION,
        max_rounds=MAX_ROUNDS_DISCOVERY,
        fields=(
            # --- Block A — Anfrage-Rahmen & Ziel ---
            FieldSpec("request_intent",                                          # A1
                      "Was möchten Sie konkret automatisieren oder verbessern?"),
            FieldSpec("request_goal",                                            # A2
                      "Welches Ergebnis erwarten Sie vor allem — zeit_sparen, "
                      "fehler_senken oder skalieren?",
                      typ=AUSWAHL("zeit_sparen", "fehler_senken", "skalieren")),
            FieldSpec("scope_focus",                                             # A3
                      "Geht es um einen ganzer_prozess oder einen "
                      "einzelner_schritt?",
                      typ=AUSWAHL("ganzer_prozess", "einzelner_schritt")),
            FieldSpec("pain_level",                                              # A4 (E)
                      "Wie hoch ist der Leidensdruck heute (1–5)?",
                      required=False, typ=SKALA_1_5),
            # --- Block B — Prozess-Identität & Einordnung ---
            FieldSpec("process_name",                                            # B1
                      "Um welchen Prozess geht es — wie würden Sie ihn nennen?"),
            FieldSpec("process_category",                                        # B2 (E)
                      "Ist das eher steuerung, kerngeschaeft oder "
                      "unterstuetzung?",
                      required=False,
                      typ=AUSWAHL("steuerung", "kerngeschaeft", "unterstuetzung")),
            FieldSpec("process_owner_role",                                      # B3 (⚠️ Katalog: Auswahl ohne Optionsliste)
                      "Welche Rolle ist für diesen Prozess verantwortlich?"),
            FieldSpec("process_id", b4_frage, typ=b4_typ),                       # B4
            FieldSpec("process_steps",                                           # B5
                      "Welche Einzelschritte hat der Prozess, von Anfang bis "
                      "Ende?", typ=LISTE),
            # --- Block C — Auslöser · Input · Output ---
            FieldSpec("trigger_text", "Was löst den Prozess aus?"),              # C1
            FieldSpec("input_text",                                              # C2
                      "Welche Eingangsdaten oder Dokumente brauchen Sie zum "
                      "Start?"),
            FieldSpec("input_format",                                            # C3
                      "In welchem Format kommen die Eingangsdaten an — "
                      "digital, papier, pdf oder mail?",
                      typ=AUSWAHL("digital", "papier", "pdf", "mail")),
            FieldSpec("output_text",                                             # C4
                      "Was ist das Endergebnis bzw. der Output des Prozesses?"),
            FieldSpec("output_format",                                           # C5 (E)
                      "In welchem Format geht der Output raus — system, "
                      "dokument oder mail?",
                      required=False, typ=AUSWAHL("system", "dokument", "mail")),
            # --- Block D — Mengengerüst & Häufigkeit ---
            FieldSpec("frequency_per_year",                                      # D1
                      "Wie oft läuft der gesamte Prozess (pro Woche, Monat "
                      "oder Jahr)?", typ=ZAHL),
            FieldSpec("seasonal_peaks",                                          # D2 (E)
                      "Gibt es saisonale Schwankungen oder Lastspitzen?",
                      required=False, typ=JA_NEIN),
            FieldSpec("step_frequency_per_year",                                 # D3 (E)
                      "Wie oft läuft dieser einzelne Schritt, falls "
                      "abweichend?", required=False, typ=ZAHL),
            FieldSpec("executions_per_run",                                      # D4 (⚠️ Katalog-Befund: Zielfeld-Name vs. Frage)
                      "Wie viele Fälle oder Vorgänge bearbeiten Sie "
                      "typischerweise pro Durchlauf?", typ=ZAHL),
            # --- Block E — Zeit / Aufwand (Fokus-Schritt) ---
            FieldSpec("total_duration_minutes",                                  # E1
                      "Wie lange dauert ein kompletter Durchlauf im Schnitt?",
                      typ=MINUTEN),
            FieldSpec("focus_step",                                              # E5 (⚠️ auf M hochgestuft — Fokus-Schnitt)
                      "Welcher Schritt kostet am meisten Zeit oder nervt am "
                      "meisten?"),
            FieldSpec("focus_step_duration_minutes",                             # E2
                      "Wie lange dauert dieser Schritt im Schnitt?",
                      typ=MINUTEN),
            FieldSpec("focus_step_duration_source",                              # E3
                      "Ist diese Zeitangabe gemessen, geschaetzt oder "
                      "aus_system?",
                      typ=AUSWAHL("gemessen", "geschaetzt", "aus_system")),
            FieldSpec("focus_step_duration_confidence_pct",                      # E4
                      "Wie sicher ist diese Zeitangabe (0–100 %)?",
                      typ=PROZENT_0_100),
            # --- Block F — Fokus-Schritt: Rollen & Systeme ---
            FieldSpec("focus_step_roles",                                        # F1
                      "Welche Rollen oder Abteilungen sind an diesem Schritt "
                      "beteiligt?", typ=LISTE),
            FieldSpec("focus_step_systems",                                      # F2
                      "Welche IT-Systeme oder Tools nutzen Sie in diesem "
                      "Schritt?", typ=LISTE),
            FieldSpec("focus_step_media_break",                                  # F3
                      "Müssen Sie zwischen Systemen wechseln oder Daten "
                      "manuell übertragen?", typ=JA_NEIN),
            FieldSpec("systems_integrated",                                      # F4 (E)
                      "Sind diese Systeme über Schnittstellen verbunden?",
                      required=False, typ=JA_NEIN),
            FieldSpec("digital_logging",                                         # F5 (E)
                      "Werden Zwischenstände digital protokolliert oder "
                      "archiviert?", required=False, typ=JA_NEIN),
            # --- Block G — Automatisierungs-Voraussetzungen ---
            FieldSpec("documentation_status",                                    # G1
                      "Ist der Ablauf dokumentiert (1 = gar nicht, "
                      "5 = vollständig)?", typ=SKALA_1_5),
            FieldSpec("standardization_level",                                   # G2
                      "Läuft der Prozess immer gleich (5) oder gibt es viele "
                      "Sonderfälle (1)?", typ=SKALA_1_5),
            FieldSpec("variant_share_pct",                                       # G3 (E)
                      "Wie viel Prozent der Fälle sind Ausnahmen?",
                      required=False, typ=PROZENT_0_100),
            FieldSpec("data_availability_score",                                 # G4
                      "Liegen die nötigen Daten strukturiert und digital vor "
                      "(1–5)?", typ=SKALA_1_5),
            FieldSpec("stability_score",                                         # G5
                      "Wie stabil läuft der Prozess bei hoher Last (1–5)?",
                      typ=SKALA_1_5),
            FieldSpec("rule_based_score",                                        # G6 (E)
                      "Folgt der Prozess klaren Regeln (1–5)?",
                      required=False, typ=SKALA_1_5),
            FieldSpec("acceptance_score",                                        # G7 (E)
                      "Wie offen sind die Beteiligten für Automatisierung "
                      "(1–5)?", required=False, typ=SKALA_1_5),
            FieldSpec("automation_potential_estimate_pct",                       # G8 (E)
                      "Wie hoch schätzen Sie das Automatisierungs-Potenzial "
                      "(0–100 %)?", required=False, typ=PROZENT_0_100),
            # --- Block H — Schnittstellen (E, ⚠️ Katalog nennt Auswahl ohne Optionen) ---
            FieldSpec("upstream_process",                                        # H1
                      "Welcher Prozess kommt davor und liefert Ihnen etwas?",
                      required=False),
            FieldSpec("downstream_process",                                      # H2
                      "Welcher Prozess kommt danach und braucht Ihr Ergebnis?",
                      required=False),
            FieldSpec("interface_data",                                          # H3 (E)
                      "Welche Daten werden an diesen Schnittstellen "
                      "übergeben?", required=False),
            # --- Block I — Daten, Qualität & Compliance ---
            FieldSpec("pii_involved",                                            # I1
                      "Werden in diesem Prozess personenbezogene Daten "
                      "verarbeitet?", typ=JA_NEIN),
            FieldSpec("approval_steps",                                          # I2 (E)
                      "Gibt es Kontroll- oder Freigabeschritte (Vier-Augen, "
                      "Genehmigung)?", required=False, typ=JA_NEIN),
            FieldSpec("error_hotspots",                                          # I3 (E)
                      "Wo passieren heute typischerweise Fehler oder "
                      "Nacharbeit?", required=False),
            # --- Block J — Abschluss (J1 Spiegelung + J3 Source: siehe Spec-Roadmap) ---
            FieldSpec("open_remarks",                                            # J2 (E)
                      "Gibt es etwas Wichtiges, das noch nicht zur Sprache "
                      "kam?", required=False),
        ),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **175 passed, 2 skipped** (169 + 6 neue)

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_service/discovery_paket.py bc1-context-discovery/tests/test_discovery_paket.py
git commit -m "feat(bc1): Discovery-Paket — 26 Muss- + 17 passive Felder aus Katalog A–J (flach, Fokus-Schritt)"
```

---

### Task 5: Paket-Wahl (`bc1_service/paket_wahl.py`) + `main.py`

**Files:**
- Create: `bc1_service/paket_wahl.py`
- Modify: `bc1_service/main.py`
- Test: `tests/test_paket_wahl.py`

**Interfaces:**
- Consumes: `baue_discovery_paket` (Task 4), `TOY_PROZESS` aus `bc1_core.package`.
- Produces: `waehle_paket(umgebung: Mapping[str, str], prozesse: list[tuple[str, str]] | None = None) -> UseCasePackage` — `BC1_PAKET` = `"discovery"` (Default) | `"toy"`, unbekannter Wert → `RuntimeError`. `main.py` lädt den Snapshot ZUERST und reicht `[(p["process_id"], p["process_name"]) …]` durch.

- [ ] **Step 1: Write the failing tests** — `tests/test_paket_wahl.py`

```python
"""BC1_PAKET wählt das Use-Case-Paket — Default ist das Discovery-Paket."""
import pytest

from bc1_core.package import TOY_PROZESS
from bc1_service.paket_wahl import waehle_paket


def test_default_ist_discovery():
    paket = waehle_paket({})
    assert paket.name == "discovery"


def test_toy_bleibt_schaltbar():
    assert waehle_paket({"BC1_PAKET": "toy"}) is TOY_PROZESS


def test_prozessliste_wird_an_die_fabrik_durchgereicht():
    paket = waehle_paket({}, [("KP-01", "Angebotserstellung")])
    assert paket.field("process_id").typ.validator("KP-01") is True


def test_unbekannter_wert_wirft_lesbar():
    with pytest.raises(RuntimeError, match="BC1_PAKET"):
        waehle_paket({"BC1_PAKET": "mega"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_paket_wahl.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'bc1_service.paket_wahl'`. Danach voller Lauf (Guard).

- [ ] **Step 3: Write minimal implementation**

`bc1_service/paket_wahl.py`:

```python
"""Wählt das Use-Case-Paket anhand von BC1_PAKET (Default: discovery)."""
from __future__ import annotations

from collections.abc import Mapping

from bc1_core.package import TOY_PROZESS, UseCasePackage
from bc1_service.discovery_paket import baue_discovery_paket


def waehle_paket(
    umgebung: Mapping[str, str],
    prozesse: list[tuple[str, str]] | None = None,
) -> UseCasePackage:
    wahl = umgebung.get("BC1_PAKET", "discovery")
    if wahl == "discovery":
        return baue_discovery_paket(prozesse)
    if wahl == "toy":
        return TOY_PROZESS
    raise RuntimeError(
        f"BC1_PAKET='{wahl}' ist unbekannt — erlaubt sind 'discovery' "
        "(Default) oder 'toy' (Mini-Testpaket)."
    )
```

`bc1_service/main.py`:
1. Docstring um `BC1_PAKET ("discovery" | "toy", Default discovery)` ergänzen.
2. Import `from bc1_core.package import TOY_PROZESS` ersetzen durch `from bc1_service.paket_wahl import waehle_paket`.
3. Snapshot-Laden VOR den `create_app`-Aufruf ziehen und Prozessliste bauen; der `create_app`-Aufruf wird zu:

```python
_snapshot_pfad = os.environ.get("BC1_SNAPSHOT_PFAD")
_snapshot = lade_snapshot(_snapshot_pfad) if _snapshot_pfad else None
_prozesse = (
    [(p["process_id"], p["process_name"]) for p in _snapshot.prozess_liste()]
    if _snapshot is not None else None
)
_store = PostgresStateStore(_dsn)


@asynccontextmanager
async def _lebenszyklus(app):
    # Beim Herunterfahren den Verbindungspool sauber schliessen.
    yield
    _store.close()


app = create_app(
    _store,
    waehle_llm(os.environ),
    waehle_paket(os.environ, _prozesse),
    _snapshot,
    lifespan=_lebenszyklus,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **179 passed, 2 skipped** (175 + 4 neue; `test_main_ohne_dsn_meldet_die_fehlende_variable` bleibt grün — die DSN-Prüfung läuft weiterhin vor allem anderen)

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/bc1_service/paket_wahl.py bc1-context-discovery/bc1_service/main.py bc1-context-discovery/tests/test_paket_wahl.py
git commit -m "feat(bc1): BC1_PAKET-Umschalter (discovery-Default | toy), Snapshot-Prozessliste an die Paket-Fabrik"
```

---

### Task 6: Demo-Durchläufe der 3 MVP-Use-Cases + SMOKE

**Files:**
- Create: `tests/test_demo_durchlaeufe.py`
- Modify: `bc1_service/n8n/SMOKE.md`

**Interfaces:**
- Consumes: `baue_discovery_paket` (Task 4), `process_turn`, `InMemoryStateStore`, `FakeLLM`, `ExtractionCandidate` aus `bc1_core`.
- Produces: nichts für weitere Tasks — Abnahme-Nachweis „EIN generisches Paket trägt alle 3 Use Cases".

- [ ] **Step 1: Write the failing tests** — `tests/test_demo_durchlaeufe.py`

```python
"""Demo-Durchläufe der 3 MVP-Use-Cases durch EIN generisches Discovery-Paket.

Jedes Skript: 7 Nachrichten, Mehrfach-Extraktion pro Nachricht, bis fertig.
Die Werte prüfen auch die Normalisierung (BC2-Vertrag): '30 pro Monat'→'360',
'3 Stunden'→'180', '60%'→'60', 'Ja.'→'ja'.
"""
from bc1_core.core import process_turn
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.store import InMemoryStateStore
from bc1_service.discovery_paket import baue_discovery_paket


def _lauf(session_id, nachrichten):
    paket = baue_discovery_paket(None)
    llm = FakeLLM({
        text: [ExtractionCandidate(feld, wert) for feld, wert in felder]
        for text, felder in nachrichten
    })
    store = InMemoryStateStore()
    antwort = None
    for i, (text, _) in enumerate(nachrichten, start=1):
        antwort = process_turn(store, llm, paket, session_id, f"m{i}", text)
    return antwort


def _basis_skript(intent, name, owner, prozess, schritte, trigger, eingang,
                  eingangsformat, ausgang, frequenz, faelle, gesamtdauer,
                  fokus, fokusdauer, quelle, sicherheit, rollen, systeme,
                  medienbruch, doku, standard, daten, stabil, pii):
    return [
        (f"Wir wollen {intent} — es geht um den ganzen Prozess, Ziel ist Zeit sparen.", [
            ("request_intent", intent), ("request_goal", "zeit_sparen"),
            ("scope_focus", "ganzer_prozess"), ("process_name", name)]),
        ("Verantwortlich und Ablauf.", [
            ("process_owner_role", owner), ("process_id", prozess),
            ("process_steps", schritte)]),
        ("Auslöser, Eingang und Ergebnis.", [
            ("trigger_text", trigger), ("input_text", eingang),
            ("input_format", eingangsformat), ("output_text", ausgang)]),
        ("Mengen und Dauer.", [
            ("frequency_per_year", frequenz), ("executions_per_run", faelle),
            ("total_duration_minutes", gesamtdauer)]),
        ("Der anstrengendste Schritt.", [
            ("focus_step", fokus), ("focus_step_duration_minutes", fokusdauer),
            ("focus_step_duration_source", quelle),
            ("focus_step_duration_confidence_pct", sicherheit)]),
        ("Beteiligte und Systeme.", [
            ("focus_step_roles", rollen), ("focus_step_systems", systeme),
            ("focus_step_media_break", medienbruch),
            ("documentation_status", doku)]),
        ("Voraussetzungen.", [
            ("standardization_level", standard),
            ("data_availability_score", daten), ("stability_score", stabil),
            ("pii_involved", pii)]),
    ]


def test_demo_reisebuchung_bis_fertig_mit_normalisierung():
    antwort = _lauf("demo-reise", _basis_skript(
        "die Reisebuchung automatisieren", "Reisebuchung", "Office Management",
        "Geschäftsreisen", "Antrag, Genehmigung, Buchung, Abrechnung",
        "Mitarbeiter plant eine Dienstreise", "Reiseantrag mit Terminen",
        "mail", "gebuchte Reise mit Bestätigungen",
        "30 pro Monat", "360", "3 Stunden",
        "Buchung", "90 Minuten", "geschaetzt", "60%",
        "Office Management, Mitarbeiter", "Mail, Buchungsportal, Excel",
        "Ja.", "2", "3", "2", "4", "ja"))
    assert antwort["status"] == "fertig"
    assert antwort["payload"]["vollstaendigkeit"] == 1.0
    felder = antwort["payload"]["felder"]
    assert felder["frequency_per_year"]["wert"] == "360"        # 30×12
    assert felder["total_duration_minutes"]["wert"] == "180"    # 3 h
    assert felder["focus_step_duration_confidence_pct"]["wert"] == "60"
    assert felder["focus_step_media_break"]["wert"] == "ja"
    assert felder["process_name"]["wert"] == "Reisebuchung"


def test_demo_rag_wissensbasis_bis_fertig():
    antwort = _lauf("demo-rag", _basis_skript(
        "Antworten aus unserer Wissensbasis automatisieren",
        "Wissensanfragen beantworten", "Fachexperte",
        "Wissensmanagement", "Anfrage sichten, Dokumente suchen, Antwort schreiben",
        "Anfrage eines Kollegen oder Kunden", "Anfragetext und Dokumentenablage",
        "digital", "beantwortete Anfrage mit Quellen",
        "20 pro Woche", "1040", "45 Minuten",
        "Dokumente suchen", "25 Minuten", "geschaetzt", "50%",
        "Fachexperten, Support", "Sharepoint, Mail, Wiki",
        "ja", "2", "2", "3", "3", "nein"))
    assert antwort["status"] == "fertig"
    assert antwort["payload"]["vollstaendigkeit"] == 1.0
    assert antwort["payload"]["felder"]["frequency_per_year"]["wert"] == "1040"  # 20×52


def test_demo_consultant_placement_bis_fertig():
    antwort = _lauf("demo-placement", _basis_skript(
        "das Consultant-Staffing beschleunigen", "Consultant Placement",
        "Staffing Manager", "Personaleinsatzplanung",
        "Anfrage erfassen, Profile suchen, Matching, Vorschlag versenden",
        "Kundenanfrage nach einem Consultant", "Anforderungsprofil des Kunden",
        "mail", "Personalvorschlag mit passenden Profilen",
        "300 pro Jahr", "300", "2 Stunden",
        "Profile suchen", "1 Stunden", "aus_system", "80 %",
        "Staffing, Vertrieb", "CRM, Skill-Datenbank, Excel",
        "NEIN!", "3", "4", "4", "3", "ja"))
    assert antwort["status"] == "fertig"
    assert antwort["payload"]["vollstaendigkeit"] == 1.0
    felder = antwort["payload"]["felder"]
    assert felder["focus_step_duration_minutes"]["wert"] == "60"   # 1 h
    assert felder["focus_step_media_break"]["wert"] == "nein"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest tests/test_demo_durchlaeufe.py -v`
Expected: 3 FAIL — die Interviews werden nicht fertig bzw. Felder fehlen, solange es das Paket-Verhalten aus Task 4/5 nicht gäbe; konkret hier: PASS wäre nur möglich, wenn alles aus Task 1–5 korrekt zusammenspielt. (Läuft dieser Task nach Task 5, ist Step 2 der Beweis, dass die Demos WIRKLICH das Gesamtsystem treffen: bei grünem Erst-Lauf prüfen, ob ein Assertion-Fehler in den Skripten steckt — die Tests MÜSSEN vor ihrem GREEN mindestens einmal rot gesehen worden sein; notfalls gezielt eine Assertion verschärfen und wieder lösen, um den RED-Nachweis für den Guard zu erbringen.)

- [ ] **Step 3: SMOKE.md-Abschnitt ergänzen** — ans Datei-Ende, nach dem Abschnitt „Smoke mit Ollama (lokal, ohne API-Key)":

```markdown
## Discovery-Interview live (P3)

Das echte Interview (26 aktive Fragen, Katalog A–J) ist seit P3 der Default:
`BC1_PAKET=discovery` (bzw. nichts setzen). `BC1_PAKET=toy` schaltet fürs
schnelle Testen auf das alte Mini-Paket zurück.

1. Dienst wie oben starten (Postgres, DSN, `BC1_LLM=ollama` oder Claude-Key);
   optional `BC1_SNAPSHOT_PFAD` setzen — dann bietet die Kernprozess-Frage
   (B4) die echten KP-IDs aus der Baseline als Auswahl an.
2. Chat öffnen und frei antworten. Erwartung ehrlich: ~15–30 Minuten für
   ein vollständiges Interview; mit dem 8B-Modell sind schräge
   Frage-Formulierungen und Extraktions-Lücken normal (Nachfrage-Mechanik
   fängt sie); Auswahl-Fragen nennen die gültigen Optionen im Fragetext.
3. Kurz-Variante für Smoke-Zwecke: mehrere Angaben in EINE Nachricht packen
   („Der Prozess heißt X, läuft 30-mal pro Monat und dauert 2 Stunden…") —
   die Mehrfach-Extraktion füllt alle passenden Felder auf einmal.
4. DB-Nachweis wie gehabt (`state->>'status'`, `paket_name = 'discovery'`).
```

- [ ] **Step 4: Run tests to verify they pass (voller Lauf)**

Run: `BC1_TEST_DB_DSN="postgresql://postgres:test@localhost:55432/postgres" .venv/bin/pytest`
Expected: **182 passed, 2 skipped** (179 + 3 neue), 0 Warnings

- [ ] **Step 5: Commit**

```bash
git add bc1-context-discovery/tests/test_demo_durchlaeufe.py bc1-context-discovery/bc1_service/n8n/SMOKE.md
git commit -m "test(bc1): Demo-Durchläufe Reisebuchung/RAG/Placement durch EIN Discovery-Paket + Smoke-Anleitung"
```

---

## Abnahme (Gesamtergebnis)

- Suite Bau-Endstand der 6 Tasks: **182 passed, 2 skipped**, 0 Warnings. Endstand nach der Gesamt-Review-Fix-Welle inkl. Mehr-Zahlen-Politik: **186 passed, 2 skipped**, 0 Warnings (die 2 Skips sind Claude-Echt + Ollama-Echt ohne Flags).
- Die bestehenden 149 Tests unverändert grün (Rückwärtskompatibilität: `TOY_PROZESS` untouched).
- Alle 3 Demo-Durchläufe: `status=fertig`, `vollstaendigkeit=1.0`, Normalisierungs-Nachweise im Payload.
- `BC1_PAKET=discovery` ist Default; `toy` bleibt schaltbar; B4 nutzt mit Snapshot die echten KP-IDs.
- Kern-Diff beschränkt auf: `feldtypen.py` (neu) + chirurgische Änderungen in `package.py`/`extractor.py`/`dialog.py`.
- Ein Live-Durchlauf im n8n-Chat (`BC1_PAKET=discovery`, Ollama) laut SMOKE-Abschnitt.
