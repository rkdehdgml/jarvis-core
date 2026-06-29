"""대전광역시 버스 실시간 위치정보 API 클라이언트.

엔드포인트: https://apis.data.go.kr/6300000/busposinfo/getBusPosByRtid
파라미터:   busRouteId (ROUTE_CD, 예: 30300094)  ← getArrInfoByStopID 응답의 ROUTE_CD와 동일

응답 필드 (itemList):
  BUS_NODE_ID  현재 버스가 위치한 정류소 BIS ID  (daejeon_bis_stops.json 으로 이름 조회 가능)
  PLATE_NO     차량번호  (getArrInfoByStopID 의 CAR_REG_NO 와 동일 포맷)
  GPS_LATI     위도
  GPS_LONG     경도
  DIR          운행 방향 (0/1)
  ROUTE_CD     노선 코드
"""
import logging
import os
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

_ENDPOINT = "https://apis.data.go.kr/6300000/busposinfo/getBusPosByRtid"
_TIMEOUT  = 10


def _api_key() -> str:
    return os.getenv("DAEJEON_BUS_API_KEY", "")


def get_bus_positions(route_cd: str, service_key: str | None = None) -> list[dict]:
    """노선 코드로 운행 중인 모든 버스의 실시간 위치를 조회한다.

    Returns:
        list of {
            plate_no   : str   # 차량번호 (= car_reg_no)
            bus_node_id: str   # 현재 위치 정류소 BIS ID
            gps_lat    : float
            gps_lon    : float
            direction  : int   # 0 or 1
            route_cd   : str
        }
    """
    key = service_key or _api_key()
    if not key:
        logger.warning("DAEJEON_BUS_API_KEY 없음")
        return []

    try:
        r = requests.get(
            _ENDPOINT,
            params={"serviceKey": key, "busRouteId": route_cd},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        return _parse(r.text)
    except requests.RequestException as exc:
        logger.warning(f"버스 위치 API 호출 실패: {exc}")
        return []


def _parse(xml_text: str) -> list[dict]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning(f"버스 위치 XML 파싱 오류: {exc}")
        return []

    if root.findtext("msgHeader/headerCd") != "0":
        return []

    items = []
    for node in root.findall("msgBody/itemList"):
        def t(tag: str) -> str:
            return (node.findtext(tag) or "").strip()

        try:
            lat = float(t("GPS_LATI") or 0)
            lon = float(t("GPS_LONG") or 0)
            direction = int(t("DIR") or 0)
        except ValueError:
            lat, lon, direction = 0.0, 0.0, 0

        items.append({
            "plate_no":    t("PLATE_NO"),
            "bus_node_id": t("BUS_NODE_ID"),
            "gps_lat":     lat,
            "gps_lon":     lon,
            "direction":   direction,
            "route_cd":    t("ROUTE_CD"),
        })
    return items
