"""
Vertragstest gegen die **echte** gemeinsame Datenbank.

Läuft nicht in der Vorschleife, und **nicht auf dem Entwicklungsrechner**: eine lokale
``DATABASE_URL`` ist am 21.09.2026 bewusst abgelehnt worden. ``DEPLOY.md`` sagt, die echte
``.env`` liege ausschließlich auf dem Server, und das Fehlen der Variablen ist hier eine
Schutzmaßnahme — ``conftest.py`` löscht sie aktiv, damit die Vorschleife nie versehentlich gegen
die gemeinsame Datenbank läuft.

Gelaufen wird **auf dem Server**, wo die ``.env`` ohnehin liegt (``DEPLOY.md``, Schritt 8)::

    ssh bc2
    cd /opt/bc2/bc2-strategic-advisor/app
    set -a && . ./.env && set +a          # DATABASE_URL in die Umgebung
    BC2_ECHTE_DB=1 .venv/bin/python -m pytest tests/test_vertrag_postgres.py -q

Steht der Klon hinter ``main``, vorher ``git pull`` — das baut das Image nicht neu und lässt den
laufenden Dienst unberührt.

⚠️ **Der volle Lauf ist nicht folgenlos.** ``test_abgleich_laeuft_gegen_die_echte_view_durch``
stößt den echten Nachhol-Abgleich an und holt wartende Pakete von BC0 **tatsächlich** ab. Die
Einzelheiten stehen in ``DEPLOY.md``, Schritt 8 — vor dem Lauf dort nachlesen.

**Warum es diesen Test gibt.** Die Trigger-Tests laufen gegen
``SpeicherEingangsbuch``, einen Doppelgänger. Der ahmt die Semantik nach, aber
die **Garantien** gibt nur Postgres:

- Dass ``paket_id`` Primärschlüssel ist und damit die Idempotenz durchsetzt —
  die Entscheidung aus #190 lautet ausdrücklich »die Datenbank setzt sie durch,
  nicht der Code«. Ein grüner Speichertest beweist das nicht.
- Dass BC2 die Rechte hat, die ADR-003 zusagt: lesen auf ``public``, schreiben
  ausschließlich in ``bc2``.
- Dass ``public.v_uebergabe_offen`` die Spalten trägt, die ``_SQL_OFFEN``
  erwartet. Das Schema gehört BC0, nicht BC2 — es kann sich ändern, ohne dass
  jemand BC2 fragt. Genau dafür ist dieser Test da.

**Seit #290 dazu Schema ``bc2`` selbst** (``migration_bc2.2_lauf.sql``,
ADR-008 · BC2): dass die Datenbank die Fassung vergibt, höchstens einen offenen
Lauf je Paket zulässt, das Ergebnis nicht mehr umschreiben lässt und eine
abgeschlossene Gate-1-Entscheidung endgültig hält — auch gegen einen Handgriff
in ``psql`` am Anwendungscode vorbei. Und dass eine Entscheidung den Neustart
übersteht: eine neue Instanz liest, was die alte geschrieben hat.

Der Test räumt hinter sich auf: er schreibt Pakete und Läufe mit dem Präfix
``TEST-`` und löscht sie am Ende wieder (die Gate-1-Zeilen fallen per Kaskade).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BC2_ECHTE_DB") != "1",
    reason="Braucht die echte Datenbank. Mit BC2_ECHTE_DB=1 aktivieren.",
)


@pytest.fixture
def buch():
    from eingang import PostgresEingangsbuch

    if not (os.environ.get("DATABASE_URL") or "").strip():
        pytest.fail("BC2_ECHTE_DB=1 gesetzt, aber DATABASE_URL fehlt.")
    return PostgresEingangsbuch()


@pytest.fixture
def test_paket_id() -> str:
    return f"TEST-{uuid.uuid4().hex[:12]}"


@pytest.fixture(autouse=True)
def aufraeumen(request):
    """Löscht am Ende alle in diesem Lauf angelegten TEST-Pakete."""
    yield
    if os.environ.get("BC2_ECHTE_DB") != "1":
        return
    import psycopg2

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM bc2.eingang WHERE paket_id LIKE 'TEST-%'")
        if _hat_bc2_2(cur):
            cur.execute("DELETE FROM bc2.lauf WHERE paket_id LIKE 'TEST-%'")


def _hat_bc2_2(cur) -> bool:
    cur.execute("SELECT to_regclass('bc2.lauf')")
    return cur.fetchone()[0] is not None


def _paket(pid: str):
    from eingang import Paket

    return Paket(
        paket_id=pid,
        company_id="TEST-MANDANT",
        uebergeben_am=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
        nutzlast={"paket_id": pid, "company_id": "TEST-MANDANT", "teilprozesse": ["TP-1"]},
    )


# --------------------------------------------------------------- Die Zusagen


def test_die_datenbank_setzt_die_idempotenz_durch(buch, test_paket_id):
    """Der Kern von #190: nicht der Code entscheidet, sondern der Primaerschluessel."""
    assert buch.eintragen(_paket(test_paket_id)) is True
    assert buch.eintragen(_paket(test_paket_id)) is False


