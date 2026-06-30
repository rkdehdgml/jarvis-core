import { useCallback, useEffect, useRef, useState } from "react";

import type { NavigationData } from "../hooks/useJarvisStatus";

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    kakao: any;
  }
}

interface KakaoMapProps {
  data: NavigationData;
  jsKey: string;
  onClose: () => void;
}

const ROUTE_TYPE_LABEL: Record<string, string> = {
  RECOMMEND: "추천",
  TIME: "최단 시간",
  DISTANCE: "최단 거리",
  TOLL_FREE: "무료도로 우선",
};

export function KakaoMap({ data, jsKey, onClose }: KakaoMapProps) {
  const mapCanvasRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);

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

    if (window.kakao?.maps) {
      initMap();
    } else {
      const existing = document.getElementById("kakao-maps-sdk");
      if (existing) {
        existing.addEventListener("load", initMap);
        return () => {
          existing.removeEventListener("load", initMap);
          roCleanup?.();
        };
      }
      const script = document.createElement("script");
      script.id = "kakao-maps-sdk";
      script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${jsKey}&autoload=false`;
      script.async = true;
      script.onload = initMap;
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
        </div>
      </div>
    </div>
  );
}
