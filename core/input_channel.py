import logging
from dataclasses import dataclass
from typing import Literal

from core.status_events import broadcaster

logger = logging.getLogger(__name__)

Channel = Literal["voice", "chat"]

_STT_FAIL_LIMIT = 3
_stt_fail_count = 0


@dataclass
class InputEvent:
    """음성(STT)이든 채팅이든 동일한 형태로 통일된 입력.

    Router/Dispatcher는 channel 값을 거의 신경 쓰지 않는다.
    """
    text: str
    channel: Channel


def normalize_input(text: str, channel: Channel) -> InputEvent:
    """STT 결과든 채팅 텍스트든 InputEvent로 통일해 Router에 넘긴다."""
    return InputEvent(text=text.strip(), channel=channel)


def record_stt_failure() -> bool:
    """STT 호출 실패를 기록한다.

    voice/stt.py가 STT 호출이 실패할 때마다 호출해야 한다 (STEP 7/8 연동 지점).
    연속 실패가 임계값(기본 3회)에 도달하면 채팅 모드 전환을 상태 이벤트로
    알리고 True를 반환한다. 호출 측은 True를 받으면 channel을 "chat"으로
    전환해야 한다.
    """
    global _stt_fail_count
    _stt_fail_count += 1

    if _stt_fail_count >= _STT_FAIL_LIMIT:
        logger.warning("STT 연속 실패로 채팅 모드로 전환합니다.")
        broadcaster.emit(
            state="idle",
            last_response="음성 인식을 사용할 수 없어 채팅 모드로 전환합니다",
        )
        return True
    return False


def reset_stt_failures() -> None:
    """STT 호출이 성공하면 호출해 실패 카운트를 초기화한다."""
    global _stt_fail_count
    _stt_fail_count = 0
