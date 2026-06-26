import re
import threading
import time
import winsound

from core.skill_base import Skill, SkillResult

_DURATION_PATTERN = re.compile(r"(\d+)\s*(시간|분|초)")


def _beep_notification(label: str) -> None:
    print(f"\n⏰ 타이머 완료: {label}")
    for _ in range(3):
        winsound.Beep(880, 400)
        time.sleep(0.15)


class TimerSkill(Skill):
    """'3분 타이머', '30초 후 알려줘' 같은 명령으로 백그라운드 타이머를 설정한다."""

    name = "timer"
    description = "N분/초/시간 후 알림 타이머를 설정한다"
    triggers = ["타이머", "알려줘", "알림"]
    examples = ["3분 타이머", "30초 후 알려줘", "1시간 타이머"]

    def can_handle(self, intent: str, text: str) -> float:
        if "타이머" in text:
            return 0.9
        if _DURATION_PATTERN.search(text) and ("후" in text or "뒤" in text) and ("알려" in text or "알림" in text):
            return 0.9
        return 0.0

    def execute(self, text: str, context: dict) -> SkillResult:
        match = _DURATION_PATTERN.search(text)
        if not match:
            return SkillResult(
                speech="몇 분/초 타이머를 설정할지 알 수 없습니다. 예: '3분 타이머'",
                success=False,
            )

        value = int(match.group(1))
        unit = match.group(2)

        if unit == "시간":
            seconds = value * 3600
            label = f"{value}시간"
        elif unit == "분":
            seconds = value * 60
            label = f"{value}분"
        else:
            seconds = value
            label = f"{value}초"

        if seconds <= 0 or seconds > 86400:
            return SkillResult(
                speech="타이머는 1초 이상 24시간 이하로 설정해주세요.",
                success=False,
            )

        t = threading.Timer(seconds, _beep_notification, args=[label])
        t.daemon = True
        t.start()

        return SkillResult(
            speech=f"{label} 타이머를 시작했습니다.",
            success=True,
            data={"seconds": seconds, "label": label},
        )
