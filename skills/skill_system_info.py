from core.skill_base import Skill, SkillResult


class SystemInfoSkill(Skill):
    """CPU/메모리/배터리 사용량을 보고한다 (psutil)."""

    name = "system_info"
    description = "CPU, 메모리, 배터리 사용량을 알려준다"
    triggers = ["CPU", "메모리", "배터리"]
    examples = ["CPU 얼마나 써", "배터리 얼마나 남았어"]

    def can_handle(self, intent: str, text: str) -> float:
        upper = text.upper()
        if "CPU" in upper or "메모리" in text or "배터리" in text:
            return 0.9
        return 0.0

    def execute(self, text: str, context: dict) -> SkillResult:
        try:
            import psutil
        except ImportError:
            return SkillResult(
                speech="시스템 정보 조회 기능을 사용할 수 없습니다 (psutil 미설치).",
                success=False,
            )

        upper = text.upper()

        if "CPU" in upper:
            percent = psutil.cpu_percent(interval=0.5)
            return SkillResult(
                speech=f"CPU 사용량은 {percent:.0f}% 입니다",
                success=True,
                data={"cpuPercent": percent},
            )

        if "메모리" in text:
            percent = psutil.virtual_memory().percent
            return SkillResult(
                speech=f"메모리 사용량은 {percent:.0f}% 입니다",
                success=True,
                data={"memoryPercent": percent},
            )

        if "배터리" in text:
            battery = psutil.sensors_battery()
            if battery is None:
                return SkillResult(speech="배터리 정보를 가져올 수 없습니다.", success=False)
            return SkillResult(
                speech=f"배터리는 {battery.percent:.0f}% 남았습니다",
                success=True,
                data={"batteryPercent": battery.percent},
            )

        return SkillResult(speech="어떤 정보를 원하시는지 알 수 없습니다.", success=False)
