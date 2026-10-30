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
    # Soll-Endwert eines Felds ohne Versuche (Startfeld, Rueckfall-Antwort); mit Versuchen
    # ergibt er sich aus diesen.
    soll: str | None = None


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
    endstatus: str | None = None   # Status des Felds am Ende des Laufs
    endsoll: str | None = None   # erwarteter Endwert (Wert der letzten Erwartung)


# Ergebnisse, die im Bericht als ✗ stehen.
FEHLER = ("falsch", "aufgegeben", "unerwartete_nachfrage", "nebenwirkung")


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


def _geaendert(turn, vorher, erlaubt=()):
    """Felder ausser dem beantworteten, deren (Wert, Status) die Antwort geaendert hat."""
    return sorted(name for name, stand in turn.werte.items()
                  if name != turn.gefragt and name not in erlaubt
                  and stand != vorher.get(name, (None, "fehlt")))


def _geaenderte_fremdfelder(lauf, feld):
    """Felder, deren (Wert, Status) eine Antwort auf `feld` gesetzt oder geaendert hat (ohne `feld`)."""
    geaendert = set()
    for nummer, turn in enumerate(lauf.turns):
        if turn.gefragt != feld:
            continue
        vorher = lauf.turns[nummer - 1].werte
        geaendert |= set(_geaendert(turn, vorher))
    return sorted(geaendert)


