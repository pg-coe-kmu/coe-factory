"""
Tests der Gate-1-Oberfläche (#243, Fassung D aus #167).

Gesprochen wird über **HTTP**, nicht über die Endpunktfunktionen — dieselbe
Regel wie bei BC0 und bei den Trigger-Tests: geprüft wird, was ein Aufrufer
sieht, samt Statuscode und Rumpf.

**Keine Zahl aus dem Messsatz ist hier verdrahtet.** Was heute elf Potenziale in
vier Kernprozessen sind, ist ein Testdatenstand (so die Karte #158
ausdrücklich); ein Test, der auf ``== 11`` prüft, bricht beim ersten echten Lauf
und prüft dabei nichts Fachliches. Geprüft werden **Regeln**: dass eine
Nicht-Freigabe eine Begründung braucht, dass eine gesetzte Folge eine
Permutation ist, dass ein fremdes Potenzial abgewiesen wird.

Die beiden Tests am Ende messen gegen den **Vertrag**: der ``gate1``-Block, den
der Dienst zurückgibt, wird gegen ``priorisierung.schema.json`` geprüft. Ohne
das wäre die Auflage aus #167 nur auf dem Papier eingelöst.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from laeufe import Laufansicht, Laufkopf, SpeicherLaufquelle

VERTRAG = (
    Path(__file__).resolve().parents[3] / "contracts" / "bc2-to-bc3" / "priorisierung.schema.json"
)


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


def ein_lauf(client, kopf) -> dict:
    """Der erste Lauf der Liste, vollständig geladen."""
    liste = client.get("/api/oberflaeche/laeufe", headers=kopf).json()["laeufe"]
    assert liste, "Die Behelfsquelle liefert keinen Lauf — dann prueft hier nichts."
    return client.get(
        f"/api/oberflaeche/laeufe/{liste[0]['paket_id']}", headers=kopf
    ).json()


def alle_freigeben(lauf: dict, **weiteres) -> dict:
    """Die Entscheidung, die dem Vorschlag folgt — der einfachste gültige Fall."""
    return {
        "status": "approved",
        "entscheider": "Testlauf",
        "approved_potenzial_ids": [e["potenzial_id"] for e in lauf["eintraege"]],
        "nicht_freigegeben": [],
        **weiteres,
    }


def sende(client, kopf, paket_id: str, rumpf: dict):
    return client.post(
        f"/api/oberflaeche/laeufe/{paket_id}/gate1", headers=kopf, json=rumpf
    )


# ---------------------------------------------------------------------------
# Die Seite selbst
# ---------------------------------------------------------------------------


def test_die_seite_wird_ausgeliefert(client):
    """Eine Datei über StaticFiles, ohne Schlüssel — sie enthält keine Daten."""
    antwort = client.get("/")
    assert antwort.status_code == 200
    assert "text/html" in antwort.headers["content-type"]
    # Sie holt ihre Daten selbst; im Auslieferungsstand steht nichts Fachliches.
    # Relativ, damit sie auch unter /vorschau/ ihren eigenen Dienst ruft.
    assert '"api/oberflaeche/laeufe"' in antwort.text
    assert '"/api/oberflaeche' not in antwort.text and "`/api/oberflaeche" not in antwort.text
    assert "data-vorschau" not in antwort.text.split("<body")[1][:30]


def test_die_vorschau_ist_gekennzeichnet_und_ihre_policy_passt(monkeypatch, buch, gate1_buch, laufquelle):
    """Das Kennzeichen steht am <body>, nicht im Skript — der Hash bleibt derselbe."""
    from fastapi.testclient import TestClient

    from app import erzeuge_app

    normal = TestClient(erzeuge_app(buch, laufquelle=laufquelle, gate1_buch=gate1_buch)).get("/")
    monkeypatch.setenv("BC2_VORSCHAU", "1")
    vorschau = TestClient(erzeuge_app(buch, laufquelle=laufquelle, gate1_buch=gate1_buch)).get("/")
    assert "<body data-vorschau>" in vorschau.text
    assert vorschau.headers["content-security-policy"] == normal.headers["content-security-policy"]


def test_die_seite_traegt_keine_daten_im_quelltext(client):
    """Der Prototyp hatte die Zahlen eingebettet — diese Fassung nicht.

    Sonst wäre die Seite ohne Schlüssel lesbar und trüge Mandantendaten.
    """
    text = client.get("/").text
    assert "PROTOTYP_DATEN" not in text
    assert "potenzial_id" not in text or "window.DATEN" not in text


# ---------------------------------------------------------------------------
# Schlüssel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pfad",
    ["/api/oberflaeche/zustand", "/api/oberflaeche/laeufe", "/api/oberflaeche/laeufe/egal"],
)
def test_ohne_schluessel_kein_zugang(client, pfad):
    assert client.get(pfad).status_code == 401


def test_entscheiden_ohne_schluessel(client):
    assert client.post("/api/oberflaeche/laeufe/egal/gate1", json={}).status_code == 401


# ---------------------------------------------------------------------------
# Zustand und Liste
# ---------------------------------------------------------------------------


def test_zustand_sagt_die_ablage_an(client, kopf):
    """Die Seite soll ansagen koennen, dass die Entscheidung fluechtig ist."""
    zustand = client.get("/api/oberflaeche/zustand", headers=kopf).json()
    assert zustand["ablage"] == "arbeitsspeicher"
    assert zustand["fluechtig"] is True
    assert "Neustart" in zustand["hinweis"]


def test_liste_filtert_nach_company_id(client, kopf):
    """**Invariante:** jede Abfrage filtert nach ``company_id``.

    Es liegen zwei Mandanten in derselben Datenbank, und die Datenbank trennt
    sie nicht (``CLAUDE.md``; im Eingang liegt nachweislich ein Paket des
    Übungsmandanten neben denen von NoroAI, #190).
    """
    alle = client.get("/api/oberflaeche/laeufe", headers=kopf).json()["laeufe"]
    assert alle
    eine = alle[0]["company_id"]

    gefiltert = client.get(
        "/api/oberflaeche/laeufe", params={"company_id": eine}, headers=kopf
    ).json()["laeufe"]
    assert gefiltert and all(z["company_id"] == eine for z in gefiltert)

    leer = client.get(
        "/api/oberflaeche/laeufe", params={"company_id": "gibt-es-nicht"}, headers=kopf
    ).json()["laeufe"]
    assert leer == []


def test_unbekannter_lauf_ist_404(client, kopf):
    assert client.get("/api/oberflaeche/laeufe/GIBT-ES-NICHT", headers=kopf).status_code == 404


def test_lauf_traegt_die_vertragsbloecke(client, kopf):
    lauf = ein_lauf(client, kopf)
    assert {"kopf", "eintraege", "prozess_raenge", "potenziale", "gate1", "score_formel"} <= set(
        lauf
    )
    assert lauf["gate1"]["status"] == "pending"
    # Jeder Eintrag hat ein Detail, sonst liefe die Schublade ins Leere.
    for eintrag in lauf["eintraege"]:
        assert eintrag["potenzial_id"] in lauf["potenziale"]


def test_ein_nicht_nachrechenbarer_lauf_sagt_das_an(client, kopf):
    """Der Sperrgrund des Messsatzes reist bis in die Kopfzeile.

    Ihn zu schlucken hiesse, erfundene Zahlen wie erhobene aussehen zu lassen —
    genau die Scheingenauigkeit, gegen die das ganze Bandbreitenmodell steht.
    """
    lauf = ein_lauf(client, kopf)
    assert lauf["kopf"]["sperrgrund"]
    assert "warnung" not in lauf["kopf"]


def test_ein_lauf_mit_sperrgrund_laesst_sich_trotzdem_freigeben(client, kopf):
    """Die Freigabe ist die Entscheidung des Menschen, der Sperrgrund ein Merkmal
    des Laufs (#305, Punkt 5) — er sperrt die Lieferung, nicht Gate 1."""
    lauf = ein_lauf(client, kopf)
    assert lauf["kopf"]["sperrgrund"]
    antwort = sende(client, kopf, lauf["kopf"]["paket_id"], alle_freigeben(lauf))
    assert antwort.status_code == 200
    assert antwort.json()["gate1"]["status"] == "approved"


def test_hinweise_stehen_getrennt_vom_sperrgrund(buch, gate1_buch, kopf):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from app import erzeuge_app

    ansicht = _nachrechenbarer_lauf()
    ansicht = replace(ansicht, kopf=replace(ansicht.kopf, hinweise=("Modellurteil.",)))
    with TestClient(erzeuge_app(buch, laufquelle=SpeicherLaufquelle([ansicht]),
                                gate1_buch=gate1_buch)) as c:
        lauf = c.get("/api/oberflaeche/laeufe/PKT-2026-0042", headers=kopf).json()
    assert lauf["kopf"]["hinweise"] == ["Modellurteil."]
    assert "sperrgrund" not in lauf["kopf"]


# ---------------------------------------------------------------------------
# Die Begründungspflicht — der Kern von Fassung D
# ---------------------------------------------------------------------------


def test_nicht_freigabe_ohne_begruendung_wird_abgewiesen(client, kopf):
    """Die Regel aus #167, **auf dem Server**.

    Im Prototyp war sie ein ausgegrauter Knopf — wer die Seite umging, kam
    daran vorbei. Eine Regel, die nur die Anzeige kennt, ist keine Regel.
    """
    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]

    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        {
            "status": "approved",
            "approved_potenzial_ids": ids[1:],
            "nicht_freigegeben": [{"potenzial_id": ids[0], "begruendung": ""}],
        },
    )
    assert antwort.status_code == 422
    maengel = " ".join(antwort.json()["maengel"])
    assert ids[0] in maengel and "Begruendung" in maengel


