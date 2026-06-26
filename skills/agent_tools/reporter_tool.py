"""에이전트 진행 상황을 보고하는 도구.

voice/tts.py를 직접 임포트하지 않고 콜백 패턴으로 TTS를 연결한다.
- 기본: 콘솔 print + WebSocket broadcast
- skill_agent.py에서 set_callback(tts.speak)으로 TTS 연결

모든 함수는 {"ok": bool, "data": ..., "error": str} 형식을 반환하고 예외를 던지지 않는다.
"""
import logging
from collections.abc import Callable
from typing import Any

from core.status_events import broadcaster

logger = logging.getLogger(__name__)

_callback: Callable[[str], None] | None = None


def set_callback(fn: Callable[[str], None] | None) -> None:
    """TTS 함수(tts.speak 등)를 연결한다. None을 전달하면 print 전용으로 복원."""
    global _callback
    _callback = fn


def report(message: str) -> dict[str, Any]:
    """진행 상황 메시지를 보고한다.

    콘솔 출력 + WebSocket broadcast(채팅 UI 실시간 표시)를 항상 수행하고,
    TTS 콜백이 연결되어 있으면 음성으로도 읽는다.
    콜백 실패 시에도 report 자체는 ok=True — 에이전트 루프가 멈추지 않아야 한다.
    """
    logger.info(f"[agent] {message}")
    print(f"[자비스 에이전트] {message}")

    # 채팅 UI에 중간 보고 메시지를 실시간으로 표시한다.
    # broadcaster 구독자가 없으면(UI 서버 미실행) 아무 일도 일어나지 않는다.
    try:
        broadcaster.emit(state="responded", last_response=message)
    except Exception as exc:
        logger.warning(f"reporter_tool broadcaster 실패: {exc}")

    if _callback is not None:
        try:
            _callback(message)
        except Exception as exc:
            logger.warning(f"reporter_tool TTS 콜백 실패: {exc}")
    return {"ok": True, "data": message, "error": ""}
