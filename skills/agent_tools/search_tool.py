"""DuckDuckGo(ddgs)를 사용하는 웹 검색 도구.

Stage 2의 Groq tool-calling 루프에서 search_tool 함수로 노출된다.
ddgs 패키지는 requests 레벨에서 이미 requirements.txt에 있다.
모든 함수는 {"ok": bool, "data": ..., "error": str} 형식을 반환하고 예외를 던지지 않는다.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

_MAX_RESULTS = 5


def search(query: str, max_results: int = _MAX_RESULTS) -> dict[str, Any]:
    """DuckDuckGo로 query를 검색해 결과 목록을 반환한다.

    Args:
        query: 검색어
        max_results: 최대 결과 수 (기본 5)

    Returns:
        {"ok": True, "data": [{"title", "url", "summary"}, ...], "error": ""}
        실패 시 {"ok": False, "data": [], "error": 메시지} — 예외를 던지지 않는다.
    """
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "summary": r.get("body", ""),
                })
        return {"ok": True, "data": results, "error": ""}
    except Exception as exc:
        logger.warning(f"search_tool.search 실패 ({query!r}): {exc}")
        return {"ok": False, "data": [], "error": str(exc)}