def test_zu_kurze_begruendung_zaehlt_nicht(client, kopf):
    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        {
            "status": "approved",
            "approved_potenzial_ids": ids[1:],
            "nicht_freigegeben": [{"potenzial_id": ids[0], "begruendung": "ok"}],
        },
    )
    assert antwort.status_code == 422


def test_mit_begruendung_geht_es_durch(client, kopf, gate1_buch):
    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    grund = "Haengt an einer Schnittstelle, die erst im naechsten Quartal steht."

    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        {
            "status": "approved",
            "entscheider": "S. Morazan",
            "approved_potenzial_ids": ids[1:],
            "nicht_freigegeben": [{"potenzial_id": ids[0], "begruendung": grund}],
        },
    )
    assert antwort.status_code == 200

    # Die Begruendung ist abgelegt — sie ist der einzige Grund, aus dem ein
    # spaeterer Leser versteht, warum ein gerechnetes Potenzial fehlt (#167).
    abgelegt = gate1_buch.lesen(lauf["kopf"]["paket_id"])
    assert abgelegt is not None
    assert abgelegt.nicht_freigegeben[0].begruendung == grund
    assert abgelegt.entscheider == "S. Morazan"


def test_ein_potenzial_darf_nicht_vergessen_werden(client, kopf):
    """Weder freigegeben noch begründet herausgenommen: das ist keine Entscheidung."""
    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        {"status": "approved", "approved_potenzial_ids": ids[1:], "nicht_freigegeben": []},
    )
    assert antwort.status_code == 422
    assert "weder freigegeben" in " ".join(antwort.json()["maengel"])


