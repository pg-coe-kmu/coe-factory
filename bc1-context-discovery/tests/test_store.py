import pytest

from bc1_core.store import InMemoryStateStore
from tests.store_contract import StoreVertrag


class TestInMemoryStore(StoreVertrag):
    @pytest.fixture
    def store(self):
        return InMemoryStateStore()
