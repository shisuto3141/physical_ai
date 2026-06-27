import sys
import threading

from loguru import logger

from core.audio import AudioTranscriber
from core.llm import LLMClient
from core.vision import VisionCapture
from memory.db import MemoryDB

logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")

CURRENT_USER = "ゲスト"


def main() -> None:
    logger.info("Alice を起動しています...")

    db = MemoryDB()
    llm = LLMClient()
    vision = VisionCapture(device_index=0, capture_interval=5.0)
    audio = AudioTranscriber(model_size="small", device="cuda", compute_type="float16")
    response_lock = threading.Lock()

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

            print("Alice: ", end="", flush=True)
            full_response = ""
            for token in llm.chat(text, vision_context=vision_ctx, user_profile=profile_text):
                print(token, end="", flush=True)
                full_response += token
            print()

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
        audio.stop()
        vision.close()
        db.close()


if __name__ == "__main__":
    main()
