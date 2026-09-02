import json
from decimal import Decimal

import pytest

from bc1_core.feldtypen import AUSWAHL, MINUTEN, PROZENT_0_100, ZAHL
from bc1_core.package import FieldSpec, UseCasePackage
from bc1_core.types import FieldStatus, FieldValue, SessionState
from bc1_service.paket_feldtypen import baue_system_typ
from bc1_service.profil_writer import (
    GRUND_SNN_ENTFALLEN,
    ProfilWriteError,
    baue_profilinhalt,
    wende_sweep_an,
)

PAKET = UseCasePackage(
    name="discovery", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa",
    fields=(
        FieldSpec("focus_step", "Welcher Schritt?", typ=AUSWAHL("KP-01.TP-1"),
                  identitaetskritisch=True),
        FieldSpec("process_id", "Welcher Kernprozess?", typ=AUSWAHL("KP-01", "KP-02")),
        FieldSpec("frequency_per_year", "Wie oft?", typ=ZAHL),
        FieldSpec("total_duration_minutes", "Wie lange?", typ=MINUTEN),
        FieldSpec("focus_step_duration_confidence_pct", "Wie sicher?",
                  typ=PROZENT_0_100),
        FieldSpec("upstream_process", "Was kommt davor?", required=False),
    ),
)


# Paket mit ALLEN neun Feldern, die der Writer liest. PAKET oben deckt nur sechs ab —
# damit blieb die Verdrahtung von vier Spalten ungeprueft: eine Spalte, die aus dem
# FALSCHEN Feld liest, ergab im Test genauso None wie eine korrekte (Review 02.09.,
# per Mutation belegt: vier Vertauschungen liessen die volle Suite gruen).
VOLL_PAKET = UseCasePackage(
    name="discovery", schema_version="1.1+ctx-bbbbbbbbbbbbbbbb",
    fields=(
        FieldSpec("focus_step", "Welcher Schritt?", typ=AUSWAHL("KP-01.TP-1"),
                  identitaetskritisch=True),
        FieldSpec("frequency_per_year", "Wie oft?", typ=ZAHL),
        FieldSpec("executions_per_run", "Wie viele je Lauf?", typ=ZAHL),
        FieldSpec("total_duration_minutes", "Wie lange gesamt?", typ=MINUTEN),
        FieldSpec("focus_step_duration_minutes", "Wie lange der Schritt?", typ=MINUTEN),
        FieldSpec("focus_step_duration_source", "Woher die Dauer?",
                  typ=AUSWAHL("gemessen", "geschaetzt", "aus_system")),
        FieldSpec("focus_step_duration_confidence_pct", "Wie sicher?", typ=PROZENT_0_100),
        FieldSpec("upstream_process", "Was kommt davor?", required=False),
        FieldSpec("downstream_process", "Was kommt danach?", required=False),
    ),
)


def _state(**werte):
    st = SessionState("s1", PAKET.schema_version, paket_name="discovery",
                      company_id="11111111-1111-1111-1111-111111111111")
    for name, (wert, status) in werte.items():
        st.values[name] = FieldValue(value=wert, status=status,
                                     source_message_id="m1")
    return st


def _bau(state, kp_bekannt=lambda kp: kp in {"KP-01", "KP-02"}):
    return baue_profilinhalt(state, PAKET, kp_bekannt=kp_bekannt)


def test_ohne_gueltige_tp_id_entsteht_kein_profil():
    assert _bau(_state(focus_step=("Bestellung", FieldStatus.UNGUELTIG))) is None


def test_identitaet_kommt_allein_aus_der_tp_id():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         process_id=("KP-02", FieldStatus.GUELTIG)))
    assert inhalt.focus_step_id == "KP-01.TP-1"
    assert inhalt.process_id == "KP-01"                       # Praefix schlaegt Interview
    assert inhalt.profil["befunde"]["kp_tp_diskrepanz"] == {
        "interview_kp": "KP-02", "abgeleiteter_kp": "KP-01"}


def test_ohne_diskrepanz_kein_befund():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         process_id=("KP-01", FieldStatus.GUELTIG)))
    assert "kp_tp_diskrepanz" not in inhalt.profil["befunde"]


