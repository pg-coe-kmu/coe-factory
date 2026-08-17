# -*- coding: utf-8 -*-
"""
Benutzerverwaltung von der Kommandozeile — für den ersten Zugang und für Notfälle.

Warum es dieses Skript gibt
---------------------------
Die Anwendung legt bewusst **kein** Standardkonto an. Ein vorkonfigurierter
Zugang mit bekanntem Passwort wäre die verwundbarste Stelle der ganzen
Anwendung. Der erste Admin entsteht deshalb hier, auf dem Server, durch jemanden
mit Zugriff auf die Maschine.

Danach wird das Skript nur noch selten gebraucht: Alles Weitere läuft über die
Admin-Oberfläche. Es bleibt der Rettungsweg, falls kein Admin mehr anmeldefähig
ist.

Passwörter werden **nie** als Argument entgegengenommen, sondern immer verdeckt
abgefragt. Argumente stehen in der Shell-History und in der Prozessliste; beides
ist für ein Passwort der falsche Ort.

Aufrufe
-------
    python benutzer_verwalten.py liste
    python benutzer_verwalten.py anlegen --email a@b.de --name "Vorname Name" --rolle admin
    python benutzer_verwalten.py anlegen --email c@d.de --name "…" --mandant <company_id>
    python benutzer_verwalten.py passwort --email a@b.de
    python benutzer_verwalten.py mandanten --email c@d.de --mandant <id> [--mandant <id> …]
    python benutzer_verwalten.py sperren --email c@d.de
    python benutzer_verwalten.py entsperren --email c@d.de

Im Container:
    docker compose exec app python benutzer_verwalten.py liste
"""

from __future__ import annotations

import argparse
import getpass
import sys

# app.py stellt die Datenbankanbindung bereit (Verbindungsfabrik `db`, Schalter `PG`).
# Der Import führt `init_db()` aus; das ist idempotent und darum unbedenklich.
from app import PG, db  # noqa: E402

from bc0_auth import AuthDienst, Rolle  # noqa: E402
from bc0_auth.passwoerter import PasswortFehler  # noqa: E402


def _dienst() -> AuthDienst:
    dienst = AuthDienst(db, PG)
    dienst.einrichten()
    return dienst


def _passwort_abfragen(zweck: str) -> str:
    """Fragt ein Passwort zweimal verdeckt ab und vergleicht die Eingaben."""
    erste = getpass.getpass("%s: " % zweck)
    zweite = getpass.getpass("Wiederholung: ")
    if erste != zweite:
        print("Die Eingaben stimmen nicht überein.", file=sys.stderr)
        raise SystemExit(2)
    return erste


def _benutzer_per_email(dienst: AuthDienst, email: str):
    treffer = dienst.benutzer.finde_per_email(email)
    if treffer is None:
        print("Kein Benutzer mit der Adresse %s." % email, file=sys.stderr)
        raise SystemExit(1)
    return treffer[0]


# --------------------------------------------------------------------------- #
# Unterbefehle
# --------------------------------------------------------------------------- #
def befehl_liste(dienst: AuthDienst, _args) -> None:
    benutzer = dienst.alle_benutzer()
    if not benutzer:
        print("Noch kein Benutzer angelegt. Die Anwendung ist damit für alle gesperrt.")
        print("Ersten Admin anlegen:")
        print('  python benutzer_verwalten.py anlegen --email … --name "…" --rolle admin')
        return
    print("%-38s %-10s %-7s %s" % ("E-Mail", "Rolle", "aktiv", "Mandanten"))
    print("-" * 80)
    for b in benutzer:
        mandanten = ", ".join(sorted(b.mandanten)) if b.mandanten else ("alle" if b.ist_admin else "—")
        print("%-38s %-10s %-7s %s" % (b.email, b.rolle.value, "ja" if b.aktiv else "nein", mandanten))


