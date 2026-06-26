"""파일 저장 도구 (텍스트 / JSON / xlsx).

Stage 2의 Groq tool-calling 루프에서 file_tool 함수로 노출된다.
저장 위치: 사용자 바탕화면(~/Desktop). filename이 비어 있으면 타임스탬프로 자동 생성.
openpyxl은 save_xlsx() 내부에서 lazy import — 패키지 없이도 나머지 함수는 정상 동작.
모든 함수는 {"ok": bool, "data": str|None, "error": str} 형식을 반환하고 예외를 던지지 않는다.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DESKTOP = Path.home() / "Desktop"


def _make_path(filename: str, ext: str) -> Path:
    if not filename:
        filename = f"jarvis_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    path = _DESKTOP / filename
    if not path.suffix:
        path = path.with_suffix(ext)
    return path


def save_text(content: str, filename: str = "") -> dict[str, Any]:
    """텍스트 파일을 바탕화면에 저장한다.

    Returns:
        {"ok": True, "data": "C:\\Users\\...\\파일명.txt", "error": ""}
    """
    try:
        path = _make_path(filename, ".txt")
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "data": str(path), "error": ""}
    except Exception as exc:
        logger.warning(f"file_tool.save_text 실패: {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


def save_json(data: Any, filename: str = "") -> dict[str, Any]:
    """JSON 파일을 바탕화면에 저장한다.

    Args:
        data: JSON으로 직렬화할 Python 객체
        filename: 저장 파일명 (비어 있으면 자동 생성)
    """
    try:
        path = _make_path(filename, ".json")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "data": str(path), "error": ""}
    except Exception as exc:
        logger.warning(f"file_tool.save_json 실패: {exc}")
        return {"ok": False, "data": None, "error": str(exc)}


def save_xlsx(
    rows: list[list],
    headers: list[str] | None = None,
    filename: str = "",
) -> dict[str, Any]:
    """xlsx 파일을 바탕화면에 저장한다.

    Args:
        rows: [[값, ...], ...] 형식의 데이터 행 목록
        headers: 첫 행으로 쓸 헤더 목록. None이면 헤더 없음.
        filename: 저장 파일명 (비어 있으면 자동 생성)
    """
    try:
        import openpyxl
        path = _make_path(filename, ".xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        if headers:
            ws.append(headers)
        for row in rows:
            ws.append(row)
        wb.save(path)
        return {"ok": True, "data": str(path), "error": ""}
    except Exception as exc:
        logger.warning(f"file_tool.save_xlsx 실패: {exc}")
        return {"ok": False, "data": None, "error": str(exc)}
