# -*- coding: utf-8 -*-
"""
Ableitung und Prüfung von Passwort-Hashes.

Verfahren
---------
PBKDF2-HMAC-SHA256 mit 600.000 Durchläufen und 16 Byte Zufallssalz je Passwort.

Begründung der Wahl (bewusst dokumentiert, weil sie später hinterfragt wird):

* **Warum überhaupt ein Ableitungsverfahren?** Ein gewöhnlicher Hash wie SHA-256
  ist schnell — das ist beim Passwortschutz ein Nachteil, weil es dem Angreifer
  ebenso hilft wie dem Server. PBKDF2 macht die Prüfung absichtlich teuer.
* **Warum PBKDF2 und nicht bcrypt/argon2?** Beide wären fachlich vorzuziehen,
  benötigen aber eine zusätzliche Abhängigkeit (``passlib``/``argon2-cffi``) und
  bei bcrypt eine kompilierte Erweiterung im Container. PBKDF2 liegt in der
  Standardbibliothek und ist nach BSI TR-02102-1 und NIST SP 800-132 zulässig.
  Für eine App mit einer zweistelligen Zahl von Konten ist das angemessen.
* **Warum 600.000 Durchläufe?** Das ist die OWASP-Empfehlung für
  PBKDF2-HMAC-SHA256. Die Zahl steht in :data:`DURCHLAEUFE` und wird im Hash
  mitgespeichert — ältere Hashes bleiben also gültig, wenn der Wert später
  erhöht wird.

Format
------
Ein Hash wird als eine Zeichenkette mit vier durch ``$`` getrennten Feldern
gespeichert::

    pbkdf2_sha256$600000$<salz-base64>$<abdruck-base64>

Das entspricht dem Format, das auch Django verwendet. Vorteil: Verfahren und
Kosten stehen im Datensatz selbst, ein Wechsel ist ohne Migration möglich.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

VERFAHREN = "pbkdf2_sha256"
DURCHLAEUFE = 600_000
SALZ_BYTES = 16
MINDESTLAENGE = 12


class PasswortFehler(ValueError):
    """Das gewählte Passwort erfüllt die Mindestanforderungen nicht."""


def pruefe_mindestanforderungen(passwort: str) -> None:
    """Prüft ein *neues* Passwort, bevor es abgelegt wird.

    Bewusst nur eine Längenregel und keine Zeichenklassen-Pflicht: Erzwungene
    Sonderzeichen führen erfahrungsgemäß zu kürzeren, schlechter merkbaren
    Passwörtern. Die Länge ist der wirksamere Hebel (NIST SP 800-63B).

    Raises:
        PasswortFehler: wenn das Passwort zu kurz ist oder nur aus Leerzeichen besteht.
    """
    if passwort is None or not passwort.strip():
        raise PasswortFehler("Das Passwort darf nicht leer sein.")
    if len(passwort) < MINDESTLAENGE:
        raise PasswortFehler(
            "Das Passwort muss mindestens %d Zeichen lang sein." % MINDESTLAENGE
        )


def hash_erzeugen(passwort: str, durchlaeufe: int = DURCHLAEUFE) -> str:
    """Erzeugt den zu speichernden Hash-Text zu einem Klartextpasswort.

    Args:
        passwort: Klartext. Wird nicht protokolliert und nicht zurückgegeben.
        durchlaeufe: Kostenparameter. Nur für Tests herabsetzen.

    Returns:
        Der vollständige Hash-Text im oben beschriebenen Format.
    """
    pruefe_mindestanforderungen(passwort)
    salz = secrets.token_bytes(SALZ_BYTES)
    abdruck = hashlib.pbkdf2_hmac("sha256", passwort.encode("utf-8"), salz, durchlaeufe)
    return "%s$%d$%s$%s" % (
        VERFAHREN,
        durchlaeufe,
        base64.b64encode(salz).decode("ascii"),
        base64.b64encode(abdruck).decode("ascii"),
    )


def hash_pruefen(passwort: str, gespeicherter_hash: str) -> bool:
    """Prüft ein eingegebenes Passwort gegen den gespeicherten Hash.

    Der Vergleich läuft über :func:`hmac.compare_digest` und damit in konstanter
    Zeit. Ein zeichenweiser Vergleich würde über die Antwortdauer verraten, wie
    viele Zeichen bereits stimmen.

    Ein fehlerhaft aufgebauter Hash-Text führt zu ``False`` und nicht zu einer
    Ausnahme: Ein beschädigter Datensatz soll die Anmeldung verweigern, nicht die
    Anwendung zum Absturz bringen.
    """
    if not passwort or not gespeicherter_hash:
        return False
    try:
        verfahren, durchlaeufe_text, salz_b64, abdruck_b64 = gespeicherter_hash.split("$")
        if verfahren != VERFAHREN:
            return False
        salz = base64.b64decode(salz_b64)
        erwartet = base64.b64decode(abdruck_b64)
        berechnet = hashlib.pbkdf2_hmac(
            "sha256", passwort.encode("utf-8"), salz, int(durchlaeufe_text)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(berechnet, erwartet)


def muss_neu_gehasht_werden(gespeicherter_hash: str) -> bool:
    """Meldet, ob ein Hash unter veralteten Parametern erzeugt wurde.

    Wird beim Anmelden ausgewertet: Stimmt das Passwort, ist der Hash aber mit
    weniger Durchläufen erzeugt worden, wird er im selben Zug erneuert. So wächst
    der Bestand ohne Zwangs-Passwortwechsel mit.
    """
    try:
        verfahren, durchlaeufe_text, _, _ = (gespeicherter_hash or "").split("$")
    except ValueError:
        return True
    return verfahren != VERFAHREN or int(durchlaeufe_text) < DURCHLAEUFE


def sitzungsschluessel_erzeugen() -> str:
    """Erzeugt einen kryptografisch zufälligen Sitzungsschlüssel (32 Byte).

    Liegt hier und nicht im Repository, damit alle Zufallsquellen der
    Benutzerverwaltung an einer Stelle stehen und geprüft werden können.
    """
    return secrets.token_urlsafe(32)


def schluessel_abdruck(sitzungsschluessel: str) -> str:
    """Bildet den in der Datenbank gespeicherten Abdruck eines Sitzungsschlüssels.

    Ein einfacher SHA-256 genügt hier — anders als beim Passwort ist der
    Ausgangswert bereits 256 Bit Zufall und nicht erratbar. Ein teures Verfahren
    würde nur jede Anfrage verlangsamen.
    """
    return hashlib.sha256(sitzungsschluessel.encode("utf-8")).hexdigest()
