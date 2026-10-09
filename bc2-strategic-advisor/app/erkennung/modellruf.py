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
import os
import subprocess
from dataclasses import dataclass, field
from typing import Protocol

__all__ = ["Antwort", "CliModell", "Doppelgaenger", "Modellruf", "SdkModell", "schaele_json"]

#: Voreinstellung. Siehe Modulkopf.
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


def schaele_json(roh: str) -> dict | None:
    """Zieht das JSON-Objekt aus einer Modellantwort.

    Übernommen aus dem Prototyp. Das Modell hält sich meist an „antworte mit
    nichts als JSON", aber eben nur meist — und ein Lauf an einem
    Einleitungssatz scheitern zu lassen, wäre teurer Purismus.
    """
    t = roh.strip()
    if "```" in t:
        for teil in t.split("```"):
            teil = teil.lstrip()
            if teil.startswith("json"):
                teil = teil[4:]
            teil = teil.strip()
            if teil.startswith("{"):
                t = teil
                break
    a, b = t.find("{"), t.rfind("}")
    if a == -1 or b == -1:
        return None
    try:
        geschaelt = json.loads(t[a : b + 1])
    except json.JSONDecodeError:
        return None
    return geschaelt if isinstance(geschaelt, dict) else None


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
        antwort = klient.messages.create(
            model=self.modell,
            max_tokens=self.max_token,
            messages=[{"role": "user", "content": text}],
        )
        roh = "".join(b.text for b in antwort.content if getattr(b, "type", "") == "text")
        return Antwort(roh=roh, ergebnis=schaele_json(roh), modell=self.modell)


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
        return Antwort(
            roh=lauf.stdout, ergebnis=schaele_json(lauf.stdout), modell=f"cli:{self.modell}"
        )


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
        return Antwort(roh=roh, ergebnis=schaele_json(roh), modell=self.modell)
