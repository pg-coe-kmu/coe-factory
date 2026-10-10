"""
BC2 · Die Naht zum Modell.

Dieselbe Bauform wie :mod:`eingang`: ein Protokoll, dahinter austauschbare
Umsetzungen. Hier aus drei Gründen, die alle drei belegt sind.

**Betrieb und Werkbank sind nicht dasselbe.** BC2 läuft als Docker-Container auf
dem netcup-VPS; dort gibt es keine Claude-CLI und keine angemeldete Sitzung. Der
Prototyp zu #194 startete ``claude -p`` als Unterprozess — im Container liefe das
ins Leere. :class:`SdkModell` ist darum der Betriebsweg.

**Ein Bau, den nie ein echtes Modell beantwortet hat, ist nicht gebaut.** Genau
diese Lücke hat die Karte an #205 teuer bezahlt: 48 grüne Tests belegten nicht,
dass je ein echter Ruf durchging, weil sie mit ihrem eigenen Testschlüssel
signierten. :class:`CliModell` ist deshalb kein Vorrat, sondern der Weg, diesen
Schritt ohne API-Schlüssel an einem echten Aufruf zu messen.

**Tests rufen nie ein Modell.** :class:`Doppelgaenger` antwortet aus einer
Liste. Er beweist nichts über das Modell — er hält die Prüfkette prüfbar.

Modellwahl: **Sonnet** als Voreinstellung, weil die Entscheidung in #194 auf
Sonnet gemessen wurde. Auf Opus zu wechseln hieße, den einzigen Beleg gegen ein
ungemessenes Modell zu tauschen; es bleibt ein Parameter, kein Umbau.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Protocol

__all__ = [
    "Antwort", "CliModell", "Doppelgaenger", "Modellruf", "SdkModell",
    "lies_json", "protokolliere_unlesbar", "schaele_json",
]

#: Voreinstellung. Siehe Modulkopf.
_log = logging.getLogger("bc2.modell")

STANDARDMODELL = "sonnet"

#: Ein Erkennungsaufruf über den ganzen NoroAI-Bestand landet bei ~8.500 Token
#: Eingabe; die Antwort ist ein Vielfaches kürzer, aber zehn Potenziale mit
#: Begründungen brauchen Platz. Großzügig gesetzt: eine abgeschnittene Antwort
#: ist kein Fehler, den man sieht — sie ist ein JSON, das nicht mehr schließt.
STANDARD_MAX_TOKEN = 16_000


@dataclass(frozen=True)
class Antwort:
    """Eine Modellantwort, roh und geschält."""

    roh: str
    #: ``None``, wenn sich aus der Antwort kein JSON schälen ließ.
    ergebnis: dict | None
    modell: str
    #: Warum ``ergebnis`` fehlt — als fertiger Prüfgrund mit Stelle und Umfeld,
    #: damit er in die Mahnung und an den Lauf gehen kann (#317).
    lesefehler: str | None = None

    @property
    def potenziale(self) -> list[dict]:
        return list((self.ergebnis or {}).get("potenziale") or [])

    @property
    def nicht_geschnitten(self) -> list[dict]:
        return list((self.ergebnis or {}).get("nicht_geschnitten") or [])


class Modellruf(Protocol):
    """Was der Erkennungsschritt vom Modell braucht — mehr nicht."""

    def frage(self, text: str) -> Antwort:
        ...


def lies_json(roh: str) -> tuple[dict | None, str | None]:
    """Zieht das JSON-Objekt aus einer Modellantwort — oder sagt, woran es bricht.

    Gelesen wird ab der ersten ``{`` mit ``raw_decode``: das endet am Ende des
    Objekts, also stören weder ein äußerer ```` ```json ````-Zaun noch ein
    Nachsatz. Bis #317 wurde die Antwort an *jedem* Zaun zerlegt — ein
    Codeblock in einem Markdown-Feld (``loesungsansatz``) schnitt das JSON dann
    mittendrin ab, und drei von vier Ausarbeitungen scheiterten daran.

    Die Zerlegung am Zaun bleibt als Rückfall für eine Einleitung, die selbst
    eine ``{`` enthält. Der Lesefehler stammt aus dem ersten Versuch, weil der
    auf das ganze Objekt zielt.
    """
    t = roh.strip()
    a = t.find("{")
    if a == -1:
        return None, (
            "Die Antwort enthält kein JSON-Objekt: es gibt keine öffnende "
            "geschweifte Klammer {."
        )
    try:
        gelesen, _ = json.JSONDecoder().raw_decode(t, a)
    except json.JSONDecodeError as fehler:
        gelesen, lesefehler = None, _lesefehler(fehler)
    else:
        if isinstance(gelesen, dict):
            return gelesen, None
        lesefehler = "Die Antwort ist kein JSON-Objekt, sondern ein anderer JSON-Wert."
    for teil in t.split("```")[1:]:
        teil = teil.lstrip()
        if teil.startswith("json"):
            teil = teil[4:]
        teil = teil.strip()
        if teil.startswith("{"):
            try:
                gelesen, _ = json.JSONDecoder().raw_decode(teil)
            except json.JSONDecodeError:
                continue
            if isinstance(gelesen, dict):
                return gelesen, None
    return None, lesefehler


def _lesefehler(fehler: json.JSONDecodeError, rand: int = 100) -> str:
    """Stelle und Umfeld eines Lesefehlers, für Mensch und Modell lesbar."""
    s, pos = fehler.doc, fehler.pos
    umfeld = s[max(0, pos - rand) : pos] + "⟦hier⟧" + s[pos : pos + rand]
    return (
        f"Die Antwort ist kein gültiges JSON: {fehler.msg} "
        f"(Zeile {fehler.lineno}, Spalte {fehler.colno}). Umfeld: {umfeld!r}. "
        'Häufigste Ursache: ein Anführungszeichen " in einem Text, das nicht '
        'als \\" geschützt ist.'
    )


def schaele_json(roh: str) -> dict | None:
    """Nur das Objekt aus :func:`lies_json` — für alle, die den Grund nicht brauchen."""
    return lies_json(roh)[0]


def protokolliere_unlesbar(modell: str, roh: str, lesefehler: str | None) -> None:
    """Die **ganze** Rohantwort ins Protokoll, wenn sie sich nicht lesen ließ.

    Am Lauf stehen nur Anfang und Ende; beim ersten Fehlschlag (#317) ließ sich
    deshalb nicht sagen, woran 27.726 Zeichen gescheitert waren. Ins Log, nicht
    in die Datenbank: die Antwort trägt die Texte des Mandanten, und eine
    Fehlerspalte ist kein Archiv.
    """
    _log.warning(
        "Antwort von %s nicht lesbar (%s). Vollständig, %d Zeichen:\n%s",
        modell, lesefehler, len(roh), roh,
    )


def _antwort(roh: str, modell: str, *, protokollieren: bool = True) -> Antwort:
    ergebnis, lesefehler = lies_json(roh)
    if ergebnis is None and protokollieren:
        protokolliere_unlesbar(modell, roh, lesefehler)
    return Antwort(roh=roh, ergebnis=ergebnis, modell=modell, lesefehler=lesefehler)


@dataclass
class SdkModell:
    """Der Betriebsweg: die Anthropic-API über ``ANTHROPIC_API_KEY``.

    Der Schlüssel gehört **ausschließlich** in eine Umgebungsvariable — nicht in
    Repo, Issue, Code oder Kommentar (ADR-003, BC0-Regel 5). Das ``anthropic``-
    Paket wird erst beim Aufruf importiert, damit Tests und der Trigger-Endpunkt
    ohne es auskommen.

    .. warning::
       **Beim Bau (#248) nicht gefahren** — es lag kein ``ANTHROPIC_API_KEY``
       vor. Gemessen wurde über :class:`CliModell`. Der erste echte Lauf über
       diesen Weg gehört zu #206.
    """

    modell: str = "claude-sonnet-4-6"
    max_token: int = STANDARD_MAX_TOKEN
    schluessel: str | None = None

    def frage(self, text: str) -> Antwort:
        import anthropic

        schluessel = self.schluessel or (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        if not schluessel:
            raise RuntimeError(
                "ANTHROPIC_API_KEY ist nicht gesetzt. Der Schluessel gehoert "
                "ausschliesslich in eine Umgebungsvariable (ADR-003)."
            )
        klient = anthropic.Anthropic(api_key=schluessel)
        beginn = time.monotonic()
        antwort = klient.messages.create(
            model=self.modell,
            max_tokens=self.max_token,
            messages=[{"role": "user", "content": text}],
        )
        roh = "".join(b.text for b in antwort.content if getattr(b, "type", "") == "text")
        # Jeder Aufruf ins Protokoll: Abbruchgrund, Token, Dauer. Der zweite echte
        # Lauf (10.10.2026) scheiterte an einer Antwort ohne JSON, und ohne
        # ``stop_reason`` war nicht zu sagen, ob sie abgeschnitten war.
        nutzung = getattr(antwort, "usage", None)
        _log.log(
            logging.WARNING if antwort.stop_reason != "end_turn" else logging.INFO,
            "Modellaufruf %s: stop_reason=%s, Token ein=%s aus=%s, %.0f s, %d Zeichen Antwort",
            self.modell, antwort.stop_reason,
            getattr(nutzung, "input_tokens", "?"), getattr(nutzung, "output_tokens", "?"),
            time.monotonic() - beginn, len(roh),
        )
        if antwort.stop_reason == "max_tokens":
            roh += f"\n[BC2: abgeschnitten bei max_tokens={self.max_token}]"
        return _antwort(roh, self.modell)


@dataclass
class CliModell:
    """Die Werkbank: ``claude -p`` als Unterprozess, wie im Prototyp zu #194.

    Nur für Messungen von Hand. Im Container gibt es die CLI nicht.
    """

    modell: str = STANDARDMODELL
    zeitgrenze_s: int = 900

    def frage(self, text: str) -> Antwort:
        lauf = subprocess.run(
            ["claude", "-p", "--model", self.modell, text],
            capture_output=True,
            text=True,
            timeout=self.zeitgrenze_s,
        )
        if lauf.returncode != 0:
            raise RuntimeError(f"claude-CLI scheiterte: {lauf.stderr[-2000:]}")
        return _antwort(lauf.stdout, f"cli:{self.modell}")


@dataclass
class Doppelgaenger:
    """Antwortet aus einer vorbereiteten Liste. Für Tests.

    **Er beweist nichts über das Modell.** Er hält nur die Kette um das Modell
    herum prüfbar: Nutzlast, Wächter, Wiederholung, Abbildung. Dass ein Modell
    sich an das Rechenverbot hält, ist damit *nicht* gezeigt — in #194 hielt es
    sich in 2 von 21 Aufrufen nicht daran, und genau dafür gibt es den Wächter.
    """

    antworten: list[str | dict] = field(default_factory=list)
    #: Jede gestellte Frage, in der Reihenfolge — damit ein Test prüfen kann,
    #: dass die Wiederholung die Mahnung wirklich mitführt.
    fragen: list[str] = field(default_factory=list)
    modell: str = "doppelgaenger"

    def frage(self, text: str) -> Antwort:
        self.fragen.append(text)
        if not self.antworten:
            raise AssertionError(
                "Doppelgaenger: mehr Aufrufe als vorbereitete Antworten "
                f"(bisher {len(self.fragen)})."
            )
        naechste = self.antworten.pop(0)
        roh = (
            naechste
            if isinstance(naechste, str)
            else json.dumps(naechste, ensure_ascii=False)
        )
        return _antwort(roh, self.modell, protokollieren=False)
