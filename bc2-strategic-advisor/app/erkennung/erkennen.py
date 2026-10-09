"""
BC2 · Der Erkennungsschritt — lesen, packen, fragen, nachkontrollieren.

Der Ablauf eines Analyselaufs bis zu dem Punkt, an dem feststeht, **welche
Potenziale ein Paket trägt**. Was danach kommt — der Value, die Priorisierung —
liegt in :mod:`modell` und rührt hier nichts an.

Der Wächter
-----------

Das Rechenverbot brach in #194 in **2 von 21** Aufrufen, genau dort, wo Zahlen
in der Nutzlast standen. Eine Prompt-Regel reicht dafür nicht; es braucht eine
Prüfung, die den Lauf anhält. Sie tut das in zwei Stufen:

1. Ein **Wiederholungsaufruf**, der den Verstoß benennt.
2. Hält er wieder nicht, **bricht der Lauf ab** (:class:`ErkennungAbgebrochen`).

Warum nicht sofort abbrechen: bei ~10 % Bruchrate und einem Aufruf je Lauf
kostet die Wiederholung wenige Minuten, ein abgebrochener Lauf einen Menschen.
Warum nicht das betroffene Potenzial verwerfen: ein still verworfenes Potenzial
ist ein Loch im Paket, das niemand sieht — die Deckungsprüfung meldete seinen
Teilprozess dann fälschlich als „nicht geschnitten", und aus einem Verstoß
würde eine Lücke, die wie eine Entscheidung aussieht.

Die Abgrenzung ist wichtig: die Regel „anhängen statt zurückweisen" (#172) gilt
für die **Plausibilität fremder Daten**. Hier bricht BC2 seine **eigene**
Zusage, und auf der ruht alles, was danach gerechnet wird.

Was dieser Schritt **nicht** liefert
------------------------------------

Er liefert noch keinen vollständigen :class:`modell.Potenzialeingang`. ADR-006 ·
BC2 (2.0) lässt das LLM an **vier** Stellen urteilen; dieser Schritt deckt
**eine** ab:

===========================================  =========================
Urteilsstelle (ADR-006, 2.0)                 hier?
===========================================  =========================
Lösungsansatz-Klasse                         ✅ ``klasse``
Lage im Korridor                             ❌ fehlt
Die fünf Nutzwert-Kategorien                 ❌ fehlt
Begründetes Überschreiben der Komplexität    ❌ fehlt
===========================================  =========================

Das ist **kein Versehen, sondern der Zuschnitt von #248**: dort steht, was das
Modell liefert, und der Nutzwert steht nicht darin. Die drei offenen
Urteilsstellen brauchen einen eigenen Schritt — er sieht das *geschnittene*
Potenzial, das dieser Schritt erst erzeugt, und kann deshalb gar nicht vorher
laufen. Dazu gehört eine Frage, die niemand entschieden hat: ein Potenzial
berührt mehrere Teilprozesse, BC1 misst aber **je Fokus-Schritt** — wie aus *n*
gemessenen Größen die eine des Potenzials wird, sagt ADR-006 nicht.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .anweisung import baue_frage
from .bestand import Paketbestand
from .modellruf import Modellruf
from .nutzlast import GRENZE_ZEICHEN, Aufruf, packe
from .pruefen import Paar, Pruefbericht, paare_im_kernprozess, pruefe_schnitt

__all__ = [
    "Aufrufprotokoll",
    "Erkennung",
    "ErkennungAbgebrochen",
    "ErkanntesPotenzial",
    "NichtGeschnitten",
    "erkenne",
]


class ErkennungAbgebrochen(RuntimeError):
    """Der Lauf wurde angehalten, weil das Modell seine Zusage brach.

    Trägt die Gründe der letzten Prüfung und die rohe Antwort mit, damit ein
    Mensch nachsehen kann, ohne den Aufruf zu wiederholen.
    """

    def __init__(self, aufruf: str, gruende: tuple[str, ...], roh: str = "") -> None:
        super().__init__(f"Aufruf {aufruf} angehalten: " + "; ".join(gruende))
        self.aufruf = aufruf
        self.gruende = gruende
        self.roh = roh


@dataclass(frozen=True)
class ErkanntesPotenzial:
    """Ein geschnittenes Potenzial — qualitativ, ohne eine einzige Zahl."""

    potenzial_id: str
    kernprozess_id: str
    titel: str
    beruehrte_teilprozess_ids: tuple[str, ...]
    ausgangslage: str
    schmerzpunkte: tuple[str, ...]
    loesungsansatz: str
    #: Eine der fünf Klassen aus ADR-006 · BC2. Der Wächter hat bereits
    #: geprüft, dass sie im Vertrag steht — ein Korridor hängt daran.
    klasse: str
    trenntest_begruendung: str
    unsicherheit: str | None = None


@dataclass(frozen=True)
class NichtGeschnitten:
    """Ein freigegebener Teilprozess, aus dem bewusst kein Potenzial entstand.

    Die Regel aus #194: Platzhalter und unbewertete Teilprozesse werden
    **gemeldet, nicht geschnitten**. Sie wegzulassen hieße, sie aus einem Paket
    verschwinden zu lassen, das sie ausdrücklich freigegeben hat.
    """

    teilprozess_id: str
    grund: str


@dataclass(frozen=True)
class Aufrufprotokoll:
    """Was ein Modellaufruf gekostet hat und wie oft er nötig war."""

    name: str
    schnitt: str
    zeichen: int
    modell: str
    versuche: int
    #: Die Gründe, aus denen ein Versuch verworfen wurde — leer, wenn der erste
    #: saß. Sie gehören ins Protokoll, weil die Bruchrate des Rechenverbots
    #: sonst niemand misst.
    verworfen: tuple[str, ...] = ()


@dataclass(frozen=True)
class Erkennung:
    """Das Ergebnis des Erkennungsschritts für einen Lauf."""

    company_id: str
    paket_id: str
    uebergeben_am: datetime
    gelesen_am: datetime
    potenziale: tuple[ErkanntesPotenzial, ...]
    nicht_geschnitten: tuple[NichtGeschnitten, ...]
    pruefung: Pruefbericht
    #: Die Paare innerhalb eines Kernprozesses — die Vorlage für Gate 1. Der
    #: Trenntest ist einseitig; das hier ist, was ein Mensch ansehen muss.
    paare: tuple[Paar, ...]
    aufrufe: tuple[Aufrufprotokoll, ...] = ()
    hinweise: tuple[str, ...] = ()

    @property
    def kernprozess_ids(self) -> tuple[str, ...]:
        return tuple(sorted({p.kernprozess_id for p in self.potenziale}))


def _als_potenzial(roh: dict[str, Any], aufruf: Aufruf, mehrere: bool) -> ErkanntesPotenzial:
    """Bildet eine Modellantwort auf den Typ ab.

    Bei mehreren Aufrufen (Schnitt B) wird die ID mit dem Aufrufnamen
    vorangestellt: jeder Aufruf zählt bei ``P1`` wieder von vorn, und zwei
    Potenziale mit derselben Kennung wären in der Lieferung nicht mehr
    auseinanderzuhalten.
    """
    kennung = str(roh.get("id") or "P?")
    schmerz = roh.get("schmerzpunkte") or []
    if isinstance(schmerz, str):
        schmerz = [schmerz]
    tps = tuple(str(t) for t in (roh.get("beruehrte_teilprozesse") or []))
    return ErkanntesPotenzial(
        potenzial_id=f"{aufruf.name}/{kennung}" if mehrere else kennung,
        kernprozess_id=str(
            roh.get("kernprozess_id") or (tps[0].split(".")[0] if tps else "")
        ),
        titel=str(roh.get("titel") or ""),
        beruehrte_teilprozess_ids=tps,
        ausgangslage=str(roh.get("ausgangslage") or ""),
        schmerzpunkte=tuple(str(s) for s in schmerz),
        loesungsansatz=str(roh.get("loesungsansatz") or ""),
        klasse=str(roh.get("loesungsklasse") or ""),
        trenntest_begruendung=str(roh.get("trenntest_begruendung") or ""),
        unsicherheit=(
            str(roh["unsicherheit"]) if roh.get("unsicherheit") not in (None, "") else None
        ),
    )


def _frage_mit_waechter(
    aufruf: Aufruf,
    modell: Modellruf,
    wiederholungen: int,
) -> tuple[list[dict], list[dict], Pruefbericht, Aufrufprotokoll]:
    """Stellt einen Aufruf und hält ihn an, wenn die Zusage bricht."""
    gruende: list[str] = []
    verworfen: list[str] = []
    versuch = 0

    while True:
        versuch += 1
        antwort = modell.frage(baue_frage(aufruf.inhalt, gruende or None))
        if antwort.ergebnis is None:
            bericht = Pruefbericht(anzahl=0)
            gruende = ["Die Antwort enthielt kein lesbares JSON-Objekt."]
        else:
            bericht = pruefe_schnitt(
                antwort.potenziale,
                list(aufruf.teilprozess_ids),
                antwort.nicht_geschnitten,
            )
            gruende = list(bericht.verstoesse)

        if not gruende:
            return (
                antwort.potenziale,
                antwort.nicht_geschnitten,
                bericht,
                Aufrufprotokoll(
                    name=aufruf.name,
                    schnitt=aufruf.schnitt,
                    zeichen=aufruf.zeichen,
                    modell=antwort.modell,
                    versuche=versuch,
                    verworfen=tuple(verworfen),
                ),
            )

        verworfen.extend(gruende)
        if versuch > wiederholungen:
            raise ErkennungAbgebrochen(aufruf.name, tuple(gruende), antwort.roh)


def erkenne(
    bestand: Paketbestand,
    modell: Modellruf,
    *,
    grenze: int = GRENZE_ZEICHEN,
    wiederholungen: int = 1,
) -> Erkennung:
    """Schneidet die Potenziale eines Pakets.

    :param bestand: der auf ``stand_zum(uebergeben_am)`` gelesene Datenstand.
    :param modell: die Naht zum LLM.
    :param grenze: ab wie vielen Zeichen nach Kernprozess aufgeteilt wird.
    :param wiederholungen: wie oft ein verworfener Aufruf wiederholt wird,
        bevor der Lauf anhält. ``0`` schaltet die Wiederholung ab — der Wächter
        bleibt, er wird nur unnachsichtig.
    :raises ErkennungAbgebrochen: wenn das Modell seine Zusage auch in der
        Wiederholung bricht.
    """
    aufrufe = packe(bestand, grenze)
    mehrere = len(aufrufe) > 1

    potenziale: list[ErkanntesPotenzial] = []
    roh_potenziale: list[dict] = []
    nicht: list[NichtGeschnitten] = []
    protokoll: list[Aufrufprotokoll] = []

    for aufruf in aufrufe:
        rohe, rohe_nicht, _, prot = _frage_mit_waechter(aufruf, modell, wiederholungen)
        protokoll.append(prot)
        for r in rohe:
            p = _als_potenzial(r, aufruf, mehrere)
            potenziale.append(p)
            # Fuer die Gesamtpruefung die ID durchreichen, die auch im Ergebnis
            # steht -- sonst nennt der Bericht Kennungen, die es nicht gibt.
            roh_potenziale.append({**r, "id": p.potenzial_id})
        for e in rohe_nicht:
            if e.get("teilprozess_id"):
                nicht.append(
                    NichtGeschnitten(
                        teilprozess_id=str(e["teilprozess_id"]),
                        grund=str(e.get("grund") or ""),
                    )
                )

    # Die Gesamtpruefung laeuft ueber ALLE Aufrufe zusammen und gegen das ganze
    # Paket. Unter Schnitt C ist das dieselbe Pruefung wie eben; unter Schnitt B
    # ist es die einzige Stelle, an der kernprozessuebergreifende Deckung
    # ueberhaupt sichtbar wird -- sehen kann sie das Modell dort nicht mehr.
    #
    # Die Deckungspruefung verdient ihren Platz gemessen. Zwei echte Laeufe ueber
    # DASSELBE Paket am 21.09.2026 (#248): der erste liess KP-02.TP-2 und
    # KP-03.TP-3 aus -- beide voll bewertet, beide schneidbar --, ohne sie zu
    # melden; der zweite deckte alle zwoelf ab. Also Streuung, nicht Struktur,
    # aber ein stiller Ausfall, den sonst niemand gesehen haette. Eine Luecke
    # bleibt trotzdem ein Befund und kein Verstoss: dass ein Teilprozess kein
    # Potenzial traegt, kann richtig sein.
    gesamt = pruefe_schnitt(
        roh_potenziale,
        list(bestand.teilprozess_ids),
        [{"teilprozess_id": n.teilprozess_id} for n in nicht],
    )

    hinweise = list(bestand.hinweise)
    if mehrere:
        hinweise.append(
            f"Nutzlast ueber der Grenze von {grenze} Zeichen: aufgeteilt in "
            f"{len(aufrufe)} Aufrufe je Kernprozess (Schnitt B). Doppelgaenger "
            "ueber Kernprozessgrenzen hinweg kann kein Aufruf mehr sehen."
        )
    if gesamt.unbedeckt:
        hinweise.append(
            "Freigegeben, aber weder geschnitten noch gemeldet: "
            + ", ".join(gesamt.unbedeckt)
        )

    return Erkennung(
        company_id=bestand.company_id,
        paket_id=bestand.paket_id,
        uebergeben_am=bestand.uebergeben_am,
        gelesen_am=bestand.gelesen_am,
        potenziale=tuple(potenziale),
        nicht_geschnitten=tuple(nicht),
        pruefung=gesamt,
        paare=paare_im_kernprozess(roh_potenziale),
        aufrufe=tuple(protokoll),
        hinweise=tuple(hinweise),
    )
