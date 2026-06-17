"""STEP 5 검증: skills/ 에 넣은 스킬 2개가 레지스트리에 자동 등록되는지 확인.

실행: python -m tests.test_skills_step5  (프로젝트 루트에서)
"""
import logging

from core.registry import SkillRegistry
from core.router import Router
from core.dispatcher import Dispatcher
from core.context import ConversationContext


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    registry = SkillRegistry()
    names = [s.name for s in registry.get_all_skills()]
    print("등록된 스킬:", names)

    assert "app_launch" in names, "skill_app_launch 가 자동 등록되지 않음"
    assert "ai_chat" in names, "skill_ai_chat 가 자동 등록되지 않음"

    router = Router(registry)
    dispatcher = Dispatcher(registry)
    ctx = ConversationContext()

    # 키워드 매칭 → app_launch
    skill = router.route("계산기 켜줘")
    assert skill is not None and skill.name == "app_launch"
    result = dispatcher.dispatch(skill, "계산기 켜줘", ctx)
    print("[app_launch]", result.speech, result.success)

    # 매칭 안 됨 → ai_chat 폴백
    skill = router.route("오늘 점심 메뉴 추천해줘")
    assert skill is None, "애매한 문장은 None(폴백 대상)이어야 함"
    result = dispatcher.dispatch(skill, "오늘 점심 메뉴 추천해줘", ctx)
    print("[ai_chat 폴백]", result.speech)
    assert result.success

    print("\nSTEP 5 검증 통과")


if __name__ == "__main__":
    main()
