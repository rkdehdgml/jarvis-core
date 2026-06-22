"""웹 채팅 대화 기록을 디스크에 저장해 서버 재시작 후에도 복원한다.

ui/server.py가 시작될 때 load_history()로 이전 대화를 _chat_context에
복원하고, 매 채팅 턴이 끝날 때마다 append_turn()으로 누적 저장한다.
음성 루프(main.py)의 ConversationContext는 이 모듈을 쓰지 않는다 — 대화 기록
영구 보존은 웹 채팅 UI에만 필요한 기능이라 core가 아닌 ui 계층에 둔다.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_HISTORY_PATH = Path(__file__).parent.parent / "data" / "chat_history.json"

# ConversationContext의 기본 max_history와 맞춰, 화면에 보여줄 만큼만 보존한다.
_MAX_STORED_TURNS = 20


def load_history() -> list[dict]:
    """저장된 대화 턴 목록을 시간순으로 반환한다. 없으면 빈 리스트."""
    try:
        return json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def append_turn(turn: dict) -> None:
    """완료된 대화 턴 1개를 디스크에 누적 저장한다(최근 N개만 유지)."""
    history = load_history()
    history.append(turn)
    history = history[-_MAX_STORED_TURNS:]

    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False), encoding="utf-8")