def test_freitext_kernprozess_erzeugt_keinen_diskrepanz_befund():
    # Ohne BC0-Snapshot ist das KP-Feld FREITEXT (BC1_SNAPSHOT_PFAD ist laut main.py
    # ausdruecklich optional). Dann waere JEDE normale Antwort != "KP-01", der Befund
    # entstuende in jedem Profil und das Warnlog schriebe bei jeder Sitzung rohen
    # Nutzertext mit (Review 02.09., am echten Paket gemessen). Ein Freitext
    # widerspricht einer KP-ID nicht — er ist schlicht etwas anderes.
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         process_id=("Auftragsabwicklung", FieldStatus.GUELTIG)))
    assert "kp_tp_diskrepanz" not in inhalt.profil["befunde"]


def test_nur_gueltige_werte_landen_in_den_spalten():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         frequency_per_year=("120", FieldStatus.GUELTIG),
                         total_duration_minutes=("90", FieldStatus.UNKLAR)))
    assert inhalt.spalten["frequency_per_year"] == Decimal("120")
    assert inhalt.spalten["total_duration_minutes"] is None    # UNKLAR => NULL
    assert inhalt.spalten["process_owner_rolle_id"] is None     # Etappe 1


def test_zahlen_kommen_als_decimal_nie_als_float():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         frequency_per_year=("0.1", FieldStatus.GUELTIG)))
    assert isinstance(inhalt.spalten["frequency_per_year"], Decimal)


def test_upstream_nur_als_bekannte_kanonische_fremde_kp_id():
    def bau(wert, kp_bekannt=lambda kp: kp == "KP-02"):
        return _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                           upstream_process=(wert, FieldStatus.GUELTIG)),
                    kp_bekannt=kp_bekannt)
    assert bau("KP-02").spalten["upstream_process_id"] == "KP-02"
    assert bau("Wareneingang").spalten["upstream_process_id"] is None
    assert bau("KP-09").spalten["upstream_process_id"] is None       # nicht in Baseline
    assert bau("KP-01").spalten["upstream_process_id"] is None       # Selbstbezug


def test_unkonvertierbarer_gueltiger_wert_ist_ein_harter_fehler():
    # Konstruierter Widerspruch Validator<->Spaltentyp (im Discovery-Paket durch
    # PROZENT_GANZ_0_100 ausgeschlossen) — er MUSS laut werden, nicht still NULL.
    state = _state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                   focus_step_duration_confidence_pct=("70.5", FieldStatus.GUELTIG))
    with pytest.raises(ProfilWriteError):
        _bau(state)


def test_unkonvertierbare_dezimalzahl_ist_ebenfalls_ein_harter_fehler():
    # Der Plan-Testsatz prueft den harten Fehler nur fuer die GANZZAHL-Spalte. Ohne
    # diesen Test kaeme bei einer Dezimalspalte eine rohe decimal.InvalidOperation
    # durch. Bewiesener Vertrag: der DB-freie Bau leakt keine Implementierungs-
    # Exception, sondern meldet JEDEN Konvertierungswiderspruch als ProfilWriteError.
    # (Meine urspruengliche Begruendung "sonst 500 statt 503" ging zu weit — Task 11
    # hat keinen HTTP-Pfad, und Task 14 uebersetzt fremde Exceptions ohnehin.
    # Codex-Review 02.09.)
    state = _state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                   frequency_per_year=("dreimal jaehrlich", FieldStatus.GUELTIG))
    with pytest.raises(ProfilWriteError):
        _bau(state)


def test_konvertierungsfehler_wird_strukturiert_geloggt(caplog):
    # Der Plan verlangt "ProfilWriteError plus strukturiertes Log". Der Fehler wird
    # spaeter als generischer 503 ausgeliefert — ohne serverseitigen Eintrag mit
    # Session und Feld ist eine blockierte Sitzung nicht diagnostizierbar
    # (Review 02.09.). Der ROHWERT gehoert NICHT ins Log (Nutzertext).
    state = _state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                   frequency_per_year=("dreimal jaehrlich", FieldStatus.GUELTIG))
    with caplog.at_level("ERROR"), pytest.raises(ProfilWriteError):
        _bau(state)
    eintraege = [s for s in caplog.messages if "profil_konvertierung_widerspruch" in s]
    assert len(eintraege) == 1, caplog.messages
    assert "s1" in eintraege[0] and "frequency_per_year" in eintraege[0]
    assert "dreimal jaehrlich" not in eintraege[0]


