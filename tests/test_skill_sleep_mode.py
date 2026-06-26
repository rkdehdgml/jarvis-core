"""skill_sleep_mode 검증 — context["data"] 플래그 설정과 충돌 방지 확인.

실행: python -m tests.test_skill_sleep_mode
"""
from skills.skill_sleep_mode import SleepModeSkill


def main() -> None:
    skill = SleepModeSkill()

    # --- can_handle: 발동해야 하는 케이스 ---
    assert skill.can_handle("", "슬립 모드") >= 0.4
    assert skill.can_handle("", "슬립") >= 0.4
    assert skill.can_handle("", "잠자기 모드") >= 0.4
    assert skill.can_handle("", "자비스 잠깐 꺼줘") >= 0.4
    assert skill.can_handle("", "자비스 잠시 멈춰") >= 0.4

    # --- can_handle: 충돌 방지 ---
    assert skill.can_handle("", "컴퓨터 꺼줘") == 0.0    # skill_power 영역
    assert skill.can_handle("", "크롬 꺼줘") == 0.0       # skill_app_control 영역
    assert skill.can_handle("", "절전 모드") == 0.0        # skill_power 영역 ("절전" ≠ "슬립")
    assert skill.can_handle("", "오늘 날씨 어때") == 0.0

    # --- execute: sleep_requested 플래그가 context["data"]에 설정되어야 한다 ---
    ctx = {"data": {}}
    result = skill.execute("슬립 모드", ctx)
    assert result.success is True
    assert ctx["data"].get("sleep_requested") is True
    assert "멈춥니다" in result.speech or "잠시" in result.speech

    # --- 두 번 실행해도 플래그가 올바르게 설정된다 ---
    ctx2 = {"data": {"sleep_requested": False}}
    skill.execute("자비스 잠깐 꺼줘", ctx2)
    assert ctx2["data"]["sleep_requested"] is True

    print("test_skill_sleep_mode 통과")


if __name__ == "__main__":
    main()
