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
_CATEGORY_ENDPOINT = "https://dapi.kakao.com/v2/local/search/category.json"
_DIRECTIONS_ENDPOINT = "https://apis-navi.kakaomobility.com/v1/directions"
_TIMEOUT = 10


def _rest_key() -> str:
    return os.getenv("KAKAO_REST_API_KEY", "")


def _headers() -> dict:
    return {"Authorization": f"KakaoAK {_rest_key()}"}


def geocode_candidates(place_name: str, size: int = 5) -> list[dict]:
    """장소명 → 최대 size개의 후보 목록.

    각 항목: {"lat", "lng", "name", "address"}
    결과 없거나 오류 시 [].
    """
    key = _rest_key()
    if not key:
        logger.warning("KAKAO_REST_API_KEY 미설정")
        return []
    try:
        r = requests.get(
            _LOCAL_ENDPOINT,
            headers=_headers(),
            params={"query": place_name, "size": size},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return [
            {
                "lat": float(doc["y"]),
                "lng": float(doc["x"]),
                "name": doc.get("place_name", place_name),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
            }
            for doc in r.json().get("documents", [])
        ]
    except Exception as exc:
        logger.warning(f"카카오 Geocoding 후보 조회 실패 ({place_name}): {exc}")
        return []


def geocode(place_name: str) -> dict | None:
    """장소명 → {"lat": float, "lng": float, "name": str} (1순위 결과만)."""
    candidates = geocode_candidates(place_name, size=1)
    return candidates[0] if candidates else None


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


def _search_at_points(
    points: list[list[float]],
    category_code: str | None,
    keyword: str | None,
    radius: int,
    max_per_point: int = 15,
) -> list[dict]:
    """샘플 지점 목록 주변 POI를 검색한다. 중복 제거 후 거리순 반환."""
    seen_ids: set[str] = set()
    results: list[dict] = []

    for point in points:
        lng, lat = point[0], point[1]
        try:
            if category_code:
                r = requests.get(
                    _CATEGORY_ENDPOINT,
                    headers=_headers(),
                    params={
                        "category_group_code": category_code,
                        "x": lng, "y": lat,
                        "radius": radius,
                        "size": max_per_point,
                        "sort": "distance",
                    },
                    timeout=_TIMEOUT,
                )
            else:
                r = requests.get(
                    _LOCAL_ENDPOINT,
                    headers=_headers(),
                    params={
                        "query": keyword or "",
                        "x": lng, "y": lat,
                        "radius": radius,
                        "size": max_per_point,
                        "sort": "distance",
                    },
                    timeout=_TIMEOUT,
                )
            r.raise_for_status()
            for doc in r.json().get("documents", []):
                pid = doc.get("id", "")
                if pid and pid in seen_ids:
                    continue
                if pid:
                    seen_ids.add(pid)
                results.append({
                    "id": pid,
                    "name": doc.get("place_name", ""),
                    "address": doc.get("road_address_name") or doc.get("address_name", ""),
                    "lat": float(doc.get("y", 0)),
                    "lng": float(doc.get("x", 0)),
                    "categoryCode": category_code or "",
                    "phone": doc.get("phone", ""),
                    "distance": int(doc.get("distance", 0)),
                })
        except Exception as exc:
            logger.warning(f"POI 검색 실패 ({lat:.4f},{lng:.4f} r={radius}): {exc}")

    return sorted(results, key=lambda x: x["distance"])


def search_pois_along_route(
    vertexes: list[list[float]],
    category_code: str | None,
    keyword: str | None,
) -> tuple[list[dict], int]:
    """경로 polyline 주변 POI 검색.

    vertexes: [[lng, lat], ...]  (카카오 Directions 반환 형식)

    검색 반경을 단계적으로 넓혀 결과가 나올 때까지 시도한다:
      1단계 500m  → 경로 위 (on-route)
      2단계 2000m → 경로 근처 (slight detour)
      3단계 5000m → 경로 중간점 기준 (significant detour)

    Returns:
        (pois[:10], search_radius_m)  — 결과 없으면 ([], 0)
    """
    if not vertexes:
        return [], 0

    n = len(vertexes)
    # 경로에서 최대 20개 균등 샘플 포인트 추출
    step = max(1, n // 20)
    samples = vertexes[::step]
    if vertexes[-1] not in samples:
        samples = [*samples, vertexes[-1]]

    for radius, pts in (
        (500, samples),
        (2000, samples),
        (5000, [vertexes[n // 2]]),  # 넓은 반경은 중간점 한 곳만
    ):
        pois = _search_at_points(pts, category_code, keyword, radius)
        if pois:
            return pois[:50], radius

    return [], 0
