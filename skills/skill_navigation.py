"""목적지까지 카카오맵 경로 안내 스킬.

"XX까지 경로 안내해줘" 발화를 받아 broadcaster로 navigation_request 이벤트를 발행한다.
웹 대시보드(useJarvisStatus)가 이벤트를 수신해 브라우저 Geolocation을 획득하고
/api/navigate를 호출해 지도에 경로를 표시한다.
"""
import re

from core.skill_base import Skill, SkillResult
from core.status_events import broadcaster

_TRIGGER_WORDS = [
    "경로", "가는 길", "가는길", "어떻게 가", "내비", "네비", "길 안내", "길안내", "루트",
]

_ROUTE_TYPE_MAP = {
    "최단": "TIME",
    "빠른": "TIME",
    "최적": "RECOMMEND",
    "추천": "RECOMMEND",
    "무료": "TOLL_FREE",
    "무료도로": "TOLL_FREE",
    "최단거리": "DISTANCE",
}

_ROUTE_LABELS = {
    "TIME": "최단 시간",
    "RECOMMEND": "추천",
    "TOLL_FREE": "무료도로 우선",
    "DISTANCE": "최단 거리",
}


def _extract_destination(text: str) -> str | None:
    # "XX까지" 패턴
    m = re.search(r"(.+?)까지", text)
    if m:
        dest = m.group(1).strip()
        dest = re.sub(r"^(경로|내비|네비|길|안내|검색|찾아)\s*", "", dest).strip()
        if dest and len(dest) >= 2:
            return dest

    # "XX 가는 길" / "XX로 경로"
    m = re.search(r"(.+?)\s*(?:가는\s*길|가는길|(?:로|으로)\s*(?:경로|가자|가줘|가려면))", text)
    if m:
        dest = m.group(1).strip()
        if dest and len(dest) >= 2:
            return dest

    # "경로 XX" / "내비 XX"
    m = re.search(r"(?:경로|내비|네비|길안내|길 안내)\s+(.+?)(?:까지|로|으로|$)", text)
    if m:
        dest = m.group(1).strip()
        # 경로 타입 키워드 제거
        for kw in _ROUTE_TYPE_MAP:
            dest = dest.replace(kw, "").strip()
        if dest and len(dest) >= 2:
            return dest

    return None


def _extract_route_type(text: str) -> str:
    for keyword, route_type in _ROUTE_TYPE_MAP.items():
        if keyword in text:
            return route_type
    return "RECOMMEND"


class NavigationSkill(Skill):
    name = "navigation"
    description = "목적지까지 카카오맵으로 경로를 안내한다"
    triggers = ["경로", "길", "내비", "네비", "어떻게 가"]
    examples = ["홍대까지 최단 경로 알려줘", "강남역 가는 길", "부산까지 어떻게 가"]

    def can_handle(self, intent: str, text: str) -> float:
        if not any(w in text for w in _TRIGGER_WORDS):
            return 0.0
        if _extract_destination(text):
            return 0.85
        # 트리거는 있지만 목적지 불명확
        return 0.35

    def execute(self, text: str, context: dict) -> SkillResult:
        destination = _extract_destination(text)
        if not destination:
            return SkillResult(
                speech="목적지를 말씀해 주세요. 예: 홍대까지 경로 안내해줘",
                success=False,
            )

        route_type = _extract_route_type(text)
        label = _ROUTE_LABELS.get(route_type, "추천")

        broadcaster.emit(
            state="navigation_request",
            last_response=f"{destination}까지 {label} 경로를 웹 대시보드에 표시합니다.",
            extra={"destination": destination, "routeType": route_type},
        )

        return SkillResult(
            speech=f"{destination}까지 {label} 경로를 검색합니다. 웹 대시보드에서 확인해 주세요.",
            success=True,
        )
