import asyncio
import threading

import numpy as np

from backend.backends.mlx_backend import MLXTTSBackend


def test_mlx_tts_load_and_generate_use_same_worker_thread(monkeypatch):
    backend = MLXTTSBackend()

    class FakeResult:
        audio = np.array([0.0], dtype=np.float32)
        sample_rate = 24000

    class FakeModel:
        def __init__(self, load_thread_id: int):
            self.load_thread_id = load_thread_id

        def generate(self, text, lang_code="auto"):
            assert threading.get_ident() == self.load_thread_id
            yield FakeResult()

    def fake_load_model_sync(model_size: str):
        backend.model = FakeModel(threading.get_ident())
        backend._current_model_size = model_size
        backend.model_size = model_size

    monkeypatch.setattr(backend, "_load_model_sync", fake_load_model_sync)

    async def run():
        await backend.load_model_async("1.7B")
        audio, sample_rate = await backend.generate("Hello", {}, language="en")
        return audio, sample_rate

    audio, sample_rate = asyncio.run(run())

    assert sample_rate == 24000
    assert audio.tolist() == [0.0]
