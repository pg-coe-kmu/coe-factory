"""BC1_PAKET wählt das Use-Case-Paket — Default ist das Discovery-Paket."""
import pytest

from bc1_core.package import TOY_PROZESS
from bc1_service.discovery_paket import Bc0Kontext
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


def test_kontext_wird_an_die_fabrik_durchgereicht():
    kontext = Bc0Kontext(
        company_id="11111111-1111-1111-1111-111111111111",
        teilprozesse=(("KP-01.TP-1", "Erfassen"),),
        system_ids=("S-01",))
    paket = waehle_paket({}, kontext=kontext)
    assert paket.field("focus_step").identitaetskritisch is True