def test_migration_ist_gelaufen(buch):
    """Ohne bc2.eingang laeuft nichts — das soll deutlich scheitern."""
    import psycopg2

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('bc2.eingang')")
        assert cur.fetchone()[0] is not None, (
            "bc2.eingang fehlt. migration_bc2.1_eingang.sql einspielen."
        )


def test_bc2_darf_nur_in_sein_eigenes_schema_schreiben(buch):
    """Gegenprobe zu ADR-003. Schlaegt sie fehl, erst melden, dann weiterarbeiten."""
    import psycopg2

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_user")
        assert cur.fetchone()[0].startswith("bc2_role")

    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
            cur.execute("UPDATE bitkom_bewertungen SET stufe = stufe")


def test_die_view_von_bc0_traegt_noch_die_erwarteten_spalten(buch):
    """Das Schema gehoert BC0. Aendert es sich, faellt es hier auf, nicht im Betrieb."""
    import psycopg2

    erwartet = {
        "paket_id",
        "company_id",
        "uebergeben_am",
        "hinweis",
        "sub_process_id",
        "anfrage_id",
    }
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='v_uebergabe_offen'"
        )
        vorhanden = {z[0] for z in cur.fetchall()}

    fehlend = erwartet - vorhanden
    assert not fehlend, f"v_uebergabe_offen hat sich geaendert, es fehlen: {fehlend}"


def test_abgleich_laeuft_gegen_die_echte_view_durch(buch):
    """Prueft die Abfrage selbst, nicht ihr Ergebnis.

    Wie viele Pakete offen sind, haengt am Datenbestand und ist keine Zusage —
    dass ``_SQL_OFFEN`` gegen das echte Schema uebersetzt und ausfuehrbar ist,
    schon.
    """
    pakete = buch.offene_pakete_von_bc0()
    assert isinstance(pakete, list)
    for p in pakete:
        assert p.paket_id and p.company_id
        assert p.quelle == "nachgeholt"
        assert isinstance(p.nutzlast.get("teilprozesse"), list)


def test_der_bestand_des_pakets_ist_json(buch):
    """Erster echter Lauf (10.10.2026): BC1s ``numeric``-Spalten kamen als
    ``Decimal`` an, und die Erkennung brach beim Packen der Nutzlast ab. Er
    schreibt nichts."""
    import json

    import psycopg2
    import psycopg2.extras

    from erkennung.bestand import PostgresBestand

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT e.company_id, e.paket_id, e.uebergeben_am, "
                "array_agg(i.sub_process_id::text) AS tps FROM bc2.eingang e "
                "JOIN public.gate_paket_inhalt i ON i.paket_id::text = e.paket_id "
                "GROUP BY 1, 2, 3 LIMIT 1"
            )
            z = cur.fetchone()
    if z is None:
        pytest.skip("Kein angenommenes Paket mit Inhalt.")
    bestand = PostgresBestand().lies_paket(z["company_id"], z["paket_id"], z["uebergeben_am"], z["tps"])
    from dataclasses import asdict

    json.dumps(asdict(bestand), default=str)  # default nur fuer datetime, nicht fuer Decimal
    profile = [t.bc1_profil for kp in bestand.kernprozesse for t in kp.teilprozesse if t.bc1_profil]
    assert all(not isinstance(p.frequency_per_year, __import__("decimal").Decimal) for p in profile)


