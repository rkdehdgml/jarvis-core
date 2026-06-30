import { useCallback, useEffect, useRef, useState } from "react";

export type JarvisState = "idle" | "listening" | "processing" | "responded" | "navigation_request";

export interface ConversationTurn {
  role: "user" | "jarvis";
  text: string;
  timestamp: number;
}

export interface SystemInfo {
  cpuPercent: number;
  memoryPercent: number;
}

/** 현재 ai_chat 폴백이 쓰는 엔진(Groq 또는 Claude Code) 식별 정보. */
export interface EngineInfo {
  provider: string;
  model: string;
  connected: boolean;
}

export interface NavigationData {
  destination: { lat: number; lng: number; name: string };
  origin: { lat: number; lng: number };
  routeType: string;
  distance: number;
  duration: number;
  distanceText: string;
  durationText: string;
  vertexes: [number, number][];
  fareToll: number;
  fareTaxi: number;
}

export interface JarvisStatus {
  engineInfo: EngineInfo;
  usageToday: number | null;
  activeSkills: string[];
  systemInfo: SystemInfo | null;
  currentState: JarvisState;
  lastResponse: string | null;
  conversationLog: ConversationTurn[];
  navigationData: NavigationData | null;
  kakaoJsKey: string;
}

export interface UseJarvisStatusResult extends JarvisStatus {
  sendMessage: (text: string) => Promise<void>;
  clearNavigation: () => void;
}

interface StatusApiResponse {
  state: JarvisState;
  lastResponse: string | null;
  timestamp: number;
  engineInfo: EngineInfo;
  activeSkills: string[];
  systemInfo: SystemInfo;
  usageToday: number | null;
}

interface WsPushPayload {
  state: JarvisState;
  lastResponse: string | null;
  timestamp: number;
  engineInfo: EngineInfo;
  systemInfo: SystemInfo;
  usageToday: number | null;
  extra?: Record<string, unknown>;
}

type HistoryApiResponse = ConversationTurn[];

const API_BASE = "http://127.0.0.1:8765";
const WS_URL = "ws://127.0.0.1:8765/ws";
const RECONNECT_DELAY_MS = 2000;

const initialStatus: JarvisStatus = {
  engineInfo: { provider: "-", model: "-", connected: false },
  usageToday: null,
  activeSkills: [],
  systemInfo: null,
  currentState: "idle",
  lastResponse: null,
  conversationLog: [],
  navigationData: null,
  kakaoJsKey: "",
};

/**
 * ui/server.py 의 /ws, /api/status 를 구독하는 공유 상태 훅.
 *
 * JarvisMinimal과 JarvisFull이 동일한 훅을 구독하고, 반환된 데이터를
 * 다르게 배치만 하면 된다. WebSocket 연결이 끊기면 자동으로 재연결한다.
 */
export function useJarvisStatus(): UseJarvisStatusResult {
  const [status, setStatus] = useState<JarvisStatus>(initialStatus);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 마지막으로 처리한 상태 이벤트의 timestamp. 백엔드의 3초 주기 시스템 정보
  // push는 새 이벤트가 없으면 같은 timestamp로 broadcaster.get_current()를
  // 그대로 재전송하므로, 이 값이 같으면 "새 응답"이 아니라 "재전송"이다.
  const lastEventTimestampRef = useRef<number | null>(null);

  const handlePush = useCallback((payload: WsPushPayload) => {
    const isNewEvent = payload.timestamp !== lastEventTimestampRef.current;
    lastEventTimestampRef.current = payload.timestamp;

    setStatus((prev) => {
      const next: JarvisStatus = {
        ...prev,
        currentState: payload.state,
        lastResponse: payload.lastResponse ?? prev.lastResponse,
        engineInfo: payload.engineInfo,
        systemInfo: payload.systemInfo,
        usageToday: payload.usageToday,
      };

      if (isNewEvent && payload.state === "responded" && payload.lastResponse) {
        next.conversationLog = [
          ...prev.conversationLog,
          { role: "jarvis", text: payload.lastResponse, timestamp: payload.timestamp },
        ];
      }

      return next;
    });

    // navigation_request 이벤트: Geolocation 취득 후 /api/navigate 호출
    if (isNewEvent && payload.state === "navigation_request" && payload.extra?.destination) {
      const destination = payload.extra.destination as string;
      const routeType = (payload.extra.routeType as string) || "RECOMMEND";

      if (!navigator.geolocation) return;

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const origin = {
            lat: position.coords.latitude,
            lng: position.coords.longitude,
          };
          try {
            const res = await fetch(`${API_BASE}/api/navigate`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ destination, origin, routeType }),
            });
            const data = (await res.json()) as NavigationData & { error?: string };
            if (!data.error) {
              setStatus((prev) => ({ ...prev, navigationData: data }));
            }
          } catch {
            // 네트워크 오류 시 조용히 무시
          }
        },
        () => {
          // Geolocation 거부/실패 시 조용히 무시
        },
        { timeout: 10000 },
      );
    }
  }, []);

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onmessage = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as WsPushPayload;
        handlePush(payload);
      } catch {
        // 파싱 실패한 페이로드는 무시
      }
    };

    ws.onclose = () => {
      if (wsRef.current !== ws) return;
      reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [handlePush]);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    setStatus((prev) => ({
      ...prev,
      conversationLog: [
        ...prev.conversationLog,
        { role: "user", text: trimmed, timestamp: Date.now() },
      ],
    }));

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
      });
      const data = (await res.json()) as { cleared?: boolean };
      if (data.cleared) {
        setStatus((prev) => ({ ...prev, conversationLog: [] }));
      }
    } catch {
      // 네트워크 오류 시에도 사용자 본인의 발화는 이미 로그에 남아 있다.
    }
  }, []);

  const clearNavigation = useCallback(() => {
    setStatus((prev) => ({ ...prev, navigationData: null }));
  }, []);

  useEffect(() => {
    let cancelled = false;

    fetch(`${API_BASE}/api/status`)
      .then((res) => res.json() as Promise<StatusApiResponse>)
      .then((data) => {
        if (cancelled) return;
        setStatus((prev) => ({
          ...prev,
          engineInfo: data.engineInfo,
          usageToday: data.usageToday,
          activeSkills: data.activeSkills,
          systemInfo: data.systemInfo,
          currentState: data.state,
          lastResponse: data.lastResponse,
        }));
      })
      .catch(() => {});

    fetch(`${API_BASE}/api/history`)
      .then((res) => res.json() as Promise<HistoryApiResponse>)
      .then((data) => {
        if (cancelled) return;
        setStatus((prev) => ({ ...prev, conversationLog: data }));
      })
      .catch(() => {});

    // 카카오 JS 앱 키 로드
    fetch(`${API_BASE}/api/config`)
      .then((res) => res.json() as Promise<{ kakaoJsKey: string }>)
      .then((data) => {
        if (cancelled) return;
        setStatus((prev) => ({ ...prev, kakaoJsKey: data.kakaoJsKey }));
      })
      .catch(() => {});

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { ...status, sendMessage, clearNavigation };
}
