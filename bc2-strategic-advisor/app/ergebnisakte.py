"""
BC2 · Die Ergebnisakte — was bei der Freigabe aus einem Lauf festgehalten wird (#378).

Entschieden in #376 (ADR-007 · BC2, Nachtrag vom 13.11.2026): **jede Freigabe
friert eine Akte ein**, auch bei einem Lauf mit Sperrgrund, und zwar in
derselben Transaktion wie ``approved``. Scheitert das Einfrieren, gilt die
Freigabe nicht. Die Akte trägt die Dateien Byte für Byte, jede mit ihrem
Empfänger:

==============================  =========  =====================================
``prozesspriorisierung.json``   ``bc3``    das abgelegte Dokument plus ``gate1``
``konzept_<KP>.json``           ``bc3``    je Konzept
``NACHRICHT_AN_BC3.md``         ``bc3``    Paket, Fassung, Freigabe, Reihenfolge
``praesentation.pptx``          mandant    der Foliensatz, einmal gezeichnet
==============================  =========  =====================================

Die drei ``bc3``-Dateien gibt es nur bei einem **lieferbaren** Lauf: ein Lauf
mit Sperrgrund hat eine Akte, aber keine Lieferung (Nachtrag 13.11., Punkt 2).
Damit gibt es **eine** Stelle, an der die Lieferdatei entsteht — hier, im
Dienst. ``tools/lieferung_ziehen.py`` schreibt die ``bc3``-Dateien nur noch ab.

Darum liegen hier, umgezogen aus dem Werkzeug, das **Ordnen** der Schlüssel
nach den Vertragsschemas (sie kommen dafür ins Image, ``BC2_VERTRAG``) und die
**Nachricht** an BC3. Beide unverändert: die Lieferung ``cc7f4d1b`` (f1) liegt
schon im Repo und muss beim nachträglichen Einfrieren byte-gleich herauskommen.

Ablage und Unveränderlichkeit setzt die Datenbank durch
(``migration_bc2.4_ergebnisakte.sql``); die Tabellen schreibt
``gate1.PostgresGate1Buch``, weil die Akte in dessen Transaktion entsteht.

Aufruf im Container, für das nachträgliche Einfrieren (#378, Punkt 6)::

    docker exec app-app-1 python -m ergebnisakte offen
    docker exec app-app-1 python -m ergebnisakte nachtragen <paket_id> --vermerk "…" --trocken
    docker exec app-app-1 python -m ergebnisakte nachtragen <paket_id> --vermerk "…"
    docker exec app-app-1 python -m ergebnisakte sperren <link_token>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # nur für Signaturen; gate1.py importiert dieses Modul
    from ablage import AbgelegterLauf, Ergebnisbuch
    from gate1 import Gate1Buch, Gate1Entscheidung
    from laeufe import Laufansicht

__all__ = [
    "AkteFehlt",
    "AkteUngueltig",
    "Aktendatei",
    "Ergebnisakte",
    "NachtragNichtMoeglich",
    "akte_einfrieren",
    "bc3_dateien",
    "mandantenkuerzel",
    "nachricht",
    "nachtragen",
    "ordne",
    "ordnername",
]

PRIO_DATEI = "prozesspriorisierung.json"
NACHRICHT_DATEI = "NACHRICHT_AN_BC3.md"
#: Wie ``praesentation.DATEINAME`` — hier wiederholt, damit dieses Modul ohne
#: ``python-pptx`` importierbar bleibt (das Werkzeug liest nur Bytes).
PRAESENTATION_DATEI = "praesentation.pptx"
EMPFAENGER = ("bc3", "mandant")

#: Die Form, die ``bc2.ergebnisakte.link_token`` zulässt. Alles andere ist
#: unbekannt, ohne dass die Datenbank gefragt wird.
TOKEN_FORM = re.compile(r"[A-Za-z0-9_-]{20,}")

PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"


class AkteFehlt(Exception):
    """Eine Freigabe ohne Ergebnisakte gilt nicht (Nachtrag 13.11., Punkt 1)."""


class AkteUngueltig(ValueError):
    """Die Akte passt nicht zum Lauf oder zur Entscheidung."""


class NachtragNichtMoeglich(Exception):
    """Der Lauf lässt sich nicht nachträglich einfrieren — mit Grund."""


# ----------------------------------------------------------------------------
# Die Akte
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Aktendatei:
    name: str
    #: ``bc3`` oder ``mandant``.
    empfaenger: str
    inhalt: bytes

    @property
    def pruefsumme(self) -> str:
        """SHA-256 des Inhalts, hexadezimal — so prüft es auch die Datenbank."""
        return hashlib.sha256(self.inhalt).hexdigest()


@dataclass(frozen=True)
class Ergebnisakte:
    """Kopf und Dateien einer Akte. Unveränderlich, bis auf die Sperre des Links."""

    company_id: str
    paket_id: str
    fassung: int
    ordner: str
    sperrgrund: str | None
    link_token: str
    dateien: tuple[Aktendatei, ...]
    #: Nur beim nachträglichen Einfrieren eines schon freigegebenen Laufs.
    vermerk: str | None = None
    #: Setzt die Ablage; vor dem Schreiben ``None``.
    eingefroren_am: datetime | None = None
    link_gesperrt_am: datetime | None = None

    @property
    def lieferbar(self) -> bool:
        return self.sperrgrund is None

    def datei(self, name: str) -> Aktendatei | None:
        return next((d for d in self.dateien if d.name == name), None)

    def fuer(self, empfaenger: str) -> tuple[Aktendatei, ...]:
        return tuple(d for d in self.dateien if d.empfaenger == empfaenger)

    @property
    def praesentation(self) -> bytes | None:
        d = self.datei(PRAESENTATION_DATEI)
        return d.inhalt if d is not None else None

    def als_uebersicht(self) -> dict:
        """Was die Oberfläche zeigt — ohne die Bytes.

        ``link`` ist **relativ zur Seite** (``praesentation/<token>``): die
        Vorschau liegt unter ``/vorschau/``, und dort muss der Link auf ihre
        eigene Instanz zeigen, nicht auf die echte.
        """
        return {
            "ordner": self.ordner,
            "lieferbar": self.lieferbar,
            "eingefroren_am": self.eingefroren_am.isoformat() if self.eingefroren_am else None,
            "vermerk": self.vermerk,
            "link": None if self.link_gesperrt_am else f"praesentation/{self.link_token}",
            "link_gesperrt_am": (
                self.link_gesperrt_am.isoformat() if self.link_gesperrt_am else None
            ),
            "dateien": [
                {"name": d.name, "empfaenger": d.empfaenger, "pruefsumme": d.pruefsumme,
                 "groesse": len(d.inhalt)}
                for d in self.dateien
            ],
        }


def pruefe(akte: Ergebnisakte, entscheidung: Gate1Entscheidung | None = None) -> None:
    """Was die Datenbank beim Einfügen ohnehin prüft, vorher und mit Klartext.

    Der Doppelgänger im Arbeitsspeicher lebt allein von dieser Prüfung; in
    Postgres steht sie zusätzlich als Trigger (``migration_bc2.4``).
    """
    maengel = []
    if entscheidung is not None:
        if entscheidung.status != "approved":
            maengel.append(f"eine Akte gibt es nur zu einer Freigabe, nicht zu {entscheidung.status!r}")
        if (entscheidung.paket_id, entscheidung.fassung) != (akte.paket_id, akte.fassung):
            maengel.append(
                f"Akte {akte.paket_id} f{akte.fassung} gehoert nicht zur Entscheidung ueber "
                f"{entscheidung.paket_id} f{entscheidung.fassung}"
            )
    namen = [d.name for d in akte.dateien]
    if len(namen) != len(set(namen)):
        maengel.append("ein Dateiname kommt doppelt vor")
    for d in akte.dateien:
        if d.empfaenger not in EMPFAENGER:
            maengel.append(f"{d.name}: Empfaenger {d.empfaenger!r} gibt es nicht")
        if d.empfaenger == "bc3" and not akte.lieferbar:
            maengel.append(f"{d.name}: ein Lauf mit Sperrgrund hat keine Lieferung an BC3")
    if akte.praesentation is None:
        maengel.append("die Praesentation fehlt")
    if not TOKEN_FORM.fullmatch(akte.link_token):
        maengel.append("das Link-Token hat nicht die erwartete Form")
    if maengel:
        raise AkteUngueltig("; ".join(maengel))


def neues_token() -> str:
    """32 Zeichen aus 24 Zufallsbytes — nicht zu erraten, und ohne Schlüssel gültig."""
    return secrets.token_urlsafe(24)


# ----------------------------------------------------------------------------
# Ordnername (aus lieferung.py umgezogen, #306)
# ----------------------------------------------------------------------------


def mandantenkuerzel(name: str | None, company_id: str) -> str:
    """Der ``<company>``-Teil des Ordnernamens aus ADR-007 (2.2).

    ADR-007 legt ``<company>-<paket_id>-f<n>`` fest, aber nicht, woraus
    ``<company>`` entsteht; die erste Lieferung nennt NoroAI ``noroai``. Hier:
    das erste Wort des Mandantennamens, klein, nur Buchstaben und Ziffern —
    und ohne Namen die ersten acht Zeichen der ``company_id``, statt einen
    Namen zu raten. **Annahme aus #257**, rückbaubar an dieser einen Stelle.
    """
    teile = (name or "").split()
    if teile:
        erstes = re.sub(r"[^a-z0-9]", "", teile[0].lower())
        if erstes:
            return erstes
    return company_id[:8].lower()


def ordnername(kuerzel: str, paket_id: str, fassung: int) -> str:
    """``<company>-<paket_id>-f<n>`` (ADR-007 · BC2, 2.2)."""
    return f"{kuerzel}-{paket_id}-f{fassung}"


# ----------------------------------------------------------------------------
# Byte-gleich: Schlüssel nach dem Schema ordnen (aus tools/lieferung_ziehen.py)
# ----------------------------------------------------------------------------


def vertragsverzeichnis() -> Path:
    """Wo die Vertragsschemas liegen.

    Im Container ``/vertrag`` (``BC2_VERTRAG``, gesetzt im ``Dockerfile``; die
    Schemas kommen über einen zweiten Bau-Kontext ins Image, weil sie
    ausserhalb von ``app/`` liegen). Lokal ``contracts/bc2-to-bc3`` im Repo.
    """
    gesetzt = (os.environ.get("BC2_VERTRAG") or "").strip()
    if gesetzt:
        return Path(gesetzt)
    return Path(__file__).resolve().parent.parent.parent / "contracts" / "bc2-to-bc3"


def vertragsschemas() -> tuple[dict, dict]:
    """``(priorisierung, konzept)``. Fehlen sie, scheitert das Einfrieren laut."""
    ort = vertragsverzeichnis()
    try:
        return (
            json.loads((ort / "priorisierung.schema.json").read_text(encoding="utf-8")),
            json.loads((ort / "konzept.schema.json").read_text(encoding="utf-8")),
        )
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Die Vertragsschemas fehlen unter {ort} (BC2_VERTRAG). Ohne sie lassen sich "
            "die Dateien an BC3 nicht byte-gleich ordnen."
        ) from e


def _aufloesen(knoten: dict, wurzel: dict) -> dict:
    """Folgt ``$ref`` und wählt aus ``anyOf``/``oneOf``/``allOf`` den Zweig, der
    eine Gestalt hat — für die Reihenfolge genügt das, geprüft wird anderswo."""
    while "$ref" in knoten:
        teile = knoten["$ref"].lstrip("#/").split("/")
        ziel = wurzel
        for t in teile:
            ziel = ziel[t]
        knoten = ziel
    if "properties" in knoten or "items" in knoten:
        return knoten
    for schluessel in ("anyOf", "oneOf", "allOf"):
        for zweig in knoten.get(schluessel, []):
            zweig = _aufloesen(zweig, wurzel)
            if "properties" in zweig or "items" in zweig:
                return zweig
    return knoten


def ordne(daten, knoten: dict | None, wurzel: dict):
    """Ordnet die Schlüssel wie im Schema; Unbekanntes alphabetisch dahinter.

    Nötig, weil Postgres ``jsonb`` die Reihenfolge nicht bewahrt — es gibt die
    Schlüssel kurz vor lang zurück. Byte-gleich wäre auch das, lesbar nicht.
    """
    knoten = _aufloesen(knoten or {}, wurzel)
    if isinstance(daten, dict):
        eigenschaften = knoten.get("properties", {})
        reihe = [k for k in eigenschaften if k in daten]
        reihe += sorted(k for k in daten if k not in eigenschaften)
        return {k: ordne(daten[k], eigenschaften.get(k), wurzel) for k in reihe}
    if isinstance(daten, list):
        items = knoten.get("items")
        return [ordne(x, items if isinstance(items, dict) else None, wurzel) for x in daten]
    return daten


def als_text(daten) -> str:
    return json.dumps(daten, ensure_ascii=False, indent=2) + "\n"


# ----------------------------------------------------------------------------
# Die Nachricht an BC3 (aus tools/lieferung_ziehen.py)
# ----------------------------------------------------------------------------


def _reihenfolge(gesetzt: list[str], gerechnet: list[str]) -> list[str]:
    return list(gesetzt) if gesetzt else list(gerechnet)


def nachricht(lieferung: dict) -> str:
    """Kurz und ohne Zeitpunkt des Einfrierens — sonst wäre sie nicht wiederholbar.

    **Der Kopf nennt weiter ``tools/lieferung_ziehen.py``**, obwohl die
    Nachricht seit #378 hier entsteht: er ist Wortlaut gelieferter Dateien, und
    die Lieferung ``cc7f4d1b`` (f1) muss beim nachträglichen Einfrieren
    byte-gleich herauskommen. Eine neue Kopfzeile gehört in eine
    Vertragsänderung, nicht in einen Umzug.
    """
    p = lieferung["priorisierung"]
    g = p["gate1"]
    kp_namen = lieferung.get("kp_namen") or {}
    verwiesen = lieferung.get("verwiesen") or {}
    konzepte = {k["kontext"]["kp_id"]: k for k in lieferung["konzepte"]}
    mandant = ((p.get("ausgangslage") or {}).get("unternehmen") or {}).get("name")

    eintraege = {e["potenzial_id"]: e for e in p["eintraege"]}
    potenzialfolge = _reihenfolge(
        g.get("finale_reihenfolge_potenzial_ids") or [],
        [e["potenzial_id"] for e in sorted(p["eintraege"], key=lambda e: e["potenzialrang"])],
    )
    prozessfolge = _reihenfolge(
        g.get("finale_prozessreihenfolge_kp_ids") or [],
        [r["kp_id"] for r in sorted(p["prozess_raenge"], key=lambda r: r["prozessrang"])],
    )
    nicht = {n["potenzial_id"]: n["begruendung"] for n in g.get("nicht_freigegeben") or []}

    def verweis(pid: str) -> str:
        v = verwiesen.get(pid) or {}
        titel = v.get("titel") or "unbekannt"
        herkunft = f", Paket {v['paket_id']}" if v.get("paket_id") else ""
        return f"{titel} (`{pid}`{herkunft})"

    freigabe = f"freigegeben am {g.get('entschieden_am', 'unbekannt')}"
    if g.get("entscheider"):
        freigabe += f" durch {g['entscheider']}"

    z = [
        f"# Lieferung an BC3 — {lieferung['ordner']}",
        "",
        "> Maschinell erzeugt von `bc2-strategic-advisor/tools/lieferung_ziehen.py` aus Schema",
        "> `bc2` (ADR-007 · BC2, Nachtrag #305). Nicht von Hand ändern: der nächste Zug bricht",
        "> dann ab, weil eine Lieferung sich nach der Übergabe nicht mehr ändert.",
        "",
        "| | |",
        "|---|---|",
        f"| Mandant | {mandant or '—'} (`{p['company_id']}`) |",
        f"| Paket | `{p['paket_id']}`, übergeben am {p['uebergeben_am']} |",
        f"| Fassung | f{p['fassung']} |",
        f"| Gate 1 | {freigabe} |",
        f"| Vertrag | {p['schema_version']} |",
        "",
        "## Konzepte in finaler Reihenfolge",
        "",
    ]
    for i, kp in enumerate(prozessfolge, 1):
        k = konzepte[kp]
        name = kp_namen.get(kp)
        z.append(f"{i}. **{kp}{' — ' + name if name else ''}** · `konzept_{kp}.json`")
        if k.get("ersetzt_konzept_id"):
            z.append(f"   - ersetzt Konzept `{k['ersetzt_konzept_id']}` aus der vorigen Fassung")
        alte = {p_["potenzial_id"]: p_.get("ersetzt_potenzial_ids") or [] for p_ in k["potenziale"]}
        for pid in potenzialfolge:
            e = eintraege[pid]
            if e["kp_id"] != kp:
                continue
            if pid in nicht:
                z.append(f"   - ~~{e['titel']}~~ — nicht freigegeben: {nicht[pid]}")
            else:
                z.append(f"   - {e['titel']} · {e['prioritaetsgruppe']} · Score {e['score']}")
            for alt in alte.get(pid, []):
                z.append(f"     - schreibt fort: {verweis(alt)}")
    gestrichen = p.get("gestrichene_potenziale") or []
    if gestrichen:
        z += ["", "## Gestrichen", ""]
        z += [f"- {verweis(s['potenzial_id'])}: {s['begruendung']}" for s in gestrichen]
    if g.get("abweichungsbegruendung"):
        z += ["", "## Abweichung vom gerechneten Rang", "", g["abweichungsbegruendung"]]
    hinweise = lieferung.get("hinweise") or []
    if hinweise:
        z += ["", "## Hinweise", ""]
        z += [f"- {h}" for h in hinweise]
    return "\n".join(z) + "\n"


def bc3_dateien(lieferung: dict, prio_schema: dict, konzept_schema: dict) -> dict[str, str]:
    """Name → Inhalt der Dateien an BC3, wie sie im Lieferordner liegen."""
    ergebnis = {PRIO_DATEI: als_text(ordne(lieferung["priorisierung"], prio_schema, prio_schema))}
    for k in lieferung["konzepte"]:
        name = f"konzept_{k['kontext']['kp_id']}.json"
        ergebnis[name] = als_text(ordne(k, konzept_schema, konzept_schema))
    ergebnis[NACHRICHT_DATEI] = nachricht(lieferung)
    return dict(sorted(ergebnis.items()))


# ----------------------------------------------------------------------------
# Einfrieren
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Aktenstoff:
    """Was aus einem Lauf in die Akte geht, noch ohne Gate 1."""

    company_id: str
    paket_id: str
    fassung: int
    #: Das Priorisierungsdokument **ohne** ``gate1``.
    priorisierung: dict
    konzepte: list[dict]
    sperrgrund: str | None
    hinweise: tuple[str, ...] = ()
    kp_namen: dict | None = None
    #: Was hinter den Kennungen von Vorgängern und Gestrichenen steht (für die Nachricht).
    verwiesen: dict | None = None


def stoff_aus_ablage(lauf: AbgelegterLauf, verwiesen: dict | None = None) -> Aktenstoff:
    """Aus dem **abgelegten** Lauf — die Dokumente, wie sie in ``bc2`` liegen.

    Das ist der Weg des Betriebs: ausgeliefert wird das Dokument, nie eine
    Rekonstruktion (ADR-008 · BC2, 2.2).
    """
    assert lauf.dokument is not None, "nur ein gerechneter Lauf hat eine Akte"
    b = lauf.beleg
    return Aktenstoff(
        company_id=b.company_id, paket_id=b.paket_id, fassung=b.fassung,
        priorisierung=lauf.dokument, konzepte=list(lauf.konzepte),
        sperrgrund=lauf.sperrgrund, hinweise=tuple(lauf.hinweise),
        kp_namen=dict(lauf.kp_namen), verwiesen=dict(verwiesen or {}),
    )


def stoff_aus_ansicht(ansicht: Laufansicht) -> Aktenstoff:
    """Für eine Quelle **ohne Ablage** (Messsatz in Tests und Vorschau).

    Dort liegt kein Dokument; die Vertragsform kommt aus ``als_vertrag``. Im
    Betrieb hängt immer die ``AblegendeLaufquelle`` davor, und dieser Weg
    wird nicht gegangen.
    """
    konzepte, priorisierung = ansicht.als_vertrag({})
    priorisierung = {k: v for k, v in priorisierung.items() if k != "gate1"}
    k = ansicht.kopf
    return Aktenstoff(
        company_id=k.company_id, paket_id=k.paket_id, fassung=k.fassung,
        priorisierung=priorisierung, konzepte=list(konzepte), sperrgrund=k.sperrgrund,
        hinweise=tuple(k.hinweise), kp_namen=dict(ansicht.kp_namen),
        verwiesen=dict(ansicht.verwiesen),
    )


def einfrieren(
    stoff: Aktenstoff,
    entscheidung: Gate1Entscheidung,
    *,
    praesentation: bytes,
    vermerk: str | None = None,
    token: str | None = None,
) -> Ergebnisakte:
    """Setzt die Akte zusammen. Rein: geschrieben wird sie von ``Gate1Buch``.

    Der ``gate1``-Block kommt in der Form, in der die Entscheidung aus der
    Datenbank zurückkäme (``gate1.wie_abgelegt``): so ergibt das Einfrieren beim
    Freigeben dieselben Bytes wie das nachträgliche — und wie das Werkzeug bis
    #378, das den Block aus der Datenbank las.
    """
    from gate1 import wie_abgelegt

    priorisierung = {**stoff.priorisierung, "gate1": wie_abgelegt(entscheidung).als_vertrag()}
    name = ((priorisierung.get("ausgangslage") or {}).get("unternehmen") or {}).get("name")
    ordner = ordnername(mandantenkuerzel(name, stoff.company_id), stoff.paket_id, stoff.fassung)

    dateien: list[Aktendatei] = []
    if stoff.sperrgrund is None:
        prio_schema, konzept_schema = vertragsschemas()
        lieferung = {
            "ordner": ordner,
            "priorisierung": priorisierung,
            "konzepte": stoff.konzepte,
            "hinweise": list(stoff.hinweise),
            "kp_namen": stoff.kp_namen or {},
            "verwiesen": stoff.verwiesen or {},
        }
        dateien += [
            Aktendatei(n, "bc3", text.encode("utf-8"))
            for n, text in bc3_dateien(lieferung, prio_schema, konzept_schema).items()
        ]
    dateien.append(Aktendatei(PRAESENTATION_DATEI, "mandant", praesentation))

    akte = Ergebnisakte(
        company_id=stoff.company_id, paket_id=stoff.paket_id, fassung=stoff.fassung,
        ordner=ordner, sperrgrund=stoff.sperrgrund, link_token=token or neues_token(),
        dateien=tuple(dateien), vermerk=vermerk,
    )
    pruefe(akte, entscheidung)
    return akte


def zeichne_praesentation(ansicht: Laufansicht, entscheidung: Gate1Entscheidung) -> bytes:
    """Der Foliensatz, wie ihn der Download bis #378 bei jedem Klick zeichnete —
    jetzt einmal, beim Einfrieren."""
    from praesentation import als_bytes, baue_praesentation

    konzepte, priorisierung = ansicht.als_vertrag(entscheidung.als_vertrag())
    return als_bytes(
        baue_praesentation(
            konzepte,
            priorisierung,
            sperrgrund=ansicht.kopf.sperrgrund,
            hinweise=ansicht.kopf.hinweise,
        )
    )


def akte_einfrieren(
    ansicht: Laufansicht,
    entscheidung: Gate1Entscheidung,
    *,
    abgelegt: AbgelegterLauf | None = None,
    vermerk: str | None = None,
) -> Ergebnisakte:
    """Präsentation zeichnen und die Akte zusammensetzen — der eine Weg für die
    Freigabe an der Oberfläche und für das nachträgliche Einfrieren."""
    if abgelegt is not None and abgelegt.beleg.fassung != ansicht.kopf.fassung:
        raise AkteUngueltig(
            f"Abgelegt ist Fassung {abgelegt.beleg.fassung}, gezeigt Fassung {ansicht.kopf.fassung}."
        )
    stoff = (
        stoff_aus_ablage(abgelegt, ansicht.verwiesen)
        if abgelegt is not None and abgelegt.dokument is not None
        else stoff_aus_ansicht(ansicht)
    )
    return einfrieren(
        stoff,
        entscheidung,
        praesentation=zeichne_praesentation(ansicht, entscheidung),
        vermerk=vermerk,
    )


# ----------------------------------------------------------------------------
# Nachträglich einfrieren (#378, Punkt 6)
# ----------------------------------------------------------------------------

MINDESTLAENGE_VERMERK = 5


def nachtragen(
    ergebnisse: Ergebnisbuch,
    gate1_buch: Gate1Buch,
    paket_id: str,
    *,
    vermerk: str,
    trocken: bool = False,
) -> Ergebnisakte:
    """Friert einen **vor bc2.4 freigegebenen** Lauf ein, einmalig und mit Vermerk.

    Dieselbe Akte, die die Freigabe heute schriebe — nur aus der gelesenen
    Entscheidung statt aus der frischen, und mit der dann aktuellen
    Präsentation (#376, Punkt 5). ``trocken``: nur zusammensetzen, nichts
    schreiben; so lassen sich die ``bc3``-Dateien gegen den Lieferordner
    vergleichen, **bevor** etwas in der Datenbank liegt.
    """
    from ablage import ansicht_aus_ablage, verwiesene_ids

    if len((vermerk or "").strip()) < MINDESTLAENGE_VERMERK:
        raise NachtragNichtMoeglich(
            "Ein nachträgliches Einfrieren braucht einen Vermerk (wer, wann, warum)."
        )
    lauf = ergebnisse.letzter(paket_id)
    if lauf is None or lauf.dokument is None:
        raise NachtragNichtMoeglich(f"Zu {paket_id} liegt kein gerechneter Lauf.")
    fassung = lauf.beleg.fassung
    entscheidung = gate1_buch.lesen(paket_id, fassung)
    if entscheidung is None or entscheidung.status != "approved":
        stand = entscheidung.status if entscheidung is not None else "pending"
        raise NachtragNichtMoeglich(
            f"{paket_id} f{fassung} ist nicht freigegeben (Stand: {stand}). Eingefroren "
            "wird nur eine Freigabe."
        )
    if gate1_buch.akte(paket_id, fassung) is not None:
        raise NachtragNichtMoeglich(f"{paket_id} f{fassung} hat schon eine Ergebnisakte.")

    ansicht = ansicht_aus_ablage(lauf)
    ids = verwiesene_ids(ansicht)
    if ids:
        ansicht = replace(ansicht, verwiesen=ergebnisse.nachschlagen(lauf.beleg.company_id, ids))
    akte = akte_einfrieren(ansicht, entscheidung, abgelegt=lauf, vermerk=vermerk.strip())
    if not trocken:
        gate1_buch.nachtragen(akte)
    return akte


# ----------------------------------------------------------------------------
# Postgres — geschrieben in der Transaktion von ``PostgresGate1Buch``
# ----------------------------------------------------------------------------

_SQL_KOPF_SCHREIBEN = """
INSERT INTO bc2.ergebnisakte (priorisierung_id, company_id, paket_id, fassung, ordner,
                              sperrgrund, link_token, vermerk)
VALUES (%(priorisierung_id)s, %(company_id)s, %(paket_id)s, %(fassung)s, %(ordner)s,
        %(sperrgrund)s, %(link_token)s, %(vermerk)s)
"""

_SQL_DATEI_SCHREIBEN = """
INSERT INTO bc2.ergebnisakte_datei (priorisierung_id, name, empfaenger, inhalt, pruefsumme)
VALUES (%(priorisierung_id)s, %(name)s, %(empfaenger)s, %(inhalt)s, %(pruefsumme)s)
"""

_SPALTEN = """a.priorisierung_id::text, a.company_id, a.paket_id, a.fassung, a.ordner,
       a.sperrgrund, a.link_token, a.vermerk, a.eingefroren_am, a.link_gesperrt_am"""

SQL_AKTE_ZUM_LAUF = f"""
SELECT {_SPALTEN} FROM bc2.ergebnisakte a
 WHERE a.paket_id = %(paket_id)s AND a.fassung = %(fassung)s
"""

SQL_LIEFERBARE = f"""
SELECT {_SPALTEN} FROM bc2.ergebnisakte a
  JOIN bc2.gate1 g USING (priorisierung_id)
 WHERE a.sperrgrund IS NULL AND g.status = 'approved'
 ORDER BY a.paket_id, a.fassung
"""

_SQL_DATEIEN = """
SELECT name, empfaenger, inhalt, pruefsumme FROM bc2.ergebnisakte_datei
 WHERE priorisierung_id = %(priorisierung_id)s
 ORDER BY empfaenger, name
"""

SQL_PRAESENTATION_ZUM_TOKEN = """
SELECT d.inhalt FROM bc2.ergebnisakte a
  JOIN bc2.ergebnisakte_datei d USING (priorisierung_id)
 WHERE a.link_token = %(token)s AND a.link_gesperrt_am IS NULL
   AND d.name = %(name)s
"""

SQL_SPERREN = """
UPDATE bc2.ergebnisakte SET link_gesperrt_am = now()
 WHERE link_token = %(token)s AND link_gesperrt_am IS NULL
"""

SQL_OHNE_AKTE = """
SELECT l.paket_id, l.fassung, l.company_id, g.entschieden_am, (l.sperrgrund IS NULL) AS lieferbar
  FROM bc2.lauf l
  JOIN bc2.gate1 g USING (priorisierung_id)
  LEFT JOIN bc2.ergebnisakte a USING (priorisierung_id)
 WHERE g.status = 'approved' AND a.priorisierung_id IS NULL
 ORDER BY g.entschieden_am, l.paket_id
"""


def schreiben(cur, priorisierung_id: str, akte: Ergebnisakte) -> None:
    """Kopf und Dateien — **im Cursor des Aufrufers**, also in seiner Transaktion."""
    import psycopg2

    cur.execute(
        _SQL_KOPF_SCHREIBEN,
        {"priorisierung_id": priorisierung_id, "company_id": akte.company_id,
         "paket_id": akte.paket_id, "fassung": akte.fassung, "ordner": akte.ordner,
         "sperrgrund": akte.sperrgrund, "link_token": akte.link_token,
         "vermerk": akte.vermerk},
    )
    for d in akte.dateien:
        cur.execute(
            _SQL_DATEI_SCHREIBEN,
            {"priorisierung_id": priorisierung_id, "name": d.name, "empfaenger": d.empfaenger,
             "inhalt": psycopg2.Binary(d.inhalt), "pruefsumme": d.pruefsumme},
        )


def lesen(cur, kopf: dict) -> Ergebnisakte:
    """Die Dateien zum gelesenen Kopf (``RealDictCursor``)."""
    cur.execute(_SQL_DATEIEN, {"priorisierung_id": kopf["priorisierung_id"]})
    dateien = []
    for z in cur.fetchall():
        datei = Aktendatei(z["name"], z["empfaenger"], bytes(z["inhalt"]))
        if datei.pruefsumme != z["pruefsumme"]:  # die Datenbank prüft das schon; hier der Gürtel
            raise AkteUngueltig(f"{kopf['paket_id']} {z['name']}: Pruefsumme stimmt nicht")
        dateien.append(datei)
    return Ergebnisakte(
        company_id=kopf["company_id"], paket_id=kopf["paket_id"], fassung=kopf["fassung"],
        ordner=kopf["ordner"], sperrgrund=kopf["sperrgrund"], link_token=kopf["link_token"],
        dateien=tuple(dateien), vermerk=kopf["vermerk"],
        eingefroren_am=kopf["eingefroren_am"], link_gesperrt_am=kopf["link_gesperrt_am"],
    )


# ----------------------------------------------------------------------------
# Aufruf im Container
# ----------------------------------------------------------------------------


def _als_lieferjson(akten: list[Ergebnisakte]) -> dict:
    from lieferung import lieferung_aus

    return {"lieferungen": [l.als_json() for a in akten if (l := lieferung_aus(a)) is not None]}


def main(argv: list[str] | None = None) -> int:
    from ablage import PostgresErgebnisbuch
    from gate1 import PostgresGate1Buch

    parser = argparse.ArgumentParser(prog="python -m ergebnisakte",
                                     description="Ergebnisakten in Schema bc2 (#378).")
    befehle = parser.add_subparsers(dest="befehl", required=True)
    befehle.add_parser("offen", help="freigegebene Läufe ohne Akte (liest nur)")
    nach = befehle.add_parser("nachtragen", help="einen vor bc2.4 freigegebenen Lauf einfrieren")
    nach.add_argument("paket_id")
    nach.add_argument("--vermerk", required=True, help="wer, wann, warum nachträglich")
    nach.add_argument("--trocken", action="store_true",
                      help="nur zusammensetzen und die bc3-Dateien ausgeben, nichts schreiben")
    sperr = befehle.add_parser("sperren", help="den Link einer Akte sperren")
    sperr.add_argument("link_token")
    args = parser.parse_args(argv)

    if args.befehl == "offen":
        for z in PostgresGate1Buch(nur_lesen=True).ohne_akte():
            print(f"{z['paket_id']}  f{z['fassung']}  freigegeben {z['entschieden_am']}"
                  f"  {'lieferbar' if z['lieferbar'] else 'nicht lieferbar'}")
        return 0

    if args.befehl == "sperren":
        if not PostgresGate1Buch().sperren(args.link_token):
            print("Kein ungesperrter Link mit diesem Token.", file=sys.stderr)
            return 1
        print("gesperrt")
        return 0

    try:
        akte = nachtragen(
            PostgresErgebnisbuch(nur_lesen=args.trocken),
            PostgresGate1Buch(nur_lesen=args.trocken),
            args.paket_id,
            vermerk=args.vermerk,
            trocken=args.trocken,
        )
    except NachtragNichtMoeglich as e:
        print(f"Nicht eingefroren: {e}", file=sys.stderr)
        return 1
    for d in akte.dateien:
        print(f"{d.empfaenger:8} {d.name:32} {len(d.inhalt):>8} B  sha256 {d.pruefsumme}",
              file=sys.stderr)
    if args.trocken:
        # Dieselbe Form wie `python -m lieferung`: lokal mit
        # `tools/lieferung_ziehen.py --aus <datei> --pruefen` gegen den Ordner halten.
        json.dump(_als_lieferjson([akte]), sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        print("Trocken: nichts geschrieben.", file=sys.stderr)
    else:
        print(f"Eingefroren: {akte.ordner}, Link-Token {akte.link_token}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    # Über den Import, nicht als ``__main__``: sonst gäbe es dieses Modul zweimal,
    # und ``gate1`` sähe andere Klassen als der Aufruf.
    from ergebnisakte import main as _main

    sys.exit(_main())