def test_der_mandantensatz_ist_auf_dem_freigabestand_lesbar(buch):
    """Die Quelle von ``ausgangslage.unternehmen`` (v3.1, #254), **nur lesend**.

    Beim Bau von #254 lag keine Verbindung vor; die Abfrage ist gegen BC0s
    Schemadateien geschnitten (``companies`` + ``company_profile``, beide unter
    ``stand_zum``). Dieser Test ist die Gegenprobe: dass sie übersetzt, dass
    ``bc2_role`` beide Tabellen über die Historie lesen darf und dass der Name
    aus der Spalte ``name`` kommt — die Vorgängerfassung las ``company_name``
    und bekam still ``NULL``. Er schreibt nichts.
    """
    import psycopg2
    import psycopg2.extras

    from erkennung.bestand import _SQL_MANDANT

    noroai = "7c2d5ee9-2a9a-5990-810f-502ea2b2012d"
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        conn.set_session(readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(_SQL_MANDANT, {"company_id": noroai, "stand": datetime.now(timezone.utc)})
            zeile = cur.fetchone()

    assert zeile is not None, "stand_zum('companies', …) liefert fuer NoroAI keine Zeile."
    assert zeile["name"], "Der Mandantenname kommt leer an — Spaltenname pruefen."
    assert set(zeile) == {"name", "branche", "mitarbeitende", "region", "geschaeftsmodell"}


# ------------------------------------------------- Schema bc2 (#290, bc2.2)


def _db():
    import psycopg2

    return psycopg2.connect(os.environ["DATABASE_URL"])


@pytest.fixture
def ergebnisse():
    from ablage import PostgresErgebnisbuch

    return PostgresErgebnisbuch()


@pytest.fixture
def gate1_buch():
    from gate1 import PostgresGate1Buch

    return PostgresGate1Buch()


@pytest.fixture
def quelle(ergebnisse, test_paket_id):
    """Der Messsatz unter einer TEST-Paketkennung, hinter der echten Ablage.

    **Ohne Sperrgrund**, als käme der Lauf aus dem echten Weg: nur ein
    gelieferter Lauf stellt Kandidaten (#305), und die Kette ist hier zu prüfen.
    """
    from dataclasses import replace
    from pathlib import Path

    from ablage import AblegendeLaufquelle
    from laeufe import MesssatzLaufquelle, SpeicherLaufquelle

    messsaetze = Path(__file__).resolve().parent.parent.parent / "kalibrierung"
    vorlage = MesssatzLaufquelle(messsaetze)
    ansicht = vorlage.ansicht(vorlage.uebersicht()[0].paket_id)
    test_ansicht = replace(
        ansicht,
        kopf=replace(
            ansicht.kopf, paket_id=test_paket_id, company_id="TEST-MANDANT",
            sperrgrund=None, hinweise=("Vertragstest.",),
        ),
    )
    return AblegendeLaufquelle(SpeicherLaufquelle([test_ansicht]), ergebnisse)


def _entscheidung(ansicht, status: str):
    from gate1 import Gate1Entscheidung, NichtFreigegeben, jetzt

    ids = ansicht.potenzial_ids()
    return Gate1Entscheidung(
        paket_id=ansicht.kopf.paket_id,
        company_id=ansicht.kopf.company_id,
        status=status,
        fassung=ansicht.kopf.fassung,
        approved_potenzial_ids=tuple(ids[1:]) if status == "approved" else (),
        nicht_freigegeben=(NichtFreigegeben(ids[0], "Kommt in dieser Runde nicht mit."),)
        if status == "approved" else (),
        finale_reihenfolge_potenzial_ids=tuple(reversed(ids)) if status == "approved" else (),
        finale_prozessreihenfolge_kp_ids=tuple(ansicht.kp_ids()),
        abweichungsbegruendung="Umgekehrt, um den Rang zu pruefen." if status == "approved" else "",
        entscheider="Vertragstest",
        kommentar="Vertragstest" if status == "rejected" else "",
        entschieden_am=jetzt(),
    )


def test_migration_bc2_2_ist_gelaufen():
    with _db() as conn, conn.cursor() as cur:
        for objekt in ("bc2.lauf", "bc2.konzept", "bc2.potenzial", "bc2.gate1",
                       "bc2.gate1_potenzial", "bc2.gate1_prozess", "bc2.v_ergebnis_je_paket"):
            cur.execute("SELECT to_regclass(%s)", (objekt,))
            assert cur.fetchone()[0] is not None, (
                f"{objekt} fehlt. migration_bc2.2_lauf.sql einspielen."
            )


def test_migration_bc2_3_ist_gelaufen():
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'bc2' AND table_name = 'lauf' "
            "AND column_name IN ('sperrgrund', 'hinweise')"
        )
        assert {z[0] for z in cur.fetchall()} == {"sperrgrund", "hinweise"}, (
            "migration_bc2.3_sperrgrund.sql einspielen."
        )


