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
