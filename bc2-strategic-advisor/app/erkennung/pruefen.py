"""
BC2 · Die deterministische Nachkontrolle über der Modellantwort.

Portiert aus ``pruefeSchnitt()`` des Prototyps zu #194 (``vorlage.html``,
unterhalb von ``// Der liftbare Teil``) — der einzige Teil des Prototyps, der
befördert wird. Die Logik ist unverändert; hinzugekommen sind der
Vertragsabgleich der Lösungsklasse und die Trennung zwischen **Verstoß** und
**Befund**.

**Was diese Prüfung kann und was nicht.** Sie misst mechanisch Prüfbares:
Deckung, Mehrfachbelegung, Kernprozessgrenze, Zahlen im Text, Klassenname. Sie
kann **keine Doppelzählung erkennen** — das ist eine Aussage über ein *Paar*,
und in #194 hat sie für fünf Kopien desselben Sachverhalts **null**
Überschneidungen gemeldet, weil jede Kopie nur ihren eigenen Teilprozess nannte.
Das ist kein Mangel der Prüfung, sondern der Grund, warum Schnitt A ausschied:
sie ist nur so scharf wie der Schnitt, in dem sie läuft. Unter Schnitt C sieht
ein Aufruf alle Hälften, und die Prüfung greift.

**Der Trenntest bleibt einseitig, und das ist entschieden.** Das Modell wendet
ihn zwischen Geschwistern an — es kann zwei Potenziale zu einem zusammenfassen,
aber nie eines in zwei aufteilen. #194 hat **Über**-Schnitt gemessen,
**Unter**-Schnitt hat niemand gemessen; ein zweiter Modelldurchgang wäre ein Bau
gegen einen unbelegten Verdacht und verschöbe die Asymmetrie nur um eine Ebene
— seine Aufteilung prüfte dann wieder niemand. Stattdessen liefert
:func:`paare_im_kernprozess` die **Vorlage für das Menschenurteil am Gate 1**,
dem laut Karte ohnehin das Umsortieren und Herausnehmen zusteht. Was ihm fehlte,
war nicht die Befugnis, sondern die Sicht auf den Schnitt. *(Entschieden am
21.09.2026 in #248; gemessen wird die Frage am ersten echten Lauf, #206.)*
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Pruefbericht",
    "Paar",
    "ZAHL_MIT_EINHEIT",
    "erlaubte_klassen",
    "paare_im_kernprozess",
    "pruefe_schnitt",
]

#: Eine Zahl mit einer Einheit, die nur aus einer Rechnung kommen kann.
#: Wörtlich die Regel des Prototyps. Sie ist **absichtlich an die Einheit
#: gebunden** und nicht an die Ziffer: „Item 6" und „KP-02.TP-5" sind harmlos,
#: „540 Stunden" und „23.220 €" sind der Verstoß, der in 2 von 21 Aufrufen
#: auftrat — genau dort, wo Zahlen in der Nutzlast standen.
ZAHL_MIT_EINHEIT = re.compile(
    r"\b\d[\d.,]*\s*(€|EUR|Euro|Stunden|h\b|Std|Minuten|%|PT|Punkte)",
    re.IGNORECASE,
)


def erlaubte_klassen() -> tuple[str, ...]:
    """Die fünf Lösungsansatz-Klassen des Vertrags v3.0.

    Aus :mod:`modell.parameter` gelesen statt hier wiederholt: die Korridore
    hängen an genau diesen Namen, und eine zweite Liste wäre die Stelle, an der
    sie auseinanderlaufen.
    """
    from modell.parameter import STANDARD

    return tuple(STANDARD.korridore)


@dataclass(frozen=True)
class Paar:
    """Zwei Potenziale desselben Kernprozesses."""

    a: str
    b: str
    kernprozess_id: str
    gemeinsame_teilprozesse: tuple[str, ...] = ()


@dataclass(frozen=True)
class Pruefbericht:
    """Das Ergebnis der Nachkontrolle über einem Satz Potenziale."""

    anzahl: int
    #: Freigegebene Teilprozesse, die kein Potenzial berührt und die auch nicht
    #: als ``nicht_geschnitten`` gemeldet wurden. Ein stilles Loch im Paket.
    unbedeckt: tuple[str, ...] = ()
    #: Teilprozesse, die mehrere Potenziale berühren. **Kein Fehler** — ein
    #: Teilprozess kann mehrere Potenziale tragen (CONTEXT.md). Nur ein Zeiger
    #: für das Auge am Gate 1.
    mehrfach: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: Paare, die sich einen Teilprozess teilen. Verdachtsmomente für
    #: Doppelzählung, keine Feststellung.
    ueberschneidungen: tuple[Paar, ...] = ()
    #: Potenziale über mehr als einen Kernprozess. **Vertragsbruch:** ein
    #: Konzept deckt genau einen Kernprozess ab.
    ueber_kernprozess: tuple[str, ...] = ()
    #: Genannte Teilprozesse, die gar nicht im Aufruf standen.
    fremd: tuple[tuple[str, str], ...] = ()
    #: Potenziale mit einer Zahl im Text. **Verstoß gegen das Rechenverbot.**
    zahlen_im_text: tuple[str, ...] = ()
    #: Potenziale mit einer Lösungsklasse, die der Vertrag nicht kennt.
    unbekannte_klasse: tuple[tuple[str, str], ...] = ()
    #: Gemeldete, bewusst nicht geschnittene Teilprozesse.
    nicht_geschnitten: tuple[str, ...] = field(default=())

    @property
    def verstoesse(self) -> tuple[str, ...]:
        """Was den Lauf anhält, im Unterschied zu dem, was ihn nur kommentiert.

        Drei Dinge sind Verstöße, nicht Befunde: eine Zahl im Text bricht das
        Rechenverbot, auf dem alles Folgende ruht; ein Potenzial über zwei
        Kernprozesse bricht den Vertrag an BC3; eine unbekannte Klasse hat
        keinen Korridor und damit keinen Automatisierungsgrad.

        Deckungslücken gehören **nicht** dazu. Dass ein Teilprozess kein
        Potenzial trägt, kann richtig sein — die Regel „nicht schneiden,
        sondern melden" verlangt genau das.
        """
        gruende: list[str] = []
        if self.zahlen_im_text:
            gruende.append(
                "Rechenverbot gebrochen in: " + ", ".join(self.zahlen_im_text)
            )
        if self.ueber_kernprozess:
            gruende.append(
                "Potenzial ueber mehr als einen Kernprozess: "
                + ", ".join(self.ueber_kernprozess)
            )
        if self.unbekannte_klasse:
            gruende.append(
                "Loesungsklasse ausserhalb des Vertrags: "
                + ", ".join(f"{pid} -> {k!r}" for pid, k in self.unbekannte_klasse)
            )
        return tuple(gruende)

    @property
    def sauber(self) -> bool:
        return not self.verstoesse


def pruefe_schnitt(
    potenziale: list[dict[str, Any]],
    teilprozesse_im_aufruf: list[str],
    nicht_geschnitten: list[dict[str, Any]] | None = None,
) -> Pruefbericht:
    """Prüft einen Satz Potenziale gegen die mechanisch prüfbaren Zusagen.

    ``teilprozesse_im_aufruf`` ist die Menge, für die **dieser Aufruf**
    zuständig war — nicht das ganze Paket. Unter Schnitt B meldete sonst jeder
    Aufruf die Teilprozesse der anderen Kernprozesse als unbedeckt.
    """
    gemeldet = {
        e.get("teilprozess_id")
        for e in (nicht_geschnitten or [])
        if e.get("teilprozess_id")
    }
    deckung: dict[str, list[str]] = {tp: [] for tp in teilprozesse_im_aufruf}
    fremd: list[tuple[str, str]] = []
    klassen = set(erlaubte_klassen())

    for p in potenziale:
        pid = str(p.get("id", "?"))
        for tp in p.get("beruehrte_teilprozesse") or []:
            if tp not in deckung:
                fremd.append((pid, str(tp)))
                continue
            deckung[tp].append(pid)

    ueberschneidungen: list[Paar] = []
    nach_kp = {str(p.get("id", "?")): str(p.get("kernprozess_id", "")) for p in potenziale}
    for tp, ids in deckung.items():
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                ueberschneidungen.append(
                    Paar(
                        a=ids[i],
                        b=ids[j],
                        kernprozess_id=nach_kp.get(ids[i], tp.split(".")[0]),
                        gemeinsame_teilprozesse=(tp,),
                    )
                )

    ueber_kp = tuple(
        str(p.get("id", "?"))
        for p in potenziale
        if len({str(t).split(".")[0] for t in (p.get("beruehrte_teilprozesse") or [])}) > 1
    )

    zahlen = tuple(
        str(p.get("id", "?"))
        for p in potenziale
        if ZAHL_MIT_EINHEIT.search(json.dumps(p, ensure_ascii=False))
    )

    unbekannt = tuple(
        (str(p.get("id", "?")), str(p.get("loesungsklasse")))
        for p in potenziale
        if p.get("loesungsklasse") not in klassen
    )

    return Pruefbericht(
        anzahl=len(potenziale),
        unbedeckt=tuple(
            tp for tp, ids in deckung.items() if not ids and tp not in gemeldet
        ),
        mehrfach=tuple(
            (tp, tuple(ids)) for tp, ids in deckung.items() if len(ids) > 1
        ),
        ueberschneidungen=tuple(ueberschneidungen),
        ueber_kernprozess=ueber_kp,
        fremd=tuple(fremd),
        zahlen_im_text=zahlen,
        unbekannte_klasse=unbekannt,
        nicht_geschnitten=tuple(sorted(gemeldet)),
    )


def paare_im_kernprozess(potenziale: list[dict[str, Any]]) -> tuple[Paar, ...]:
    """Alle Paare innerhalb eines Kernprozesses — die Vorlage für Gate 1.

    Das Gegenstück zum einseitigen Trenntest: hier steht, **was das Modell
    getrennt gelassen hat**, damit ein Mensch fragen kann, ob es das durfte. Die
    gemeinsamen Teilprozesse stehen dabei, weil sie der einzige mechanische
    Anhaltspunkt für Doppelzählung sind — der Rest ist Urteil.
    """
    paare: list[Paar] = []
    for i in range(len(potenziale)):
        for j in range(i + 1, len(potenziale)):
            a, b = potenziale[i], potenziale[j]
            if a.get("kernprozess_id") != b.get("kernprozess_id"):
                continue
            gemeinsam = tuple(
                sorted(
                    set(a.get("beruehrte_teilprozesse") or [])
                    & set(b.get("beruehrte_teilprozesse") or [])
                )
            )
            paare.append(
                Paar(
                    a=str(a.get("id", "?")),
                    b=str(b.get("id", "?")),
                    kernprozess_id=str(a.get("kernprozess_id", "")),
                    gemeinsame_teilprozesse=gemeinsam,
                )
            )
    return tuple(paare)