def test_regulaeres_interview_kann_diesen_fehler_nicht_ausloesen():
    # Gegenprobe zum Test darueber: mit dem Paket-Feldtyp entsteht '70.5' gar
    # nicht erst als gueltig (Codex R1-C4).
    from bc1_service.paket_feldtypen import PROZENT_GANZ_0_100
    assert PROZENT_GANZ_0_100.validator(
        PROZENT_GANZ_0_100.normalisiere("70,5")) is False


@pytest.mark.parametrize("status", [FieldStatus.FEHLT, FieldStatus.UNGUELTIG,
                                    FieldStatus.UNKLAR, FieldStatus.UNGELOEST])
def test_jeder_nicht_gueltige_status_ergibt_null(status):
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG),
                         frequency_per_year=("120", status)))
    assert inhalt.spalten["frequency_per_year"] is None


def test_jede_typisierte_spalte_wird_belegt():
    # Vollstaendigkeitsprobe gegen die Mapping-Tabelle: keine Spalte darf
    # vergessen werden, sonst schreibt der Writer sie stumm nie.
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG)))
    assert set(inhalt.spalten) == {
        "process_owner_rolle_id", "upstream_process_id", "downstream_process_id",
        "frequency_per_year", "executions_per_run", "total_duration_minutes",
        "focus_step_duration_minutes", "focus_step_duration_source",
        "focus_step_duration_confidence_pct"}


def test_jede_spalte_liest_aus_ihrem_eigenen_feld():
    # Jedes Feld bekommt einen UNTERSCHEIDBAREN Wert — nur so faellt eine
    # vertauschte Zuordnung auf. Der Vollstaendigkeitstest darueber prueft nur die
    # Schluesselmenge und bliebe bei einer Vertauschung gruen (Review 02.09.).
    st = SessionState("s2", VOLL_PAKET.schema_version, paket_name="discovery",
                      company_id="11111111-1111-1111-1111-111111111111")
    for name, wert in (("focus_step", "KP-01.TP-1"), ("frequency_per_year", "11"),
                       ("executions_per_run", "22"), ("total_duration_minutes", "33"),
                       ("focus_step_duration_minutes", "44"),
                       ("focus_step_duration_source", "gemessen"),
                       ("focus_step_duration_confidence_pct", "55"),
                       ("upstream_process", "KP-02"), ("downstream_process", "KP-03")):
        st.values[name] = FieldValue(value=wert, status=FieldStatus.GUELTIG,
                                     source_message_id="m1")
    inhalt = baue_profilinhalt(
        st, VOLL_PAKET, kp_bekannt=lambda kp: kp in {"KP-02", "KP-03"})
    assert inhalt.spalten == {
        "process_owner_rolle_id": None,
        "frequency_per_year": Decimal("11"), "executions_per_run": Decimal("22"),
        "total_duration_minutes": Decimal("33"),
        "focus_step_duration_minutes": Decimal("44"),
        "focus_step_duration_source": "gemessen",
        "focus_step_duration_confidence_pct": 55,
        "upstream_process_id": "KP-02", "downstream_process_id": "KP-03"}


def test_json_traegt_den_vollen_payload_inklusive_zaehler():
    inhalt = _bau(_state(focus_step=("KP-01.TP-1", FieldStatus.GUELTIG)))
    assert set(inhalt.profil) >= {"felder", "vollstaendigkeit", "ungeloeste_felder",
                                  "pflicht_erfasst", "pflicht_gesamt",
                                  "schema_version", "befunde"}
    assert inhalt.profil["schema_version"] == PAKET.schema_version


