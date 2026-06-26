"""skill_timer 검증 — threading.Timer는 mock으로 대체해 실제 대기하지 않는다.

실행: python -m tests.test_skill_timer
"""
from unittest.mock import patch

from skills.skill_timer import TimerSkill


def main() -> None:
    skill = TimerSkill()

    # --- can_handle ---
    assert skill.can_handle("", "3분 타이머") >= 0.4
    assert skill.can_handle("", "30초 후 알려줘") >= 0.4
    assert skill.can_handle("", "1시간 타이머") >= 0.4
    assert skill.can_handle("", "10분 뒤 알림") >= 0.4
    assert skill.can_handle("", "오늘 날씨 어때") == 0.0
    assert skill.can_handle("", "내일 일정 알려줘") == 0.0  # skill_schedule 영역

    # --- execute: 분 ---
    with patch("skills.skill_timer.threading.Timer") as mock_timer:
        mock_instance = mock_timer.return_value
        result = skill.execute("3분 타이머", {})
        assert result.success is True
        assert "3분" in result.speech
        assert result.data["seconds"] == 180
        assert result.data["label"] == "3분"
        mock_timer.assert_called_once()
        mock_instance.start.assert_called_once()

    # --- execute: 초 ---
    with patch("skills.skill_timer.threading.Timer") as mock_timer:
        result = skill.execute("30초 후 알려줘", {})
        assert result.success is True
        assert result.data["seconds"] == 30

    # --- execute: 시간 ---
    with patch("skills.skill_timer.threading.Timer") as mock_timer:
        result = skill.execute("1시간 타이머", {})
        assert result.success is True
        assert result.data["seconds"] == 3600

    # --- execute: 지속시간 파싱 실패 ---
    result = skill.execute("타이머 설정해줘", {})
    assert result.success is False

    print("test_skill_timer 통과")


if __name__ == "__main__":
    main()
