from core.skill_base import Skill, SkillResult


class SleepModeSkill(Skill):
    """음성인식을 일시 중단하고 웨이크워드 대기 상태로 돌아간다.

    skill_power가 "절전"/"PC 종료"를 담당하고, 이 스킬은 자비스 자신의 리스닝을
    잠시 끄는 용도다. skill_power.py가 "슬립"/"잠자기"를 의도적으로 제외해 둔
    슬롯을 채운다.
    """

    name = "sleep_mode"
    description = "음성인식을 일시 중단(슬립)하고 웨이크워드 대기 상태로 돌아간다"
    triggers = ["슬립", "잠자기 모드", "잠시 꺼줘"]
    examples = ["슬립 모드", "잠자기 모드", "자비스 잠깐 꺼줘"]

    def can_handle(self, intent: str, text: str) -> float:
        if "슬립" in text:
            return 0.9
        if "잠자기" in text and "모드" in text:
            return 0.9
        # "자비스 잠깐/잠시 꺼/멈춰/쉬어" — 자비스 본인을 대상으로 한 것만 받는다.
        if "자비스" in text and ("잠깐" in text or "잠시" in text) and any(w in text for w in ("꺼", "멈춰", "쉬어")):
            return 0.85
        return 0.0

    def execute(self, text: str, context: dict) -> SkillResult:
        # context["data"]는 ConversationContext._data의 직접 참조(복사본 아님)이므로
        # 여기서 쓴 값을 main.py의 _run_voice_loop가 context.get()으로 즉시 읽을 수 있다.
        context["data"]["sleep_requested"] = True
        return SkillResult(
            speech="음성인식을 잠시 멈춥니다. 다시 깨우려면 '자비스' 또는 박수를 쳐주세요.",
            success=True,
        )
