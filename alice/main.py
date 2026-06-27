import sys
import threading
from typing import Generator

from loguru import logger

from core.audio import AudioTranscriber
from core.llm import LLMClient
from core.search import search_web
from core.tts import TTSEngine, has_output_device
from core.vision import VisionCapture
from memory.db import MemoryDB

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")

CURRENT_USER = "ゲスト"
_SENTENCE_ENDS = frozenset("。！？\n")


def _stream_with_tts(token_gen: Generator[str, None, None], tts: TTSEngine | None) -> str:
    """LLMトークンを画面表示しながら、文末単位でTTSキューに送る。"""
    buffer = ""
    full = ""
    for token in token_gen:
        print(token, end="", flush=True)
        full += token
        if tts:
            buffer += token
            if _SENTENCE_ENDS & set(buffer):
                cut = max((buffer.rfind(c) for c in _SENTENCE_ENDS if c in buffer), default=-1)
                if cut >= 0:
                    sentence = buffer[:cut + 1].strip()
                    buffer = buffer[cut + 1:]
                    if sentence:
                        tts.speak(sentence)
    if tts and buffer.strip():
        tts.speak(buffer.strip())
    print()
    return full


def main() -> None:
    logger.info("Alice を起動しています...")

    db = MemoryDB()
    llm = LLMClient()
    vision = VisionCapture(device_index=0, capture_interval=5.0)
    audio = AudioTranscriber(model_size="small", device="cuda", compute_type="float16")
    response_lock = threading.Lock()

    tts: TTSEngine | None
    if has_output_device():
        tts = TTSEngine()
        logger.info("音声出力: 有効 (ja-JP-NanamiNeural)")
    else:
        tts = None
        logger.warning("音声出力デバイスが検出されません。テキストのみで動作します")

    profile_id = db.upsert_profile(CURRENT_USER)

    if vision.open():
        vision.start_background_capture()
    else:
        logger.warning("カメラなしで起動します")

    if not AudioTranscriber.has_input_device():
        logger.warning("マイクが検出されません。音声入力なしで起動します")

    logger.info("Alice の起動完了。話しかけるかテキストを入力してください。(Ctrl+C で終了)")

    def _fix_surrogates(text: str) -> str:
        return text.encode("utf-8", "surrogateescape").decode("utf-8", "replace")

    def handle_input(text: str) -> None:
        text = _fix_surrogates(text)
        if not text.strip():
            return

        with response_lock:
            logger.info(f"[ユーザー] {text}")
            db.save_turn(profile_id, "user", text)

            profile_text = db.format_profile(CURRENT_USER)
            vision_ctx = vision.get_latest_description()

            search_query, search_type = llm.decide_search_query(text)
            web_ctx = search_web(search_query, search_type) if search_query else ""

            print("Alice: ", end="", flush=True)
            full_response = _stream_with_tts(
                llm.chat(
                    text,
                    vision_context=vision_ctx,
                    user_profile=profile_text,
                    web_context=web_ctx,
                ),
                tts,
            )

            db.save_turn(profile_id, "assistant", full_response)

    try:
        import io
        stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
        audio.start_continuous(handle_input)
        while True:
            try:
                print("You: ", end="", flush=True)
                text = stdin.readline().rstrip("\n")
            except EOFError:
                break
            if text == "":
                break
            handle_input(text)
    except KeyboardInterrupt:
        logger.info("終了します...")
    finally:
        if tts:
            tts.stop()
        audio.stop()
        vision.close()
        db.close()


if __name__ == "__main__":
    main()
