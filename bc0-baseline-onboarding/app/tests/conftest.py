# -*- coding: utf-8 -*-
"""
Gemeinsame Vorbereitung der Tests.

Dieses Modul wird von pytest vor allen Testdateien geladen. Es sorgt für genau
eine Sache, die aber wesentlich ist: **Die Tests dürfen unter keinen Umständen
die Produktivdatenbank berühren.**

Die Gefahr ist real. ``app.py`` lädt beim Import eine ``.env`` aus dem
Anwendungsverzeichnis, und auf dem Server steht dort die Verbindung zu Supabase.
Würde ein Test unbedacht importieren, liefe er gegen die echten Daten. Das
Einlesen geschieht über ``os.environ.setdefault`` — ein bereits gesetzter Wert
wird also nicht überschrieben. Genau das nutzen wir: ``DATABASE_URL`` wird hier
auf eine leere Zeichenkette gesetzt, bevor ``app`` importiert werden kann. Die
Anwendung sieht damit „kein PostgreSQL" und arbeitet auf einer SQLite-Datei in
einem temporären Verzeichnis.
"""

import os
import tempfile

# Muss vor jedem Import von `app` geschehen — siehe Modul-Docstring.
os.environ["DATABASE_URL"] = ""
os.environ["BC0_DB"] = os.path.join(tempfile.mkdtemp(prefix="bc0_test_"), "test.db")
os.environ["BELEGE_DIR"] = tempfile.mkdtemp(prefix="bc0_belege_")

# Der Testclient spricht über HTTP, nicht HTTPS. Ohne diesen Schalter würde der
# Browser-Cookie-Mechanismus das Sitzungs-Cookie verwerfen (secure=True).
# Im Betrieb wird die Variable nicht gesetzt — dort gilt die sichere Vorbelegung.
os.environ["BC0_COOKIE_UNSICHER"] = "1"
