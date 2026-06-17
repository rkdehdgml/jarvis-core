import logging

from core.skill_base import Skill
from core.registry import SkillRegistry

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD = 0.4


class Router:
    """입력 텍스트를 보고 처리할 스킬을 선택한다.

    모든 스킬의 can_handle()을 호출해 가장 높은 점수를 받은 스킬을 고른다.
    최고 점수가 임계값 미만이면 None을 반환해 AI 폴백(Dispatcher)이 처리하게 한다.
    """

    def __init__(self, registry: SkillRegistry, threshold: float = _DEFAULT_THRESHOLD) -> None:
        self._registry = registry
        self._threshold = threshold

    def route(self, text: str) -> Skill | None:
        """텍스트를 처리할 스킬을 반환한다.

        Args:
            text: 사용자 원문 입력.

        Returns:
            선택된 Skill 인스턴스. 임계값 미달이면 None (→ AI 폴백).
        """
        skills = self._registry.get_all_skills()
        if not skills:
            logger.warning("등록된 스킬이 없습니다.")
            return None

        best_skill: Skill | None = None
        best_score: float = 0.0

        for skill in skills:
            try:
                score = skill.can_handle(intent=text, text=text)
            except Exception as e:
                logger.error(f"can_handle 오류 [{skill.name}]: {e}")
                score = 0.0

            logger.debug(f"  {skill.name}: {score:.2f}")

            if score > best_score:
                best_score = score
                best_skill = skill

        if best_score >= self._threshold:
            logger.info(f"라우팅 → {best_skill.name} (점수: {best_score:.2f})")
            return best_skill

        logger.info(f"임계값 미달 (최고 점수: {best_score:.2f}) → AI 폴백")
        return None