def test_gar_nichts_freigegeben_ist_eine_ablehnung(client, kopf):
    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        {
            "status": "approved",
            "approved_potenzial_ids": [],
            "nicht_freigegeben": [
                {"potenzial_id": i, "begruendung": "Kommt in dieser Runde nicht mit."}
                for i in ids
            ],
        },
    )
    assert antwort.status_code == 422
    assert "abgelehnt" in " ".join(antwort.json()["maengel"])


def test_fremdes_potenzial_wird_abgewiesen(client, kopf):
    """Ein Potenzial, das das Paket nicht trägt, ist kein Formfehler.

    Es ist der Hinweis, dass die Oberfläche auf einem anderen Stand gearbeitet
    hat als der Server — etwa weil inzwischen neu gerechnet wurde.
    """
    lauf = ein_lauf(client, kopf)
    rumpf = alle_freigeben(lauf)
    rumpf["approved_potenzial_ids"] = rumpf["approved_potenzial_ids"] + ["fremde-id"]
    antwort = sende(client, kopf, lauf["kopf"]["paket_id"], rumpf)
    assert antwort.status_code == 422
    assert "gehoert aber nicht zu diesem Lauf" in " ".join(antwort.json()["maengel"])


# ---------------------------------------------------------------------------
# Ablehnung des ganzen Laufs
# ---------------------------------------------------------------------------


