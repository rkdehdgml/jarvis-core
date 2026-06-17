import { useState, type FormEvent } from "react";

import "./ChatInput.css";

interface ChatInputProps {
  onSend: (text: string) => void | Promise<void>;
}

/**
 * JarvisFull 의 대화 로그 바로 아래에 위치하는 채팅 입력창.
 *
 * 마이크/채팅 토글 버튼은 입력 모드를 수동으로 전환하는 자동 감지의 백업이다.
 * 단, 브라우저 음성 캡처(Web Speech API 등)는 이 STEP의 범위 밖이라 아직
 * 연결되어 있지 않다 — 토글은 현재 표시만 바뀌고, 텍스트 입력은 항상 동작한다.
 */
export function ChatInput({ onSend }: ChatInputProps) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"voice" | "chat">("chat");
  const [sending, setSending] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    setSending(true);
    setText("");
    try {
      await onSend(trimmed);
    } finally {
      setSending(false);
    }
  };

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <button
        type="button"
        className="chat-input__toggle"
        title={mode === "chat" ? "채팅 모드 (클릭하면 음성 모드로)" : "음성 모드 (클릭하면 채팅 모드로)"}
        onClick={() => setMode((m) => (m === "chat" ? "voice" : "chat"))}
      >
        {mode === "chat" ? "⌨" : "🎙"}
      </button>
      <input
        className="chat-input__field"
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="메시지를 입력하세요..."
      />
      <button className="chat-input__send" type="submit" disabled={sending || !text.trim()}>
        전송
      </button>
    </form>
  );
}
