import logging

from core.skill_base import Skill, SkillResult
from core.registry import SkillRegistry
from core.context import ConversationContext
from core.status_events import broadcaster
from core.input_channel import Channel

logger = logging.getLogger(__name__)

_FALLBACK_SKILL_NAME = "ai_chat"


class Dispatcher:
    """Router가 선택한 스킬을 실행하고 SkillResult를 반환한다.

    - 스킬 실행 중 예외가 발생해도 본체가 죽지 않도록 격리한다.
    - Router가 None을 반환하면 폴백 스킬(skill_ai_chat)로 넘긴다.
    - 폴백 스킬도 없으면 에러 SkillResult를 반환한다.
    """

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def dispatch(
        self,
        skill: Skill | None,
        text: str,
        context: ConversationContext,
        channel: Channel = "voice",
    ) -> SkillResult:
        """스킬을 실행해 결과를 반환한다.

        Args:
            skill: Router가 선택한 스킬. None이면 폴백으로 전환.
            text: 사용자 원문 입력.
            context: 대화 맥락 객체.
            channel: 입력 출처("voice" | "chat"). Dispatcher 자신은 TTS를
                직접 호출하지 않으므로 이 값을 context에 기록만 해 둔다.
                음성 루프(main.py)는 channel=="chat"이면 결과를 TTS로
                읽지 않고 텍스트로만 보여줘야 한다.

        Returns:
            SkillResult. 실행 실패 시에도 반드시 SkillResult를 반환한다.
        """
        context.set("channel", channel)
        broadcaster.emit(state="processing")

        target = skill if skill is not None else self._get_fallback()

        if target is None:
            logger.error("처리 가능한 스킬이 없고 폴백 스킬도 없습니다.")
            result = SkillResult(
                speech="죄송합니다. 지금은 처리할 수 없습니다.",
                success=False,
            )
            broadcaster.emit(state="responded", last_response=result.speech)
            return result

        if skill is None:
            logger.info(f"폴백 스킬 실행: {target.name}")

        result = self._run(target, text, context)
        broadcaster.emit(state="responded", last_response=result.speech)
        return result

    def _run(self, skill: Skill, text: str, context: ConversationContext) -> SkillResult:
        try:
            result = skill.execute(text, context.to_dict())
            context.add_turn(user=text, jarvis=result.speech)
            return result
        except Exception as e:
            logger.error(f"스킬 실행 오류 [{skill.name}]: {e}")
            return SkillResult(
                speech=f"'{skill.name}' 처리 중 오류가 발생했습니다.",
                success=False,
            )

    def _get_fallback(self) -> Skill | None:
        for skill in self._registry.get_all_skills():
            if skill.name == _FALLBACK_SKILL_NAME:
                return skill
        return None