def test_ablehnung_braucht_einen_kommentar(client, kopf):
    lauf = ein_lauf(client, kopf)
    antwort = sende(client, kopf, lauf["kopf"]["paket_id"], {"status": "rejected"})
    assert antwort.status_code == 422
    assert "Kommentar" in " ".join(antwort.json()["maengel"])


def test_ablehnung_verlangt_keine_einzelbegruendungen(client, kopf):
    """Wird der ganze Lauf abgelehnt, ist die Begründung **eine**.

    Elf Mal dasselbe zu schreiben wäre genau die Zumutung, die die Vorbelegung
    vermeidet — und nach ADR-007 geht bei Reject ohnehin nichts an BC3.
    """
    lauf = ein_lauf(client, kopf)
    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        {"status": "rejected", "kommentar": "Der Zuschnitt des Pakets passt nicht."},
    )
    assert antwort.status_code == 200
    assert antwort.json()["gate1"]["status"] == "rejected"


# ---------------------------------------------------------------------------
# Die gesetzte Reihenfolge — die zweite Auflage aus #167
# ---------------------------------------------------------------------------


def test_gesetzte_folge_muss_eine_permutation_sein(client, kopf):
    """Sie trägt auch die herausgenommenen Potenziale.

    Sonst liesse sich nach einer Ablehnung nicht mehr sagen, wo das Potenzial
    gestanden hätte.
    """
    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        alle_freigeben(
            lauf,
            finale_reihenfolge_potenzial_ids=ids[:-1],  # eines fehlt
            abweichungsbegruendung="Compliance zuerst.",
        ),
    )
    assert antwort.status_code == 422
    assert "genau die Potenziale dieses Laufs" in " ".join(antwort.json()["maengel"])


def test_umsortieren_verlangt_eine_begruendung(client, kopf):
    """Der gerechnete Rang ist ein Vorschlag — die Abweichung ist zu begründen."""
    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    gedreht = list(reversed(ids))

    ohne = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        alle_freigeben(lauf, finale_reihenfolge_potenzial_ids=gedreht),
    )
    assert ohne.status_code == 422
    assert "abweichungsbegruendung" in " ".join(ohne.json()["maengel"])

    mit = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        alle_freigeben(
            lauf,
            finale_reihenfolge_potenzial_ids=gedreht,
            abweichungsbegruendung="Die Compliance-Themen muessen vor dem Audit stehen.",
        ),
    )
    assert mit.status_code == 200
    assert mit.json()["gate1"]["finale_reihenfolge_potenzial_ids"] == gedreht


