from core.skill_base import Skill, SkillResult

# skill_app_launch.py 와 짝을 이루는 앱 이름 → 프로세스명 매핑.
# 의도적으로 별도 파일에 중복 정의해 두 스킬을 독립적으로 유지한다.
_APP_PROCESSES = {
    "크롬": "chrome.exe",
    "메모장": "notepad.exe",
    "계산기": "CalculatorApp.exe",
    "탐색기": "explorer.exe",
    "워드": "WINWORD.EXE",
    "엑셀": "EXCEL.EXE",
}


class AppControlSkill(Skill):
    """"크롬 종료해줘", "메모장 꺼줘" 같은 명령으로 실행 중인 앱을 종료한다."""

    name = "app_control"
    description = "이름을 말하면 해당 앱 프로세스를 종료한다"
    triggers = ["종료", "꺼줘", "닫아"]
    examples = ["크롬 종료해줘", "메모장 꺼줘", "계산기 닫아"]

    def can_handle(self, intent: str, text: str) -> float:
        has_trigger = any(t in text for t in self.triggers)
        has_known_app = any(app in text for app in _APP_PROCESSES)
        if has_trigger and has_known_app:
            return 0.9
        if has_trigger:
            # 앱 이름이 없는 모호한 "꺼줘"/"닫아"는 낮은 점수만 줘서
            # 다른 스킬(예: 볼륨의 "소리 꺼줘")이 더 명확하면 그쪽이 이기게 한다.
            return 0.3
        return 0.0

    def execute(self, text: str, context: dict) -> SkillResult:
        try:
            import psutil
        except ImportError:
            return SkillResult(
                speech="앱 종료 기능을 사용할 수 없습니다 (psutil 미설치).",
                success=False,
            )

        app_name = next((app for app in _APP_PROCESSES if app in text), None)
        if app_name is None:
            return SkillResult(speech="어떤 앱을 종료할지 알 수 없습니다.", success=False)

        process_name = _APP_PROCESSES[app_name]
        killed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                if (proc.info["name"] or "").lower() == process_name.lower():
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if killed == 0:
            return SkillResult(speech=f"실행 중인 {app_name}을 찾지 못했습니다.", success=False)

        return SkillResult(
            speech=f"{app_name} 종료했습니다",
            success=True,
            data={"app": app_name, "killed": killed},
        )
