import asyncio
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DB_URL = os.environ.get("LYNXAUTH_TEST_DATABASE_URL", "postgresql://lynxauth:lynxauth@127.0.0.1:55432/lynxauth")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_embedding_store_persists_and_matches_across_instances():
    module = load_module("embedding_store_module", ROOT / "inference-worker/services/embedding_store.py")

    async def scenario() -> None:
        store = module.EmbeddingStore(database_url=TEST_DB_URL, threshold=0.6)
        await store.initialize(reset=True)

        enrolled_embedding = [0.25] * 512
        await store.store("usr_001", enrolled_embedding)

        fresh_store = module.EmbeddingStore(database_url=TEST_DB_URL, threshold=0.6)
        await fresh_store.initialize()
        user_id, confidence = await fresh_store.match(enrolled_embedding)

        assert user_id == "usr_001"
        assert confidence is not None
        assert confidence >= 0.999

    asyncio.run(scenario())
