"""skill_agent.py 단위 테스트 (mock 기반 — 실제 Groq API 호출 없음).

실행: python -m tests.test_skill_agent
"""
import json
import os
from unittest.mock import MagicMock, patch


# ── can_handle 라우팅 ────────────────────────────────────────────────────────

def test_routing_strong_triggers() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    assert skill.can_handle("", "인공지능 트렌드 조사해줘") == 0.9
    assert skill.can_handle("", "최신 기술 수집해줘") == 0.9
    assert skill.can_handle("", "데이터 조사해서 보고해줘") == 0.9
    assert skill.can_handle("", "에이전트로 처리해줘") == 0.9
    print("[can_handle] STRONG TRIGGERS OK")


def test_routing_multi_step_combo() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    assert skill.can_handle("", "삼성전자 뉴스 찾아서 엑셀로 저장해줘") == 0.9
    assert skill.can_handle("", "AI 트렌드 검색해서 저장해줘") == 0.9
    assert skill.can_handle("", "파이썬 라이브러리 찾아서 파일로 만들어줘") == 0.9
    print("[can_handle] MULTI_STEP COMBO OK")


def test_routing_no_match() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    assert skill.can_handle("", "날씨 알려줘") == 0.0
    assert skill.can_handle("", "유튜브 켜줘") == 0.0
    assert skill.can_handle("", "검색해줘") == 0.0          # web_search 영역
    assert skill.can_handle("", "찾아줘") == 0.0             # web_search 영역
    assert skill.can_handle("", "저장해줘") == 0.0           # 파일 저장 단독은 모호
    print("[can_handle] NO MATCH OK")


# ── execute() API 키 없음 ────────────────────────────────────────────────────

def test_execute_no_api_key() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    with patch.dict(os.environ, {}, clear=True):
        # GROQ_API_KEY가 없는 환경 시뮬레이션
        os.environ.pop("GROQ_API_KEY", None)
        result = skill.execute("조사해줘", {"history": [], "data": {}})

    assert result.success is False
    assert "GROQ API" in result.speech
    print("[execute] NO_API_KEY OK")


# ── _dispatch_tool ───────────────────────────────────────────────────────────

def test_dispatch_search() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    with patch("skills.agent_tools.search_tool.search", return_value={"ok": True, "data": [], "error": ""}) as mock_fn:
        result = skill._dispatch_tool("search", {"query": "파이썬", "max_results": 3})

    mock_fn.assert_called_once_with("파이썬", 3)
    assert result["ok"] is True
    print("[dispatch] search OK")


def test_dispatch_open_url() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    with patch("skills.agent_tools.browser_tool.open_url", return_value={"ok": True, "data": "url", "error": ""}) as mock_fn:
        result = skill._dispatch_tool("open_url", {"url": "https://example.com"})

    mock_fn.assert_called_once_with("https://example.com")
    assert result["ok"] is True
    print("[dispatch] open_url OK")


def test_dispatch_get_all_text() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    with patch("skills.agent_tools.browser_tool.get_all_text", return_value={"ok": True, "data": "본문", "error": ""}) as mock_fn:
        result = skill._dispatch_tool("get_all_text", {})

    mock_fn.assert_called_once()
    assert result["data"] == "본문"
    print("[dispatch] get_all_text OK")


def test_dispatch_save_text() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    with patch("skills.agent_tools.file_tool.save_text", return_value={"ok": True, "data": "path.txt", "error": ""}) as mock_fn:
        result = skill._dispatch_tool("save_text", {"content": "내용", "filename": "out.txt"})

    mock_fn.assert_called_once_with("내용", "out.txt")
    assert result["ok"] is True
    print("[dispatch] save_text OK")


def test_dispatch_save_xlsx() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    with patch("skills.agent_tools.file_tool.save_xlsx", return_value={"ok": True, "data": "path.xlsx", "error": ""}) as mock_fn:
        result = skill._dispatch_tool("save_xlsx", {
            "rows": [["A", 1], ["B", 2]],
            "headers": ["항목", "값"],
            "filename": "report.xlsx",
        })

    mock_fn.assert_called_once_with([["A", 1], ["B", 2]], ["항목", "값"], "report.xlsx")
    print("[dispatch] save_xlsx OK")


def test_dispatch_report() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    with patch("skills.agent_tools.reporter_tool.report", return_value={"ok": True, "data": "msg", "error": ""}) as mock_fn:
        result = skill._dispatch_tool("report", {"message": "작업 시작합니다"})

    mock_fn.assert_called_once_with("작업 시작합니다")
    print("[dispatch] report OK")


def test_dispatch_unknown_tool() -> None:
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    result = skill._dispatch_tool("nonexistent_tool", {})
    assert result["ok"] is False
    assert "알 수 없는 도구" in result["error"]
    print("[dispatch] UNKNOWN TOOL OK")


# ── _run_agent 루프 (Groq 클라이언트 mock) ──────────────────────────────────