def test_den_vorschlag_zu_bestaetigen_braucht_keine_begruendung(client, kopf):
    """Gleiche Liste in gleicher Folge ist keine Abweichung.

    Wer der Rechnung folgt, schuldet keine Erklärung — das ist der ganze Grund,
    warum der Vorschlag vorbelegt ist.
    """
    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    antwort = sende(
        client, kopf, lauf["kopf"]["paket_id"],
        alle_freigeben(lauf, finale_reihenfolge_potenzial_ids=ids),
    )
    assert antwort.status_code == 200


def test_prozessfolge_wird_eigenstaendig_geprueft(client, kopf):
    """Fassung D lässt auf **zwei** Ebenen ziehen — beide reisen mit."""
    lauf = ein_lauf(client, kopf)
    kps = [r["kp_id"] for r in lauf["prozess_raenge"]]
    if len(kps) < 2:
        pytest.skip("Der Messsatz traegt nur einen Kernprozess.")

    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        alle_freigeben(
            lauf,
            finale_prozessreihenfolge_kp_ids=list(reversed(kps)),
            abweichungsbegruendung="Der Abrechnungsprozess bindet Personal im Quartalsschluss.",
        ),
    )
    assert antwort.status_code == 200
    assert antwort.json()["gate1"]["finale_prozessreihenfolge_kp_ids"] == list(reversed(kps))


# ---------------------------------------------------------------------------
# Der Stand überlebt den Ruf — und kommt beim Laden zurück
# ---------------------------------------------------------------------------


def test_entscheidung_kommt_beim_naechsten_laden_zurueck(client, kopf):
    lauf = ein_lauf(client, kopf)
    paket_id = lauf["kopf"]["paket_id"]
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    grund = "Wartet auf die Ablösung des Altsystems."

    sende(
        client, kopf, paket_id,
        {
            "status": "approved",
            "approved_potenzial_ids": ids[1:],
            "nicht_freigegeben": [{"potenzial_id": ids[0], "begruendung": grund}],
        },
    )

    erneut = client.get(f"/api/oberflaeche/laeufe/{paket_id}", headers=kopf).json()
    assert erneut["gate1"]["status"] == "approved"
    assert erneut["gate1"]["nicht_freigegeben"] == [
        {"potenzial_id": ids[0], "begruendung": grund}
    ]

    # Und die Liste zeigt den Stand, ohne dass man den Lauf oeffnen muss.
    liste = client.get("/api/oberflaeche/laeufe", headers=kopf).json()["laeufe"]
    assert next(z for z in liste if z["paket_id"] == paket_id)["gate1_status"] == "approved"


def test_ein_entwurf_wird_ersetzt(client, kopf):
    """Solange Gate 1 ``pending`` ist, ersetzt eine neue Angabe die alte."""
    lauf = ein_lauf(client, kopf)
    paket_id = lauf["kopf"]["paket_id"]

    assert sende(client, kopf, paket_id, alle_freigeben(lauf, status="pending")).status_code == 200
    assert sende(
        client, kopf, paket_id, {"status": "rejected", "kommentar": "Doch nicht."}
    ).status_code == 200

    erneut = client.get(f"/api/oberflaeche/laeufe/{paket_id}", headers=kopf).json()
    assert erneut["gate1"]["status"] == "rejected"
    assert "approved_potenzial_ids" not in erneut["gate1"]


def test_nach_abschluss_ist_gate1_endgueltig(client, kopf):
    """``approved`` und ``rejected`` sind endgültig (ADR-008 · BC2, 2.3).

    Bis #290 ersetzte eine zweite Entscheidung die erste still. Jetzt ist sie
    ein Konflikt: die Geschichte des Pendelns trägt die *Fassung*, nicht ein
    Überschreiben — und wer überschreibt, hat meist einen alten Stand vor sich.
    """
    lauf = ein_lauf(client, kopf)
    paket_id = lauf["kopf"]["paket_id"]

    assert sende(client, kopf, paket_id, alle_freigeben(lauf)).status_code == 200
    zweite = sende(client, kopf, paket_id, {"status": "rejected", "kommentar": "Doch nicht."})

    assert zweite.status_code == 409
    # Der geltende Stand kommt mit, damit die Seite ihn zeigen kann.
    assert zweite.json()["gate1"]["status"] == "approved"
    erneut = client.get(f"/api/oberflaeche/laeufe/{paket_id}", headers=kopf).json()
    assert erneut["gate1"]["status"] == "approved"


