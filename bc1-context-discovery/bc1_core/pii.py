"""PII-Filter (B2): ersetzt personenbezogene Angaben durch Platzhalter, BEVOR der
Kern eine Nachricht speichert oder an einen Anbieter gibt.

Total (wirft nie), deterministisch, idempotent — nur Standardbibliothek.
Was erkannt wird, was bewusst nicht (nackte Nachnamen, Kartennummern,
Konsistenz über Turns) und warum: design/Konzept-B2-PII-Filter.md.
"""
from __future__ import annotations

import re

# Buchstaben lateinischer Namen: ASCII, Latin-1 (é, ñ, ß, Umlaute) und Latin
# Extended-A (ł, ő, ř; U+0100–U+017F, per chr gebaut). Keine Ziffern — sonst
# frisst das Muster Kennungen wie S-03/KP-06.
_GROSS = "[A-ZÀ-ÖØ-Þ" + chr(0x100) + "-" + chr(0x17F) + "]"
_KLEIN = "[a-zß-öø-ÿ" + chr(0x100) + "-" + chr(0x17F) + "]"
# Ein Namenswort: Großbuchstabe + Kleinbuchstaben, Binnenbindestrich erlaubt.
_WORT = _GROSS + _KLEIN + "+(?:-" + _GROSS + _KLEIN + "+)*"
# Namenspartikel ("van der Muster", "von Muster") — "der" allein ist keiner.
_PARTIKEL = r"(?:(?:von|van|zu|zur|de|da|di|du|le|la|del|dos)(?:\s+de[rnm])?\s+)"
_TITEL = (r"(?:(?:Dr|Prof|Dipl)\.(?:-Ing\.)?\s+"
          r"(?:(?:med|jur|phil|ing|rer\.\s?nat|h\.\s?c)\.\s+)?)")
_ANREDE = r"(?:Herrn?|Frau|Hr\.|Fr\.|Kolleg(?:e|in)|[Ii]ch heiße|[Mm]ein Name ist)"
# Titel + optionaler Partikel + ein bis drei Namenswörter (je mit optionalem Partikel).
_NAME = (_TITEL + "*" + _PARTIKEL + "?" + _WORT
         + r"(?:\s+" + _PARTIKEL + "?" + _WORT + r"){0,2}")
_STRASSE = r"[A-ZÄÖÜ][a-zäöüß]*(?:-[A-ZÄÖÜ][a-zäöüß]*)*-?"
_HAUSNR = r"\d+[a-zA-Z]?(?:\s*[-–/]\s*\d+[a-zA-Z]?)?"
# Zweites Ortswort nur in derselben Zeile ("Bad Beispielstadt"), nie über einen
# Zeilenumbruch hinweg — sonst wird die nächste Zeile Teil der Adresse.
_ORT = r"[A-ZÄÖÜ][a-zäöüß-]+(?:[ \t]+[A-ZÄÖÜ][a-zäöüß-]+)?"
_PLZ_ORT = r"(?:(?:,\s*|\s+in\s+|\s+)\d{5}\s+" + _ORT + r")"
# Prozessbegriffe mit Straßenwort sind keine Adressen ("Fertigungsstraße 3").
_KEINE_ADRESSE = ("fertigungs", "produktions", "montage", "prozess", "verarbeitungs")

# Soll-Länge je Land (Zeichen ohne Leerzeichen): nur diese Länder gelten als IBAN,
# Folgetext wird anhand der Länge nicht verschluckt.
_IBAN_LAENGE = {"AT": 20, "BE": 16, "CH": 21, "CZ": 24, "DE": 22, "DK": 18, "ES": 24,
                "FI": 18, "FR": 27, "GB": 22, "HU": 28, "IE": 22, "IT": 27, "LI": 21,
                "LU": 20, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "SE": 24, "SK": 24}
# Leerzeichen zwischen den Gruppen: normal oder geschützt (U+00A0, beim Einfügen aus
# Dokumenten), beliebig viele. Eine Gruppe, die selbst wie ein IBAN-Anfang aussieht
# (Ländercode + Prüfziffern), beendet die IBAN — sonst frisst sie die nächste.
_LEER = "[ " + chr(160) + "]"   # chr(160) statt Zeichen im Quelltext (Editor-Normalisierung)
# Telefon-Trenner: Leerzeichen, geschützt (U+00A0), schmal geschützt (U+202F), "/", "-".
_TRENN = "[ " + chr(160) + chr(8239) + "/-]"
_IBAN = re.compile(
    r"\b(?:" + "|".join(_IBAN_LAENGE) + r")\d{2}"
    r"(?:" + _LEER + r"*(?![a-z]{2}\d{2}(?:" + _LEER + r"|$))[a-z0-9]{4}){2,7}"
    r"(?:" + _LEER + r"*(?![a-z]{2}\d{2}(?:" + _LEER + r"|$))[a-z0-9]{1,4})?\b",
    re.IGNORECASE)

