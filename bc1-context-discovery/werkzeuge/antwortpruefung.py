"""Pruefwerkzeug Schicht b: Ablauf, Auswertung, Bericht (Spec Antwortformen, Abschnitt 6).

KI-unabhaengig: der Ablauf ruft nur `process_turn` und liest den Zustand; er
befuellt nie selbst den Zustand."""
import re
from dataclasses import dataclass, field

from bc1_core.core import process_turn
from bc1_core.feldtypen import vergleichsschluessel


@dataclass
class Turn:
    status: str
    gefragt: str | None = None   # Feld, auf dessen Frage die Nachricht antwortet
    werte: dict = field(default_factory=dict)   # Feld -> (Wert, Status) nach dem Turn
    antwort: dict = field(default_factory=dict)   # Antwort von process_turn
    nachricht: str = ""   # gesendete Nachricht dieses Turns


@dataclass
class Lauf:
    turns: list = field(default_factory=list)
    aufrufe: dict = field(default_factory=dict)
    wiederholungen: int = 0
    technisch_abgebrochen: bool = False


@dataclass
class Erwartung:
    feld: str
    versuche: list


@dataclass
class FeldErgebnis:
    feld: str
    ergebnis: str
    gesendet: list = field(default_factory=list)   # gesendete Antworten, der Reihe nach
    nachfragen: int = 0   # wie oft nach dem Feld erneut gefragt wurde
    endwert: str | None = None   # Wert des Felds am Ende des Laufs
    erwartet: list = field(default_factory=list)   # erwartetes Ergebnis je Versuch
    nachfragetexte: list = field(default_factory=list)   # Texte der Nachfragen, woertlich
    detail: str = ""
    verstoesse: list = field(default_factory=list)   # Nachfragetexte gegen die Antwortform
    lauf: int = 1   # Nummer des Laufs im Szenario


def pruefe_nachfragetext(spec, text):
    """Verstoesse eines Nachfragetexts gegen die Antwortform des Felds (leer = in Ordnung)."""
    verstoesse = []
    if spec.typ.name == "ja_nein":
        for wort in ("Ja", "Nein"):
            if not re.search(rf"\b{wort}\b", text, re.IGNORECASE):
                verstoesse.append(f"nennt {wort} nicht")
    elif spec.typ.name.startswith("auswahl("):
        schluessel_text = vergleichsschluessel(text)
        namen = dict(spec.typ.namen)
        if not spec.typ.optionen:
            verstoesse.append("Optionen nicht ermittelbar")
        for option in spec.typ.optionen:
            # Kennung ODER Name, als ganze Wortfolge (nicht als Teilstring)
            if not any(re.search(rf"(?<!\w){re.escape(vergleichsschluessel(bezeichnung))}(?!\w)",
                                 schluessel_text)
                       for bezeichnung in (option, namen.get(option)) if bezeichnung):
                verstoesse.append(f"nennt {option} nicht")
    elif spec.typ.name == "skala_1_5":
        for ziffer in ("1", "5"):
            if not re.search(rf"(?<!\d){ziffer}(?!\d)", text):
                verstoesse.append(f"nennt {ziffer} nicht")
    return verstoesse


def _geaenderte_fremdfelder(lauf, feld):
    """Felder, deren Wert eine Antwort auf `feld` gesetzt oder geaendert hat (ohne `feld`)."""
    geaendert = set()
    for nummer, turn in enumerate(lauf.turns):
        if turn.gefragt != feld:
            continue
        vorher = lauf.turns[nummer - 1].werte
        geaendert |= {name for name, (wert, _) in turn.werte.items()
                      if name != feld and wert != vorher.get(name, (None, ""))[0]}
    return sorted(geaendert)


