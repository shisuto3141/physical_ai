from typing import Generator

import requests
from loguru import logger

OLLAMA_URL = "http://localhost:11434/api/chat"
TEXT_MODEL = "gemma3:12b"

SYSTEM_PROMPT = """あなたはAliceという名前の物理AIアシスタントです。
カメラで周囲の環境を観察し、マイクで会話相手の声を聞いてリアルタイムに応答します。
会話相手のプロフィールと過去の会話を覚えており、自然で親しみやすい日本語で話します。
応答は簡潔に、2〜3文程度でまとめてください。"""


class LLMClient:
    def __init__(self, model: str = TEXT_MODEL, base_url: str = OLLAMA_URL):
        self.model = model
        self.base_url = base_url
        self._history: list[dict] = []

    def reset_history(self) -> None:
        self._history = []

    def chat(
        self,
        user_message: str,
        vision_context: str = "",
        user_profile: str = "",
        stream: bool = True,
    ) -> Generator[str, None, None]:
        system = SYSTEM_PROMPT
        if user_profile:
            system += f"\n\n【会話相手の情報】\n{user_profile}"
        if vision_context:
            system += f"\n\n【現在の視覚情報】\n{vision_context}"

        messages = [{"role": "system", "content": system}]
        messages.extend(self._history)
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }

        try:
            with requests.post(self.base_url, json=payload, stream=stream, timeout=60) as resp:
                resp.raise_for_status()
                full_response = ""
                for line in resp.iter_lines():
                    if not line:
                        continue
                    import json
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    full_response += token
                    yield token
                    if chunk.get("done"):
                        break

            self._history.append({"role": "user", "content": user_message})
            self._history.append({"role": "assistant", "content": full_response})
            if len(self._history) > 20:
                self._history = self._history[-20:]

        except requests.RequestException as e:
            logger.error(f"Ollama APIエラー: {e}")
            yield "すみません、応答の生成中にエラーが発生しました。"

    def chat_sync(self, user_message: str, **kwargs) -> str:
        return "".join(self.chat(user_message, **kwargs))
