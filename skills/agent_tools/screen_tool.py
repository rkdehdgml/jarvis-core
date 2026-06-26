"""pyautogui + pytesseract 기반 PC 화면 인식·제어 도구.

skill_screen_agent.py의 Groq/Ollama 루프에서 tool로 노출된다.
모든 함수는 {"ok": bool, "data": ..., "error": str} 형식을 반환하고 예외를 던지지 않는다.

사전 요구사항:
  1. pip install pyautogui pytesseract Pillow
  2. Tesseract OCR 설치: https://github.com/UB-Mannheim/tesseract/wiki
     (기본 경로: C:\\Program Files\\Tesseract-OCR\\tesseract.exe)
  3. Tesseract 설치 시 Korean language pack 체크 필수
  4. .env에 TESSERACT_PATH 지정 (기본 경로와 다를 경우)
"""
import logging
import os
import re
import subprocess
import time
import webbrowser
from typing import Any

logger = logging.getLogger(__name__)

_TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)
_MAX_ELEMENTS = 50   # 한 화면에서 반환할 최대 요소 수
_OCR_CONF_MIN = 40   # 이 값 미만의 OCR 신뢰도는 버림


def _setup_tesseract() -> None:
    """pytesseract에 Tesseract 바이너리 경로를 알려준다."""
    try:
        import pytesseract
        if os.path.exists(_TESSERACT_PATH):
            pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH
    except ImportError:
        pass


# ── 화면 인식 ─────────────────────────────────────────────────────────────────

