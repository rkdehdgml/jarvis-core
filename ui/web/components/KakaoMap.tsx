import { useEffect, useRef } from "react";

import type { NavigationData } from "../hooks/useJarvisStatus";

// Kakao Maps SDK는 window.kakao 전역으로 노출된다.
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
  const mapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!jsKey || !mapRef.current) return;

    const initMap = () => {
      window.kakao.maps.load(() => {
        const container = mapRef.current;
        if (!container) return;

        const map = new window.kakao.maps.Map(container, {
          center: new window.kakao.maps.LatLng(data.origin.lat, data.origin.lng),
          level: 7,
        });

        // 출발지 마커
        const originPos = new window.kakao.maps.LatLng(data.origin.lat, data.origin.lng);
        const originMarker = new window.kakao.maps.Marker({ position: originPos, map });
        new window.kakao.maps.InfoWindow({
          content: '<div style="padding:4px 8px;font-size:12px;color:#111;white-space:nowrap">출발지</div>',
        }).open(map, originMarker);

        // 목적지 마커
        const destPos = new window.kakao.maps.LatLng(data.destination.lat, data.destination.lng);
        const destMarker = new window.kakao.maps.Marker({ position: destPos, map });
        new window.kakao.maps.InfoWindow({
          content: `<div style="padding:4px 8px;font-size:12px;color:#111;white-space:nowrap">${data.destination.name}</div>`,
        }).open(map, destMarker);

        // 경로 폴리라인 (vertexes: [lng, lat][])
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

          // 출발지·목적지 모두 보이도록 bounds 자동 조정
          const bounds = new window.kakao.maps.LatLngBounds();
          bounds.extend(originPos);
          bounds.extend(destPos);
          map.setBounds(bounds);
        }
      });
    };

    // SDK가 이미 로드된 경우
    if (window.kakao?.maps) {
      initMap();
      return;
    }

    // 이미 스크립트 태그가 있으면 중복 삽입 방지
    const existingScript = document.getElementById("kakao-maps-sdk");
    if (existingScript) {
      existingScript.addEventListener("load", initMap);
      return () => existingScript.removeEventListener("load", initMap);
    }

    const script = document.createElement("script");
    script.id = "kakao-maps-sdk";
    script.src = `//dapi.kakao.com/v2/maps/sdk.js?appkey=${jsKey}&autoload=false`;
    script.async = true;
    script.onload = initMap;
    document.head.appendChild(script);
  }, [data, jsKey]);

  const routeLabel = ROUTE_TYPE_LABEL[data.routeType] ?? data.routeType;

  return (
    <div className="kakao-map-wrapper">
      <div className="kakao-map-header">
        <span className="kakao-map-header__title">
          {data.destination.name}
        </span>
        <span className="kakao-map-header__meta">
          {routeLabel} · {data.distanceText} · {data.durationText}
          {data.fareToll > 0 && ` · 통행료 ${data.fareToll.toLocaleString()}원`}
        </span>
        <button className="kakao-map-header__close" onClick={onClose} type="button">
          ✕
        </button>
      </div>
      <div ref={mapRef} className="kakao-map-canvas" />
    </div>
  );
}
