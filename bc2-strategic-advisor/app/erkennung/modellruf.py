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

**Die Form sichert das Antwortschema, den Inhalt der Wächter (#319).** Jeder
Schritt reicht neben seiner Anweisung ein Schema mit. :class:`SdkModell` gibt es
als ``output_config`` weiter, und die API dekodiert beschränkt: die Antwort *ist*
gültiges JSON in dieser Form — außer bei ``stop_reason`` ``max_tokens`` oder
``refusal``, die darum eigene Lesefehler bleiben. :class:`CliModell` gibt es als
``--json-schema`` weiter; die CLI dekodiert nicht beschränkt, sondern prüft und
fragt nach. Mindestlängen, Rechenverbot, Platzhalter, SOPHIST/GWT und gebundene
Systeme kann ein Schema nicht ausdrücken (kein ``minLength``, keine Muster mit
Wortgrenzen) — sie bleiben in Python. :func:`lies_json` bleibt als Netz darunter.

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
    "lies_json", "objekt", "oder_null", "protokolliere_unlesbar", "schaele_json",
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
    """Was die drei Schritte vom Modell brauchen — mehr nicht."""

    def frage(self, text: str, schema: dict | None = None) -> Antwort:
        ...


def objekt(**eigenschaften: dict) -> dict:
    """Ein Objekt im Antwortschema: jedes Feld Pflicht, keine fremden Felder.

    Alles Pflicht, weil die API höchstens 24 optionale Felder je Request
    zulässt und optionale Felder in der Ausgabe hinter die Pflichtfelder
    rücken. Was fehlen darf, ist :func:`oder_null` — ausdrücklich ``null``
    statt weggelassen, wie es die Anweisungen ohnehin verlangen.
    """
    return {
        "type": "object",
        "properties": eigenschaften,
        "required": list(eigenschaften),
        "additionalProperties": False,
    }


def oder_null(schema: dict) -> dict:
    """Ein Feld, das ``null`` sein darf. Zählt gegen die 16 Union-Typen."""
    return {**schema, "type": [schema["type"], "null"]}


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

    Erster echter Lauf am 10.10.2026 (#206); mit Antwortschema seit #319.
    """

    modell: str = "claude-sonnet-4-6"
    max_token: int = STANDARD_MAX_TOKEN
    schluessel: str | None = None

    def frage(self, text: str, schema: dict | None = None) -> Antwort:
        import anthropic

        schluessel = self.schluessel or (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        if not schluessel:
            raise RuntimeError(
                "ANTHROPIC_API_KEY ist nicht gesetzt. Der Schluessel gehoert "
                "ausschliesslich in eine Umgebungsvariable (ADR-003)."
            )
        klient = anthropic.Anthropic(api_key=schluessel)
        beginn = time.monotonic()
        zusatz = (
            {"output_config": {"format": {"type": "json_schema", "schema": schema}}}
            if schema is not None
            else {}
        )
        antwort = klient.messages.create(
            model=self.modell,
            max_tokens=self.max_token,
            messages=[{"role": "user", "content": text}],
            **zusatz,
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
        # Die beiden Fälle, in denen auch das Schema nichts garantiert: die
        # Antwort ist abgeschnitten oder eine Ablehnung. Nicht schälen — ein
        # zufällig lesbarer Rest wäre schlimmer als ein benannter Fehler.
        grund = {
            "max_tokens": (
                f"Die Antwort ist bei max_tokens={self.max_token} abgeschnitten "
                "(stop_reason=max_tokens). Fasse die Texte knapper."
            ),
            "refusal": "Das Modell hat die Antwort abgelehnt (stop_reason=refusal).",
        }.get(antwort.stop_reason)
        if grund:
            protokolliere_unlesbar(self.modell, roh, grund)
            return Antwort(roh=roh, ergebnis=None, modell=self.modell, lesefehler=grund)
        return _antwort(roh, self.modell)


@dataclass
class CliModell:
    """Die Werkbank: ``claude -p`` als Unterprozess, wie im Prototyp zu #194.

    Nur für Messungen von Hand. Im Container gibt es die CLI nicht.

    Mit Schema antwortet die CLI als JSON-Hülle (``--output-format json``), das
    Ergebnis steht in ``structured_output``. Die CLI dekodiert nicht beschränkt,
    sie prüft gegen das Schema und fragt selbst nach; gibt sie auf
    (``error_max_structured_output_retries``) oder meldet ``success`` ohne
    Ergebnis, ist das ein Lesefehler wie jeder andere.
    """

    modell: str = STANDARDMODELL
    zeitgrenze_s: int = 900

    def frage(self, text: str, schema: dict | None = None) -> Antwort:
        befehl = ["claude", "-p", "--model", self.modell]
        if schema is not None:
            befehl += [
                "--output-format", "json",
                "--json-schema", json.dumps(schema, ensure_ascii=False),
            ]
        lauf = subprocess.run(
            befehl + [text],
            capture_output=True,
            text=True,
            timeout=self.zeitgrenze_s,
        )
        name = f"cli:{self.modell}"
        if schema is None:
            if lauf.returncode != 0:
                raise RuntimeError(f"claude-CLI scheiterte: {lauf.stderr[-2000:]}")
            return _antwort(lauf.stdout, name)
        return _aus_huelle(lauf.stdout, lauf.stderr, name)


def _aus_huelle(stdout: str, stderr: str, modell: str) -> Antwort:
    """Das Ergebnis aus der JSON-Hülle der CLI — oder der Grund, warum keines da ist.

    Der Rückgabewert des Prozesses entscheidet nicht: ein gescheiterter Lauf
    druckt seine Hülle trotzdem, und erst ``subtype`` sagt, woran er scheiterte.
    """
    try:
        huelle = json.loads(stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"claude-CLI lieferte keine JSON-Hülle: {(stderr or stdout)[-2000:]}"
        ) from None
    ergebnis = huelle.get("structured_output") if isinstance(huelle, dict) else None
    art = huelle.get("subtype") if isinstance(huelle, dict) else None
    if art == "success" and isinstance(ergebnis, dict):
        return Antwort(
            roh=json.dumps(ergebnis, ensure_ascii=False), ergebnis=ergebnis, modell=modell
        )
    if art == "success":
        grund = "Die CLI meldet Erfolg, aber ohne structured_output."
    else:
        grund = f"Die CLI hat kein schemagültiges Ergebnis geliefert ({art})."
    protokolliere_unlesbar(modell, stdout, grund)
    return Antwort(roh=stdout, ergebnis=None, modell=modell, lesefehler=grund)


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
    #: Das mitgegebene Antwortschema je Frage. Geprüft wird die vorbereitete
    #: Antwort dagegen **nicht** — die Tests füttern absichtlich auch Formen,
    #: die nur über die CLI oder ohne Schema ankommen können.
    schemas: list[dict | None] = field(default_factory=list)
    modell: str = "doppelgaenger"

    def frage(self, text: str, schema: dict | None = None) -> Antwort:
        self.fragen.append(text)
        self.schemas.append(schema)
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
