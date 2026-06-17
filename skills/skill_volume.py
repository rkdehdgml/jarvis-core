from core.skill_base import Skill, SkillResult

_VOLUME_STEP = 0.1


class VolumeSkill(Skill):
    """시스템 볼륨을 올리거나 내리거나 음소거한다 (Windows, pycaw)."""

    name = "volume"
    description = "볼륨을 조절하거나 음소거한다"
    triggers = ["볼륨", "소리", "음소거"]
    examples = ["볼륨 올려", "볼륨 내려", "음소거", "소리 켜줘"]

    def can_handle(self, intent: str, text: str) -> float:
        if "음소거" in text:
            return 0.95

        has_subject = any(k in text for k in ("볼륨", "소리"))
        if not has_subject:
            return 0.0

        if any(k in text for k in ("올려", "높여", "크게", "키워")):
            return 0.9
        if any(k in text for k in ("내려", "낮춰", "작게", "줄여")):
            return 0.9
        if any(k in text for k in ("켜줘", "켜")):
            return 0.85
        return 0.6

    def execute(self, text: str, context: dict) -> SkillResult:
        try:
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        except ImportError:
            return SkillResult(
                speech="볼륨 조절 기능을 사용할 수 없습니다 (pycaw 미설치).",
                success=False,
            )

        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))

            if "음소거" in text:
                muted = volume.GetMute()
                volume.SetMute(0 if muted else 1, None)
                speech = "음소거를 해제했습니다" if muted else "음소거했습니다"
            elif any(k in text for k in ("올려", "높여", "크게", "키워")):
                current = volume.GetMasterVolumeLevelScalar()
                volume.SetMasterVolumeLevelScalar(min(1.0, current + _VOLUME_STEP), None)
                speech = "볼륨을 올렸습니다"
            elif any(k in text for k in ("내려", "낮춰", "작게", "줄여")):
                current = volume.GetMasterVolumeLevelScalar()
                volume.SetMasterVolumeLevelScalar(max(0.0, current - _VOLUME_STEP), None)
                speech = "볼륨을 내렸습니다"
            elif any(k in text for k in ("켜줘", "켜")):
                volume.SetMute(0, None)
                speech = "소리를 켰습니다"
            else:
                return SkillResult(speech="어떤 볼륨 조작인지 알 수 없습니다.", success=False)

            return SkillResult(speech=speech, success=True)
        except Exception:
            return SkillResult(speech="볼륨 조절에 실패했습니다.", success=False)
