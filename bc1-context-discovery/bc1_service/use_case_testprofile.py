"""Use-Case-Testprofile (Anhang A, Rev. 12) — die drei Faelle als Daten.

Ueber den REGULAEREN Schreibweg: process_turn -> ProfilWriter, wie in api.py.
Werte: NoroAI (rund 10 Mitarbeitende), GESETZT, nicht erhoben. Seit Version 3 gilt
Menge je Durchlauf (D4) = 1; die Werte von Version 1/2 (08.09.2026) sind historisch.

Kennzeichnung (open_remarks) steht in derselben Nachricht wie das letzte
Pflichtfeld: mit dem letzten Pflichtfeld wird der Kern terminal (status=fertig)
und der Writer friert die Zeile ein — eine spaetere Nachricht bleibt 'fehlt'
(am 08.09. an Version 1 gemessen).

Wiederholbarkeit: ein zweiter Lauf mit denselben session_ids erzeugt KEINE neue
Version. Traeger ist die Vorpruefung: ein schon fertig zur selben Anfrage gebundener
Fall gilt als erledigt ('bereits geschrieben') und erreicht den Writer nicht. Die
Replay-Weiche des Kerns greift hier nicht — der Session-Store ist je Lauf frisch.

Korrektur: 'fertig' ist final (Freeze gegen UPDATE und DELETE). Der einzige Weg,
Werte zu aendern, ist ein Lauf mit NEUER session_id — er legt je Fokus-TP eine
neue Version an; die juengste Version zaehlt fuer BC0 und BC2.

Version 3 (C1a): neue Sitzungsnummern (-v3), Menge je Durchlauf 1. Die Anfragen kommen
als Parameter (--anfrage TP=A-JJJJ-NN, je Fall; mit --echt Pflicht). Ablauf:
1. Pruefen (pruefe_anfragen): Anfrage vorhanden, Sitzungsnummer nicht zu einer ANDEREN
   Anfrage gebunden, Anfrage interviewbar und umfasst den Fokus-TP, die Rolle, die das Skript
   fuer B3 waehlt, ist beim Mandanten aktiv. Bei Fehlern (VorpruefungFehler) wird
   nichts gemeldet und nichts geschrieben.
2. BC0 melden (nur mit Melder): Konto pruefen, Interview-Beginn je nicht erledigter Anfrage.
3. Schreiben; schon fertig zur selben Anfrage Gebundenes ist erledigt ('bereits geschrieben').
4. Gate nachziehen (nur mit Melder) fuer jede Anfrage mit fertigem Fall, erledigte
   eingeschlossen — ein zweiter Lauf mit denselben Parametern holt so ein gescheitertes
   Gate nach. Ein Fehler dabei ist nur eine Warnzeile (stderr), kein Abbruch.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from bc1_core.core import process_turn
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.store import InMemoryStateStore
from bc1_service.api import OVERLAY_SCHLUESSEL
from bc1_service.discovery_paket import baue_discovery_paket
from bc1_service.profil_writer import ProfilWriter, _fehlergrund
from bc1_service.bc0_lesepfade import anfrage_status
from bc1_service.bc0_meldungen import Bc0MeldungFehler, baue_melder
from bc1_service.start import lade_kontext, melde_interview_beginn

KENNZEICHEN = ("Testdaten Use-Case-Definition 24.08., nicht erhoben, Version 3. "
               "Quelle: Projektgruppe CoE-Factory.")

Nachricht = tuple[str, tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class Fall:
    """Die Anfrage kommt seit Version 3 als Parameter (--anfrage TP=A-JJJJ-NN), nicht
    mehr aus dem Fall; fokus_tp ist der Schluessel dafuer und muss zum focus_step im
    Skript passen, ein Test prueft das."""
    session_id: str
    fokus_tp: str
    nachrichten: tuple[Nachricht, ...]


def _skript(*, intent, name, owner, prozess, schritte, trigger, eingang,
            eingangsformat, ausgang, frequenz, faelle, gesamtdauer,
            fokus, fokusdauer, quelle, sicherheit, rollen, systeme,
            medienbruch, doku, standard, daten, stabil, pii) -> tuple[Nachricht, ...]:
    """Sieben Nachrichten, wie die Demo-Durchlaeufe — nur benannte Argumente,
    damit aehnliche Zahlen und Skalen nicht vertauscht werden koennen."""
    return (
        (f"Wir wollen {intent} — es geht um den ganzen Prozess, Ziel ist Zeit sparen.", (
            ("request_intent", intent), ("request_goal", "zeit_sparen"),
            ("scope_focus", "ganzer_prozess"), ("process_name", name))),
        ("Verantwortlich und Ablauf.", (
            ("process_owner_role", owner), ("process_id", prozess),
            ("process_steps", schritte))),
        ("Auslöser, Eingang und Ergebnis.", (
            ("trigger_text", trigger), ("input_text", eingang),
            ("input_format", eingangsformat), ("output_text", ausgang))),
        (f"Mengen und Dauer: {frequenz}, {gesamtdauer}.", (
            ("frequency_per_year", frequenz), ("executions_per_run", faelle),
            ("total_duration_minutes", gesamtdauer))),
        (f"Der anstrengendste Schritt ist {fokus}, er dauert {fokusdauer}.", (
            ("focus_step", fokus), ("focus_step_duration_minutes", fokusdauer),
            ("focus_step_duration_source", quelle),
            ("focus_step_duration_confidence_pct", sicherheit))),
        ("Beteiligte und Systeme.", (
            ("focus_step_roles", rollen), ("focus_step_systems", systeme),
            ("focus_step_media_break", medienbruch),
            ("documentation_status", doku))),
        ("Voraussetzungen und Herkunft dieser Angaben.", (
            ("standardization_level", standard),
            ("data_availability_score", daten), ("stability_score", stabil),
            ("pii_involved", pii), ("open_remarks", KENNZEICHEN))),
    )


# faelle (executions_per_run = Faelle JE DURCHLAUF) steht seit Version 3 auf 1 (in
# Version 1/2 gleich der Jahreshaeufigkeit, siehe Review 08.09., Codex B2). Nicht still
# aendern: eine Korrektur ist ein neuer Lauf mit neuer session_id (siehe Modul-Docstring).
FAELLE: tuple[Fall, ...] = (
    Fall("uc1-reisebuchung-testdaten-v3", "KP-06.TP-2", _skript(
        intent="die Reise- und Einsatzplanung automatisieren",
        name="Reise- und Einsatzplanung", owner="R-05", prozess="KP-06",
        schritte="Bedarf melden, Termine abstimmen, Reise buchen, Abrechnung",
        trigger="Ein Einsatz beim Kunden steht an",
        eingang="Einsatztermine und Reisewunsch", eingangsformat="mail",
        ausgang="gebuchte Reise mit Bestätigungen",
        frequenz="15 pro Monat", faelle="1", gesamtdauer="3 Stunden",
        fokus="KP-06.TP-2", fokusdauer="90 Minuten", quelle="geschaetzt", sicherheit="60%",
        rollen="Office Management, Consultants", systeme="S-01, S-02",
        medienbruch="Ja.", doku="2", standard="2", daten="3", stabil="3", pii="ja")),
    Fall("uc2-wissensbasis-testdaten-v3", "KP-05.TP-1", _skript(
        intent="den Wissenstransfer aus Projekten automatisieren",
        name="Wissenstransfer", owner="R-05", prozess="KP-05",
        schritte="Anfrage sichten, Dokumente suchen, Antwort schreiben, ablegen",
        trigger="Anfrage eines Kollegen oder Kunden",
        eingang="Anfragetext und Dokumentenablage", eingangsformat="digital",
        ausgang="beantwortete Anfrage mit Quellen",
        frequenz="5 pro Woche", faelle="1", gesamtdauer="45 Minuten",
        fokus="KP-05.TP-1", fokusdauer="25 Minuten", quelle="geschaetzt", sicherheit="50%",
        rollen="Fachexperten, Projektleitung", systeme="S-03, S-04",
        medienbruch="ja", doku="3", standard="3", daten="3", stabil="4", pii="nein")),
    Fall("uc3-consultant-matching-testdaten-v3", "KP-06.TP-1", _skript(
        intent="das Consulting-Matching beschleunigen",
        name="Consulting-Matching", owner="R-05", prozess="KP-06",
        schritte="Anfrage erfassen, Profile suchen, Matching, Vorschlag versenden",
        trigger="Kundenanfrage nach einem Consultant",
        eingang="Anforderungsprofil des Kunden", eingangsformat="mail",
        ausgang="Personalvorschlag mit passenden Profilen",
        frequenz="40 pro Jahr", faelle="1", gesamtdauer="2 Stunden",
        fokus="KP-06.TP-1", fokusdauer="1 Stunden", quelle="geschaetzt", sicherheit="70 %",
        rollen="Staffing, Vertrieb", systeme="S-05, S-06",
        medienbruch="nein", doku="2", standard="3", daten="3", stabil="3", pii="ja")),
)


def fuehre_interview(store, paket, fall: Fall, *, company_id: str, anfrage_id: str,
                     writer=None) -> dict:
    """Faehrt einen Fall Nachricht fuer Nachricht durch den Kern; mit `writer`
    wird nach jedem Turn reconciled und die Datenbank-Rueckgabe als Overlay
    uebernommen — wie api.py. Die Transport-Guards von api.py (pruefe_mandant,
    HTTP-Fehlercodes) entfallen: der Store ist je Lauf frisch."""
    llm = FakeLLM({text: [ExtractionCandidate(f, w) for f, w in felder]
                   for text, felder in fall.nachrichten})
    antwort: dict = {}
    for i, (text, _) in enumerate(fall.nachrichten, start=1):
        antwort = process_turn(store, llm, paket, fall.session_id, f"m{i}", text,
                               company_id=company_id, anfrage_id=anfrage_id)
        if writer is not None:
            db_profil = writer.reconcile(store.load(fall.session_id), antwort)
            if db_profil is not None:
                # Wie api.py: was in der Datenbank steht, gilt — bei bestehender
                # Bindung ist das die eingefrorene Zeile, nicht der frische Kern.
                antwort["payload"].update(
                    {k: db_profil[k] for k in OVERLAY_SCHLUESSEL})
    return antwort


class VorpruefungFehler(RuntimeError):
    """Die Vorpruefung hat etwas gefunden; der Text ist fuer Menschen geschrieben."""


@dataclass(frozen=True)
class Vorpruefung:
    """fehler: alles, was vor dem Schreiben auffaellt; erledigt: Sitzungsnummern, die
    schon fertig zur selben Anfrage gebunden sind."""
    fehler: tuple[str, ...]
    erledigt: frozenset[str]


def pruefe_anfragen(pool, company_id: str, anfragen: Mapping[str, str]) -> Vorpruefung:
    fehler = []
    erledigt = set()
    for fall in FAELLE:
        if fall.fokus_tp not in anfragen:
            fehler.append(f"Für {fall.fokus_tp} fehlt --anfrage {fall.fokus_tp}=A-JJJJ-NN.")
            continue
        with pool.connection() as conn:
            bindung = conn.execute(
                "SELECT p.anfrage_id, p.status "
                "  FROM bc1.profil_write_status w "
                "  JOIN bc1.prozessprofil p ON p.company_id = w.company_id "
                "   AND p.focus_step_id = w.focus_step_id "
                "   AND p.profil_version = w.profil_version "
                " WHERE w.session_id = %s AND w.company_id = %s",
                (fall.session_id, company_id)).fetchone()
        if bindung is not None and bindung[0] != anfragen[fall.fokus_tp]:
            fehler.append(f"{fall.session_id} ist schon zu {bindung[0]} geschrieben; "
                          f"für {anfragen[fall.fokus_tp]} braucht es eine neue Sitzungsnummer.")
            continue
        if bindung is not None and bindung[1] == "fertig":
            erledigt.add(fall.session_id)
            continue
        try:
            with pool.connection() as conn:
                kontext = lade_kontext(conn, company_id, anfragen[fall.fokus_tp])
        except RuntimeError as f:
            fehler.append(str(f))
            continue
        if fall.fokus_tp not in dict(kontext.teilprozesse):
            fehler.append(f"Die Anfrage {anfragen[fall.fokus_tp]} umfasst "
                          f"{fall.fokus_tp} nicht.")
        rolle = next(wert for _, felder in fall.nachrichten
                     for feld, wert in felder if feld == "process_owner_role")
        if rolle not in {rollen_id for rollen_id, _ in kontext.rollen}:
            fehler.append(f"Die Rolle {rolle} ist beim Mandanten nicht aktiv; "
                          f"{fall.session_id} wählt sie für B3.")
    return Vorpruefung(tuple(fehler), frozenset(erledigt))


def schreibe_testprofile(pool, company_id: str, anfragen: Mapping[str, str],
                         melder=None) -> list[dict]:
    """Schreibt alle Faelle ueber den regulaeren Writer-Pfad; Session-Store
    bewusst In-Memory — kein ungeprueftes bc1.sessions in der Ziel-DB.
    Je Fall mit dessen Anfrage (anfragen: Fokus-TP -> Anfrage): Auswahl, Fingerabdruck und
    Writer haengen an ihr. Ablauf siehe Modul-Docstring (Version 3)."""
    vor = pruefe_anfragen(pool, company_id, anfragen)
    if vor.fehler:
        raise VorpruefungFehler("\n".join(vor.fehler))
    if melder is not None:
        melder.pruefe_konto()
        for fall in FAELLE:
            if fall.session_id in vor.erledigt:
                continue
            with pool.connection() as conn:
                status = anfrage_status(conn, company_id, anfragen[fall.fokus_tp])
            melde_interview_beginn(melder, anfragen[fall.fokus_tp], status)
    ergebnis = []
    for fall in FAELLE:
        if fall.session_id in vor.erledigt:
            ergebnis.append({"session_id": fall.session_id, "status": "fertig",
                             "vollstaendigkeit": None, "vermerk": "bereits geschrieben"})
            continue
        anfrage = anfragen[fall.fokus_tp]
        with pool.connection() as conn:
            kontext = lade_kontext(conn, company_id, anfrage)
        paket = baue_discovery_paket(kontext=kontext)
        writer = ProfilWriter(pool, company_id, paket)
        antwort = fuehre_interview(InMemoryStateStore(), paket, fall,
                                   company_id=company_id, anfrage_id=anfrage, writer=writer)
        ergebnis.append({"session_id": fall.session_id, "status": antwort["status"],
                         "vollstaendigkeit": antwort["payload"].get("vollstaendigkeit")})
    if melder is not None:
        for fall, e in zip(FAELLE, ergebnis):
            if e["status"] == "fertig":
                try:
                    melder.ziehe_gate_nach(anfragen[fall.fokus_tp])
                except Exception as fehler:                  # noqa: BLE001
                    # Nie das Ausnahmeobjekt ausgeben: eine fremde Ausnahme koennte Interna tragen.
                    grund = (str(fehler) if isinstance(fehler, Bc0MeldungFehler)
                             else type(fehler).__name__)
                    print(f"WARNUNG Gate fuer {anfragen[fall.fokus_tp]} nicht nachgezogen: "
                          f"{grund}", file=sys.stderr)
    return ergebnis


def _anfrage_paar(text: str) -> tuple[str, str]:
    tp, gleich, anfrage = text.partition("=")
    if not gleich:
        raise argparse.ArgumentTypeError(f"{text!r}: erwartet TP=A-JJJJ-NN")
    return tp, anfrage


def main(argv: list[str] | None = None) -> int:
    """Aufruf: BC1_DB_DSN=... python -m bc1_service.use_case_testprofile --company-id <uuid>
    --anfrage KP-06.TP-2=A-JJJJ-NN [--anfrage ...] [--echt]
    Ohne --echt ein Trockenlauf: nichts wird geschrieben, nichts gemeldet.
    Ein Fehler in Vorpruefung, Melden oder Schreiben beendet den Lauf mit Exit 1 ohne
    Ergebniszeilen (Meldungen der Vorpruefung und von BC0 im Klartext, jede andere
    Ausnahme nur mit Klasse und erster Zeile); ein Gate-Fehler ist nur eine Warnzeile.
    Ein zweiter Lauf mit denselben Parametern holt Gate und Rest nach."""
    ap = argparse.ArgumentParser(
        description="Use-Case-Testprofile ueber den regulaeren Writer schreiben.")
    ap.add_argument("--company-id", required=True)
    ap.add_argument("--echt", action="store_true",
                    help="wirklich schreiben (sonst Trockenlauf)")
    ap.add_argument("--anfrage", action="append", default=[], type=_anfrage_paar,
                    metavar="TP=A-JJJJ-NN",
                    help="Anfrage je Fokus-TP; mit --echt fuer alle Faelle Pflicht")
    args = ap.parse_args(argv)
    anfragen = dict(args.anfrage)
    print(f"{len(FAELLE)} Faelle: " + ", ".join(f.session_id for f in FAELLE))
    if not args.echt:
        print("TROCKENLAUF — nichts geschrieben. Mit --echt schreiben.")
        return 0
    dsn = os.environ.get("BC1_DB_DSN")
    if not dsn:
        print("BC1_DB_DSN ist nicht gesetzt — ohne Datenbank-DSN kann nichts "
              "geschrieben werden (als bc1_role verbinden, siehe EINSPIELEN.md).",
              file=sys.stderr)
        return 1
    pool = ConnectionPool(dsn, min_size=1, max_size=3, open=True)
    try:
        melder = baue_melder(os.environ, args.company_id)
        ergebnis = schreibe_testprofile(pool, args.company_id, anfragen, melder)
    except (VorpruefungFehler, Bc0MeldungFehler) as fehler:
        print(fehler, file=sys.stderr)
        return 1
    except Exception as fehler:                             # noqa: BLE001
        print(_fehlergrund(fehler), file=sys.stderr)
        return 1
    finally:
        pool.close()
    for e in ergebnis:
        if "vermerk" in e:
            print(f"OK {e['session_id']}: {e['vermerk']}")
            continue
        print(f"{'OK ' if e['status'] == 'fertig' else 'FEHLER'} {e['session_id']}: "
              f"{e['status']} vollstaendigkeit={e['vollstaendigkeit']}")
    return 0 if all(e["status"] == "fertig" for e in ergebnis) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
