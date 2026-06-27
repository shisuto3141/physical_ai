import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from loguru import logger

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AliceBot/1.0)"}
_SNIPPET_CHARS = 400
_PAGE_CHARS = 2500
_FETCH_TIMEOUT = 8


def _fetch_page_text(url: str) -> str:
    """URLからメイン本文テキストを抽出する。失敗時は空文字。"""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_FETCH_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
        return "\n".join(lines)[:_PAGE_CHARS]
    except Exception as e:
        logger.debug(f"ページ取得失敗 {url}: {e}")
        return ""


def search_web(query: str, search_type: str = "web") -> str:
    """
    query       : 検索クエリ
    search_type : "web" または "news"
    戻り値      : LLMに渡す文字列。失敗時は空文字。
    """
    if search_type == "news":
        return _search_news(query)
    return _search_text(query)


def _search_text(query: str) -> str:
    max_results = 3
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        logger.warning(f"Web検索失敗: {e}")
        return ""

    if not results:
        return ""

    parts = []
    for i, r in enumerate(results):
        title = r.get("title", "")
        snippet = (r.get("body") or "")[:_SNIPPET_CHARS]
        url = r.get("href", "")

        # 上位1件はページ本文も取得して内容を補強
        detail = ""
        if i == 0:
            detail = _fetch_page_text(url)

        body = detail if detail else snippet
        parts.append(f"■ {title}\n{body}\n出典: {url}")

    logger.info(f"Web検索完了: {len(results)} 件取得")
    return "\n\n".join(parts)


def _search_news(query: str) -> str:
    max_results = 5
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
    except Exception as e:
        logger.warning(f"ニュース検索失敗: {e}")
        return ""

    if not results:
        return ""

    parts = []
    for i, r in enumerate(results):
        title = r.get("title", "")
        snippet = (r.get("body") or "")[:_SNIPPET_CHARS]
        url = r.get("url", "")
        date = r.get("date", "")
        source = r.get("source", "")

        # 上位2件はページ本文も取得
        detail = ""
        if i < 2:
            detail = _fetch_page_text(url)

        body = detail if detail else snippet
        parts.append(f"■ {title}（{source} / {date}）\n{body}\n出典: {url}")

    logger.info(f"ニュース検索完了: {len(results)} 件取得")
    return "\n\n".join(parts)