def bewerte(lauf, erwartungen, paket=None, *, start_felder=()):
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
            ergebnis.endwert, ergebnis.endstatus = lauf.turns[-1].werte.get(
                erwartung.feld, (None, "fehlt"))
        ergebnis.erwartet = [erwartet for _, erwartet in erwartung.versuche]
        if erwartung.versuche:
            # Soll aus dem Verlauf: wurde der Grenzfall im 1. Versuch als X angenommen,
            # gab es keine Zweitantwort; nur nach einer Nachfrage gilt deren Wert.
            angenommen = (turns and turns[0].werte[erwartung.feld][1] == "gueltig"
                          and erwartung.versuche[0][1].endswith(" oder Nachfrage"))
            soll = erwartung.versuche[0 if angenommen else -1][1]
            ergebnis.endsoll = soll.removesuffix(" oder Nachfrage")
        else:
            ergebnis.endsoll = erwartung.soll
        ergebnis.nachfragetexte = [t.antwort["payload"]["naechste_frage"] for t in turns
                                   if t.antwort["payload"].get("feld") == erwartung.feld]
        if paket is not None:
            ergebnis.verstoesse = [
                verstoss for text in ergebnis.nachfragetexte
                for verstoss in pruefe_nachfragetext(paket.field(erwartung.feld), text)]
    # Antworten auf Felder ohne Erwartung (freie Felder, Rueckfall): Aenderungen anderer Felder
    # stehen als eigene Zeile.
    geprueft = {erwartung.feld for erwartung in erwartungen if erwartung.versuche}
    for nummer, turn in enumerate(lauf.turns):
        if turn.gefragt in geprueft:
            continue
        vorher = lauf.turns[nummer - 1].werte if nummer else {}
        erlaubt = start_felder if nummer == 0 else ()
        geaendert = _geaendert(turn, vorher, erlaubt)
        if geaendert:
            ergebnisse.append(FeldErgebnis(
                "Nebenwirkung: " + ("Startnachricht" if nummer == 0
                                    else f"Antwort auf {turn.gefragt}"), "nebenwirkung",
                gesendet=[turn.nachricht],
                detail="Antwort änderte auch: " + ", ".join(geaendert)))
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
                    "nebenwirkung": "✗ Nebenwirkung",
                    "nicht_geprueft": "nicht geprüft"}[r.ergebnis]
        if r.detail:
            ergebnis += f" ({r.detail})"
        zeilen.append(f"| {r.feld} | {' / '.join(r.gesendet)} | {r.nachfragen} "
                      f"| {r.endwert or '–'} | {', '.join(r.erwartet)} | {ergebnis} |")
    if pflicht or laeufe:
        gelaufen = {(r.feld, r.lauf, r.gesendet[0]) for r in ergebnisse
                    if r.ergebnis != "nicht_geprueft"}
        fehlend = [f for f in pflicht if (f.feld, f.lauf, f.antwort) not in gelaufen]
        if teillauf is not None:
            urteil = (f"Teilergebnis: Abdeckung nur für Lauf {teillauf} geprüft — "
                      "Abnahme hier nicht beurteilbar")
        elif code_stand == "unbekannt":
            urteil = "Abnahme nicht beurteilbar (Code-Stand unbekannt)"
        else:
            fehler = [r for r in ergebnisse if r.ergebnis in FEHLER]
            gruende = []
            if fehlend:
                gruende.append("mindestens ein Pflichtfall ist nicht gelaufen")
            if fehler:
                gruende.append(f"{len(fehler)} {'Feld' if len(fehler) == 1 else 'Felder'} mit ✗")
            # Automatisch erkannte Nachfragetext-Verstösse; Polarität und Richtung bewertet
            # weiter der Mensch (unten je Feld „offen für die Projektleitung“).
            verstoss = [r for r in ergebnisse if r.verstoesse]
            if verstoss:
                gruende.append("Nachfragetext verstößt gegen die Antwortform: " + ", ".join(
                    f"{r.feld} ({'; '.join(r.verstoesse)})" for r in verstoss))
            gruende += [f"Lauf {nummer} nicht fertig" for nummer, lauf in laeufe
                        if not lauf.turns or lauf.turns[-1].status != "fertig"]
            # Felder mit ✗ stehen schon oben; ungefragte Felder gehören zum Lauf-Urteil.
            gruende += [f"Endwert weicht ab: {r.feld} (Lauf {r.lauf})" for r in ergebnisse
                        if r.endsoll is not None
                        and r.ergebnis not in FEHLER
                        and (r.ergebnis != "nicht_geprueft" or not r.erwartet)
                        and (r.endwert, r.endstatus) != (r.endsoll, "gueltig")]
            for nummer, lauf in laeufe:
                if lauf.turns and lauf.turns[-1].status == "fertig":
                    p = lauf.turns[-1].antwort["payload"]
                    if p["pflicht_erfasst"] != p["pflicht_gesamt"]:
                        gruende.append(f"Lauf {nummer} Pflichtfelder "
                                       f"{p['pflicht_erfasst']} von {p['pflicht_gesamt']}")
            urteil = ("Abnahme NICHT erfüllt: " + "; ".join(gruende) + "." if gruende
                      else "Abnahme erfüllt: jeder Pflichtfall ist gelaufen, kein ✗, "
                           "Endprüfung in allen Läufen grün (automatische Prüfung; "
                           "Polarität und Richtung der Nachfragetexte bewertet die "
                           "Projektleitung).")
        zeilen += ["", "## Abnahme", urteil, "", "Endprüfung je Lauf:"]
        for nummer, lauf in laeufe:
            letzter = lauf.turns[-1] if lauf.turns else None
            payload = letzter.antwort["payload"] if letzter else {}
            zeilen.append(
                f"- Lauf {nummer}: Status {letzter.status if letzter else 'keiner'}, "
                f"Pflichtfelder {payload.get('pflicht_erfasst')} von {payload.get('pflicht_gesamt')}"
                + (" — nicht fertig" if not letzter or letzter.status != "fertig"
                   else " — Pflichtfelder fehlen"
                   if payload.get("pflicht_erfasst") != payload.get("pflicht_gesamt") else ""))
        zeilen += ["", "| Lauf | Feld | Endwert | Endstatus | Soll | Endprüfung |",
                   "|---|---|---|---|---|---|"]
        zeilen += [f"| {r.lauf} | {r.feld} | {r.endwert or '–'} | {r.endstatus or '–'} "
                   f"| {r.endsoll} | "
                   f"{'✓' if (r.endwert, r.endstatus) == (r.endsoll, 'gueltig') else '✗'} |"
                   for r in ergebnisse if r.endsoll is not None]
    if pflicht:
        zeilen += ["", "## Abdeckung",
                   "| Feld | Antwort | Szenario | Lauf | Status |", "|---|---|---|---|---|"]
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
