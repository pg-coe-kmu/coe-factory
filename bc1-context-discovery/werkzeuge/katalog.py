import json

from bc1_service.discovery_paket import Bc0Kontext, baue_discovery_paket


def lade_katalog(pfad):
    with open(pfad, encoding="utf-8") as datei:
        return json.load(datei)


def baue_paket(kontext):
    """Discovery-Paket mit dem Testkontext des Katalogs (Schluessel wie `Bc0Kontext`).

    Genau ein Eintrag in `eigner` heisst: fuer den Kernprozess der Anfrage wird
    dieser Eigner vorgeschlagen (Frage B3); mehrere oder keiner: kein Vorschlag."""
    return baue_discovery_paket(kontext=Bc0Kontext(
        kontext["company_id"], tuple(map(tuple, kontext["teilprozesse"])),
        tuple(kontext["system_ids"]), rollen=tuple(map(tuple, kontext["rollen"])),
        eigner=tuple(map(tuple, kontext["eigner"])),
        prozesse=tuple(map(tuple, kontext["prozesse"]))))


def weg_direkt(spec, antwort):
    """Kurzform -> Normalisierer -> Pruefer; Ergebnis Wert oder "Nachfrage"."""
    kurz = spec.typ.kurzform(antwort) if spec.typ.kurzform else None
    if kurz is None:
        return "Nachfrage"
    wert = spec.typ.normalisiere(kurz)
    return wert if spec.typ.validator(wert) else "Nachfrage"


def weg_woertlich(spec, antwort):
    """Die KI reicht den Rohtext durch: Normalisierer -> Pruefer; Wert oder "Nachfrage"."""
    wert = spec.typ.normalisiere(antwort)
    return wert if spec.typ.validator(wert) else "Nachfrage"