# ---------------------------------------------------------------------------
# Ausnahmefälle der Anzeige
# ---------------------------------------------------------------------------


def test_ein_leerer_lauf_bricht_nichts(client, kopf, buch, gate1_buch):
    """Ein Paket ohne Potenziale ist ein zulässiger Zustand, kein Fehler."""
    from app import erzeuge_app
    from fastapi.testclient import TestClient

    leer = Laufansicht(
        kopf=Laufkopf(
            paket_id="LEER-1",
            company_id="7c2d5ee9-2a9a-5990-810f-502ea2b2012d",
            uebergeben_am=datetime(2026, 9, 21, tzinfo=timezone.utc),
        ),
        score_formel="",
        eintraege=[],
        prozess_raenge=[],
        potenziale={},
    )
    with TestClient(
        erzeuge_app(buch, laufquelle=SpeicherLaufquelle([leer]), gate1_buch=gate1_buch)
    ) as c:
        antwort = c.get("/api/oberflaeche/laeufe/LEER-1", headers=kopf)
        assert antwort.status_code == 200
        assert antwort.json()["eintraege"] == []

        # Freigeben laesst sich so ein Lauf nicht: es gibt nichts freizugeben.
        weiter = c.post(
            "/api/oberflaeche/laeufe/LEER-1/gate1",
            headers=kopf,
            json={"status": "approved", "approved_potenzial_ids": []},
        )
        assert weiter.status_code == 422


def test_fehlende_value_zahl_ist_ein_etikett_keine_null(client, kopf):
    """#167 Frage 6: bei fehlenden Daten **nie eine 0**.

    Der Listeneintrag lässt ``einsparung_eur_jahr`` dann ganz weg, statt eine
    Null zu schreiben — eine 0 wäre die Aussage „spart nichts", und das ist
    etwas anderes als „nicht erhoben".
    """
    lauf = ein_lauf(client, kopf)
    ohne = [e for e in lauf["eintraege"] if "einsparung_eur_jahr" not in e]
    if not ohne:
        pytest.skip("Der Messsatz traegt keinen Fall ohne Value-Zahl.")

    for eintrag in ohne:
        assert eintrag.get("einsparung_eur_jahr") is None
        detail = lauf["potenziale"][eintrag["potenzial_id"]]
        assert detail["value"]["value_quelle"] == "keine"
        assert detail["value"]["grund"]
        # Der Nutzwert traegt die Bewertung trotzdem — BC2 rechnet qualitativ
        # weiter und scheitert nur an der monetaeren Aussage (#163).
        assert detail["nutzwert"]["mittel"] > 0


# ---------------------------------------------------------------------------
# Gegen den Vertrag
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not VERTRAG.exists(), reason="priorisierung.schema.json nicht gefunden")
def test_gate1_block_gilt_gegen_den_vertrag(client, kopf):
    """Was der Dienst zurückgibt, muss ``priorisierung.schema.json`` genügen.

    Sonst wäre die Auflage aus #167 nur auf dem Papier eingelöst: der Vertrag
    hätte die Felder, und der Dienst füllte sie anders.
    """
    import jsonschema

    schema = json.loads(VERTRAG.read_text(encoding="utf-8"))
    gate1_schema = schema["properties"]["gate1"]

    lauf = ein_lauf(client, kopf)
    ids = [e["potenzial_id"] for e in lauf["eintraege"]]
    kps = [r["kp_id"] for r in lauf["prozess_raenge"]]

    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        alle_freigeben(
            lauf,
            nicht_freigegeben=[],
            finale_reihenfolge_potenzial_ids=list(reversed(ids)),
            finale_prozessreihenfolge_kp_ids=list(reversed(kps)),
            abweichungsbegruendung="Compliance vor Ertrag, so der Beschluss vom Quartalsmeeting.",
        ),
    )
    assert antwort.status_code == 200
    jsonschema.validate(antwort.json()["gate1"], gate1_schema)


