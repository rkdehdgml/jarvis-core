import { useCallback, useEffect, useRef, useState } from "react";

export type JarvisState = "idle" | "listening" | "processing" | "responded";

export interface ConversationTurn {
  role: "user" | "jarvis";
  text: string;
  timestamp: number;
}

export interface SystemInfo {
  cpuPercent: number;
  memoryPercent: number;
}

export interface JarvisStatus {
  engineStatus: boolean;
  usageToday: number | null;
  activeSkills: string[];
  systemInfo: SystemInfo | null;
  currentState: JarvisState;
  lastResponse: string | null;
  conversationLog: ConversationTurn[];
}

export interface UseJarvisStatusResult extends JarvisStatus {
  /** 채팅 메시지를 보낸다. 사용자 발화를 즉시 로그에 추가하고 /api/chat 으로 전송한다. */
  sendMessage: (text: string) => Promise<void>;
}

interface StatusApiResponse {
  state: JarvisState;
  lastResponse: string | null;
  timestamp: number;
  engineStatus: boolean;
  activeSkills: string[];
  systemInfo: SystemInfo;
  usageToday: number | null;
}

interface WsPushPayload {
  state: JarvisState;
  lastResponse: string | null;
  timestamp: number;
}

const API_BASE = "http://127.0.0.1:8765";
const WS_URL = "ws://127.0.0.1:8765/ws";
const RECONNECT_DELAY_MS = 2000;

const initialStatus: JarvisStatus = {
  engineStatus: false,
  usageToday: null,
  activeSkills: [],
  systemInfo: null,
  currentState: "idle",
  lastResponse: null,
  conversationLog: [],
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

  const handlePush = useCallback((payload: WsPushPayload) => {
    setStatus((prev) => {
      const next: JarvisStatus = {
        ...prev,
        currentState: payload.state,
        lastResponse: payload.lastResponse ?? prev.lastResponse,
      };

      if (payload.state === "responded" && payload.lastResponse) {
        next.conversationLog = [
          ...prev.conversationLog,
          { role: "jarvis", text: payload.lastResponse, timestamp: payload.timestamp },
        ];
      }

      return next;
    });
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
      await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
      });
      // 자비스의 응답은 /ws 를 통해 "responded" 이벤트로 push되어
      // handlePush가 conversationLog에 자동으로 추가한다.
    } catch {
      // 네트워크 오류 시에도 사용자 본인의 발화는 이미 로그에 남아 있다.
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    fetch(`${API_BASE}/api/status`)
      .then((res) => res.json() as Promise<StatusApiResponse>)
      .then((data) => {
        if (cancelled) return;
        setStatus((prev) => ({
          ...prev,
          engineStatus: data.engineStatus,
          usageToday: data.usageToday,
          activeSkills: data.activeSkills,
          systemInfo: data.systemInfo,
          currentState: data.state,
          lastResponse: data.lastResponse,
        }));
      })
      .catch(() => {
        // 서버가 아직 안 떴을 수 있음. 초기값 유지하고 WebSocket 재연결에 맡긴다.
      });

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { ...status, sendMessage };
}
