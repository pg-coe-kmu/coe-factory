"""Gemeinsame Vorbereitung für die Trigger-Tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# app.py und eingang.py liegen eine Ebene ueber tests/ und werden flach
# importiert (wie bei BC0). Der Container legt sie nach /app.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Vor dem Import von app.py setzen: der Lebenszyklus verweigert sonst den Start.
# Ein bewusst anderer Wert als der echte — faellt der Testschluessel je in ein
# Protokoll, ist nichts verloren.
TEST_TOKEN = "test-schluessel-nicht-echt"
os.environ["BC2_TRIGGER_TOKEN"] = TEST_TOKEN
# DATABASE_URL bleibt leer: die Tests schieben ein SpeicherEingangsbuch unter,
# es wird nie eine Verbindung aufgebaut.
os.environ.pop("DATABASE_URL", None)

from app import erzeuge_app  # noqa: E402
from eingang import SpeicherEingangsbuch  # noqa: E402


@pytest.fixture
def buch() -> SpeicherEingangsbuch:
    return SpeicherEingangsbuch()


@pytest.fixture
def client(buch):
    from fastapi.testclient import TestClient

    # with-Block, damit der Lebenszyklus (und damit der Start-Abgleich)
    # tatsaechlich laeuft — sonst bliebe genau der ungeprueft.
    with TestClient(erzeuge_app(buch)) as c:
        yield c


@pytest.fixture
def token() -> str:
    return TEST_TOKEN


@pytest.fixture
def kopf() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def paket() -> dict:
    """Eine gültige Nutzlast, wie sie im Vertrag als Beispiel steht."""
    return {
        "paket_id": "PKT-2026-0007",
        "company_id": "NOROAI",
        "uebergeben_am": "2026-09-10T14:32:11+02:00",
        "teilprozesse": ["KP-02.TP-1", "KP-02.TP-3", "KP-04.TP-2"],
        "anfrage_id": "A-2026-01",
    }
