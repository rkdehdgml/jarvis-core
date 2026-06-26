"""skill_calendar 검증 — threading.Thread를 mock해 실제 Tkinter 창을 열지 않는다.

실행: python -m tests.test_skill_calendar
"""
from unittest.mock import patch

from skills.skill_calendar import CalendarSkill


def main() -> None:
    skill = CalendarSkill()

    # --- can_handle ---
    assert skill.can_handle("", "달력 띄워줘") >= 0.4
    assert skill.can_handle("", "달력 보여줘") >= 0.4
    assert skill.can_handle("", "캘린더 열어줘") >= 0.4
    assert skill.can_handle("", "이번 달 달력") >= 0.4
    assert skill.can_handle("", "6월 달력") >= 0.4
    assert skill.can_handle("", "오늘 날씨 어때") == 0.0
    assert skill.can_handle("", "타이머 설정해줘") == 0.0

    # --- execute: 현재 월 ---
    with patch("skills.skill_calendar.threading.Thread") as mock_t:
        mock_t.return_value.start.return_value = None
        result = skill.execute("달력 띄워줘", {})
        assert result.success is True
        mock_t.assert_called_once()

    # --- execute: 특정 월 지정 ---
    with patch("skills.skill_calendar.threading.Thread") as mock_t:
        mock_t.return_value.start.return_value = None
        result = skill.execute("6월 달력 보여줘", {})
        assert result.success is True
        assert "6월" in result.speech
        assert result.data["month"] == 6

    # --- execute: 연월 지정 ---
    with patch("skills.skill_calendar.threading.Thread") as mock_t:
        mock_t.return_value.start.return_value = None
        result = skill.execute("2025년 3월 달력", {})
        assert result.success is True
        assert "3월" in result.speech
        assert result.data["year"] == 2025
        assert result.data["month"] == 3

    print("test_skill_calendar 통과")


if __name__ == "__main__":
    main()
