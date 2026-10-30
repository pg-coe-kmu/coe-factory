from __future__ import annotations
import logging
import re
from bc1_core.types import Candidate, FieldStatus, FieldValue, SessionState
from bc1_core.package import UseCasePackage, FieldSpec
from bc1_core.feldtypen import Feldtyp, ist_nackte_zahl, vergleichsschluessel
from bc1_core.llm import ExtractionCandidate, LLMClient
from bc1_core.pii import ersetze_pii
from bc1_core.protokoll import aktuelle_korrelation, ki_aufruf

log = logging.getLogger("bc1.kern")

def status_fuer(spec: FieldSpec, value: str) -> FieldStatus:
    # Policy: ein werfender Validator macht den Wert UNGUELTIG, bricht aber
    # nie den Turn ab — sonst ginge die Nachricht nach Raw-First-Save (Task 8)
    # beim Idempotenz-Replay dauerhaft verloren.
    pruefer = spec.validator if spec.validator is not None else spec.typ.validator
    try:
        gueltig = pruefer(value)
    except Exception:
        return FieldStatus.UNGUELTIG
    return FieldStatus.GUELTIG if gueltig else FieldStatus.UNGUELTIG

def _nennt_nur_option(message: str, typ: Feldtyp, option: str) -> bool:
    if "?" in message:
        return False
    schluessel = vergleichsschluessel(message)
    def nennt(opt: str) -> bool:
        woerter = [opt, *(name for o, name in typ.namen if o == opt)]
        return any(re.search(rf"(?<!\w){re.escape(vergleichsschluessel(w))}(?!\w)", schluessel)
                   for w in woerter)
    return nennt(option) and not any(nennt(o) for o in typ.optionen if o != option)

def _merke_kandidat(fv: FieldValue, wert: str, quelle: str) -> None:
    # Dedup nach Wert: die erste Quelle eines Werts bleibt maßgeblich.
    if all(k.value != wert for k in fv.candidates):
        fv.candidates.append(Candidate(wert, quelle))

def extract_and_merge(state: SessionState, message: str, message_id: str,
                      package: UseCasePackage, llm: LLMClient, *,
                      gefragt: FieldSpec | None = None) -> None:
    # Kurzantwort auf die gestellte Frage: der rohe Wert geht ohne KI in das
    # gefragte Feld; Filter, Normalisierung und Zusammenführung laufen unten
    # wie sonst. Ohne Kurzform (oder ohne Treffer) fragt der Extraktor die KI.
    wert_roh = None
    if gefragt is not None and gefragt.typ.kurzform is not None:
        wert_roh = gefragt.typ.kurzform(message)
    if wert_roh is not None:
        # Nur der Feldname, nie der Wert (B7 Teil 2).
        log.info("kurzantwort_direkt korrelation=%s feld=%s",
                 aktuelle_korrelation.get(), gefragt.name)
        kandidaten = [ExtractionCandidate(gefragt.name, wert_roh)]
    else:
        with ki_aufruf("extraktion"):
            kandidaten = llm.extract(message, package, state)
    for cand in kandidaten:
        spec = package.field(cand.field_name)
        if spec is None:
            continue
        # Spec 2 „Fester Schutz“: eine KI-Zahl ohne Zeitraum bzw. Einheit gilt nicht
        # (Nachfrage); die nackte Zahl gilt nur, wenn die Person sie selbst schreibt.
        if (wert_roh is None and spec.typ.nackte_zahl_nur_von_person
                and ist_nackte_zahl(cand.value)):
            continue
        # Normalisierung VOR dem Merge: Vergleiche, Klärung und Kandidaten
        # arbeiten auf dem normalisierten Wert; gespeichert wird er auch.
        # Davor der PII-Filter (B2): der Anbieter sah nur Platzhalter, kann aber
        # Klartext halluzinieren oder echoen — auch der darf nicht in den State.
        wert = spec.typ.normalisiere(ersetze_pii(cand.value))
        # Spec 2 „Feste Sperren“ (a): ein KI-Wert für ein Identitätsfeld gilt nur, wenn
        # die Nachricht die Option selbst nennt.
        if (wert_roh is None and spec.identitaetskritisch
                and wert in spec.typ.optionen
                and not _nennt_nur_option(message, spec.typ, wert)):
            continue
        fv = state.values.get(cand.field_name)
        if fv is None or fv.value is None:
            state.values[cand.field_name] = FieldValue(
                value=wert,
                status=status_fuer(spec, wert),
                source_message_id=message_id,
                # Nachfrage-Zähler gehört dem Dialog (Task 7) — beim Befüllen
                # eines angefragten Felds nicht zurücksetzen (Cap-Politik).
                attempts=fv.attempts if fv is not None else 0,
            )
        elif fv.value == wert:
            # Erneute Nennung desselben Werts: für UNKLAR ist das die Klärung
            # (Spec B4 „Nutzer klären lassen"), sonst No-op.
            if fv.status is FieldStatus.UNKLAR:
                fv.status = status_fuer(spec, wert)
        elif (fv.status is FieldStatus.UNKLAR
              and any(k.value == wert for k in fv.candidates)):
            # Klärung zugunsten eines Kandidaten (Spec B4): Tausch — der alte
            # Wert bleibt mit seiner Quelle als Kandidat, nichts geht verloren.
            fv.candidates = [k for k in fv.candidates if k.value != wert]
            _merke_kandidat(fv, fv.value, fv.source_message_id)
            fv.value = wert
            fv.status = status_fuer(spec, wert)
            fv.source_message_id = message_id
        elif fv.status is FieldStatus.UNGUELTIG:
            # Korrektur: UNGUELTIG ist nicht bestätigt → ersetzen, alter Wert
            # bleibt als Kandidat — mit der Quelle, aus der er stammte.
            _merke_kandidat(fv, fv.value, fv.source_message_id)
            fv.value = wert
            fv.status = status_fuer(spec, wert)
            fv.source_message_id = message_id
        else:
            _merke_kandidat(fv, wert, message_id)
            fv.status = FieldStatus.UNKLAR
        # B7 Teil 2: nur der Feldname, nie der Wert. Bewusst hier und nicht in
        # status_fuer — den ruft auch der Sweep des Writers auf.
        status = state.values[cand.field_name].status
        if status in (FieldStatus.UNGUELTIG, FieldStatus.UNKLAR):
            log.info("validierung korrelation=%s feld=%s ergebnis=%s",
                     aktuelle_korrelation.get(), spec.name, status.value)
