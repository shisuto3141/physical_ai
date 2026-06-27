import asyncio
import io
import queue
import threading

import miniaudio
import numpy as np
import sounddevice as sd
from loguru import logger

VOICE = "ja-JP-NanamiNeural"
# 文末で音声を区切る文字（読み上げの自然な間を作る）
_SENTENCE_ENDS = frozenset("。！？\n")


def has_output_device() -> bool:
    try:
        return any(d["max_output_channels"] > 0 for d in sd.query_devices())
    except Exception:
        return False


class TTSEngine:
    """edge-tts による日本語音声合成エンジン。
    speak() はノンブロッキング（キューに積んで別スレッドで再生）。
    """

    def __init__(self, voice: str = VOICE):
        import edge_tts  # noqa: F401 — インポート可否チェック
        self.voice = voice
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._worker = threading.Thread(target=self._run_loop, daemon=True)
        self._worker.start()

    def speak(self, text: str) -> None:
        text = text.strip()
        if text:
            self._queue.put(text)

    def clear(self) -> None:
        """キューをクリアして現在の再生を即停止（割り込み対応）。"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        sd.stop()

    def stop(self) -> None:
        sd.stop()
        self._queue.put(None)

    # ------------------------------------------------------------------ internal

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            text = self._queue.get()
            if text is None:
                break
            loop.run_until_complete(self._synthesize_and_play(text))
        loop.close()

    async def _synthesize_and_play(self, text: str) -> None:
        import edge_tts
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            if not chunks:
                return

            decoded = miniaudio.decode(
                b"".join(chunks),
                output_format=miniaudio.SampleFormat.FLOAT32,
            )
            arr = np.frombuffer(decoded.samples, dtype=np.float32)
            if decoded.nchannels > 1:
                arr = arr.reshape(-1, decoded.nchannels)

            sd.play(arr, samplerate=decoded.sample_rate)
            sd.wait()
        except Exception as e:
            logger.warning(f"TTS再生失敗: {e}")
