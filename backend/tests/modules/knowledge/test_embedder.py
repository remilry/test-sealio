"""The embedding model is built once, even when the first fill's groups all ask for it at once."""

import threading
import time

import pytest

from app.modules.knowledge import embedding


def test_concurrent_first_uses_build_the_model_once(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[object] = []

    class SlowToLoad(embedding.HashEmbedder):
        def __init__(self) -> None:
            time.sleep(0.05)  # loading a real model takes seconds
            built.append(self)

    monkeypatch.setattr(embedding, "HashEmbedder", SlowToLoad)
    embedding._embedder.cache_clear()  # pyright: ignore[reportPrivateUsage]
    try:
        got: list[object] = []
        threads = [
            threading.Thread(target=lambda: got.append(embedding.get_embedder())) for _ in range(10)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        embedding._embedder.cache_clear()  # pyright: ignore[reportPrivateUsage]

    assert len(built) == 1
    assert all(e is built[0] for e in got)
