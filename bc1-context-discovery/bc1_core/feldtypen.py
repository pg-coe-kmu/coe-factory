"""Deklarative Feldtypen nach den Antworttypen des BC0-Fragenkatalogs.

Vertrag (Spec P3, BC2-relevant): normalisiere() ist TOTAL — wirft nie,
Unparsebares kommt unverändert zurück und fällt dann in der Validierung
durch (bestehende Nachfrage-Mechanik). Gespeichert wird der normalisierte
Wert; Werte bleiben Strings (Wire-Format).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Feldtyp:
    name: str
    validator: Callable[[str], bool]
    normalisiere: Callable[[str], str]


# Deutsche Tausendergruppierung (z. B. "1.000", "12.345,5") VOR der einfachen
# Zahl versuchen (Codex I4) — sonst liest float() den Punkt als Dezimaltrenner.
# Führende Gruppe [1-9]\d{0,2} statt \d{1,3} (Verifikations-Important): eine
# führende "0"-Gruppe ("0.999") ist keine Tausendertrennung — niemand
# schreibt "0 Tausend 999", das ist die Dezimalzahl 0,999.
# (?!\d) nach der Tausendergruppe (Verifikations-Minor): "1.0000" darf nicht
# als "1.000" + übrig gebliebene "0" (= zwei Zahlen) gelesen werden — die
# Gruppe darf nicht matchen, wenn direkt eine weitere Ziffer folgt. Ein
# nachfolgendes Komma-Dezimal ("1.234,5") bleibt davon unberührt (Komma ist
# keine Ziffer).
_ZAHL_TOKEN = r"-?[1-9]\d{0,2}(?:\.\d{3})+(?!\d)(?:,\d+)?|-?\d+(?:[.,]\d+)?"
_ZAHL_MUSTER = re.compile(_ZAHL_TOKEN)
_TAUSENDER_MUSTER = re.compile(r"^-?[1-9]\d{0,2}(?:\.\d{3})+(?!\d)(?:,\d+)?$")


def _zahl_aus_token(token: str) -> float:
    if _TAUSENDER_MUSTER.match(token):
        return float(token.replace(".", "").replace(",", "."))
    return float(token.replace(",", "."))


def _zahl_in(text: str) -> float | None:
    treffer = _ZAHL_MUSTER.findall(text)
    # Mehr als eine Zahl im Text (z. B. "1 Stunde 30 Minuten", "30-45 Minuten")
    # ist nicht eindeutig normalisierbar — dann NICHT weiterreichen, sondern
    # unverändert zurück (Gesamt-Review I2: Nachfrage statt Rateversuch).
    if len(treffer) != 1:
        return None
    zahl = _zahl_aus_token(treffer[0])
    # Riesenzahlen (z. B. 400-stellig) werden zu inf — dann NICHT weiterreichen,
    # sonst wirft _formatiere() bei int(inf) einen OverflowError (Total-Vertrag).
    return zahl if math.isfinite(zahl) else None


def _nur_zahl(text: str) -> bool:
    return re.fullmatch(rf"\s*(?:{_ZAHL_TOKEN})\s*", text) is not None


def _formatiere(zahl: float) -> str:
    return str(int(zahl)) if zahl == int(zahl) else str(zahl)


_PERIODEN = {"woche": 52.0, "monat": 12.0, "jahr": 1.0}
_PERIODE_MUSTER = re.compile(r"\b(woche|monat|jahr)\b")
# Codex-Residuum (Fix-Welle 5): ".search()" auf "pro\s+(\w+)" prüfte bisher
# nur das ERSTE "pro"-Vorkommen — ein zweites ("pro Woche und pro
# Mitarbeiter") sowie Interpunktion direkt nach "pro" ohne \s+ ("pro/Tag")
# rutschten am Muster vorbei durch. Fix: negativer Lookahead auf JEDES
# "pro" im Text — matcht nur dann NICHT, wenn "pro" von \s+ und einer der
# drei bekannten Perioden gefolgt wird; jede andere Fortsetzung (zweites
# "pro", unbekanntes Wort, direkte Interpunktion) triggert die Ablehnung.
_PRO_MUSTER = re.compile(r"\bpro\b(?!\s+(?:woche|monat|jahr)\b)")


def _normalisiere_zahl(wert: str) -> str:
    zahl = _zahl_in(wert)
    if zahl is None:
        return wert
    text = wert.lower()
    # Codex I4: "pro <Wort>" mit unbekanntem Wort (z. B. "pro Tag") ist eine
    # explizit genannte, aber nicht unterstützte Periode — ablehnen, auch wenn
    # zufällig woanders im Text ein bekanntes Periodenwort steht.
    if _PRO_MUSTER.search(text):
        return wert
    perioden_treffer = set(_PERIODE_MUSTER.findall(text))
    # Fix-Welle 6 (M2): ZWEI verschiedene Periodenwörter im selben Text (z. B.
    # "pro Woche pro Monat") sind beide je für sich bekannt — der pro-Guard
    # oben greift dann nicht. Bisher gewann stillschweigend die ERSTE per
    # .search() gefundene Periode; das ist eine geratene statt eine
    # nachgefragte Mehrdeutigkeit (gegen die Policy). set() statt Zählung,
    # damit dieselbe Periode zweimal (keine Mehrdeutigkeit) weiter akzeptiert
    # bleibt — nur > 1 DISTINCT Periode lehnt ab.
    if len(perioden_treffer) > 1:
        return wert
    if perioden_treffer:
        produkt = zahl * _PERIODEN[perioden_treffer.pop()]
        # Auch nach der Multiplikation total bleiben (Codex I3): Riesenzahlen
        # können hier erst zu inf überlaufen — dann unverändert zurück.
        return _formatiere(produkt) if math.isfinite(produkt) else wert
    return _formatiere(zahl) if _nur_zahl(wert) else wert


def _normalisiere_minuten(wert: str) -> str:
    zahl = _zahl_in(wert)
    if zahl is None:
        return wert
    text = wert.lower()
    # Codex Minor: Einheit direkt an die Zahl angehängt ("1,5h", "45min") hat
    # keine \b-Wortgrenze zwischen Ziffer und Buchstabe — zusätzlich per
    # Lookbehind auf eine direkt vorangehende Ziffer matchen.
    if re.search(r"(?:\b|(?<=\d))(stunden?|std\.?|h)\b", text):
        produkt = zahl * 60
        return _formatiere(produkt) if math.isfinite(produkt) else wert
    if re.search(r"(?:\b|(?<=\d))(minuten?|min\.?)\b", text) or _nur_zahl(wert):
        return _formatiere(zahl)
    return wert


def _entferne_rand(wert: str) -> str:
    return wert.strip().strip('.!?,;:„“”‘’"\' ').strip()


def _normalisiere_ja_nein(wert: str) -> str:
    kern = _entferne_rand(wert).lower()
    return kern if kern in ("ja", "nein") else wert


def _normalisiere_prozent(wert: str) -> str:
    kern = wert.strip()
    if kern.endswith("%"):
        kern = kern[:-1].strip()
    if not _nur_zahl(kern):
        return wert
    # Verifikations-Critical: derselbe Token-Parser wie ZAHL/MINUTEN
    # (_zahl_aus_token) statt rohem float() — sonst liest float() bei
    # deutscher Tausendergruppierung mit Dezimalstelle ("1.234,5" →
    # "1.234.5" nach dem naiven Komma-Ersatz) und wirft ValueError.
    zahl = _zahl_aus_token(kern)
    if not math.isfinite(zahl):
        return wert
    # Kanonisch formatieren wie _formatiere() (Codex I5): "1,5%" und "1.5%"
    # sind derselbe Wert, dürfen aber nicht als unterschiedliche Strings
    # gespeichert werden (sonst false-UNKLAR bei nachgelagerten Vergleichen).
    return _formatiere(zahl)


def _normalisiere_liste(wert: str) -> str:
    teile = [t.strip() for t in re.split(r"[,\n]", wert) if t.strip()]
    return ", ".join(teile) if teile else wert


def _ist_skala(wert: str) -> bool:
    return re.fullmatch(r"[1-5]", wert.strip()) is not None


def _ist_prozent(wert: str) -> bool:
    return _nur_zahl(wert) and 0 <= _zahl_aus_token(wert.strip()) <= 100


# Fix-Welle 6 (M1): über denselben Token-Parser wie _ist_prozent
# (_zahl_aus_token) statt rohem float() — sonst wirft der Validator bei
# deutscher Tausendergruppierung mit Dezimalstelle ("1.234,5" -> "1.234.5"
# nach dem naiven Komma-Ersatz) einen ValueError.
ZAHL = Feldtyp("zahl", lambda w: _nur_zahl(w) and _zahl_aus_token(w.strip()) >= 0,
               _normalisiere_zahl)
MINUTEN = Feldtyp("minuten", lambda w: _nur_zahl(w) and _zahl_aus_token(w.strip()) >= 0,
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
