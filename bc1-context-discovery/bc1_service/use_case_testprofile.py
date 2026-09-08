"""Use-Case-Testprofile (Anhang A, Rev. 12) — die drei Faelle als Daten.

Ueber den REGULAEREN Schreibweg: process_turn -> ProfilWriter, wie in api.py.
Werte: NoroAI (rund 10 Mitarbeitende), GESETZT, nicht erhoben — exakt die Zahlen,
die am 08.09.2026 in bc1.prozessprofil geschrieben wurden (Test pinnt sie).

Kennzeichnung (open_remarks) steht in derselben Nachricht wie das letzte
Pflichtfeld: mit dem letzten Pflichtfeld wird der Kern terminal (status=fertig)
und der Writer friert die Zeile ein — eine spaetere Nachricht bleibt 'fehlt'
(am 08.09. an Version 1 gemessen).

Wiederholbarkeit: ein zweiter Lauf mit denselben session_ids erzeugt KEINE neue
Version. Traeger ist die Writer-Bindung (profil_write_status): bei fertiger Zeile
liefert reconcile das gespeicherte Profil zurueck. Die Replay-Weiche des Kerns
greift hier nicht — der Session-Store ist je Lauf frisch, der Kern rechnet alles
neu (Review 08.09., gemessen).

Korrektur: 'fertig' ist final (Freeze gegen UPDATE und DELETE). Der einzige Weg,
Werte zu aendern, ist ein Lauf mit NEUER session_id — er legt je Fokus-TP eine
neue Version an; die juengste Version zaehlt fuer BC0 und BC2.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from bc1_core.core import process_turn
from bc1_core.llm import ExtractionCandidate, FakeLLM
from bc1_core.store import InMemoryStateStore
from bc1_service.api import OVERLAY_SCHLUESSEL
from bc1_service.discovery_paket import baue_discovery_paket
from bc1_service.profil_writer import ProfilWriter
from bc1_service.start import lade_kontext

KENNZEICHEN = ("Testdaten Use-Case-Definition 24.08., nicht erhoben. "
               "Quelle: Projektgruppe CoE-Factory.")

Nachricht = tuple[str, tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class Fall:
    """anfrage_id ist dokumentarisch (die BC0-Anfrage, an der der Fokus-TP haengt —
    BC0 setzt am_gate, sobald ihr Profil fertig ist); fokus_tp muss zum focus_step
    im Skript passen, ein Test prueft das."""
    session_id: str
    anfrage_id: str
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
        ("Mengen und Dauer.", (
            ("frequency_per_year", frequenz), ("executions_per_run", faelle),
            ("total_duration_minutes", gesamtdauer))),
        ("Der anstrengendste Schritt.", (
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


# faelle (executions_per_run = Faelle JE DURCHLAUF) steht hier gleich der Jahres-
# haeufigkeit — so am 08.09. geschrieben und in der Datenbank. Ob das fachlich
# "je Durchlauf" oder "je Jahr" meint, ist eine Vertragsfrage mit BC2 (Review
# 08.09., Codex B2; Abschlussplan A1). Nicht still aendern: eine Korrektur ist
# ein neuer Lauf mit neuer session_id (siehe Modul-Docstring).
FAELLE: tuple[Fall, ...] = (
    Fall("uc1-reisebuchung-testdaten-v2", "A-2026-01", "KP-06.TP-2", _skript(
        intent="die Reise- und Einsatzplanung automatisieren",
        name="Reise- und Einsatzplanung", owner="Office Management", prozess="KP-06",
        schritte="Bedarf melden, Termine abstimmen, Reise buchen, Abrechnung",
        trigger="Ein Einsatz beim Kunden steht an",
        eingang="Einsatztermine und Reisewunsch", eingangsformat="mail",
        ausgang="gebuchte Reise mit Bestätigungen",
        frequenz="15 pro Monat", faelle="180", gesamtdauer="3 Stunden",
        fokus="KP-06.TP-2", fokusdauer="90 Minuten", quelle="geschaetzt", sicherheit="60%",
        rollen="Office Management, Consultants", systeme="S-01, S-02",
        medienbruch="Ja.", doku="2", standard="2", daten="3", stabil="3", pii="ja")),
    Fall("uc2-wissensbasis-testdaten-v2", "A-2026-02", "KP-05.TP-1", _skript(
        intent="den Wissenstransfer aus Projekten automatisieren",
        name="Wissenstransfer", owner="Fachexperte", prozess="KP-05",
        schritte="Anfrage sichten, Dokumente suchen, Antwort schreiben, ablegen",
        trigger="Anfrage eines Kollegen oder Kunden",
        eingang="Anfragetext und Dokumentenablage", eingangsformat="digital",
        ausgang="beantwortete Anfrage mit Quellen",
        frequenz="5 pro Woche", faelle="260", gesamtdauer="45 Minuten",
        fokus="KP-05.TP-1", fokusdauer="25 Minuten", quelle="geschaetzt", sicherheit="50%",
        rollen="Fachexperten, Projektleitung", systeme="S-03, S-04",
        medienbruch="ja", doku="3", standard="3", daten="3", stabil="4", pii="nein")),
    Fall("uc3-consultant-matching-testdaten-v2", "A-2026-03", "KP-06.TP-1", _skript(
        intent="das Consulting-Matching beschleunigen",
        name="Consulting-Matching", owner="Staffing Manager", prozess="KP-06",
        schritte="Anfrage erfassen, Profile suchen, Matching, Vorschlag versenden",
        trigger="Kundenanfrage nach einem Consultant",
        eingang="Anforderungsprofil des Kunden", eingangsformat="mail",
        ausgang="Personalvorschlag mit passenden Profilen",
        frequenz="40 pro Jahr", faelle="40", gesamtdauer="2 Stunden",
        fokus="KP-06.TP-1", fokusdauer="1 Stunden", quelle="geschaetzt", sicherheit="70 %",
        rollen="Staffing, Vertrieb", systeme="S-05, S-06",
        medienbruch="nein", doku="2", standard="3", daten="3", stabil="3", pii="ja")),
)


def fuehre_interview(store, paket, fall: Fall, *, company_id: str, writer=None) -> dict:
    """Faehrt einen Fall Nachricht fuer Nachricht durch den Kern; mit `writer`
    wird nach jedem Turn reconciled und die Datenbank-Rueckgabe als Overlay
    uebernommen — wie api.py. Die Transport-Guards von api.py (pruefe_mandant,
    HTTP-Fehlercodes) entfallen: der Store ist je Lauf frisch."""
    llm = FakeLLM({text: [ExtractionCandidate(f, w) for f, w in felder]
                   for text, felder in fall.nachrichten})
    antwort: dict = {}
    for i, (text, _) in enumerate(fall.nachrichten, start=1):
        antwort = process_turn(store, llm, paket, fall.session_id, f"m{i}", text,
                               company_id=company_id)
        if writer is not None:
            db_profil = writer.reconcile(store.load(fall.session_id), antwort)
            if db_profil is not None:
                # Wie api.py: was in der Datenbank steht, gilt — bei bestehender
                # Bindung ist das die eingefrorene Zeile, nicht der frische Kern.
                antwort["payload"].update(
                    {k: db_profil[k] for k in OVERLAY_SCHLUESSEL})
    return antwort


def schreibe_testprofile(pool, company_id: str) -> list[dict]:
    """Schreibt alle Faelle ueber den regulaeren Writer-Pfad; Session-Store
    bewusst In-Memory — kein ungeprueftes bc1.sessions in der Ziel-DB."""
    with pool.connection() as conn:
        kontext = lade_kontext(conn, company_id)
    paket = baue_discovery_paket(kontext=kontext)
    writer = ProfilWriter(pool, company_id, paket)
    ergebnis = []
    for fall in FAELLE:
        antwort = fuehre_interview(InMemoryStateStore(), paket, fall,
                                   company_id=company_id, writer=writer)
        ergebnis.append({"session_id": fall.session_id, "status": antwort["status"],
                         "vollstaendigkeit": antwort["payload"].get("vollstaendigkeit")})
    return ergebnis


def main(argv: list[str] | None = None) -> int:
    """Aufruf: BC1_DB_DSN=... python -m bc1_service.use_case_testprofile --company-id <uuid> [--echt]
    Ohne --echt ein Trockenlauf: nichts wird geschrieben."""
    ap = argparse.ArgumentParser(
        description="Use-Case-Testprofile ueber den regulaeren Writer schreiben.")
    ap.add_argument("--company-id", required=True)
    ap.add_argument("--echt", action="store_true",
                    help="wirklich schreiben (sonst Trockenlauf)")
    args = ap.parse_args(argv)
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
        ergebnis = schreibe_testprofile(pool, args.company_id)
    finally:
        pool.close()
    for e in ergebnis:
        print(f"{'OK ' if e['status'] == 'fertig' else 'FEHLER'} {e['session_id']}: "
              f"{e['status']} vollstaendigkeit={e['vollstaendigkeit']}")
    return 0 if all(e["status"] == "fertig" for e in ergebnis) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
