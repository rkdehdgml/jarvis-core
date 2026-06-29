"""대전광역시 버스정류소 이름 → BIS ID 변환 클라이언트.

두 단계로 동작한다:
1. GetStatListService(NODENM=name) → 정규 정류소명(NODENM) + TAGO ID
2. BIS 캐시(data/daejeon_bis_stops.json)에서 정규 정류소명으로 BIS ID 조회
   → getArrInfoByStopID에 바로 사용 가능한 ID 반환

캐시는 최초 1회 스캔(core/build_bis_cache.py)으로 생성하며,
data.go.kr 정류소조회 API(15110691)로 정규 이름을 확인한 뒤
캐시에서 BIS ID를 찾는 방식이라 두 API가 별도 ID 체계여도 무관하다.
"""
import json
import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_ENDPOINT   = "https://apis.data.go.kr/6300000/GetStatListService/getStatList"
_CACHE_PATH = Path(__file__).parent.parent / "data" / "daejeon_bis_stops.json"
_TIMEOUT    = 10

# 모듈 로드 시 캐시를 한 번만 읽는다
_cache: dict | None = None


def _load_cache() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if _cache_path := _CACHE_PATH:
        try:
            data = json.loads(_cache_path.read_text(encoding="utf-8"))
            _cache = data
            logger.debug(f"BIS 캐시 로드: {len(data.get('name_to_id', {}))}개")
            return _cache
        except Exception as exc:
            logger.warning(f"BIS 캐시 로드 실패: {exc}")
    _cache = {"name_to_id": {}, "id_to_name": {}}
    return _cache


def bis_name_from_id(bis_id: str) -> str | None:
    """BIS 캐시에서 정류소 ID → 정류소명 조회."""
    cache = _load_cache()
    return cache.get("id_to_name", {}).get(str(bis_id))


def _bis_id_from_name(name: str) -> str | None:
    """BIS 캐시에서 정류소 이름 → BIS ID 조회 (완전 일치 우선, 부분 일치 후순)."""
    cache = _load_cache()
    n2i = cache.get("name_to_id", {})

    # 완전 일치
    if name in n2i:
        return n2i[name]

    # 부분 일치 (검색어가 정류소명에 포함)
    matches = [(k, v) for k, v in n2i.items() if name in k]
    if len(matches) == 1:
        return matches[0][1]
    if len(matches) > 1:
        # 이름 길이가 가장 가까운 것 선택 (가장 정확한 매칭)
        matches.sort(key=lambda x: len(x[0]))
        return matches[0][1]

    return None


def _api_key() -> str:
    return os.getenv("DAEJEON_BUS_API_KEY", "")


def search_stops(name: str, service_key: str | None = None) -> list[dict]:
    """정류소 이름으로 검색 → [{id(BIS), name, lat, lon}, ...] 반환.

    GetStatListService로 정규 이름을 확인한 뒤 BIS 캐시에서 BIS ID를 찾는다.
    API 미승인(403)이어도 캐시만으로 동작 가능.
    """
    cache = _load_cache()
    results: list[dict] = []

    # ── 1단계: GetStatListService로 정규 정류소명 조회 ──────────────────────
    tago_stops: list[dict] = []
    key = service_key or _api_key()
    if key:
        try:
            r = requests.get(
                _ENDPOINT,
                params={
                    "serviceKey": key,
                    "numOfRows": "10",
                    "pageNo": "1",
                    "type": "json",
                    "NODENM": name,
                },
                timeout=_TIMEOUT,
            )
            if r.status_code == 200:
                tago_stops = _parse_tago(r.json())
            elif r.status_code == 403:
                logger.info("버스정류소조회 API 미승인(403) — 캐시만 사용.")
        except Exception as exc:
            logger.debug(f"버스정류소조회 API 실패: {exc}")

    # ── 2단계: 각 TAGO 결과의 정규 이름으로 BIS 캐시에서 BIS ID 조회 ─────
    seen_ids: set[str] = set()
    for ts in tago_stops:
        canon_name = ts["name"]
        bis_id = _bis_id_from_name(canon_name)
        if bis_id and bis_id not in seen_ids:
            seen_ids.add(bis_id)
            results.append({
                "id":   bis_id,
                "name": canon_name,
                "lat":  ts.get("lat"),
                "lon":  ts.get("lon"),
            })

    # ── 3단계: TAGO 결과 없거나 BIS ID 못 찾은 경우 — 캐시 직접 검색 ─────
    if not results:
        bis_id = _bis_id_from_name(name)
        if bis_id and bis_id not in seen_ids:
            id_to_name = cache.get("id_to_name", {})
            results.append({
                "id":   bis_id,
                "name": id_to_name.get(bis_id, name),
                "lat":  None,
                "lon":  None,
            })

    return results


def _parse_tago(data: dict) -> list[dict]:
    try:
        header = data["response"]["header"]
        if header.get("resultCode") != "00":
            return []
        raw = data["response"]["body"]["items"]["item"]
        if isinstance(raw, dict):
            raw = [raw]
        return [
            {
                "tago_id": str(it.get("NODEID", "")).strip(),
                "name":    str(it.get("NODENM", "")).strip(),
                "lat":     it.get("LATITUDE"),
                "lon":     it.get("LONGITUDE"),
            }
            for it in raw
            if it.get("NODENM")
        ]
    except (KeyError, TypeError):
        return []
