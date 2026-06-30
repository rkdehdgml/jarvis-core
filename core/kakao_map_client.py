"""카카오 지도 API 클라이언트.

사용 API:
- 카카오 로컬 API (키워드 검색): 장소명 → 위경도
- 카카오 모빌리티 API (경로 탐색): 출발지+목적지 → 경로 polyline

두 API 모두 KAKAO_REST_API_KEY 하나로 동작한다.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

_LOCAL_ENDPOINT = "https://dapi.kakao.com/v2/local/search/keyword.json"
_DIRECTIONS_ENDPOINT = "https://apis-navi.kakaomobility.com/v1/directions"
_TIMEOUT = 10


def _rest_key() -> str:
    return os.getenv("KAKAO_REST_API_KEY", "")


def _headers() -> dict:
    return {"Authorization": f"KakaoAK {_rest_key()}"}


def geocode(place_name: str) -> dict | None:
    """장소명 → {"lat": float, "lng": float, "name": str}

    카카오 로컬 키워드 검색 API를 사용한다.
    결과가 없거나 API 오류 시 None 반환.
    """
    key = _rest_key()
    if not key:
        logger.warning("KAKAO_REST_API_KEY 미설정")
        return None
    try:
        r = requests.get(
            _LOCAL_ENDPOINT,
            headers=_headers(),
            params={"query": place_name, "size": 1},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        docs = r.json().get("documents", [])
        if not docs:
            return None
        doc = docs[0]
        return {
            "lat": float(doc["y"]),
            "lng": float(doc["x"]),
            "name": doc.get("place_name", place_name),
        }
    except Exception as exc:
        logger.warning(f"카카오 Geocoding 실패 ({place_name}): {exc}")
        return None


def directions(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    priority: str = "RECOMMEND",
) -> dict | None:
    """출발지 → 목적지 경로 탐색.

    priority: RECOMMEND(추천) | TIME(최단시간) | DISTANCE(최단거리) | TOLL_FREE(무료도로)

    Returns:
        {
            "distance": int,         # 미터
            "duration": int,         # 초
            "vertexes": [[lng, lat], ...],
            "fare_toll": int,        # 통행료 (원)
            "fare_taxi": int,        # 예상 택시 요금 (원)
        }
        오류 시 None.
    """
    key = _rest_key()
    if not key:
        return None
    try:
        r = requests.get(
            _DIRECTIONS_ENDPOINT,
            headers=_headers(),
            params={
                "origin": f"{origin_lng},{origin_lat}",
                "destination": f"{dest_lng},{dest_lat}",
                "priority": priority,
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        routes = data.get("routes", [])
        if not routes or routes[0].get("result_code") != 0:
            logger.warning(f"경로 탐색 실패: {data}")
            return None

        route = routes[0]
        summary = route.get("summary", {})

        # 모든 섹션의 road vertexes 수집 (카카오는 [lng, lat, lng, lat, ...] 교대)
        vertexes: list[list[float]] = []
        for section in route.get("sections", []):
            for road in section.get("roads", []):
                vx = road.get("vertexes", [])
                for i in range(0, len(vx) - 1, 2):
                    vertexes.append([vx[i], vx[i + 1]])

        fare = summary.get("fare", {})
        return {
            "distance": summary.get("distance", 0),
            "duration": summary.get("duration", 0),
            "vertexes": vertexes,
            "fare_toll": fare.get("toll", 0),
            "fare_taxi": fare.get("taxi", 0),
        }
    except Exception as exc:
        logger.warning(f"카카오 Directions 실패: {exc}")
        return None