def test_sperrgrund_und_hinweise_liegen_getrennt(quelle, ergebnisse, gate1_buch, test_paket_id):
    """#306 gegen echtes SQL: ``text[]`` hin und zurück, und ``geliefert`` sieht
    nur, was freigegeben ist und keinen Sperrgrund trägt."""
    a = quelle.ansicht(test_paket_id)
    abgelegt = ergebnisse.letzter(test_paket_id)
    assert abgelegt.sperrgrund is None and abgelegt.hinweise == ("Vertragstest.",)
    assert test_paket_id not in ergebnisse.geliefert(), "noch nicht freigegeben"

    gate1_buch.merken(_entscheidung(a, "approved"))
    assert test_paket_id in ergebnisse.geliefert()


def test_die_lieferung_liest_nur(quelle, gate1_buch, test_paket_id):
    """``python -m lieferung`` läuft gegen die gemeinsame Datenbank — lesend."""
    import psycopg2

    from ablage import PostgresErgebnisbuch
    from lieferung import lieferungen

    a = quelle.ansicht(test_paket_id)
    gate1_buch.merken(_entscheidung(a, "approved"))
    lesend = PostgresErgebnisbuch(nur_lesen=True)
    from gate1 import PostgresGate1Buch

    gefunden = {
        l.priorisierung["paket_id"]: l
        for l in lieferungen(lesend, PostgresGate1Buch(nur_lesen=True))
    }
    l = gefunden[test_paket_id]
    assert l.priorisierung["gate1"]["status"] == "approved"
    assert l.ordner.endswith(f"-{test_paket_id}-f1")
    with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
        with lesend._verbindung() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM bc2.lauf WHERE paket_id = %s", (test_paket_id,))


def test_lauf_konzepte_und_potenziale_liegen_zusammen(quelle, ergebnisse, test_paket_id):
    ansicht = quelle.ansicht(test_paket_id)
    abgelegt = ergebnisse.letzter(test_paket_id)

    assert ansicht.kopf.fassung == 1
    assert abgelegt.beleg.zustand == "offen"
    # Gezeigt wird das abgelegte Dokument, nicht eine Rekonstruktion.
    assert ansicht.eintraege == abgelegt.dokument["eintraege"]
    with _db() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM bc2.potenzial WHERE priorisierung_id = %s",
                    (abgelegt.beleg.priorisierung_id,))
        assert cur.fetchone()[0] == len(ansicht.eintraege)


def test_die_datenbank_laesst_nur_einen_offenen_lauf_je_paket_zu(quelle, test_paket_id):
    import psycopg2

    quelle.ansicht(test_paket_id)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bc2.lauf (company_id, paket_id, uebergeben_am, fassung) "
                "VALUES ('TEST-MANDANT', %s, now(), 2)", (test_paket_id,)
            )


def test_die_fassung_ist_je_paket_eindeutig(quelle, gate1_buch, test_paket_id):
    """Auch ohne den partiellen Index: zwei gleiche Nummern lässt UNIQUE nicht zu."""
    import psycopg2

    gate1_buch.merken(_entscheidung(quelle.ansicht(test_paket_id), "rejected"))
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bc2.lauf (company_id, paket_id, uebergeben_am, fassung) "
                "VALUES ('TEST-MANDANT', %s, now(), 1)", (test_paket_id,)
            )


def test_das_ergebnis_ist_unveraenderlich(quelle, ergebnisse, test_paket_id):
    import psycopg2

    quelle.ansicht(test_paket_id)
    pid = ergebnisse.letzter(test_paket_id).beleg.priorisierung_id
    for anweisung in (
        "UPDATE bc2.lauf SET dokument = '{}'::jsonb WHERE priorisierung_id = %s",
        "UPDATE bc2.konzept SET kp_name = 'x' WHERE priorisierung_id = %s",
        "UPDATE bc2.potenzial SET score = 0 WHERE priorisierung_id = %s",
    ):
        with pytest.raises(psycopg2.errors.CheckViolation):
            with _db() as conn, conn.cursor() as cur:
                cur.execute(anweisung, (pid,))