def _make_groq_response(content: str | None, tool_calls=None) -> MagicMock:
    """Groq API 응답 mock 객체를 생성한다."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message = msg
    return response


def test_run_agent_direct_answer() -> None:
    """도구 호출 없이 바로 답변을 반환하는 케이스."""
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    mock_response = _make_groq_response("파이썬은 범용 프로그래밍 언어입니다.", tool_calls=None)

    with patch("skills.skill_agent.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_response

        result = skill._run_agent("fake-key", "파이썬이 뭐야?")

    assert "파이썬" in result
    assert mock_client.chat.completions.create.call_count == 1
    print("[_run_agent] DIRECT ANSWER OK")


def test_run_agent_one_tool_call() -> None:
    """도구를 1번 호출한 뒤 최종 답변을 반환하는 케이스."""
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    # 첫 번째 응답: report 도구 호출
    tc = MagicMock()
    tc.id = "call_001"
    tc.function.name = "report"
    tc.function.arguments = json.dumps({"message": "조사를 시작합니다"})

    resp_with_tool = _make_groq_response(None, tool_calls=[tc])
    resp_final = _make_groq_response("조사가 완료되었습니다.", tool_calls=None)

    with patch("skills.skill_agent.Groq") as mock_groq_cls, \
         patch("skills.agent_tools.reporter_tool.report", return_value={"ok": True, "data": "msg", "error": ""}):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = [resp_with_tool, resp_final]

        result = skill._run_agent("fake-key", "AI 트렌드 조사해줘")

    assert "완료" in result
    assert mock_client.chat.completions.create.call_count == 2
    print("[_run_agent] ONE TOOL CALL OK")


def test_run_agent_groq_error() -> None:
    """Groq API 호출 실패 시 한국어 에러 메시지를 반환하는 케이스."""
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    with patch("skills.skill_agent.Groq") as mock_groq_cls:
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("연결 실패")

        result = skill._run_agent("fake-key", "조사해줘")

    assert "오류" in result
    print("[_run_agent] GROQ ERROR OK")


def test_run_agent_max_turns() -> None:
    """MAX_TURNS를 초과하면 안내 메시지를 반환하는 케이스."""
    from skills.skill_agent import AgentSkill, _MAX_TURNS
    skill = AgentSkill()

    # 매 턴마다 도구를 호출 → 절대 종료 안 됨
    tc = MagicMock()
    tc.id = "call_loop"
    tc.function.name = "report"
    tc.function.arguments = json.dumps({"message": "계속 중"})
    resp_always_tool = _make_groq_response(None, tool_calls=[tc])

    with patch("skills.skill_agent.Groq") as mock_groq_cls, \
         patch("skills.agent_tools.reporter_tool.report", return_value={"ok": True, "data": "", "error": ""}):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = resp_always_tool

        result = skill._run_agent("fake-key", "무한 루프 태스크")

    assert "최대" in result
    assert mock_client.chat.completions.create.call_count == _MAX_TURNS
    print(f"[_run_agent] MAX TURNS ({_MAX_TURNS}회) OK")


def test_tool_output_truncation() -> None:
    """도구 결과가 2000자를 초과하면 절삭되어 messages에 추가되는지 확인."""
    from skills.skill_agent import AgentSkill, _MAX_TOOL_OUTPUT
    skill = AgentSkill()

    long_text = "A" * 5000
    tc = MagicMock()
    tc.id = "call_long"
    tc.function.name = "get_all_text"
    tc.function.arguments = json.dumps({})

    resp_with_tool = _make_groq_response(None, tool_calls=[tc])
    resp_final = _make_groq_response("완료", tool_calls=None)

    captured_messages: list[list] = []

    def capture_create(**kwargs):
        captured_messages.append(list(kwargs.get("messages", [])))
        if len(captured_messages) == 1:
            return resp_with_tool
        return resp_final

    with patch("skills.skill_agent.Groq") as mock_groq_cls, \
         patch("skills.agent_tools.browser_tool.get_all_text",
               return_value={"ok": True, "data": long_text, "error": ""}):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = capture_create

        skill._run_agent("fake-key", "페이지 내용 조사해줘")

    # 두 번째 호출 시 messages에 tool 결과가 있어야 함
    second_call_msgs = captured_messages[1]
    tool_msg = next(m for m in second_call_msgs if m.get("role") == "tool")
    assert len(tool_msg["content"]) <= _MAX_TOOL_OUTPUT, (
        f"도구 결과가 {_MAX_TOOL_OUTPUT}자 초과: {len(tool_msg['content'])}자"
    )
    print(f"[_run_agent] TOOL OUTPUT TRUNCATION ({_MAX_TOOL_OUTPUT}자) OK")


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== skill_agent unit tests ===\n")

    print("--- can_handle routing ---")
    test_routing_strong_triggers()
    test_routing_multi_step_combo()
    test_routing_no_match()

    print("\n--- execute ---")
    test_execute_no_api_key()

    print("\n--- _dispatch_tool ---")
    test_dispatch_search()
    test_dispatch_open_url()
    test_dispatch_get_all_text()
    test_dispatch_save_text()
    test_dispatch_save_xlsx()
    test_dispatch_report()
    test_dispatch_unknown_tool()

    print("\n--- _run_agent loop ---")
    test_run_agent_direct_answer()
    test_run_agent_one_tool_call()
    test_run_agent_groq_error()
    test_run_agent_max_turns()
    test_tool_output_truncation()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