SYS_PAKET = UseCasePackage(
    name="discovery", schema_version="1.1+ctx-aaaaaaaaaaaaaaaa",
    fields=(
        FieldSpec("focus_step", "Welcher Schritt?", typ=AUSWAHL("KP-01.TP-1"),
                  identitaetskritisch=True),
        FieldSpec("focus_step_systems", "Welche Systeme?",
                  typ=baue_system_typ(frozenset({"S-01"}))),
    ),
)
BEKANNT = frozenset({"S-01"})


def _payload(wert, status, kandidaten=()):
    return {
        "felder": {
            "focus_step": {"wert": "KP-01.TP-1", "status": "gueltig",
                           "quelle": "m1", "grund": None, "kandidaten": []},
            "focus_step_systems": {
                "wert": wert, "status": status, "quelle": "m1", "grund": None,
                "kandidaten": [{"wert": k, "quelle": "m1"} for k in kandidaten]},
        },
        "vollstaendigkeit": 1.0, "ungeloeste_felder": [],
        "pflicht_erfasst": 2, "pflicht_gesamt": 2,
        "schema_version": SYS_PAKET.schema_version, "befunde": {},
    }


def _sweep(payload):
    return wende_sweep_an(payload, SYS_PAKET, bekannte_systeme=BEKANNT,
                          session_id="s1")


def test_gueltig_wird_ungeloest_wenn_nichts_uebrig_bleibt():
    p = _sweep(_payload("S-99", "gueltig"))
    feld = p["felder"]["focus_step_systems"]
    assert feld["status"] == "ungeloest"
    assert feld["grund"] == GRUND_SNN_ENTFALLEN
    assert feld["wert"] is None
    assert p["befunde"]["snn_entfernt"] == [
        {"feld": "focus_step_systems", "anzahl": 1, "feld_status_danach": "ungeloest"}]
    assert "focus_step_systems" in p["ungeloeste_felder"]
    assert p["pflicht_erfasst"] == 1                      # Zaehler nachgezogen
    # Die Zahl, fuer die _zaehler_neu laut seiner Docstring ueberhaupt existiert —
    # und die vorher von keinem Test geschuetzt war (Review 02.09.: die Mutation
    # "vollstaendigkeit immer 1.0" ueberlebte die volle Suite).
    assert p["vollstaendigkeit"] == 0.5


def test_gueltig_bleibt_gueltig_wenn_der_rest_traegt():
    p = _sweep(_payload("SAP (S-99), DATEV (S-01)", "gueltig"))
    feld = p["felder"]["focus_step_systems"]
    assert feld["status"] == "gueltig"
    assert feld["wert"] == "SAP, DATEV (S-01)"
    assert p["befunde"]["snn_entfernt"][0]["feld_status_danach"] == "gueltig"


def test_leer_gewordener_kandidat_entfaellt():
    p = _sweep(_payload("SAP (S-01)", "gueltig", kandidaten=("S-99", "Excel (S-99)")))
    # Volle Dicts, nicht nur die Werte: "jeder Kandidat behaelt seine Quelle" ist ein
    # Spec-Vertrag (types.py). Mit nur den Werten ueberlebte die Mutation, die die
    # Quelle wegwirft, die ganze Suite (Review 02.09.).
    assert p["felder"]["focus_step_systems"]["kandidaten"] == [
        {"wert": "Excel", "quelle": "m1"}]


def test_nicht_gueltiges_feld_wird_still_bereinigt():
    p = _sweep(_payload("S-99", "ungeloest"))
    feld = p["felder"]["focus_step_systems"]
    assert feld["status"] == "ungeloest"                  # unveraendert
    assert feld["wert"] == ""                             # Token entfernt
    assert p["befunde"] == {}                             # KEIN Nutzer-Hinweis


def test_kein_unbekanntes_token_bleibt_im_json_stehen():
    p = _sweep(_payload("S-99", "gueltig", kandidaten=("Excel (S-98)",)))
    assert "S-99" not in json.dumps(p)
    assert "S-98" not in json.dumps(p)


