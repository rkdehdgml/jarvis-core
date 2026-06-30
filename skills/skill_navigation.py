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


def _clean_dest(dest: str) -> str:
    for kw in _ROUTE_TYPE_MAP:
        dest = dest.replace(kw, "")
    dest = re.sub(r"\s*(알려줘|알려주세요|안내해줘|보여줘|찾아줘|검색해줘|해줘)\s*$", "", dest)
    return re.sub(r"\s+", " ", dest).strip()


def _extract_origin(text: str) -> str | None:
    """발화에서 출발지 추출. "XX에서 YY까지" / "XX부터 YY까지" 패턴."""
    m = re.search(r"(.+?)\s*(?:에서|부터)\s+.+?(?:까지|로|으로|경로|내비|네비)", text)
    if m:
        origin = _clean_dest(m.group(1))
        # 백트래킹으로 "에서에서" 같은 경우 trailing "에서"/"부터"가 붙을 수 있어 제거
        origin = re.sub(r"(?:에서|부터)\s*$", "", origin).strip()
        if origin and len(origin) >= 2:
            return origin
    return None


def _extract_destination(text: str) -> str | None:
    # "XX에서 YY까지" — "에서" 이후만 목적지로 사용
    m = re.search(r".+?(?:에서|부터)\s+(.+?)까지", text)
    if m:
        dest = _clean_dest(m.group(1))
        if dest and len(dest) >= 2:
            return dest

    # "XX까지" 패턴 (출발지 없는 경우)
    m = re.search(r"(.+?)까지", text)
    if m:
        candidate = m.group(1)
        # "에서" 포함 → 위 패턴에서 이미 처리됐어야 하므로 스킵
        if "에서" not in candidate and "부터" not in candidate:
            dest = _clean_dest(re.sub(r"^(경로|내비|네비|길|안내|검색|찾아)\s*", "", candidate).strip())
            if dest and len(dest) >= 2:
                return dest

    # "XX 가는 길" / "XX로 경로/가자/가줘"
    m = re.search(r"(.+?)\s*(?:가는\s*길|가는길|(?:로|으로)\s*(?:경로|가자|가줘|가려면))", text)
    if m:
        dest = _clean_dest(m.group(1))
        if dest and len(dest) >= 2:
            return dest

    # "경로 XX" / "내비 XX" — 트리거 뒤에 목적지
    m = re.search(r"(?:경로|내비|네비|길안내|길 안내)\s+(.+?)(?:까지|로|으로|$)", text)
    if m:
        dest = _clean_dest(m.group(1))
        if dest and len(dest) >= 2:
            return dest

    # "XX 경로" / "XX 내비" — 목적지 뒤에 트리거 (가장 흔한 구어체)
    m = re.search(r"(.+?)\s+(?:경로|루트|내비|네비|길안내|길 안내)(?:\s|$)", text)
    if m:
        dest = _clean_dest(m.group(1))
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
        # 트리거는 있지만 목적지 불명확 — AI 폴백 대신 스킬이 직접 되물음
        return 0.5

    def execute(self, text: str, context: dict) -> SkillResult:
        destination = _extract_destination(text)
        if not destination:
            return SkillResult(
                speech="목적지를 말씀해 주세요. 예: 홍대까지 경로 안내해줘",
                success=False,
            )

        origin_name = _extract_origin(text)
        route_type = _extract_route_type(text)
        label = _ROUTE_LABELS.get(route_type, "추천")

        origin_clause = f"{origin_name}에서 " if origin_name else ""
        broadcaster.emit(
            state="navigation_request",
            last_response=f"{origin_clause}{destination}까지 {label} 경로를 웹 대시보드에 표시합니다.",
            extra={"destination": destination, "routeType": route_type, "originName": origin_name},
        )

        return SkillResult(
            speech=f"{origin_clause}{destination}까지 {label} 경로를 검색합니다. 웹 대시보드에서 확인해 주세요.",
            success=True,
        )
