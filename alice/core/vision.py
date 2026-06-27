import base64
import threading
import time
from io import BytesIO

import cv2
import requests
from loguru import logger
from PIL import Image

OLLAMA_URL = "http://localhost:11434/api/generate"
VISION_MODEL = "llava:7b"


class VisionCapture:
    def __init__(self, device_index: int = 0, capture_interval: float = 5.0):
        self.device_index = device_index
        self.capture_interval = capture_interval
        self._cap: cv2.VideoCapture | None = None
        self._latest_description: str = ""
        self._lock = threading.Lock()
        self._running = False

    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            logger.error(f"カメラ {self.device_index} を開けません")
            return False
        logger.info(f"カメラ {self.device_index} を開きました")
        return True

    def close(self) -> None:
        self._running = False
        if self._cap:
            self._cap.release()

    def _frame_to_base64(self, frame) -> str:
        img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def describe_frame(self, prompt: str = "この画像に何が見えますか？簡潔に日本語で答えてください。") -> str:
        if not self._cap or not self._cap.isOpened():
            return ""
        ret, frame = self._cap.read()
        if not ret:
            logger.warning("フレームの取得に失敗しました")
            return ""

        image_b64 = self._frame_to_base64(frame)
        payload = {
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
        }
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=30)
            resp.raise_for_status()
            description = resp.json().get("response", "")
            with self._lock:
                self._latest_description = description
            return description
        except requests.RequestException as e:
            logger.error(f"llava API エラー: {e}")
            return ""

    def get_latest_description(self) -> str:
        with self._lock:
            return self._latest_description

    def start_background_capture(self) -> None:
        self._running = True
        thread = threading.Thread(target=self._capture_loop, daemon=True)
        thread.start()
        logger.info("バックグラウンド映像解析を開始しました")

    def _capture_loop(self) -> None:
        while self._running:
            self.describe_frame()
            time.sleep(self.capture_interval)
