"""Szenario-Daten fuer das Pruefwerkzeug (Spec Antwortformen, Abschnitt 6).

Alle Antworten sind generisch (das Repo ist oeffentlich). Die Katalogeintraege
kommen aus `tests/daten/antwortkatalog.json`; hier stehen nur die freien Antworten
der Felder ohne festen Typ und der Aufbau der vier Szenarien."""
from collections import Counter
from dataclasses import dataclass, field

from werkzeuge.antwortpruefung import Erwartung

# Antworten fuer Felder ohne Katalogeintrag (freier Text, Liste, Systemkennung).
FREIE_ANTWORTEN = {
    "request_intent": "Wir möchten unseren Ablauf für Kundenanfragen gemeinsam erfassen.",
    "process_name": "Auftragsabwicklung",
    "process_steps": "Anfrage erfassen, Angebot prüfen, Auftrag bestätigen",
    "trigger_text": "Eine neue Anfrage geht ein.",
    "input_text": "Die Anfrage des Kunden mit einer Artikelliste.",
    "output_text": "Ein bestätigter Auftrag.",
    "focus_step_roles": "Vertrieb, Lager",
    "focus_step_systems": "S-01",
}


@dataclass
class Szenario:
    start: str = ""
    erwartungen: list = field(default_factory=list)
    variante: str | None = None
    rueckfall: dict = field(default_factory=dict)   # Feld -> Antwort, wenn nichts erwartet ist
    pflicht: list = field(default_factory=list)   # Faelle, die der Lauf spielen muss
    start_felder: tuple = ()   # Felder, die die Startnachricht setzen darf

    def antworten(self, feld, versuch):
        for erwartung in self.erwartungen:
            if erwartung.feld == feld and versuch < len(erwartung.versuche):
                return erwartung.versuche[versuch][0]
        return self.rueckfall[feld]


@dataclass(frozen=True)
class Fall:
    """Ein KI-Fall des Katalogs und der Lauf, der ihn als ersten Versuch seines Felds spielt."""
    feld: str
    antwort: str
    variante: str | None
    szenario: int
    lauf: int
    erwartet: str   # `ki` des Eintrags: Wert, "Nachfrage" oder "X oder Nachfrage"


def abdeckung(katalog):
    """Ordnet jeden Katalogeintrag, der die KI erreicht (fest = Nachfrage, also keine
    Kurzform), genau einem Lauf zu: ki = Wert -> Szenario 2, sonst Szenario 4; je Lauf
    hoechstens ein Fall pro Feld (der n-te Fall eines Felds kommt in Lauf n)."""
    faelle = []
    gezaehlt = {}
    for eintrag in katalog["eintraege"]:
        if eintrag["fest"] != "Nachfrage":
            continue
        szenario = 4 if eintrag["ki"].endswith("Nachfrage") else 2
        lauf = gezaehlt[(szenario, eintrag["feld"])] = (
            gezaehlt.get((szenario, eintrag["feld"]), 0) + 1)
        faelle.append(Fall(eintrag["feld"], eintrag["antwort"], eintrag.get("variante"),
                           szenario, lauf, eintrag["ki"]))
    return faelle


def anzahl_laeufe(katalog, nummer):
    """Zahl der Laeufe = groesste Fallzahl eines Felds; Szenario 2 mindestens drei."""
    je_feld = Counter(fall.feld for fall in abdeckung(katalog) if fall.szenario == nummer)
    return max([3 if nummer == 2 else 1, *je_feld.values()])


def baue_szenario(katalog, nummer, lauf=1):
    rueckfall = dict(FREIE_ANTWORTEN)
    festwerte = {}
    for eintrag in katalog["eintraege"]:
        if eintrag["fest"] == "Nachfrage" or "variante" in eintrag:
            continue
        bisher = rueckfall.get(eintrag["feld"])
        if bisher is None or len(eintrag["antwort"]) < len(bisher):
            rueckfall[eintrag["feld"]] = eintrag["antwort"]
            festwerte[eintrag["feld"]] = eintrag["fest"]
    pflicht = []
    # A2 und A3 stehen in der Startnachricht und werden nicht einzeln gefragt.
    erwartungen = {feld: Erwartung(feld, [(rueckfall[feld], wert)])
                   for feld, wert in festwerte.items()
                   if feld not in ("request_goal", "scope_focus")}
    if nummer == 3:
        for feld in ("focus_step_media_break", "process_owner_role", "focus_step",
                     "documentation_status"):
            erwartungen[feld] = Erwartung(feld, [("Wie meinen Sie das?", "Nachfrage"),
                                                 (rueckfall[feld], festwerte[feld])])
            pflicht.append(Fall(feld, "Wie meinen Sie das?", None, 3, 1, "Nachfrage"))
    start = (f"{FREIE_ANTWORTEN['request_intent']} "
             f"Der Prozess heißt {FREIE_ANTWORTEN['process_name']}.")
    variante = None   # Paket der Katalog-Variante, etwa B3 ohne Eigner-Vorschlag
    start_felder = ("request_intent", "process_name")   # A1 und B1 setzt jede Startnachricht
    if nummer in (2, 4):
        # Nur A1 und B1: A2 und A3 werden einzeln gefragt und sind damit KI-Faelle.
        # Felder ohne Fall in diesem Lauf: Rueckfall-Antwort, nicht geprueft.
        erwartungen = {feld: Erwartung(feld, [], soll=wert) for feld, wert in festwerte.items()}
        for fall in abdeckung(katalog):
            if fall.szenario == nummer and fall.lauf == lauf:
                versuche = [(fall.antwort, fall.erwartet)]
                if fall.erwartet.endswith("Nachfrage"):
                    # Danach eine gueltige Zweitantwort, damit kein Pflichtfeld aufgegeben wird.
                    versuche.append((rueckfall[fall.feld], festwerte[fall.feld]))
                erwartungen[fall.feld] = Erwartung(fall.feld, versuche)
                variante = fall.variante or variante
                pflicht.append(fall)
    else:
        start += " Das Ziel ist zeit_sparen, es geht um den ganzer_prozess."
        start_felder += ("request_goal", "scope_focus")
        # Startfelder werden nie gefragt; ihr Endwert muss trotzdem dem Wert der
        # Startnachricht entsprechen (Soll ohne Versuche).
        erwartungen["request_goal"] = Erwartung("request_goal", [], soll="zeit_sparen")
        erwartungen["scope_focus"] = Erwartung("scope_focus", [], soll="ganzer_prozess")
    return Szenario(start, list(erwartungen.values()), variante, rueckfall, pflicht,
                    start_felder)
