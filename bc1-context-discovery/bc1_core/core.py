from __future__ import annotations
from bc1_core.types import (Ergebnis, FieldStatus, FieldValue, SessionState,
                            SessionStatus, TERMINALE_STATUS)
from bc1_core.package import UseCasePackage
from bc1_core.store import StateStore
from bc1_core.llm import LLMClient
from bc1_core.extractor import extract_and_merge
from bc1_core.confidence import confidence_check, ConfidenceResult
from bc1_core.dialog import GRUND_IDENTITAET_UNGEKLAERT, decide_next
from bc1_core.gespraech import baue_turn_kontext, werte_schnappschuss

class PaketKonfliktError(ValueError):
    """Session ist an ein anderes Paket / eine andere schema_version gebunden."""

class MandantKonfliktError(ValueError):
    """Session gehoert zu einem anderen Mandanten — oder zu gar keinem."""

def ist_terminal(state: SessionState) -> bool:
    return state.status in TERMINALE_STATUS

def pruefe_mandant(state: SessionState, company_id: str) -> None:
    """Ausnahmsloser Mandanten-Guard (Spec K3): laeuft nach JEDEM load als Erstes.

    Auch Alt-Sessions ohne gespeicherte company_id werden abgewiesen — sonst
    koennte nach einem A->B-Neustart eine Antwort aus Mandant A unter B sichtbar
    werden (R12-C1). Lieber ein abgewiesener Alt-Turn als ein Datenleck.
    """
    if state.company_id != company_id:
        raise MandantKonfliktError(
            f"Session {state.session_id} gehoert zu Mandant {state.company_id}, "
            f"der Aufruf kam mit {company_id}")

def _basis(schema_version: str) -> str:
    return schema_version.split("+", 1)[0]

def _ctx(schema_version: str) -> str:
    teile = schema_version.split("+", 1)
    return teile[1] if len(teile) > 1 else ""

def darf_recovery_replay(state: SessionState, package: UseCasePackage,
                         message_id: str,
                         mitgesendete_version: str | None) -> bool:
    """Eng begrenzte Ausnahme fuer den nachholenden Profil-Write (R13-I2).

    Alle VIER Bedingungen muessen gelten: gleicher Paketname, gleiche
    Basisversion, ausschliesslich abweichender ctx-Hash UND eine im Request
    mitgesendete alte schema_version, die zur Session passt. Fehlt die Version,
    gibt es KEIN Recovery (Codex R1-I1: 'None' waere die vierte Bedingung
    stillschweigend uebersprungen). Der Turn aendert per Definition nichts am
    Interview; er holt nur den Write nach. Die Mandanten-Pruefung ist davon
    ausdruecklich AUSGENOMMEN (R11-C1).
    """
    return (mitgesendete_version is not None
            and mitgesendete_version == state.schema_version
            and ist_terminal(state)
            and message_id in state.processed_message_ids
            and state.paket_name == package.name
            and _basis(state.schema_version) == _basis(package.schema_version)
            and _ctx(state.schema_version).startswith("ctx-")
            and _ctx(package.schema_version).startswith("ctx-"))

def _profil(state: SessionState, conf: ConfidenceResult,
            package: UseCasePackage) -> dict:
    # Über die Paketfelder iterieren, nicht über state.values: Gate 0 sieht
    # das ganze Paket (nie berührte Felder als FEHLT), Fremdeinträge nicht —
    # konsistent zu conf.statuses.
    felder = {}
    for spec in package.fields:
        fv = state.values.get(spec.name) or FieldValue()
        felder[spec.name] = {
            "wert": fv.value, "status": fv.status.value,
            "quelle": fv.source_message_id, "grund": fv.grund,
            "kandidaten": [{"wert": k.value, "quelle": k.source_message_id}
                           for k in fv.candidates]}
    return {
        "felder": felder,
        "vollstaendigkeit": conf.completeness,
        "ungeloeste_felder": conf.ungeloeste_felder,
        "schema_version": state.schema_version,
    }

