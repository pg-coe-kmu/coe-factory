"""Pruefwerkzeug Schicht b: Ablauf, Auswertung, Bericht (Spec Antwortformen, Abschnitt 6).

KI-unabhaengig: der Ablauf ruft nur `process_turn` und liest den Zustand; er
befuellt nie selbst den Zustand."""
import re
from dataclasses import dataclass, field

from bc1_core.core import process_turn
from bc1_core.feldtypen import _schluessel


@dataclass
class Turn:
    status: str
    gefragt: str | None = None   # Feld, auf dessen Frage die Nachricht antwortet
    werte: dict = field(default_factory=dict)   # Feld -> (Wert, Status) nach dem Turn


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


def pruefe_nachfragetext(spec, text):
    """Verstoesse eines Nachfragetexts gegen die Antwortform des Felds (leer = in Ordnung)."""
    verstoesse = []
    if spec.typ.name == "ja_nein":
        for wort in ("Ja", "Nein"):
            if not re.search(rf"\b{wort}\b", text, re.IGNORECASE):
                verstoesse.append(f"nennt {wort} nicht")
    elif spec.typ.name.startswith("auswahl("):
        schluessel_text = _schluessel(text)
        # Optionen und Namen stehen in der Antwortform: "genau eine von: R-01 (= Name), ..."
        for option, name in re.findall(r"(?:: |, )([^\s,(]+)(?: \(= ([^)]*)\))?",
                                       spec.typ.antwortform):
            if not any(_schluessel(bezeichnung) in schluessel_text
                       for bezeichnung in (option, name) if bezeichnung):
                verstoesse.append(f"nennt {option} nicht")
    elif spec.typ.name == "skala_1_5":
        for ziffer in ("1", "5"):
            if not re.search(rf"(?<!\d){ziffer}(?!\d)", text):
                verstoesse.append(f"nennt {ziffer} nicht")
    return verstoesse


def _fremdes_feld_geaendert(lauf, feld):
    """Hat eine Antwort auf `feld` den Wert eines anderen Felds gesetzt oder geaendert?"""
    for nummer, turn in enumerate(lauf.turns):
        if turn.gefragt != feld:
            continue
        vorher = lauf.turns[nummer - 1].werte
        if any(wert != vorher.get(name, (None, ""))[0]
               for name, (wert, _) in turn.werte.items() if name != feld):
            return True
    return False


def bewerte(lauf, erwartungen):
    ergebnisse = []
    for erwartung in erwartungen:
        turns = [t for t in lauf.turns if t.gefragt == erwartung.feld]
        if not turns or not erwartung.versuche:
            ergebnisse.append(FeldErgebnis(erwartung.feld, "nicht_geprueft"))
            continue
        wert, status = turns[0].werte[erwartung.feld]
        if _fremdes_feld_geaendert(lauf, erwartung.feld):
            ergebnisse.append(FeldErgebnis(erwartung.feld, "falsch"))
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
    return ergebnisse


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
        lauf.turns.append(Turn(antwort["status"], davor, werte))
        if antwort["status"] != "frage":
            break
        feld = davor = antwort["payload"]["feld"]
        nachricht = antworten(feld, gefragt.get(feld, 0))
        gefragt[feld] = gefragt.get(feld, 0) + 1
    else:
        lauf.technisch_abgebrochen = True
    return lauf