@pytest.mark.skipif(not VERTRAG.exists(), reason="priorisierung.schema.json nicht gefunden")
def test_abgelehnter_lauf_gilt_ebenfalls(client, kopf):
    import jsonschema

    schema = json.loads(VERTRAG.read_text(encoding="utf-8"))
    lauf = ein_lauf(client, kopf)
    antwort = sende(
        client,
        kopf,
        lauf["kopf"]["paket_id"],
        {"status": "rejected", "kommentar": "Das Paket wird neu geschnuert.", "entscheider": "S. M."},
    )
    assert antwort.status_code == 200
    jsonschema.validate(antwort.json()["gate1"], schema["properties"]["gate1"])


# ---------------------------------------------------------------------------
# Die Präsentation (#257)
# ---------------------------------------------------------------------------


def _praesentation(client, kopf, paket_id: str):
    return client.post(f"/api/oberflaeche/laeufe/{paket_id}/praesentation", headers=kopf)


def test_praesentation_braucht_den_schluessel(client):
    assert _praesentation(client, {}, "egal").status_code == 401


def test_praesentation_vor_der_freigabe_gibt_es_nicht(client, kopf):
    lauf = ein_lauf(client, kopf)
    antwort = _praesentation(client, kopf, lauf["kopf"]["paket_id"])
    assert antwort.status_code == 409
    assert "Freigabe" in antwort.json()["fehler"]


def test_praesentation_bei_ablehnung_gibt_es_nicht(client, kopf):
    lauf = ein_lauf(client, kopf)
    pid = lauf["kopf"]["paket_id"]
    assert sende(client, kopf, pid, {"status": "rejected", "kommentar": "Zahlen unplausibel."}).status_code == 200
    assert _praesentation(client, kopf, pid).status_code == 409


def test_praesentation_nach_freigabe_kommt_als_pptx(client, kopf):
    from io import BytesIO

    from pptx import Presentation

    lauf = ein_lauf(client, kopf)
    pid = lauf["kopf"]["paket_id"]
    assert sende(client, kopf, pid, alle_freigeben(lauf)).status_code == 200

    antwort = _praesentation(client, kopf, pid)
    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    assert 'filename="praesentation.pptx"' in antwort.headers["content-disposition"]
    prs = Presentation(BytesIO(antwort.content))
    notizen = [f.notes_slide.notes_text_frame.text for f in prs.slides if f.has_notes_slide]
    detail = [n for n in notizen if n.startswith("potenzial_id:")]
    assert len(detail) == len(lauf["eintraege"])


def _nachrechenbarer_lauf() -> Laufansicht:
    """Ein Lauf ohne Warnung — so, wie er aus dem Erkennungsschritt käme."""
    from laeufe import aus_lauf
    from modell import Nutzwert, Nutzwertkategorie, Potenzialeingang, Schrittmessung, rechne_lauf
    from modell.ausgabe import als_ausgangslage

    k = Nutzwertkategorie(6, "Begruendungssatz fuer den Test.")
    eingang = Potenzialeingang(
        potenzial_id="00000000-0000-4000-8000-0000000000aa",
        titel="Rechnungsstellung aus der Zeiterfassung",
        kp_id="KP-06",
        betroffene_teilprozess_ids=("KP-06.TP-2",),
        klasse="Integration",
        automatisierungsgrad_begruendung="Zwei Systeme verbinden.",
        nutzwert=Nutzwert(k, k, k, k, k),
        messungen=(
            Schrittmessung(
                teilprozess_id="KP-06.TP-2",
                frequency_per_year=180.0,
                focus_step_duration_minutes=180.0,
                focus_step_duration_source="geschaetzt",
                reifeskalen=(4, 4, 3, 4),
            ),
        ),
        aufwand_schaetzung_pt=12.0,
    )
    lauf = rechne_lauf("7c2d5ee9-2a9a-5990-810f-502ea2b2012d", "PKT-2026-0042", [eingang])
    ansicht = aus_lauf(lauf, [eingang], uebergeben_am=datetime(2026, 9, 20, tzinfo=timezone.utc))

    class _M:
        name, branche, mitarbeitende, region, geschaeftsmodell = (
            "NoroAI Consulting GmbH", "KI-Beratung", 10, None, None)

    konzept = {"kontext": {"kp_id": "KP-06", "hauptschmerzpunkte": [
        {"beschreibung": "Stunden werden abgetippt", "auswirkung": "Fehler und Verzug"}]}}
    from dataclasses import replace
    return replace(ansicht, ausgangslage=als_ausgangslage(_M(), [konzept]))


