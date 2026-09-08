"""Anhang A (Rev. 12): die drei Use-Case-Testprofile sind aus dem Repo reproduzierbar."""
from bc1_core.store import InMemoryStateStore
from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket
from bc1_service.use_case_testprofile import FAELLE, fuehre_interview

NORO = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"
KONTEXT = Bc0Kontext(NORO, (("KP-05.TP-1", "Wissenstransfer"),
                            ("KP-06.TP-1", "Consulting-Matching"),
                            ("KP-06.TP-2", "Reise- und Einsatzplanung")),
                     tuple(f"S-0{i}" for i in range(1, 7)))


def _antworten():
    paket = baue_discovery_paket(kontext=KONTEXT)
    return [(fall, fuehre_interview(InMemoryStateStore(), paket, fall, company_id=NORO))
            for fall in FAELLE]


def test_jeder_fall_endet_fertig_und_vollstaendig():
    for fall, antwort in _antworten():
        assert antwort["status"] == "fertig", fall.session_id
        assert antwort["payload"]["vollstaendigkeit"] == 1.0, fall.session_id