def test_mehrere_betroffene_felder_bleiben_in_paketreihenfolge():
    p = _payload("S-99", "gueltig")
    p["felder"]["focus_step"]["wert"] = "KP-01.TP-1 (S-98)"     # zweites Feld
    # Das felder-Dict wird BEWUSST umgekehrt zur Paketreihenfolge angelegt. Sonst
    # beweist der Test nichts: beide Reihenfolgen faelen zusammen, und die Mutation
    # "iteriere ueber das JSON statt ueber das Paket" ueberlebte (Review 02.09.).
    p["felder"] = {"focus_step_systems": p["felder"]["focus_step_systems"],
                   "focus_step": p["felder"]["focus_step"]}
    ergebnis = _sweep(p)
    assert [b["feld"] for b in ergebnis["befunde"]["snn_entfernt"]] == [
        "focus_step", "focus_step_systems"]                      # Paketreihenfolge


def test_ohne_systemnennung_passiert_nichts():
    vorher = _payload("SAP, Excel", "gueltig")
    nachher = _sweep(_payload("SAP, Excel", "gueltig"))
    assert nachher == vorher


def test_entfernte_kennung_landet_im_log(caplog):
    # Die Postcondition hat zwei Haelften: keine rohe ID im JSON (oben geprueft)
    # UND die ID im strukturierten Log — sonst ist nach dem Sweep nicht mehr
    # feststellbar, WAS entfernt wurde. Der Plan testet nur die erste Haelfte.
    with caplog.at_level("WARNING"):
        _sweep(_payload("SAP (S-99)", "gueltig"))
    treffer = [s for s in caplog.messages if "snn_entfernt" in s]
    assert len(treffer) == 1, caplog.messages
    assert "S-99" in treffer[0] and "focus_step_systems" in treffer[0]
    assert "s1" in treffer[0]


def test_beim_aufraeumen_neu_entstandene_kennung_wird_auch_entfernt():
    # entferne_snn raeumt leere Klammern weg — dabei ruecken Nachbarn zusammen und
    # bilden eine NEUE Kennung: 'S-[S-98]42' -> 'S-42'. Ein Einmalscan sieht die nicht
    # mehr. Besonders scharf bei KANDIDATEN: die durchlaufen keinen Validator, dort
    # bliebe das erzeugte Token bei jedem Feldtyp stehen, waehrend der Befund weiter
    # "gueltig" meldet (Review 02.09., beides gemessen).
    p = _sweep(_payload("SAP (S-01)", "gueltig", kandidaten=("S-[S-98]42",)))
    roh = json.dumps(p)
    assert "S-98" not in roh
    assert "S-42" not in roh


def test_gueltig_wird_ungeloest_wenn_der_rest_ungueltig_ist():
    # Zweite Haelfte von Zeile 1 der Uebergangstabelle ("leer ODER ungueltig"). Im
    # Discovery-Paket unerreichbar, weil dort alle betroffenen Felder Freitext sind
    # und jeder nicht-leere Rest wieder gueltig ist. Ohne diesen Test ueberlebte die
    # Mutation "Validator ignorieren, Rest gilt immer als gueltig" (Review 02.09.).
    paket = UseCasePackage(
        name="d", schema_version="v",
        fields=(FieldSpec("a", "?", typ=AUSWAHL("SAP S-99", "DATEV")),))
    p = {"felder": {"a": {"wert": "SAP S-99", "status": "gueltig", "quelle": "m1",
                          "grund": None, "kandidaten": []}},
         "vollstaendigkeit": 1.0, "ungeloeste_felder": [], "pflicht_erfasst": 1,
         "pflicht_gesamt": 1, "schema_version": "v", "befunde": {}}
    ergebnis = wende_sweep_an(p, paket, bekannte_systeme=frozenset({"S-01"}),
                              session_id="s1")
    feld = ergebnis["felder"]["a"]
    assert feld["wert"] is None                    # Rest "SAP" ist keine Option mehr
    assert feld["status"] == "ungeloest"
    assert feld["grund"] == GRUND_SNN_ENTFALLEN
    assert ergebnis["befunde"]["snn_entfernt"] == [
        {"feld": "a", "anzahl": 1, "feld_status_danach": "ungeloest"}]