def bewerte(lauf, erwartungen, paket=None):
    ergebnisse = []
    for erwartung in erwartungen:
        turns = [t for t in lauf.turns if t.gefragt == erwartung.feld]
        if not turns or not erwartung.versuche:
            ergebnisse.append(FeldErgebnis(erwartung.feld, "nicht_geprueft"))
            continue
        wert, status = turns[0].werte[erwartung.feld]
        geaendert = _geaenderte_fremdfelder(lauf, erwartung.feld)
        if geaendert:
            ergebnisse.append(FeldErgebnis(
                erwartung.feld, "falsch",
                detail="Antwort änderte auch: " + ", ".join(geaendert)))
            continue
        if status != "gueltig" and not erwartung.versuche[0][1].endswith("Nachfrage"):
            ergebnisse.append(FeldErgebnis(erwartung.feld, "unerwartete_nachfrage"))
            continue
        if status != "gueltig" and len(turns) < 2:
            # Keine Zweitantwort: technischer Abbruch ist kein Feldfehler.
            ergebnisse.append(FeldErgebnis(
                erwartung.feld,
                "nicht_geprueft" if lauf.technisch_abgebrochen else "aufgegeben"))
            continue
        if status != "gueltig":
            wert_zweit, status_zweit = turns[1].werte[erwartung.feld]
            if status_zweit != "gueltig":
                ergebnis = "aufgegeben"
            elif wert_zweit != erwartung.versuche[1][1]:
                ergebnis = "falsch"
            else:
                ergebnis = "ok_nach_nachfrage"
            ergebnisse.append(FeldErgebnis(erwartung.feld, ergebnis))
            continue
        gelungen = wert == erwartung.versuche[0][1].removesuffix(" oder Nachfrage")
        ergebnisse.append(FeldErgebnis(erwartung.feld, "ok_1" if gelungen else "falsch"))
    for erwartung, ergebnis in zip(erwartungen, ergebnisse):
        turns = [t for t in lauf.turns if t.gefragt == erwartung.feld]
        ergebnis.gesendet = [t.nachricht for t in turns]
        ergebnis.nachfragen = sum(1 for t in turns
                                  if t.antwort["payload"].get("feld") == erwartung.feld)
        if lauf.turns:
            ergebnis.endwert = lauf.turns[-1].werte.get(erwartung.feld, (None, ""))[0]
        ergebnis.erwartet = [erwartet for _, erwartet in erwartung.versuche]
        ergebnis.nachfragetexte = [t.antwort["payload"]["naechste_frage"] for t in turns
                                   if t.antwort["payload"].get("feld") == erwartung.feld]
        if paket is not None:
            ergebnis.verstoesse = [
                verstoss for text in ergebnis.nachfragetexte
                for verstoss in pruefe_nachfragetext(paket.field(erwartung.feld), text)]
    return ergebnisse