def test_die_praesentation_wird_nirgends_abgelegt(buch, gate1_buch, kopf, tmp_path, monkeypatch):
    """Sie geht an den Mandanten, nicht an BC3 (#305, Punkt 4): Download ja,
    Lieferordner nein — auch nicht für einen lieferbaren Lauf."""
    from fastapi.testclient import TestClient

    from app import erzeuge_app

    monkeypatch.chdir(tmp_path)
    quelle = SpeicherLaufquelle([_nachrechenbarer_lauf()])
    with TestClient(erzeuge_app(buch, laufquelle=quelle, gate1_buch=gate1_buch)) as c:
        lauf = c.get("/api/oberflaeche/laeufe/PKT-2026-0042", headers=kopf).json()
        assert "sperrgrund" not in lauf["kopf"]
        sende(c, kopf, "PKT-2026-0042", alle_freigeben(lauf))
        antwort = _praesentation(c, kopf, "PKT-2026-0042")
    assert antwort.status_code == 200
    assert "x-bc2-ablage" not in antwort.headers
    assert not any(tmp_path.iterdir())


def test_die_seite_bringt_ihre_eigene_enge_policy_mit(client):
    """Caddy schickt sonst ``default-src 'none'`` und blockiert das Skript der
    Seite — so stand die Oberfläche im Betrieb bei „wird geladen“ (#290 bis heute).
    Die Browsertests laufen unter genau dieser Policy; hier steht, wie sie aussieht."""
    import base64
    import hashlib

    from oberflaeche import STATIC, inline_skripte

    antwort = client.get("/")
    csp = antwort.headers["content-security-policy"]
    # Gegenprobe ohne den Parser: von Hand zwischen den Tags geschnitten.
    html = (STATIC / "index.html").read_text("utf-8")
    anfang = html.index("<script>") + len("<script>")
    skript = html[anfang:html.index("</script>", anfang)]
    assert inline_skripte(html) == [skript]
    erwartet = base64.b64encode(hashlib.sha256(skript.encode("utf-8")).digest()).decode()
    assert f"script-src 'sha256-{erwartet}'" in csp
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]
    assert "connect-src 'self'" in csp and "frame-ancestors 'none'" in csp


def test_die_json_api_bringt_keine_eigene_policy_mit(client, kopf):
    """Dort setzt Caddy ``default-src 'none'`` — die Anwendung darf es nicht überschreiben."""
    assert "content-security-policy" not in client.get("/api/oberflaeche/laeufe", headers=kopf).headers


def test_der_hash_uebersteht_schreibweise_und_attribute():
    from oberflaeche import inline_skripte

    html = '<SCRIPT type="module">a < b</SCRIPT><script src="x.js"></script><Script>c</Script>'
    assert inline_skripte(html) == ["a < b", "c"]


def test_die_seite_kommt_nicht_aus_dem_cache(client):
    assert client.get("/").headers["cache-control"] == "no-cache"
