"""requests + BeautifulSoup4로 웹 페이지를 가져와 텍스트·링크를 추출한다.

Stage 2의 Groq tool-calling 루프에서 browser_tool 함수로 노출된다.
모든 함수는 {"ok": bool, "data": ..., "error": str} 형식을 반환하고 예외를 던지지 않는다.
"""
import logging
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
_TIMEOUT = 15
_MAX_TEXT = 8000  # 반환 텍스트 최대 길이


def _normalize_url(url: str) -> str:
    """네이버 블로그 PC URL → 모바일 URL로 변환한다.

    blog.naver.com/xxx/yyy 는 iframe 구조라 본문이 비어 있다.
    m.blog.naver.com/xxx/yyy 는 단일 페이지로 본문 전체가 담긴다.
    """
    if "blog.naver.com/" in url and "m.blog.naver.com" not in url:
        url = url.replace("://blog.naver.com/", "://m.blog.naver.com/")
    return url

# 모듈 레벨 세션 상태 — open_url() 이후 다른 함수들이 공유한다.
_state: dict[str, Any] = {"soup": None, "url": ""}


def open_url(url: str) -> dict[str, Any]:
    """URL 페이지를 열고 내부 세션에 저장한다.

    네이버 블로그 PC URL은 모바일 URL로 자동 변환해 본문을 가져온다.

    Returns:
        {"ok": True, "data": url, "error": ""} 또는 {"ok": False, "data": None, "error": 메시지}
    """
    url = _normalize_url(url)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        _state["soup"] = BeautifulSoup(resp.text, "html.parser")
        _state["url"] = url
        return {"ok": True, "data": url, "error": ""}
    except Exception as exc:
        logger.warning(f"browser_tool.open_url 실패 ({url}): {exc}")
        _state["soup"] = None
        _state["url"] = ""
        return {"ok": False, "data": None, "error": str(exc)}


def get_text(selector: str = "") -> dict[str, Any]:
    """현재 열린 페이지에서 CSS 선택자에 해당하는 요소의 텍스트를 반환한다.

    selector가 비어 있으면 get_all_text()와 동일하게 동작한다.
    """
    if not selector:
        return get_all_text()
    soup: BeautifulSoup | None = _state.get("soup")
    if soup is None:
        return {"ok": False, "data": None, "error": "열린 페이지가 없습니다. open_url()을 먼저 호출하세요."}
    try:
        elem = soup.select_one(selector)
        if elem is None:
            return {"ok": False, "data": None, "error": f"선택자 '{selector}'에 해당하는 요소가 없습니다."}
        text = elem.get_text(separator=" ", strip=True)[:_MAX_TEXT]
        return {"ok": True, "data": text, "error": ""}
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def get_all_text() -> dict[str, Any]:
    """현재 열린 페이지의 가시 텍스트(본문)를 반환한다.

    script/style/nav/footer/header 태그는 제거 후 추출한다.
    """
    soup: BeautifulSoup | None = _state.get("soup")
    if soup is None:
        return {"ok": False, "data": None, "error": "열린 페이지가 없습니다. open_url()을 먼저 호출하세요."}
    try:
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)[:_MAX_TEXT]
        return {"ok": True, "data": text, "error": ""}
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}


def get_links(selector: str = "") -> dict[str, Any]:
    """현재 열린 페이지의 링크 목록을 반환한다.

    Returns:
        data: [{"text": str, "href": str}, ...]
    """
    soup: BeautifulSoup | None = _state.get("soup")
    if soup is None:
        return {"ok": False, "data": None, "error": "열린 페이지가 없습니다. open_url()을 먼저 호출하세요."}
    try:
        container = soup.select_one(selector) if selector else soup
        if container is None:
            return {"ok": False, "data": [], "error": f"선택자 '{selector}'에 해당하는 요소가 없습니다."}
        links = [
            {"text": a.get_text(strip=True), "href": a.get("href", "")}
            for a in container.find_all("a", href=True)
        ]
        return {"ok": True, "data": links, "error": ""}
    except Exception as exc:
        return {"ok": False, "data": None, "error": str(exc)}