def befehl_anlegen(dienst: AuthDienst, args) -> None:
    passwort = _passwort_abfragen("Passwort für %s" % args.email)
    try:
        neuer = dienst.benutzer_anlegen(
            email=args.email,
            name=args.name,
            passwort=passwort,
            rolle=Rolle.aus_text(args.rolle),
            mandanten=args.mandant or [],
        )
    except (PasswortFehler, ValueError) as fehler:
        print(str(fehler), file=sys.stderr)
        raise SystemExit(1)
    print("Angelegt: %s (%s)" % (neuer.email, neuer.rolle.value))
    if neuer.rolle is Rolle.BENUTZER and not neuer.mandanten:
        print("Hinweis: Ohne Mandantenzuordnung sieht dieser Benutzer nichts.")
        print("  python benutzer_verwalten.py mandanten --email %s --mandant <company_id>" % neuer.email)


def befehl_passwort(dienst: AuthDienst, args) -> None:
    benutzer = _benutzer_per_email(dienst, args.email)
    passwort = _passwort_abfragen("Neues Passwort für %s" % benutzer.email)
    try:
        dienst.passwort_aendern(benutzer.benutzer_id, passwort)
    except PasswortFehler as fehler:
        print(str(fehler), file=sys.stderr)
        raise SystemExit(1)
    print("Passwort geändert. Alle offenen Sitzungen dieses Benutzers wurden beendet.")


def befehl_mandanten(dienst: AuthDienst, args) -> None:
    benutzer = _benutzer_per_email(dienst, args.email)
    dienst.benutzer.mandanten_setzen(benutzer.benutzer_id, args.mandant or [])
    aktualisiert = dienst.benutzer.finde_per_id(benutzer.benutzer_id)
    print("Zuordnung für %s: %s" % (
        aktualisiert.email,
        ", ".join(sorted(aktualisiert.mandanten)) or "keine",
    ))


def befehl_sperren(dienst: AuthDienst, args) -> None:
    benutzer = _benutzer_per_email(dienst, args.email)
    dienst.benutzer_sperren(benutzer.benutzer_id)
    print("Gesperrt: %s — offene Sitzungen wurden beendet." % benutzer.email)


def befehl_entsperren(dienst: AuthDienst, args) -> None:
    benutzer = _benutzer_per_email(dienst, args.email)
    dienst.benutzer_entsperren(benutzer.benutzer_id)
    print("Entsperrt: %s" % benutzer.email)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benutzerverwaltung der BC0-Onboarding-App.",
        epilog="Passwörter werden immer verdeckt abgefragt, nie als Argument übergeben.",
    )
    unterbefehle = parser.add_subparsers(dest="befehl", required=True)

    unterbefehle.add_parser("liste", help="alle Benutzer anzeigen").set_defaults(funktion=befehl_liste)

    anlegen = unterbefehle.add_parser("anlegen", help="neuen Benutzer anlegen")
    anlegen.add_argument("--email", required=True)
    anlegen.add_argument("--name", required=True)
    anlegen.add_argument("--rolle", default=Rolle.BENUTZER.value, choices=[r.value for r in Rolle])
    anlegen.add_argument("--mandant", action="append", metavar="COMPANY_ID",
                         help="mehrfach angebbar; für Admins ohne Bedeutung")
    anlegen.set_defaults(funktion=befehl_anlegen)

    passwort = unterbefehle.add_parser("passwort", help="Passwort neu setzen")
    passwort.add_argument("--email", required=True)
    passwort.set_defaults(funktion=befehl_passwort)

    mandanten = unterbefehle.add_parser("mandanten", help="Mandantenzuordnung ersetzen")
    mandanten.add_argument("--email", required=True)
    mandanten.add_argument("--mandant", action="append", metavar="COMPANY_ID")
    mandanten.set_defaults(funktion=befehl_mandanten)

    sperren = unterbefehle.add_parser("sperren", help="Konto sperren")
    sperren.add_argument("--email", required=True)
    sperren.set_defaults(funktion=befehl_sperren)

    entsperren = unterbefehle.add_parser("entsperren", help="Konto entsperren")
    entsperren.add_argument("--email", required=True)
    entsperren.set_defaults(funktion=befehl_entsperren)

    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    args.funktion(_dienst(), args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
