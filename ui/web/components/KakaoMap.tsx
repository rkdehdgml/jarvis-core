import { useCallback, useEffect, useRef, useState } from "react";

import type { NavigationData, PoiResult } from "../hooks/useJarvisStatus";

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    kakao: any;
  }
}

interface KakaoMapProps {
  data: NavigationData;
  jsKey: string;
  poiResults?: PoiResult[];
  onClose: () => void;
  onClearPoi?: () => void;
  onClearPoiLayer?: (categoryCode: string) => void;
}

// 카테고리 코드 → 마커 배경색
const POI_COLOR: Record<string, string> = {
  OL7: "#f59e0b",  // 주유소
  FD6: "#ef4444",  // 음식점
  CE7: "#92400e",  // 카페
  CS2: "#22c55e",  // 편의점
  MT1: "#3b82f6",  // 마트
  PK6: "#6b7280",  // 주차장
  HP8: "#ec4899",  // 병원
  PM9: "#8b5cf6",  // 약국
  BK9: "#0ea5e9",  // 은행
};
const POI_COLOR_DEFAULT = "#64748b";

const ROUTE_TYPE_LABEL: Record<string, string> = {
  RECOMMEND: "추천",
  TIME: "최단 시간",
  DISTANCE: "최단 거리",
  TOLL_FREE: "무료도로 우선",
};