def screenshot_read() -> dict[str, Any]:
    """화면을 캡처하고 OCR로 번호가 매겨진 텍스트 요소 목록을 반환한다.

    각 요소: {"id": int, "text": str, "x": int, "y": int}
    summary: Groq/Ollama에 전달할 요소 목록 문자열
    """
    try:
        import pyautogui
        import pytesseract
        from PIL import Image  # noqa: F401 — pytesseract 내부 의존

        _setup_tesseract()

        screenshot = pyautogui.screenshot()

        data = pytesseract.image_to_data(
            screenshot,
            lang="kor+eng",
            output_type=pytesseract.Output.DICT,
        )

        # 줄(block+par+line) 단위로 그룹화
        line_map: dict[tuple, list[int]] = {}
        for i in range(len(data["text"])):
            txt = (data["text"][i] or "").strip()
            conf = int(data["conf"][i])
            if not txt or conf < _OCR_CONF_MIN:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            line_map.setdefault(key, []).append(i)

        elements: list[dict] = []
        for indices in line_map.values():
            words = [data["text"][i] for i in indices]
            line_text = " ".join(words).strip()
            if len(line_text) < 2:
                continue

            left   = min(data["left"][i] for i in indices)
            top    = min(data["top"][i] for i in indices)
            right  = max(data["left"][i] + data["width"][i] for i in indices)
            bottom = max(data["top"][i] + data["height"][i] for i in indices)
            cx = (left + right) // 2
            cy = (top + bottom) // 2

            elements.append({
                "id": len(elements) + 1,
                "text": line_text,
                "x": cx,
                "y": cy,
            })

        elements = elements[:_MAX_ELEMENTS]

        summary = "\n".join(
            f'[{e["id"]}] "{e["text"]}" at ({e["x"]}, {e["y"]})'
            for e in elements
        )
        sz = list(pyautogui.size())

        return {
            "ok": True,
            "data": {
                "elements": elements,
                "summary": summary,
                "count": len(elements),
                "screen_size": sz,
            },
            "error": "",
        }
    except ImportError as exc:
        return {
            "ok": False, "data": None,
            "error": (
                f"필수 패키지 미설치: {exc}. "
                "'pip install pyautogui pytesseract Pillow' 를 실행하고 "
                "Tesseract OCR 바이너리도 설치해주세요."
            ),
        }
    except Exception as exc:
        logger.warning(f"screenshot_read 실패: {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


# ── 마우스 제어 ───────────────────────────────────────────────────────────────

def mouse_click(x: int, y: int, button: str = "left") -> dict[str, Any]:
    """화면 좌표를 클릭한다.

    Args:
        x, y: 클릭 좌표 (screenshot_read 결과의 x, y 값 사용)
        button: "left" (기본) / "right" / "double"
    """
    try:
        import pyautogui

        time.sleep(0.15)
        if button == "right":
            pyautogui.rightClick(x, y)
        elif button == "double":
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.click(x, y)
        time.sleep(0.15)

        return {"ok": True, "data": {"x": x, "y": y, "button": button}, "error": ""}
    except Exception as exc:
        logger.warning(f"mouse_click 실패 ({x},{y}): {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


def mouse_scroll(
    direction: str,
    amount: int = 3,
    x: int | None = None,
    y: int | None = None,
) -> dict[str, Any]:
    """마우스 휠을 스크롤한다.

    Args:
        direction: "up" 또는 "down"
        amount: 스크롤 클릭 수 (기본 3)
        x, y: 스크롤 위치 (생략 시 현재 마우스 위치)
    """
    try:
        import pyautogui

        clicks = amount if direction.lower() == "up" else -amount
        if x is not None and y is not None:
            pyautogui.scroll(clicks, x=x, y=y)
        else:
            pyautogui.scroll(clicks)
        time.sleep(0.2)

        return {"ok": True, "data": {"direction": direction, "amount": amount}, "error": ""}
    except Exception as exc:
        logger.warning(f"mouse_scroll 실패: {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


# ── 키보드 제어 ───────────────────────────────────────────────────────────────

def keyboard_type(text: str) -> dict[str, Any]:
    """텍스트를 입력한다. 한국어를 포함한 모든 문자 지원 (클립보드 붙여넣기 방식).

    Args:
        text: 입력할 텍스트 (한국어 포함 가능)
    """
    try:
        import pyautogui
        import pyperclip

        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.2)

        return {"ok": True, "data": text, "error": ""}
    except Exception as exc:
        logger.warning(f"keyboard_type 실패: {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


def keyboard_key(key: str) -> dict[str, Any]:
    """특수 키 또는 단축키를 누른다.

    Args:
        key: 키 이름 또는 조합. 예: "enter", "tab", "escape", "ctrl+c",
             "ctrl+v", "ctrl+a", "ctrl+w", "ctrl+t", "win", "alt+f4",
             "backspace", "delete", "home", "end", "page_down", "page_up",
             "f5", "ctrl+r" (새로고침), "ctrl+l" (주소창)
    """
    try:
        import pyautogui

        parts = [p.strip() for p in key.lower().split("+")]
        if len(parts) > 1:
            pyautogui.hotkey(*parts)
        else:
            pyautogui.press(parts[0])
        time.sleep(0.15)

        return {"ok": True, "data": key, "error": ""}
    except Exception as exc:
        logger.warning(f"keyboard_key 실패 ({key!r}): {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


# ── 창 관리 ───────────────────────────────────────────────────────────────────

def get_windows() -> dict[str, Any]:
    """열려 있는 모든 창 목록과 현재 활성 창 제목을 반환한다."""
    try:
        import pygetwindow as gw

        titles = [t for t in gw.getAllTitles() if t.strip()]
        active = gw.getActiveWindow()
        active_title = active.title if active else ""

        return {
            "ok": True,
            "data": {"windows": titles, "active": active_title},
            "error": "",
        }
    except Exception as exc:
        logger.warning(f"get_windows 실패: {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


def focus_window(title: str) -> dict[str, Any]:
    """제목에 title(부분 일치)이 포함된 창을 앞으로 가져온다."""
    try:
        import pygetwindow as gw

        all_wins = gw.getAllWindows()
        matches = [
            w for w in all_wins
            if w.title.strip() and title.lower() in w.title.lower()
        ]
        if not matches:
            return {
                "ok": False, "data": None,
                "error": f"창을 찾을 수 없습니다: {title!r}",
            }

        win = matches[0]
        try:
            win.activate()
        except Exception:
            win.minimize()
            win.restore()
        time.sleep(0.4)

        return {"ok": True, "data": {"title": win.title}, "error": ""}
    except Exception as exc:
        logger.warning(f"focus_window 실패: {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


def open_app(target: str) -> dict[str, Any]:
    """URL을 브라우저로 열거나 앱 이름으로 실행한다.

    Args:
        target: URL (예: https://land.naver.com) 또는 앱 이름 (예: chrome, notepad)
    """
    try:
        is_url = bool(
            target.startswith(("http://", "https://"))
            or re.match(r"[\w.-]+\.(com|kr|net|org|io|co\.kr|gov\.kr|ac\.kr)", target)
        )

        if is_url:
            if not target.startswith("http"):
                target = "https://" + target
            webbrowser.open(target)
        else:
            subprocess.Popen(target, shell=True)

        time.sleep(1.5)   # 앱/페이지 초기 로딩 대기

        return {"ok": True, "data": target, "error": ""}
    except Exception as exc:
        logger.warning(f"open_app 실패 ({target!r}): {exc}")
        return {"ok": False, "data": None, "error": str(exc)}
