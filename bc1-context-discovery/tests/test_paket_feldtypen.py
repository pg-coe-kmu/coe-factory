from bc1_service.paket_feldtypen import (PROZENT_GANZ_0_100, baue_system_typ,
                                         entferne_snn, kanonisiere_snn, snn_tokens)

BEKANNT = frozenset({"S-01", "S-02"})


def test_erkennt_eingebettete_und_kleingeschriebene_ids():
    assert snn_tokens("SAP (s-01) und DATEV S-02") == ["S-01", "S-02"]
    assert snn_tokens("MS-01 ist kein Treffer") == []


def test_normalisierung_kanonisiert_und_wendet_listenregel_an():
    typ = baue_system_typ(BEKANNT)
    assert typ.normalisiere("sap (s-01),  datev") == "sap (S-01), datev"


def test_bekannte_id_ist_gueltig_unbekannte_nicht():
    typ = baue_system_typ(BEKANNT)
    assert typ.validator(typ.normalisiere("SAP (s-01)")) is True
    assert typ.validator(typ.normalisiere("Eigenbau (S-99)")) is False


def test_leerwert_scheitert_am_komponierten_listen_validator():
    typ = baue_system_typ(BEKANNT)
    assert typ.validator("") is False
    assert typ.validator("   ") is False


def test_freitext_ohne_id_bleibt_gueltig():
    typ = baue_system_typ(BEKANNT)
    assert typ.validator(typ.normalisiere("SAP, Excel")) is True


def test_prozent_ganz_lehnt_nachkommastellen_ab():
    typ = PROZENT_GANZ_0_100
    assert typ.validator(typ.normalisiere("70 %")) is True
    assert typ.normalisiere("70 %") == "70"
    assert typ.validator(typ.normalisiere("70,5")) is False    # sonst Dauer-503
    assert typ.validator(typ.normalisiere("101")) is False


def test_prozent_ganz_wirft_nie_auch_unnormalisiert():
    # Feldtyp-Vertrag: Validatoren sind total. '70,5' UNNORMALISIERT ist der
    # Stolperstein — PROZENT_0_100 haelt es fuer gueltig, Decimal wirft darauf.
    for roh in ("70,5", "abc", "", "1.234,5", "NaN", "-5", "1e400", "70%%"):
        assert typ_wirft_nicht(PROZENT_GANZ_0_100, roh)


def typ_wirft_nicht(typ, wert) -> bool:
    try:
        typ.validator(wert)
        typ.validator(typ.normalisiere(wert))
        return True
    except Exception:                                   # noqa: BLE001 — Testprobe
        return False


def test_entfernung_ist_deterministisch_und_trimmt_die_reste():
    assert entferne_snn("SAP (S-99)", ["S-99"]) == "SAP"
    assert entferne_snn("S-99", ["S-99"]) == ""
    assert entferne_snn("SAP (S-01), Excel (S-99)", ["S-99"]) == "SAP (S-01), Excel"
    assert entferne_snn("SAP (S-01)", ["S-99"]) == "SAP (S-01)"


def test_entfernung_behandelt_semikolon_als_trenner_gleichwertig_zum_komma():
    # Fix-Runde 1: Semikolon war als ERSTER Trenner der Konsolidierungsregel nicht
    # gleichwertig zum Komma behandelt — doppelter Trenner blieb stehen.
    assert entferne_snn("SAP; S-01; DATEV", ["S-01"]) == "SAP; DATEV"
