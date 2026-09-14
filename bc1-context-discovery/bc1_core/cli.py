from __future__ import annotations
from bc1_core.package import UseCasePackage, TOY_PROZESS
from bc1_core.store import InMemoryStateStore
from bc1_core.llm import FakeLLM, ExtractionCandidate
from bc1_core.core import process_turn

DEMO_MANDANT = "11111111-1111-1111-1111-111111111111"

def run_scripted(package: UseCasePackage, llm: FakeLLM,
                 script: list[tuple[str, str]], session_id: str = "demo",
                 company_id: str = DEMO_MANDANT) -> list[dict]:
    store = InMemoryStateStore()
    out: list[dict] = []
    for message_id, message in script:
        out.append(process_turn(store, llm, package, session_id, message_id, message,
                                company_id=company_id))
    return out

def main() -> None:
    llm = FakeLLM({
        "Freigabe": [ExtractionCandidate("prozess_name", "Freigabe")],
        "Antrag": [ExtractionCandidate("ausloeser", "Antrag geht ein")],
        "100 mal/Jahr": [ExtractionCandidate("haeufigkeit", "100 mal/Jahr")],
    })
    script = [("m1", "Freigabe"), ("m2", "Antrag"), ("m3", "100 mal/Jahr")]
    for resp in run_scripted(TOY_PROZESS, llm, script):
        print(resp)

if __name__ == "__main__":
    main()
