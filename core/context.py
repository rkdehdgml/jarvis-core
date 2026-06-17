from dataclasses import dataclass, field


@dataclass
class Turn:
    """대화 한 턴 (사용자 발화 + 자비스 응답 쌍)."""
    user: str
    jarvis: str
    channel: str = "voice"  # "voice" | "chat"


class ConversationContext:
    """대화 맥락과 세션 데이터를 보관한다.

    Router와 Dispatcher가 동일한 인스턴스를 공유해
    대화가 이어지는 동안 맥락을 유지한다.
    """

    def __init__(self, max_history: int = 20) -> None:
        self._max_history = max_history
        self._history: list[Turn] = []
        self._data: dict = {}

    # --- 대화 기록 ---

    def add_turn(self, user: str, jarvis: str, channel: str = "voice") -> None:
        """완료된 대화 턴을 기록한다."""
        self._history.append(Turn(user=user, jarvis=jarvis, channel=channel))
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def get_history(self, n: int | None = None) -> list[Turn]:
        """최근 n개 턴을 반환한다. n이 None이면 전체 반환."""
        if n is None:
            return list(self._history)
        return list(self._history[-n:])

    # --- 세션 데이터 (스킬 간 공유 상태) ---

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value) -> None:
        self._data[key] = value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def to_dict(self) -> dict:
        """Dispatcher가 스킬에 넘길 context dict를 생성한다."""
        return {
            "history": self.get_history(),
            "data": self._data,
        }