def test_gate1_uebersteht_den_neustart(quelle, gate1_buch, test_paket_id):
    """Das Erledigt-Kriterium von #290: eine **neue** Instanz liest, was die alte schrieb."""
    from gate1 import PostgresGate1Buch

    ansicht = quelle.ansicht(test_paket_id)
    entscheidung = _entscheidung(ansicht, "approved")
    gate1_buch.merken(entscheidung)

    gelesen = PostgresGate1Buch().lesen(test_paket_id, 1)
    assert gelesen is not None
    assert gelesen.status == "approved"
    assert set(gelesen.approved_potenzial_ids) == set(entscheidung.approved_potenzial_ids)
    assert gelesen.nicht_freigegeben == entscheidung.nicht_freigegeben
    # Die Reihenfolgen kommen aus den Rang-Spalten genau so zurück.
    assert gelesen.finale_reihenfolge_potenzial_ids == entscheidung.finale_reihenfolge_potenzial_ids
    assert gelesen.finale_prozessreihenfolge_kp_ids == entscheidung.finale_prozessreihenfolge_kp_ids
    assert gelesen.als_vertrag()["abweichungsbegruendung"] == entscheidung.abweichungsbegruendung


def test_nach_abschluss_ist_gate1_ein_konflikt(quelle, gate1_buch, test_paket_id):
    import psycopg2

    from gate1 import Gate1Konflikt

    ansicht = quelle.ansicht(test_paket_id)
    gate1_buch.merken(_entscheidung(ansicht, "approved"))
    with pytest.raises(Gate1Konflikt):
        gate1_buch.merken(_entscheidung(ansicht, "rejected"))

    # Und am Anwendungscode vorbei: der Trigger hält die Entscheidung fest.
    with pytest.raises(psycopg2.errors.CheckViolation):
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE bc2.gate1 g SET status = 'rejected' FROM bc2.lauf l "
                "WHERE l.priorisierung_id = g.priorisierung_id AND l.paket_id = %s",
                (test_paket_id,),
            )
    assert gate1_buch.lesen(test_paket_id, 1).status == "approved"


def test_neulauf_nur_nach_reject(quelle, ergebnisse, gate1_buch, test_paket_id):
    from ablage import NeulaufNichtErlaubt

    f1 = quelle.ansicht(test_paket_id)
    with pytest.raises(NeulaufNichtErlaubt):
        quelle.neu_rechnen(test_paket_id)

    gate1_buch.merken(_entscheidung(f1, "rejected"))
    f2 = quelle.neu_rechnen(test_paket_id)
    assert f2.kopf.fassung == 2

    vorige = {k["kontext"]["kp_id"]: k["konzept_id"]
              for k in ergebnisse.letzter(test_paket_id).konzepte}
    assert all(vorige.values())
    gate1_buch.merken(_entscheidung(f2, "approved"))
    with pytest.raises(NeulaufNichtErlaubt):
        quelle.neu_rechnen(test_paket_id)


def test_die_sicht_fuer_bc0_zeigt_die_juengste_fassung(quelle, gate1_buch, test_paket_id):
    gate1_buch.merken(_entscheidung(quelle.ansicht(test_paket_id), "rejected"))
    quelle.neu_rechnen(test_paket_id)

    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT fassung, lauf_zustand, gate1_status, kp_ids, anzahl_freigegeben "
            "FROM bc2.v_ergebnis_je_paket WHERE paket_id = %s", (test_paket_id,)
        )
        zeilen = cur.fetchall()
    assert len(zeilen) == 1
    fassung, zustand, gate1, kp_ids, freigegeben = zeilen[0]
    assert (fassung, zustand, gate1, freigegeben) == (2, "offen", "pending", None)
    assert kp_ids


def test_die_sicht_ist_fuer_bc_leser_freigegeben():
    """SELECT vergibt BC2; das USAGE auf ``bc2`` muss BC0 vergeben (ADR-008 · BC2, 2.6)."""
    with _db() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname = 'bc_leser'")
        if cur.fetchone() is None:
            pytest.skip("Rolle bc_leser gibt es in dieser Datenbank nicht.")
        cur.execute(
            "SELECT has_table_privilege('bc_leser', 'bc2.v_ergebnis_je_paket', 'SELECT')"
        )
        assert cur.fetchone()[0] is True


def test_vorgaenger_kandidaten_brechen_den_lauf_ab(ergebnisse, gate1_buch, quelle, test_paket_id):
    """Auflage ADR-009 · BC2 §4.3 gegen die echte Abfrage (``&&`` über ``text[]``)."""
    from dataclasses import replace

    from ablage import AblegendeLaufquelle, NachfolgerOffen
    from laeufe import SpeicherLaufquelle

    a = quelle.ansicht(test_paket_id)
    gate1_buch.merken(_entscheidung(a, "approved"))

    zweites = f"{test_paket_id}-B"
    b_quelle = AblegendeLaufquelle(
        SpeicherLaufquelle([replace(a, kopf=replace(a.kopf, paket_id=zweites))]), ergebnisse
    )
    with pytest.raises(NachfolgerOffen) as fehler:
        b_quelle.ansicht(zweites)
    assert {k["paket_id"] for k in fehler.value.kandidaten} == {test_paket_id}
    assert ergebnisse.letzter(zweites).beleg.zustand == "fehler"
    assert ergebnisse.kandidaten("ANDERER-MANDANT", zweites, ["KP-02.TP-1"]) == []