def process_turn(store: StateStore, llm: LLMClient, package: UseCasePackage,
                 session_id: str, message_id: str, message: str,
                 *, company_id: str,
                 mitgesendete_version: str | None = None) -> dict:
    state = store.load(session_id)
    if state is None:
        # Mandanten-Bindung VOR dem ersten dauerhaften Speichern (R12-I1).
        state = SessionState(session_id, package.schema_version,
                             paket_name=package.name, company_id=company_id)
    else:
        pruefe_mandant(state, company_id)          # als ERSTES nach dem load

    if (state.schema_version != package.schema_version
            or state.paket_name not in (None, package.name)):
        if not darf_recovery_replay(state, package, message_id,
                                    mitgesendete_version):
            raise PaketKonfliktError(
                f"Session {session_id} laeuft mit Paket "
                f"{state.paket_name}/{state.schema_version}, Aufruf kam mit "
                f"{package.name}/{package.schema_version}")

    if message_id in state.processed_message_ids:
        if message_id in state.antworten:
            # Beantwortete Nachricht (n8n-/HTTP-Retry) → IHRE Antwort,
            # nicht die der neuesten Nachricht (Idempotenz je message_id).
            return state.antworten[message_id]
        if (ist_terminal(state)
                or not state.raw_log or state.raw_log[-1][0] != message_id):
            # Überholter unbeantworteter Turn (Session fertig oder andere
            # Nachricht kam dazwischen): nie neu verarbeiten — letzte
            # bekannte Antwort der Session liefern; existiert (nach
            # Doppel-Crash) keine, eine fortsetzbare Vertragsantwort.
            return next((state.antworten[mid]
                         for mid, _ in reversed(state.raw_log)
                         if mid in state.antworten),
                        {"status": "fehler_fortsetzbar",
                         "payload": {"grund": "turn_unbeantwortet"}})
        # Crash zwischen den Saves: die zuletzt geloggte, unbeantwortete
        # Nachricht fortsetzen — mit dem GELOGGTEN Text, nicht dem
        # (womöglich abweichenden) Retry-Body. Nicht erneut loggen.
        message = state.raw_log[-1][1]
    elif ist_terminal(state):
        # Nach der Gate-0-Übergabe gibt es keinen Übergang zurück (Spec B3).
        # Neue Nachrichten erhalten idempotent das Abschlussergebnis;
        # aktives Zurückweisen ist Sache der Transportschicht (P2).
        return state.antworten[state.raw_log[-1][0]]
    else:
        # Rohnachricht zuerst sichern (vor jedem LLM-Aufruf).
        state.raw_log.append((message_id, message))
        state.processed_message_ids.add(message_id)
        store.save(state)

    state.rounds += 1
    try:
        vorher = werte_schnappschuss(state)
        extract_and_merge(state, message, message_id, package, llm)
        conf = confidence_check(state, package)
        decision = decide_next(state, package, conf)
        if decision.ergebnis is not Ergebnis.WEITER:
            # decide_next kann Felder frisch gecappt haben — für Payload und
            # Abschluss-Kontext zählt der Stand NACH der Entscheidung.
            conf = confidence_check(state, package)
        if decision.ergebnis is Ergebnis.ABGEBROCHEN_OHNE_IDENTITAET:
            # Kein llm.antworte() (R8-I2) und kein Abschlusskontext: ein
            # LLM-Ausfall darf diesen Terminalzustand nicht kippen.
            antwortetext = None
        else:
            kontext = baue_turn_kontext(message, vorher, state, package, conf,
                                        decision.next_field,
                                        decision.ergebnis is Ergebnis.FERTIG)
            antwortetext = llm.antworte(kontext)
    except Exception:
        # LLM-Aussetzer (Spec B4): fortsetzbar melden. NUR der FEHLER-Marker
        # wird persistiert — auf dem letzten dauerhaften Stand, nicht auf dem
        # halb verarbeiteten Turn (sonst verbrauchte der Ausfall unsichtbar
        # rounds/attempts). Die Nachricht bleibt geloggt und UNBEANTWORTET —
        # der Retry setzt fort. Retries/Backoff → echter LLM-Client (Roadmap).
        state = store.load(session_id)
        pruefe_mandant(state, company_id)      # auch dieser load wird geprueft
        state.status = SessionStatus.FEHLER
        store.save(state)
        return {"status": "fehler_fortsetzbar",
                "payload": {"grund": "verarbeitung_fehlgeschlagen"}}

    pflicht = package.required_fields()
    erfasst = sum(1 for s in pflicht
                  if conf.statuses[s.name] is FieldStatus.GUELTIG)
    if decision.ergebnis is Ergebnis.ABGEBROCHEN_OHNE_IDENTITAET:
        state.status = SessionStatus.ABGEBROCHEN_OHNE_IDENTITAET
        resp = {"status": "abgebrochen_ohne_identitaet",
                "payload": {"grund": GRUND_IDENTITAET_UNGEKLAERT,
                            "feld": decision.next_field,
                            "pflicht_erfasst": erfasst,
                            "pflicht_gesamt": len(pflicht)}}
    elif decision.ergebnis is Ergebnis.FERTIG:
        state.status = SessionStatus.FERTIG
        payload = _profil(state, conf, package)
        payload["abschluss_text"] = antwortetext
        payload["pflicht_erfasst"] = erfasst
        payload["pflicht_gesamt"] = len(pflicht)
        resp = {"status": "fertig", "payload": payload}
    else:
        state.status = SessionStatus.WARTET
        resp = {"status": "frage",
                "payload": {"naechste_frage": antwortetext,
                            "feld": decision.next_field,
                            "pflicht_erfasst": erfasst,
                            "pflicht_gesamt": len(pflicht)}}

    state.antworten[message_id] = resp
    store.save(state)
    return resp