# Reihenfolge = Anwendungsreihenfolge: spezifisch vor allgemein.
_MUSTER: tuple[tuple[str, re.Pattern[str]], ...] = (
    # Endung: Buchstaben jeder Schrift (\w ist Unicode) oder Punycode ("xn--p1ai").
    ("E-Mail", re.compile(r"\b[\w.%+-]+@[\w.-]+\.(?:xn--[\w-]+|[^\W\d_]{2,})\b")),
    ("IBAN", _IBAN),
    # Nicht inmitten von Dezimalzahlen oder hinter Datums-Trennern beginnen, keine
    # Datumsform ("01-02-2026", "01/02/2026") als Anfang, kein ":"/"."+Ziffer danach.
    ("Telefon", re.compile(
        r"(?<![\d,./-])(?!\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b)"
        r"(?:\+\d{1,3}(?:" + _TRENN + r"*\(0\))?|\(0\d{1,5}\)|\b0)" + _TRENN + r"*\d"
        r"(?:" + _TRENN + r"{0,3}\d){6,13}\b(?![:.]\d)")),
    # Straße/Allee/Gasse mit Hausnummer, optional PLZ + Ort; Weg/Platz/Ring/
    # Damm/Ufer NUR mit PLZ + Ort ("Arbeitsplatz 3" ist keine Adresse).
    # EIN Muster für beide Formen, damit die Kennungen der Textreihenfolge folgen.
    ("Adresse", re.compile(
        r"\b" + _STRASSE
        + r"(?:(?:[Ss]traße|[Ss]trasse|[Ss]tr\.|[Aa]llee|[Gg]asse)\s+" + _HAUSNR + _PLZ_ORT + r"?"
        + r"|(?:[Ww]eg|[Pp]latz|[Rr]ing|[Dd]amm|[Uu]fer)\s+" + _HAUSNR + _PLZ_ORT + r")\b")),
    # Hinweiswort bleibt stehen (Gruppe "hinweis"), Titel + Name werden ersetzt.
    # EIN Muster für Anrede und Titel, damit die Kennungen der Textreihenfolge folgen.
    ("Person", re.compile(r"(?P<hinweis>\b" + _ANREDE + r"\s+|\b(?=" + _TITEL + r"))"
                          r"(?P<name>" + _NAME + r")")),
)
def _buchstabe(n: int) -> str:
    """0 → A, 25 → Z, 26 → AA (wie Tabellenspalten)."""
    kennung = ""
    n += 1
    while n:
        n, rest = divmod(n - 1, 26)
        kennung = chr(65 + rest) + kennung
    return kennung


_PLATZHALTER = re.compile(
    r"\[(?P<klasse>Person|E-Mail|Telefon|IBAN|Adresse) (?P<kennung>[A-Z]+)\]")


class _Vergabe:
    """Platzhalter je Klasse und Turn: gleicher Wert → gleicher Buchstabe.
    Schon vorhandene Platzhalter (Idempotenz, eingefügter Text) behalten ihre
    Kennung; sie wird nicht neu vergeben."""

    def __init__(self, text: str) -> None:
        self._kennung: dict[tuple[str, str], str] = {}
        self._belegt: dict[str, set[str]] = {}
        for m in _PLATZHALTER.finditer(text):
            self._belegt.setdefault(m.group("klasse"), set()).add(m.group("kennung"))

    def platzhalter(self, klasse: str, wert: str) -> str:
        schluessel = (klasse, " ".join(wert.split()).lower())
        if schluessel not in self._kennung:
            belegt = self._belegt.setdefault(klasse, set())
            n = 0
            while _buchstabe(n) in belegt:
                n += 1
            belegt.add(_buchstabe(n))
            self._kennung[schluessel] = f"[{klasse} {_buchstabe(n)}]"
        return self._kennung[schluessel]


def _iban_ersatz(treffer: str, vergabe: _Vergabe) -> str:
    laenge = _IBAN_LAENGE.get(treffer[:2].upper())
    if laenge is not None:
        gezaehlt = 0
        for i, zeichen in enumerate(treffer):
            gezaehlt += not zeichen.isspace()
            if gezaehlt == laenge:
                return vergabe.platzhalter("IBAN", treffer[:i + 1]) + treffer[i + 1:]
    return vergabe.platzhalter("IBAN", treffer)   # unbekanntes Land / kürzer: ganz ersetzen


def _ersatz(klasse: str, m: re.Match[str], vergabe: _Vergabe) -> str:
    if klasse == "Person":
        return m.group("hinweis") + vergabe.platzhalter(klasse, m.group("name"))
    if klasse == "IBAN":
        return _iban_ersatz(m.group(0), vergabe)
    if klasse == "Adresse" and m.group(0).lower().startswith(_KEINE_ADRESSE):
        return m.group(0)
    return vergabe.platzhalter(klasse, m.group(0))


def ersetze_pii(text: str) -> str:
    """Ersetzt personenbezogene Angaben durch Platzhalter wie "[Person A]".

    Total, deterministisch, idempotent: vorhandene Platzhalter bleiben stehen
    (kein Muster trifft ihren Wortlaut, ihre Kennungen werden nicht neu vergeben).
    """
    vergabe = _Vergabe(text)
    for klasse, muster in _MUSTER:
        text = muster.sub(lambda m, k=klasse: _ersatz(k, m, vergabe), text)
    return text
