import json
from typing import Generator

import requests
from loguru import logger

OLLAMA_URL = "http://localhost:11434/api/chat"
TEXT_MODEL = "gemma3:12b"

SYSTEM_PROMPT = """あなたはAliceという名前の物理AIアシスタントです。
カメラで周囲の環境を観察し、マイクで会話相手の声を聞いてリアルタイムに応答します。
会話相手のプロフィールと過去の会話を覚えており、自然で親しみやすい日本語で話します。
応答は簡潔に、2〜3文程度でまとめてください。"""

SEARCH_JUDGE_PROMPT = """以下のユーザーの発言に回答するためにWeb検索が必要か判断してください。
必要な場合は、検索の種類と検索クエリを以下の形式で返してください：
- ニュース・最新情報・時事・速報の場合: [news] 検索クエリ
- 一般知識・技術情報・人物・場所などの場合: [web] 検索クエリ
不要な場合は「不要」とだけ返してください。
それ以外の文章は一切出力しないでください。

ユーザーの発言: {message}"""


class LLMClient:
    def __init__(self, model: str = TEXT_MODEL, base_url: str = OLLAMA_URL):
        self.model = model
        self.base_url = base_url
        self._history: list[dict] = []

    def reset_history(self) -> None:
        self._history = []

    def _quick_call(self, prompt: str, timeout: int = 20) -> str:
        """会話履歴に影響しない単発LLM呼び出し。"""
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        try:
            resp = requests.post(self.base_url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.error(f"クイック呼び出しエラー: {e}")
            return ""

    def decide_search_query(self, user_message: str) -> tuple[str, str]:
        """(検索クエリ, 検索タイプ) を返す。不要なら ("", "")。
        検索タイプは "web" または "news"。
        """
        result = self._quick_call(SEARCH_JUDGE_PROMPT.format(message=user_message))
        if not result or "不要" in result:
            return "", ""
        if result.startswith("[news]"):
            query, search_type = result[6:].strip(), "news"
        elif result.startswith("[web]"):
            query, search_type = result[5:].strip(), "web"
        else:
            query, search_type = result.strip(), "web"
        logger.info(f"検索判断: [{search_type}] {query}")
        return query, search_type

    def chat(
        self,
        user_message: str,
        vision_context: str = "",
        user_profile: str = "",
        web_context: str = "",
        stream: bool = True,
    ) -> Generator[str, None, None]:
        system = SYSTEM_PROMPT
        if user_profile:
            system += f"\n\n【会話相手の情報】\n{user_profile}"
        if vision_context:
            system += f"\n\n【現在の視覚情報】\n{vision_context}"
        if web_context:
            system += f"\n\n【Web検索結果（最新情報として参照すること）】\n{web_context}"

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
