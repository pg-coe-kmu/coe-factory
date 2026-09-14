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
    # Zellen am "|" zerlegen und strippen (Review 2, M12): "100%", "100  %" und
    # Leerraum hinter dem letzten "|" duerfen den Abgleich nicht kippen.
    abschnitt = README.read_text(encoding="utf-8").split("## PII-Filter", 1)[1].split("\n## ", 1)[0]
    quoten: dict[str, int] = {}
    for zeile in abschnitt.splitlines():
        zellen = [z.strip() for z in zeile.strip().strip("|").split("|")]
        if len(zellen) < 4:
            continue
        prozent = re.fullmatch(r"(\d+)\s*%", zellen[-1])
        if prozent:
            assert zellen[0] not in quoten, f"Klasse doppelt im README: {zellen[0]}"
            quoten[zellen[0]] = int(prozent.group(1))
    return quoten


def test_quote_je_klasse_entspricht_der_readme_tabelle():
    assert _quoten_gemessen() == _quoten_readme()


def test_keine_fehltreffer_auf_pii_freien_interviewsaetzen():
    fehltreffer = [satz for satz in NEGATIV if ersetze_pii(satz) != satz]
    assert fehltreffer == []