export function KakaoMap({ data, jsKey, poiResults = [], onClose, onClearPoi, onClearPoiLayer }: KakaoMapProps) {
  const mapCanvasRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const poiOverlaysRef = useRef<any[]>([]);

  // position은 ref + state 분리 — 드래그 중 ref만 업데이트하고 mouseup 후 state 반영
  const posRef = useRef({
    x: Math.max(0, window.innerWidth - 500 - 16),
    y: 16,
  });
  const [pos, setPos] = useState(posRef.current);

  const isDragging = useRef(false);
  const dragStart = useRef({ mx: 0, my: 0, px: 0, py: 0 });

  // ── 지도 초기화 ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!jsKey || !mapCanvasRef.current) return;

    let roCleanup: (() => void) | undefined;

    const initMap = () => {
      const container = mapCanvasRef.current;
      if (!container) return;

      const originPos = new window.kakao.maps.LatLng(data.origin.lat, data.origin.lng);
      const destPos = new window.kakao.maps.LatLng(data.destination.lat, data.destination.lng);

      const map = new window.kakao.maps.Map(container, {
        center: originPos,
        level: 7,
      });
      mapInstanceRef.current = map;

      // 출발지 마커
      const originMarker = new window.kakao.maps.Marker({ position: originPos, map });
      new window.kakao.maps.InfoWindow({
        content: '<div style="padding:4px 8px;font-size:12px;color:#111;white-space:nowrap">출발지</div>',
      }).open(map, originMarker);

      // 목적지 마커
      const destMarker = new window.kakao.maps.Marker({ position: destPos, map });
      new window.kakao.maps.InfoWindow({
        content: `<div style="padding:4px 8px;font-size:12px;color:#111;white-space:nowrap">${data.destination.name}</div>`,
      }).open(map, destMarker);

      // 경로 폴리라인
      if (data.vertexes.length > 0) {
        const path = data.vertexes.map(([lng, lat]) => new window.kakao.maps.LatLng(lat, lng));
        new window.kakao.maps.Polyline({
          path,
          strokeWeight: 5,
          strokeColor: "#3B82F6",
          strokeOpacity: 0.85,
          strokeStyle: "solid",
          map,
        });
        const bounds = new window.kakao.maps.LatLngBounds();
        bounds.extend(originPos);
        bounds.extend(destPos);
        map.setBounds(bounds);
      }

      // 창 크기 변경 시 지도 재레이아웃
      const ro = new ResizeObserver(() => {
        map.relayout();
      });
      ro.observe(container);
      roCleanup = () => ro.disconnect();
    };

    // autoload=false 이므로 스크립트 로드 후 kakao.maps.load()를 통해 지도 모듈을 초기화해야 함
    const initMapWhenReady = () => window.kakao.maps.load(initMap);

    if (window.kakao?.maps) {
      initMapWhenReady();
    } else {
      const existing = document.getElementById("kakao-maps-sdk");
      if (existing) {
        existing.addEventListener("load", initMapWhenReady);
        return () => {
          existing.removeEventListener("load", initMapWhenReady);
          roCleanup?.();
        };
      }
      const script = document.createElement("script");
      script.id = "kakao-maps-sdk";
      script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${jsKey}&autoload=false`;
      script.async = true;
      script.onload = initMapWhenReady;
      document.head.appendChild(script);
    }

    return () => roCleanup?.();
  }, [data, jsKey]);

  // ── 드래그 ───────────────────────────────────────────────────────────────
  const onHeaderMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest("button")) return;
    isDragging.current = true;
    dragStart.current = {
      mx: e.clientX,
      my: e.clientY,
      px: posRef.current.x,
      py: posRef.current.y,
    };
    e.preventDefault();
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const newPos = {
        x: Math.max(0, dragStart.current.px + (e.clientX - dragStart.current.mx)),
        y: Math.max(0, dragStart.current.py + (e.clientY - dragStart.current.my)),
      };
      posRef.current = newPos;
      setPos({ ...newPos });
    };
    const onUp = () => {
      isDragging.current = false;
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, []);

  // ── POI 마커 (카테고리별 레이어 전체 재렌더) ─────────────────────────────
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !window.kakao?.maps) return;

    // 기존 POI 오버레이 전체 제거 후 재생성
    poiOverlaysRef.current.forEach((o) => o.setMap(null));
    poiOverlaysRef.current = [];

    if (poiResults.length === 0) return;

    for (const layer of poiResults) {
      const color = POI_COLOR[layer.categoryCode] ?? POI_COLOR_DEFAULT;

      for (const poi of layer.pois) {
        try {
          const pos = new window.kakao.maps.LatLng(poi.lat, poi.lng);
          const distKm = (poi.distance / 1000).toFixed(1);

          // 말풍선 레이블 (DOM 요소 — 문자열 전달 시 getContent()가 string 반환해 addEventListener 불가)
          const labelEl = document.createElement("div");
          labelEl.style.cssText = [
            "position:relative",
            `background:${color}`,
            "color:#fff",
            "border-radius:4px",
            "padding:3px 6px",
            "font-size:11px",
            "font-weight:bold",
            "white-space:nowrap",
            "box-shadow:0 2px 6px rgba(0,0,0,.4)",
            "cursor:pointer",
            "user-select:none",
          ].join(";");
          labelEl.textContent = poi.name;

          // 삼각형 꼬리
          const tail = document.createElement("div");
          tail.style.cssText = [
            "position:absolute",
            "bottom:-5px",
            "left:50%",
            "transform:translateX(-50%)",
            "width:0",
            "height:0",
            `border-left:5px solid transparent`,
            `border-right:5px solid transparent`,
            `border-top:5px solid ${color}`,
          ].join(";");
          labelEl.appendChild(tail);

          const overlay = new window.kakao.maps.CustomOverlay({
            position: pos,
            content: labelEl,
            yAnchor: 1.3,
            zIndex: 3,
          });
          overlay.setMap(map);

          // 클릭 → InfoWindow
          const infoEl = document.createElement("div");
          infoEl.style.cssText = "padding:6px 10px;font-size:11px;color:#111;line-height:1.6;white-space:nowrap;min-width:160px;";
          const nameB = document.createElement("b");
          nameB.textContent = poi.name;
          infoEl.appendChild(nameB);
          infoEl.appendChild(document.createElement("br"));
          infoEl.appendChild(document.createTextNode(poi.address));
          if (poi.phone) {
            infoEl.appendChild(document.createElement("br"));
            infoEl.appendChild(document.createTextNode(`📞 ${poi.phone}`));
          }
          infoEl.appendChild(document.createElement("br"));
          infoEl.appendChild(document.createTextNode(`경로에서 약 ${distKm}km`));

          const iw = new window.kakao.maps.InfoWindow({
            content: infoEl,
            position: pos,
            removable: true,
          });
          labelEl.addEventListener("click", () => iw.open(map));

          poiOverlaysRef.current.push(overlay);
        } catch (err) {
          console.warn("POI 마커 생성 실패:", err);
        }
      }
    }
  }, [poiResults]);

  const routeLabel = ROUTE_TYPE_LABEL[data.routeType] ?? data.routeType;

  return (
    <div
      className="kakao-map-wrapper"
      style={{ left: pos.x, top: pos.y }}
    >
      {/* 드래그 핸들 헤더 */}
      <div className="kakao-map-header" onMouseDown={onHeaderMouseDown}>
        <span className="kakao-map-header__title">{data.destination.name}</span>
        <button className="kakao-map-header__close" onClick={onClose} type="button">
          ✕
        </button>
      </div>

      {/* 지도 본체 + 우하단 정보 오버레이 */}
      <div className="kakao-map-body">
        <div ref={mapCanvasRef} className="kakao-map-canvas" />

        <div className="kakao-map-info">
          <div className="kakao-map-info__label">{routeLabel}</div>
          <div className="kakao-map-info__main">
            <span className="kakao-map-info__dist">{data.distanceText}</span>
            <span className="kakao-map-info__sep">·</span>
            <span className="kakao-map-info__dur">{data.durationText}</span>
          </div>
          {data.fareToll > 0 && (
            <div className="kakao-map-info__toll">
              통행료 {data.fareToll.toLocaleString()}원
            </div>
          )}
          {data.fareTaxi > 0 && (
            <div className="kakao-map-info__taxi">
              예상 택시 {data.fareTaxi.toLocaleString()}원
            </div>
          )}
          {poiResults.length > 0 && (
            <div className="kakao-map-info__poi-layers">
              {poiResults.map((layer) => (
                <div key={layer.categoryCode || layer.categoryName} className="kakao-map-info__poi">
                  <span
                    className="kakao-map-info__poi-dot"
                    style={{ background: POI_COLOR[layer.categoryCode] ?? POI_COLOR_DEFAULT }}
                  />
                  <span className="kakao-map-info__poi-name">
                    {layer.categoryName} {layer.pois.length}개
                    {!layer.onRoute && ` (${(layer.searchRadiusM / 1000).toFixed(1)}km)`}
                  </span>
                  <button
                    className="kakao-map-info__poi-clear"
                    onClick={() => onClearPoiLayer?.(layer.categoryCode)}
                    type="button"
                    title="이 레이어 제거"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button className="kakao-map-info__poi-clearall" onClick={onClearPoi} type="button">
                전체 지우기
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
