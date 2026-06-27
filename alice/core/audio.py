import io
import queue
import threading

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from loguru import logger

SAMPLE_RATE = 16000
BLOCK_DURATION = 0.5  # seconds per audio block
SILENCE_THRESHOLD = 0.01
SILENCE_BLOCKS = 6  # 3秒間無音で発話終了とみなす


class AudioTranscriber:
    def __init__(self, model_size: str = "small", device: str = "cuda", compute_type: str = "float16"):
        logger.info(f"Whisperモデル '{model_size}' をロード中...")
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self._audio_queue: queue.Queue = queue.Queue()
        self._running = False
        logger.info("Whisperモデルのロード完了")

    def _is_speech(self, block: np.ndarray) -> bool:
        return float(np.abs(block).mean()) > SILENCE_THRESHOLD

    @staticmethod
    def has_input_device() -> bool:
        try:
            devices = sd.query_devices()
            return any(d["max_input_channels"] > 0 for d in devices)
        except Exception:
            return False

    def _record_utterance(self) -> np.ndarray | None:
        frames = []
        silence_count = 0
        speaking = False

        try:
            stream_ctx = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                        blocksize=int(SAMPLE_RATE * BLOCK_DURATION))
        except Exception as e:
            logger.error(f"マイクを開けません: {e}")
            return None

        with stream_ctx as stream:
            while True:
                block, _ = stream.read(int(SAMPLE_RATE * BLOCK_DURATION))
                block = block.flatten()

                if self._is_speech(block):
                    speaking = True
                    silence_count = 0
                    frames.append(block)
                elif speaking:
                    silence_count += 1
                    frames.append(block)
                    if silence_count >= SILENCE_BLOCKS:
                        break

        if not frames:
            return None
        return np.concatenate(frames)

    def listen_once(self) -> str:
        logger.debug("発話を待機中...")
        audio = self._record_utterance()
        if audio is None:
            return ""
        return self._transcribe(audio)

    def _transcribe(self, audio: np.ndarray) -> str:
        audio_bytes = io.BytesIO()
        import soundfile as sf
        sf.write(audio_bytes, audio, SAMPLE_RATE, format="WAV")
        audio_bytes.seek(0)

        segments, info = self._model.transcribe(audio_bytes, language="ja", beam_size=5)
        text = "".join(seg.text for seg in segments).strip()
        logger.info(f"認識結果: {text}")
        return text

    def start_continuous(self, callback) -> None:
        self._running = True
        thread = threading.Thread(target=self._continuous_loop, args=(callback,), daemon=True)
        thread.start()
        logger.info("連続音声認識を開始しました")

    def _continuous_loop(self, callback) -> None:
        import time
        while self._running:
            if not self.has_input_device():
                time.sleep(5)
                continue
            text = self.listen_once()
            if text:
                callback(text)

    def stop(self) -> None:
        self._running = False
