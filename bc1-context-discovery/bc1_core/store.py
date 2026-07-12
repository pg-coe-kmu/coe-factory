from __future__ import annotations
import copy
from abc import ABC, abstractmethod
from bc1_core.types import SessionState

class StaleStateError(Exception):
    pass

class StateStore(ABC):
    @abstractmethod
    def load(self, session_id: str) -> SessionState | None: ...
    @abstractmethod
    def save(self, state: SessionState) -> None: ...

class InMemoryStateStore(StateStore):
    def __init__(self) -> None:
        self._data: dict[str, SessionState] = {}

    def load(self, session_id: str) -> SessionState | None:
        st = self._data.get(session_id)
        return copy.deepcopy(st) if st is not None else None

    def save(self, state: SessionState) -> None:
        existing = self._data.get(state.session_id)
        if existing is not None and existing.version != state.version:
            raise StaleStateError(
                f"stale write for {state.session_id}: "
                f"have {existing.version}, got {state.version}"
            )
        state.version += 1
        self._data[state.session_id] = copy.deepcopy(state)