def bericht(ergebnisse, *, modell, code_stand, szenario, pflicht=(), laeufe=(),
            teillauf=None):
    """Markdown-Bericht (Klartext zuerst, dann die Felder)."""
    geprueft = [r for r in ergebnisse if r.ergebnis != "nicht_geprueft"]
    bestanden = sum(1 for r in geprueft if r.ergebnis.startswith("ok"))
    zeilen = [
        f"# Prüfbericht Antwortformen — {szenario}",
        "",
        f"- Modell: {modell}",
        f"- Code-Stand: {code_stand}",
        f"- Szenario: {szenario}",
        f"- Ergebnis: {bestanden} von {len(geprueft)} geprüften Feldern bestanden, "
        f"{len(ergebnisse) - len(geprueft)} nicht geprüft",
    ]
    for nummer, lauf in laeufe:
        zeilen.append(
            f"- Lauf {nummer}: {len(lauf.turns)} Turns, KI-Aufrufe: "
            f"extract {lauf.aufrufe['extract']}, antworte {lauf.aufrufe['antworte']}, "
            f"Wiederholungen nach Fehler {lauf.wiederholungen}, "
            + ("technisch NICHT abgeschlossen (kein Feldfehler)"
               if lauf.technisch_abgebrochen else "abgeschlossen"))
    zeilen += [
        "",
        "| Feld | Gesendete Antworten | Nachfragen | Endwert | Erwartet | Ergebnis |",
        "|---|---|---|---|---|---|",
    ]
    for r in ergebnisse:
        ergebnis = {"ok_1": "✓ im 1. Versuch",
                    "ok_nach_nachfrage": "✓ nach erwarteter Nachfrage",
                    "falsch": "✗ falsch",
                    "aufgegeben": "✗ aufgegeben",
                    "unerwartete_nachfrage": "✗ unerwartete Nachfrage",
                    "nicht_geprueft": "nicht geprüft"}[r.ergebnis]
        zeilen.append(f"| {r.feld} | {' / '.join(r.gesendet)} | {r.nachfragen} "
                      f"| {r.endwert or '–'} | {', '.join(r.erwartet)} | {ergebnis} |")
    if pflicht:
        gelaufen = {(r.feld, r.lauf, r.gesendet[0]) for r in ergebnisse
                    if r.ergebnis != "nicht_geprueft"}
        fehlend = [f for f in pflicht if (f.feld, f.lauf, f.antwort) not in gelaufen]
        if teillauf is not None:
            urteil = (f"Teilergebnis: Abdeckung nur für Lauf {teillauf} geprüft — "
                      "Abnahme hier nicht beurteilbar")
        elif fehlend:
            urteil = "Abnahme NICHT erfüllt: mindestens ein Pflichtfall ist nicht gelaufen."
        else:
            urteil = "Abnahme erfüllt: jeder Pflichtfall ist gelaufen."
        zeilen += ["", "## Abdeckung", urteil,
                   "", "| Feld | Antwort | Szenario | Lauf | Status |", "|---|---|---|---|---|"]
        zeilen += [f"| {f.feld} | {f.antwort} | {f.szenario} | {f.lauf} | "
                   f"{'NICHT gelaufen' if f in fehlend else 'gelaufen'} |" for f in pflicht]
    for r in ergebnisse:
        if r.nachfragetexte:
            zeilen += ["", f"### {r.feld}"]
            zeilen += [f"> {text}" for text in r.nachfragetexte]
            zeilen.append("Automatische Prüfung: "
                          + ("; ".join(r.verstoesse) if r.verstoesse else "keine Verstöße"))
            zeilen.append("Bewertung durch den Ausführenden (Polarität, Richtung, Optionen): "
                          "offen für die Projektleitung")
    return "\n".join(zeilen)


class _ZaehlendeKI:
    """Reicht jeden Aufruf an die eigentliche KI durch und zaehlt ihn."""

    def __init__(self, llm, zaehler):
        self._llm = llm
        self._zaehler = zaehler

    def extract(self, message, package, state):
        self._zaehler["extract"] += 1
        return self._llm.extract(message, package, state)

    def antworte(self, kontext):
        self._zaehler["antworte"] += 1
        return self._llm.antworte(kontext)


def spiele(store, llm, paket, antworten, *, start, max_turns=60):
    lauf = Lauf(aufrufe={"extract": 0, "antworte": 0})
    llm = _ZaehlendeKI(llm, lauf.aufrufe)
    nachricht = start
    gefragt = {}
    davor = None
    for nummer in range(max_turns):
        antwort = process_turn(store, llm, paket, "pruefung", f"m{nummer}", nachricht,
                               company_id="pruefwerkzeug")
        if antwort["status"] == "fehler_fortsetzbar":
            lauf.wiederholungen += 1
            antwort = process_turn(store, llm, paket, "pruefung", f"m{nummer}",
                                   nachricht, company_id="pruefwerkzeug")
            if antwort["status"] == "fehler_fortsetzbar":
                lauf.technisch_abgebrochen = True
                break
        werte = {name: (fv.value, fv.status.value)
                 for name, fv in store.load("pruefung").values.items()}
        lauf.turns.append(Turn(antwort["status"], davor, werte, antwort, nachricht))
        if antwort["status"] != "frage":
            break
        feld = davor = antwort["payload"]["feld"]
        nachricht = antworten(feld, gefragt.get(feld, 0))
        gefragt[feld] = gefragt.get(feld, 0) + 1
    else:
        lauf.technisch_abgebrochen = True
    return lauf