def _neu_verschluesselt(ansicht, paket_id: str):
    """Dieselbe Ansicht unter neuen Potenzial-Kennungen — ein zweites Paket.

    Über den JSON-Text, damit jede Stelle mitkommt, die eine Kennung trägt
    (Einträge, Prozessränge, Potenziale). Gibt die Ansicht und alt → neu zurück.
    """
    import json
    from dataclasses import replace

    neu = {pid: str(uuid.uuid4()) for pid in ansicht.potenzial_ids()}
    text = json.dumps([ansicht.eintraege, ansicht.prozess_raenge, ansicht.potenziale])
    for alt, frisch in neu.items():
        text = text.replace(alt, frisch)
    eintraege, raenge, potenziale = json.loads(text)
    return replace(
        ansicht,
        kopf=replace(ansicht.kopf, paket_id=paket_id),
        eintraege=eintraege, prozess_raenge=raenge, potenziale=potenziale, konzepte=None,
    ), neu


def test_die_kette_ueber_pakete_gegen_die_echte_abfrage(ergebnisse, gate1_buch, quelle, test_paket_id):
    """#295 gegen echtes SQL: die Kandidaten tragen Titel und Klasse aus dem
    Konzeptdokument (JSONB), die Kette landet in ``bc2.potenzial`` und in der
    Streichliste, und was ein freigegebener Lauf fortschrieb oder strich, ist
    für das nächste Paket kein Kandidat mehr."""
    from dataclasses import replace

    import psycopg2

    from ablage import AblegendeLaufquelle
    from laeufe import SpeicherLaufquelle
    from nachfolge import Ausgang, Nachfolge

    a = quelle.ansicht(test_paket_id)
    gate1_buch.merken(_entscheidung(a, "approved"))
    company = a.kopf.company_id
    tps = list(a.kopf.teilprozess_ids)
    zweites, drittes = f"{test_paket_id}-B", f"{test_paket_id}-C"

    kandidaten = ergebnisse.kandidaten(company, zweites, tps)
    assert {k.potenzial_id for k in kandidaten} == set(a.potenzial_ids())
    erster = a.potenzial_ids()[0]
    k0 = next(k for k in kandidaten if k.potenzial_id == erster)
    assert k0.titel == a.potenziale[erster]["titel"]
    assert k0.klasse == a.potenziale[erster]["automatisierungsgrad"]["klasse"]
    assert ergebnisse.nachschlagen(company, [erster])[erster]["paket_id"] == test_paket_id

    # B streicht das erste Potenzial von A und schreibt alle anderen fort.
    b, neu = _neu_verschluesselt(a, zweites)
    ausgaenge = [Ausgang(erster, "gestrichen", begruendung="Faellt nach der Nacherhebung weg.")]
    ausgaenge += [Ausgang(alt, "fortgeschrieben", neu[alt]) for alt in a.potenzial_ids()[1:]]
    b = replace(b, ausgangslage={"unternehmen": {"name": None}},
                 nachfolge=Nachfolge(tuple(kandidaten), tuple(ausgaenge)))
    gerechnet_b = AblegendeLaufquelle(SpeicherLaufquelle([b]), ergebnisse).ansicht(zweites)
    assert gerechnet_b.gestrichene_potenziale[0]["potenzial_id"] == erster

    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT p.potenzial_id, p.ersetzt_potenzial_ids FROM bc2.potenzial p "
            "JOIN bc2.lauf l USING (priorisierung_id) WHERE l.paket_id = %s", (zweites,)
        )
        kette = dict(cur.fetchall())
    assert kette[neu[erster]] == []
    assert all(kette[neu[alt]] == [alt] for alt in a.potenzial_ids()[1:])

    assert {k.potenzial_id for k in ergebnisse.kandidaten(company, drittes, tps)} == set(
        a.potenzial_ids()
    ), "B ist noch nicht freigegeben"
    gate1_buch.merken(_entscheidung(gerechnet_b, "approved"))
    assert {k.potenzial_id for k in ergebnisse.kandidaten(company, drittes, tps)} == set(
        neu.values()
    )
