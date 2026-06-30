"""경로/현재 위치 주변 POI(주유소·음식점·카페·화장실 등) 검색 스킬.

"경로에 주유소 표시해줘", "가는 길에 카페 어디 있어?" 같은 발화를 받아
broadcaster로 poi_request 이벤트를 발행한다.
웹 대시보드(useJarvisStatus)가 이벤트를 수신해 /api/navigate/poi를 호출하고
지도에 마커를 표시한다.
"""
import re

from core.skill_base import Skill, SkillResult
from core.status_events import broadcaster

# 카카오 로컬 카테고리 코드 + 표시 이름
# None category_code → 키워드 검색으로 대체
_POI_MAP: dict[str, tuple[str | None, str]] = {
    "주유소": ("OL7", "주유소"),
    "충전소": ("OL7", "충전소"),
    "음식점": ("FD6", "음식점"),
    "밥집": ("FD6", "음식점"),
    "식당": ("FD6", "식당"),
    "한식": ("FD6", "한식당"),
    "중식": ("FD6", "중국집"),
    "일식": ("FD6", "일식당"),
    "양식": ("FD6", "양식당"),
    "카페": ("CE7", "카페"),
    "커피": ("CE7", "카페"),
    "화장실": (None, "화장실"),
    "편의점": ("CS2", "편의점"),
    "마트": ("MT1", "마트"),
    "주차장": ("PK6", "주차장"),
    "병원": ("HP8", "병원"),
    "약국": ("PM9", "약국"),
    "은행": ("BK9", "은행"),
    "휴게소": (None, "휴게소"),
}

_TRIGGER_WORDS = [
    "표시", "알려줘", "알려주세요", "어디", "찾아", "보여줘", "있어", "있나",
]
_CONTEXT_WORDS = [
    "경로", "가는 길", "가는길", "주변", "근처", "중간", "길에",
]
_ALL_WORDS = ["전체", "모두", "다 표시", "모든", "전부"]

# "전체 표시" 시 검색할 대표 카테고리 목록
_ALL_CATEGORIES: list[tuple[str | None, str]] = [
    ("OL7", "주유소"),
    ("FD6", "음식점"),
    ("CE7", "카페"),
    ("CS2", "편의점"),
    (None,  "화장실"),
    ("PK6", "주차장"),
    ("HP8", "병원"),
    ("PM9", "약국"),
]


def _extract_poi(text: str) -> tuple[str | None, str] | None:
    """텍스트에서 POI 종류 추출 → (category_code | None, display_name) or None."""
    for keyword, info in _POI_MAP.items():
        if keyword in text:
            return info
    return None


class PoiSearchSkill(Skill):
    name = "poi_search"
    description = "경로 또는 현재 위치 주변의 주유소·음식점·카페·화장실 등을 지도에 표시한다"
    triggers = list(_POI_MAP.keys()) + _TRIGGER_WORDS + _ALL_WORDS
    examples = [
        "경로에 주유소 표시해줘",
        "가는 길에 카페 어디 있어?",
        "근처 화장실 알려줘",
        "주변 편의점 찾아줘",
        "경로 주변 전체 표시해줘",
        "가는 길에 있는 거 모두 보여줘",
    ]

    def can_handle(self, intent: str, text: str) -> float:
        is_all = any(w in text for w in _ALL_WORDS)
        poi = _extract_poi(text)
        if not poi and not is_all:
            return 0.0
        has_context = any(w in text for w in _CONTEXT_WORDS)
        has_trigger = any(w in text for w in _TRIGGER_WORDS)
        if has_context and (has_trigger or is_all):
            return 0.85
        if has_context or has_trigger or is_all:
            return 0.6
        return 0.3

    def execute(self, text: str, context: dict) -> SkillResult:
        is_all = any(w in text for w in _ALL_WORDS)

        if is_all:
            # 전체 카테고리 한 번에 검색
            categories = [
                {"categoryCode": code, "keyword": name if code is None else None, "categoryName": name}
                for code, name in _ALL_CATEGORIES
            ]
            broadcaster.emit(
                state="poi_request",
                last_response="경로 주변 주요 시설을 모두 검색합니다.",
                extra={"categories": categories, "categoryName": "전체"},
            )
            return SkillResult(
                speech="경로 주변 주유소, 음식점, 카페, 편의점 등을 모두 검색합니다. 웹 대시보드에서 확인해 주세요.",
                success=True,
            )

        poi = _extract_poi(text)
        if not poi:
            return SkillResult(
                speech="어떤 것을 찾으실까요? 예: 경로에 주유소 표시해줘",
                success=False,
            )

        category_code, display_name = poi
        keyword = display_name if category_code is None else None

        broadcaster.emit(
            state="poi_request",
            last_response=f"경로 주변 {display_name}을 검색합니다.",
            extra={
                "categories": [{"categoryCode": category_code, "keyword": keyword, "categoryName": display_name}],
                "categoryName": display_name,
            },
        )

        return SkillResult(
            speech=f"경로 주변 {display_name}을 검색합니다. 웹 대시보드에서 확인해 주세요.",
            success=True,
        )
