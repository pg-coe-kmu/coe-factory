"""Deklarative Feldtypen nach den Antworttypen des BC0-Fragenkatalogs.

Vertrag (Spec P3, BC2-relevant): normalisiere() ist TOTAL — wirft nie,
Unparsebares kommt unverändert zurück und fällt dann in der Validierung
durch (bestehende Nachfrage-Mechanik). Gespeichert wird der normalisierte
Wert; Werte bleiben Strings (Wire-Format).

Auch kurzform() ist TOTAL: wirft nie, liefert `str | None`. Den reinen Wert
liefert sie nur, wenn die GANZE Nachricht die Kurzform ist, sonst `None`
(Aufrufer ohne try/except).
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class Feldtyp:
    name: str
    validator: Callable[[str], bool]
    normalisiere: Callable[[str], str]
    kurzform: Callable[[str], str | None] | None = None
    antwortform: str = field(kw_only=True)
    # Nur AUSWAHL setzt sie: die Optionen als Daten (fuer das Pruefwerkzeug).
    optionen: tuple[str, ...] = field(default=(), kw_only=True)
    # (Option, Name)-Paare; als Tupel, damit Feldtyp hashbar bleibt.
    namen: tuple[tuple[str, str], ...] = field(default=(), kw_only=True)
    # Nur ZAHL und MINUTEN setzen es: eine nackte Zahl gilt nur, wenn die Person sie selbst
    # schreibt (Kurzform); als KI-Kandidat wird sie verworfen (Spec 2, „Fester Schutz“).
    nackte_zahl_nur_von_person: bool = field(default=False, kw_only=True)
    # Nur ZAHL und MINUTEN setzen sie: Nennt die Nachricht selbst einen Zeitraum bzw. eine
    # Zeiteinheit? Ein KI-Wert gilt nur dann (Spec 2, „Feste Sperren“ (b)).
    nennt_einheit: Callable[[str], bool] | None = field(default=None, kw_only=True)


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
_TAUSENDER_MUSTER = re.compile(r"^-?[1-9]\d{0,2}(?:\.\d{3})+(?!\d)(?:,\d+)?$")


def _zahl_aus_token(token: str) -> float:
    if _TAUSENDER_MUSTER.match(token):
        return float(token.replace(".", "").replace(",", "."))
    return float(token.replace(",", "."))


def _nur_zahl(text: str) -> bool:
    return re.fullmatch(rf"\s*(?:{_ZAHL_TOKEN})\s*", text) is not None


# Die nackte Zahl bei Häufigkeit und Dauer (Vertrag D1/E1): ganze Eingabe genau eine Zahl,
# höchstens „.“/„!“ am Ende. Kurzform und Normalisierer teilen sie.
_NACKTE_ZAHL_MUSTER = re.compile(rf"({_ZAHL_TOKEN})[.!]?")


def ist_nackte_zahl(text: str) -> bool:
    return _NACKTE_ZAHL_MUSTER.fullmatch(text.strip()) is not None


# Spec 2 „Feste Sperren“ (b): Zeitraum-Wortstämme im Vergleichsschlüssel (ä -> ae), damit
# auch „wöchentlich“ und „jährlich“ zählen.
_ZEITRAUM_STAEMME = ("woch", "woech", "monat", "jahr", "jaehr")


def _nennt_zeitraum(text: str) -> bool:
    schluessel = vergleichsschluessel(text)
    return any(stamm in schluessel for stamm in _ZEITRAUM_STAEMME)


# Spec 2 „Feste Sperren“ (b): „minut“ und „stund“ als Stamm („halbe Stunde“); die Kürzel
# min, std und h nur als eigenes Wort bzw. direkt an einer Zahl („1,5h“).
_ZEITEINHEIT_MUSTER = re.compile(r"minut|stund|(?<![a-z])(?:min|std|h)(?![a-z])")


def _nennt_zeiteinheit(text: str) -> bool:
    return _ZEITEINHEIT_MUSTER.search(vergleichsschluessel(text)) is not None


def _formatiere(zahl: float) -> str:
    return str(int(zahl)) if zahl == int(zahl) else str(zahl)


_PERIODEN = {"woche": 52.0, "monat": 12.0, "jahr": 1.0}


def _normalisiere_zahl(wert: str) -> str:
    # Spec 3.4: nur die GANZE Eingabe in der geschlossenen Grammatik; sonst unveraendert.
    treffer = _HAEUFIGKEIT_MUSTER.fullmatch(wert.strip())
    if treffer:
        produkt = _zahl_aus_token(treffer.group(1)) * _PERIODEN[treffer.group(2).lower()]
        # Auch nach der Multiplikation total bleiben (Codex I3): Riesenzahlen
        # können hier erst zu inf überlaufen — dann unverändert zurück.
        return _formatiere(produkt) if math.isfinite(produkt) else wert
    # Nackte Zahl (Vertrag D1: „300“ = pro Jahr).
    nackt = _NACKTE_ZAHL_MUSTER.fullmatch(wert.strip())
    if nackt is None:
        return wert
    zahl = _zahl_aus_token(nackt.group(1))
    return _formatiere(zahl) if math.isfinite(zahl) else wert


def _normalisiere_minuten(wert: str) -> str:
    # Spec 3.4: nur die GANZE Eingabe in der geschlossenen Grammatik; sonst unveraendert.
    treffer = _MINUTEN_MUSTER.fullmatch(wert.strip())
    if treffer:
        zahl = _zahl_aus_token(treffer.group(1))
        if treffer.group(2).lower().startswith("m"):
            return _formatiere(zahl) if math.isfinite(zahl) else wert
        produkt = zahl * 60
        return _formatiere(produkt) if math.isfinite(produkt) else wert
    # Nackte Zahl (Vertrag E1: „40“ = Minuten).
    nackt = _NACKTE_ZAHL_MUSTER.fullmatch(wert.strip())
    if nackt is None:
        return wert
    zahl = _zahl_aus_token(nackt.group(1))
    return _formatiere(zahl) if math.isfinite(zahl) else wert


# Näherungswörter, gemeinsam für ANZAHL und die Kurzformen.
_NAEHERUNGSWOERTER = (
    r"(?:etwa|ca\.?|circa|ungefähr|ungefaehr|rund|im schnitt|durchschnittlich)\s+"
)
# Spec 3.4: EINE Grammatik fuer Haeufigkeit mit Periode (ganze Eingabe, `fullmatch`);
# Kurzform und Normalisierer teilen sie. Die nackte Zahl (Vertrag D1) nehmen beide
# zusaetzlich an (_NACKTE_ZAHL_MUSTER). Wortverbindungen brauchen Leerraum davor und danach.
_HAEUFIGKEIT_MUSTER = re.compile(
    rf"(?:{_NAEHERUNGSWOERTER})?({_ZAHL_TOKEN})(?:(?:\s*|-)(?:mal|x))?"
    r"(?:\s+(?:pro|im|je|in\s+der|die|den|das)\s+|\s*/\s*)(woche|monat|jahr)[.!]?",
    re.IGNORECASE)
# Spec 3.4: EINE Grammatik fuer Dauer mit Einheit (ganze Eingabe, `fullmatch`), gemeinsam
# fuer Kurzform und Normalisierer; die nackte Zahl (Vertrag E1) nehmen beide zusaetzlich an.
_MINUTEN_MUSTER = re.compile(
    rf"(?:{_NAEHERUNGSWOERTER})?({_ZAHL_TOKEN})\s*(minuten?|min|stunden?|std|h)[.!]?",
    re.IGNORECASE)
# Reine Anzahl ohne Periode (z. B. Faelle je Durchlauf): ein einziges Muster per
# fullmatch — jede Periode ("pro Woche", "im Monat"), Einheit oder zweite Zahl
# bleibt damit unpassend und faellt in der Validierung durch. Seit 25.10. (C1a (4b)):
# „ca" auch ohne Punkt, am Ende hoechstens ein „." oder „!" — „?" bleibt eine Nachfrage.
_ANZAHL_MUSTER = re.compile(
    rf"\s*(?:{_NAEHERUNGSWOERTER})?"
    rf"({_ZAHL_TOKEN})"
    rf"(?:\s+(?:fall|fälle|faelle|vorgang|vorgänge|vorgaenge|stück|stueck))?"
    rf"(?:\s+(?:je|pro)\s+durchlauf)?[.!]?\s*", re.IGNORECASE)


def _normalisiere_anzahl(wert: str) -> str:
    treffer = _ANZAHL_MUSTER.fullmatch(wert)
    if treffer is None:
        return wert
    zahl = _zahl_aus_token(treffer.group(1))
    return _formatiere(zahl) if math.isfinite(zahl) else wert


def _kurzform_anzahl(wert: str) -> str | None:
    treffer = _ANZAHL_MUSTER.fullmatch(wert)
    return treffer.group(1) if treffer else None


def _entferne_rand(wert: str) -> str:
    return wert.strip().strip('.!,;:„“”‘’"\' ').strip()


_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"})


def _schluessel_ohne_rand(text: str) -> str:
    klein = unicodedata.normalize("NFC", text).casefold().translate(_UMLAUTE)
    return re.sub(r"[\s_-]+", " ", klein)


def _schluessel(text: str) -> str:
    """Vergleichsschluessel fuer Auswahl-Eingaben, Optionen, Namen, Synonyme (Spec 3.3).

    NFC, casefold (ß -> ss), ä/ö/ü -> ae/oe/ue, „_“, „-“ und Leerraum zu EINEM
    Leerzeichen, Raender wie `_entferne_rand` (also ohne „?“: ein Text mit „?“
    trifft keine Option). Die Kurzform nutzt den Schluessel ohne Raender, weil sie
    ihre engen Raender (hoechstens ein „.“/„!“) vorher selbst prueft."""
    return _entferne_rand(_schluessel_ohne_rand(text))


# Oeffentlicher Name fuer Aufrufer ausserhalb dieses Moduls (Pruefwerkzeug).
vergleichsschluessel = _schluessel


def _normalisiere_ja_nein(wert: str) -> str:
    kern = _entferne_rand(wert).lower()
    return kern if kern in ("ja", "nein") else wert


def _kurzform_ja_nein(wert: str) -> str | None:
    treffer = re.fullmatch(r"(ja|nein)[.!]?", wert.strip(), re.IGNORECASE)
    return treffer.group(1).lower() if treffer else None


# Spec 3.4: EINE Grammatik fuer Kurzform und Normalisierer (ganze Eingabe, `fullmatch`).
_PROZENT_MUSTER = re.compile(
    rf"(?:{_NAEHERUNGSWOERTER})?({_ZAHL_TOKEN})(?:\s*%|\s+prozent)?[.!]?", re.IGNORECASE)


def _normalisiere_prozent(wert: str) -> str:
    treffer = _PROZENT_MUSTER.fullmatch(wert.strip())
    if treffer is None:
        return wert
    kern = treffer.group(1)
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


_SKALA_MUSTER = re.compile(r"([1-5])[.!]?")


def _normalisiere_skala(wert: str) -> str:
    treffer = _SKALA_MUSTER.fullmatch(wert.strip())
    return treffer.group(1) if treffer else wert.strip()


def _kurzform_skala(wert: str) -> str | None:
    treffer = _SKALA_MUSTER.fullmatch(wert.strip())
    return treffer.group(1) if treffer else None


def _kurzform_prozent(wert: str) -> str | None:
    treffer = _PROZENT_MUSTER.fullmatch(wert.strip())
    return treffer.group(1) if treffer else None


def _kurzform_minuten(wert: str) -> str | None:
    treffer = _MINUTEN_MUSTER.fullmatch(wert.strip())
    if treffer:
        return f"{treffer.group(1)} {treffer.group(2)}"
    # Spec 2 „Fester Schutz“: schreibt die Person genau eine Zahl, gilt sie (Vertrag).
    nackt = _NACKTE_ZAHL_MUSTER.fullmatch(wert.strip())
    return nackt.group(1) if nackt else None


def _kurzform_haeufigkeit(wert: str) -> str | None:
    treffer = _HAEUFIGKEIT_MUSTER.fullmatch(wert.strip())
    if treffer:
        return f"{treffer.group(1)} pro {treffer.group(2).capitalize()}"
    # Spec 2 „Fester Schutz“: schreibt die Person genau eine Zahl, gilt sie (Vertrag).
    nackt = _NACKTE_ZAHL_MUSTER.fullmatch(wert.strip())
    return nackt.group(1) if nackt else None


def _ist_prozent(wert: str) -> bool:
    return _nur_zahl(wert) and 0 <= _zahl_aus_token(wert.strip()) <= 100


# Fix-Welle 6 (M1): über denselben Token-Parser wie _ist_prozent
# (_zahl_aus_token) statt rohem float() — sonst wirft der Validator bei
# deutscher Tausendergruppierung mit Dezimalstelle ("1.234,5" -> "1.234.5"
# nach dem naiven Komma-Ersatz) einen ValueError.
def _ist_nichtnegative_zahl(wert: str) -> bool:
    """Gueltig heisst hier auch: in eine `numeric`-Spalte speicherbar (K-J).

    Die Endlichkeit ist zugleich die Stellen-Obergrenze und deshalb die einzige
    zusaetzliche Bedingung: float laeuft schon ab ~309 Stellen nach inf, waehrend
    `numeric` 131072 Vorkommastellen traegt. Was endlich ist, passt also sicher in
    die Spalte — eine zweite, frei gegriffene Ziffernschranke waere redundant und
    haette der noch offenen BC2-Frage nach den Wertebereichen (K-C) vorgegriffen.
    """
    if not _nur_zahl(wert):
        return False
    zahl = _zahl_aus_token(wert.strip())
    return math.isfinite(zahl) and zahl >= 0


ZAHL = Feldtyp("zahl", _ist_nichtnegative_zahl, _normalisiere_zahl,
               kurzform=_kurzform_haeufigkeit, nackte_zahl_nur_von_person=True,
               nennt_einheit=_nennt_zeitraum,
               antwortform="Zahl pro Woche, pro Monat oder pro Jahr, "
                           "z. B. ‚2 pro Monat‘")
MINUTEN = Feldtyp("minuten", _ist_nichtnegative_zahl, _normalisiere_minuten,
                  kurzform=_kurzform_minuten, nackte_zahl_nur_von_person=True,
                  nennt_einheit=_nennt_zeiteinheit,
                  antwortform="Dauer als Zahl mit ‚Minuten‘ oder ‚Stunden‘, "
                              "z. B. ‚90 Minuten‘")
ANZAHL = Feldtyp("anzahl", _ist_nichtnegative_zahl, _normalisiere_anzahl,
                 kurzform=_kurzform_anzahl,
                 antwortform="nur eine Zahl, ohne Einheit, z. B. ‚5‘")
SKALA_1_5 = Feldtyp("skala_1_5", _ist_skala, _normalisiere_skala,
                    kurzform=_kurzform_skala,
                    antwortform="eine Ziffer von 1 bis 5")
PROZENT_0_100 = Feldtyp("prozent_0_100", _ist_prozent, _normalisiere_prozent,
                        kurzform=_kurzform_prozent,
                        antwortform="Zahl von 0 bis 100")
JA_NEIN = Feldtyp("ja_nein", lambda w: w in ("ja", "nein"), _normalisiere_ja_nein,
                  kurzform=_kurzform_ja_nein, antwortform="ja oder nein")
LISTE = Feldtyp("liste", lambda w: bool(w.strip()), _normalisiere_liste,
                antwortform="Liste, durch Kommas getrennt")
FREITEXT = Feldtyp("freitext", lambda w: bool(w.strip()), lambda w: w,
                   antwortform="Text")


def AUSWAHL(*optionen: str, namen: Mapping[str, str] | None = None,
            synonyme: Mapping[str, Sequence[str]] | None = None) -> Feldtyp:
    """Fabrik: Auswahl-Typ mit kanonischen Optionen (case-insensitiv)."""
    # Treffertabelle Schluessel -> Option: Optionen zuerst (die Kennung gewinnt),
    # dann die Namen.
    optionen_je_schluessel: dict[str, set[str]] = {}
    for option in optionen:
        optionen_je_schluessel.setdefault(_schluessel(option), set()).add(option)
    treffer = {schluessel: next(iter(moegliche))
               for schluessel, moegliche in optionen_je_schluessel.items()
               if len(moegliche) == 1}
    # Ein Schluessel, der zwei verschiedene Optionen traefe, und leere Namen
    # werden nicht uebersetzt.
    kandidaten: dict[str, set[str]] = {}
    benennungen = list((namen or {}).items())
    for option, woerter in (synonyme or {}).items():
        benennungen += [(option, wort) for wort in woerter]
    for option, name in benennungen:
        if option in optionen and _schluessel(name):
            kandidaten.setdefault(_schluessel(name), set()).add(option)
    for schluessel, moegliche in kandidaten.items():
        if len(moegliche) == 1 and len(optionen_je_schluessel.get(schluessel, ())) < 2:
            treffer.setdefault(schluessel, next(iter(moegliche)))

    def _normalisiere(wert: str) -> str:
        if "?" in wert:
            return wert
        return treffer.get(_schluessel(wert), wert)

    def _kurzform(wert: str) -> str | None:
        if "?" in wert:
            return None
        kern = wert.strip()
        if kern[-1:] in (".", "!"):
            kern = kern[:-1]
        return treffer.get(_schluessel_ohne_rand(kern))

    return Feldtyp(
        name=f"auswahl({', '.join(optionen)})",
        validator=lambda w: w in optionen,
        normalisiere=_normalisiere,
        kurzform=_kurzform,
        optionen=tuple(optionen),
        namen=tuple((option, namen[option]) for option in optionen
                    if namen and namen.get(option)),
        antwortform="genau eine von: " + ", ".join(
            f"{option} (= {namen[option]})" if namen and namen.get(option) else option
            for option in optionen),
    )
