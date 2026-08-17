# -*- coding: utf-8 -*-
"""
bc0_auth — Benutzerverwaltung, Anmeldung und Rechteprüfung für die BC0-Onboarding-App.

Zweck
-----
Bis zum 10.08.2026 war die BC0-App ohne Anmeldung erreichbar und schreibbar. Dieses
Paket schließt die Lücke und setzt zugleich die im Meeting vom 10.08.2026 beschlossene
Rollentrennung um:

    Benutzer  — sieht ausschließlich die ihm zugeordneten Mandanten,
                darf dort anlegen, ändern und speichern.
    Admin     — sieht alle Mandanten, darf zusätzlich löschen und freigeben.

Aufbau (Schichten, von innen nach außen)
----------------------------------------
    modelle.py          Fachliche Typen ohne technische Abhängigkeiten (Rolle, Benutzer, Sitzung)
    passwoerter.py      Ableitung und Prüfung von Passwort-Hashes
    repository.py       Persistenz — der einzige Ort, an dem SQL für Benutzer und Sitzungen steht
    dienst.py           Anwendungsfälle: anmelden, abmelden, Sitzung auflösen, Benutzer anlegen
    abhaengigkeiten.py  Anbindung an FastAPI (Depends-Funktionen)
    routen.py           HTTP-Schnittstelle (APIRouter)

Die Abhängigkeiten zeigen ausschließlich nach innen: `routen` kennt `dienst`,
`dienst` kennt `repository` und `passwoerter`, alle kennen `modelle`. `modelle`
kennt niemanden. Damit sind die inneren Schichten ohne FastAPI und ohne Datenbank
testbar (siehe `tests/test_auth.py`).

Sprachregel
-----------
Fachliche Begriffe stehen auf Deutsch (Benutzer, Rolle, Sitzung, Freigabe) — analog
zu den Spaltennamen des Schemas v1.1.1 und zur Projektdokumentation. Technische
Begriffe der verwendeten Bibliotheken bleiben in ihrer Originalform (Request, Router,
Depends). Diese Regel gilt für alle ab dem 10.08.2026 neu angelegten Module.

Verbindung zur Datenbank
------------------------
Dieses Paket öffnet keine eigene Datenbankverbindung. Es bekommt die Verbindungs-
fabrik der Anwendung im Konstruktor übergeben (Konstruktor-Injektion). Dadurch
entsteht kein Import-Zyklus mit `app.py`, und die Tests können eine In-Memory-
Datenbank einsetzen, ohne die Anwendung zu starten.

Stand: 10.08.2026 · BC0 · Simeon Ehmer
"""

from .modelle import Rolle, Benutzer, Sitzung, AnmeldeFehler, RechteFehler
from .dienst import AuthDienst

__all__ = [
    "Rolle",
    "Benutzer",
    "Sitzung",
    "AnmeldeFehler",
    "RechteFehler",
    "AuthDienst",
]
