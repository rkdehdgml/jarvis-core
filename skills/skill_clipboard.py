from core.skill_base import Skill, SkillResult

_COPY_NOISE_WORDS = ("클립보드에", "클립보드", "복사해줘", "복사해", "복사")


class ClipboardSkill(Skill):
    """클립보드 텍스트를 읽거나 쓴다 (pyperclip)."""

    name = "clipboard"
    description = "클립보드에 텍스트를 복사하거나 클립보드 내용을 읽는다"
    triggers = ["클립보드", "복사"]
    examples = ["클립보드에 복사해줘", "클립보드 내용 읽어줘"]

    def can_handle(self, intent: str, text: str) -> float:
        if not any(t in text for t in self.triggers):
            return 0.0
        if any(k in text for k in ("읽어", "내용", "보여")):
            return 0.9
        if "복사" in text:
            return 0.85
        return 0.5

    def execute(self, text: str, context: dict) -> SkillResult:
        try:
            import pyperclip
        except ImportError:
            return SkillResult(
                speech="클립보드 기능을 사용할 수 없습니다 (pyperclip 미설치).",
                success=False,
            )

        try:
            if any(k in text for k in ("읽어", "내용", "보여")):
                content = pyperclip.paste()
                if not content:
                    return SkillResult(
                        speech="클립보드가 비어 있습니다.", success=True, data={"content": ""}
                    )
                return SkillResult(
                    speech=f"클립보드 내용: {content}",
                    success=True,
                    data={"content": content},
                )

            to_copy = text
            for noise in _COPY_NOISE_WORDS:
                to_copy = to_copy.replace(noise, "")
            to_copy = to_copy.strip()

            if not to_copy:
                return SkillResult(speech="복사할 내용이 없습니다.", success=False)

            pyperclip.copy(to_copy)
            return SkillResult(
                speech="클립보드에 복사했습니다", success=True, data={"content": to_copy}
            )
        except Exception:
            return SkillResult(speech="클립보드 작업에 실패했습니다.", success=False)
