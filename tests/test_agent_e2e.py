"""skill_agent 엔드투엔드 테스트 3시나리오 (mock 기반).

execute() 진입 → Groq tool-calling 루프 → agent_tools 디스패치 → SkillResult 반환까지
전체 파이프라인을 검증한다. 실제 네트워크·API 호출은 없다.

시나리오:
  1. 조사 + 텍스트 저장  — report → search → open_url → get_all_text → save_text → 최종답변
  2. 뉴스 수집 + 엑셀 저장 — report → search(복수 결과) → save_xlsx → 최종답변
  3. 도구 실패 복구       — open_url 실패 시 에이전트가 저장 단계로 넘어가는지 확인

실행: python -m tests.test_agent_e2e
"""
import json
import os
from unittest.mock import MagicMock, call, patch


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────

def _tc(call_id: str, fn_name: str, args: dict) -> MagicMock:
    """Groq tool_call mock 객체를 생성한다."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = fn_name
    tc.function.arguments = json.dumps(args, ensure_ascii=False)
    return tc


def _resp(content: str | None = None, tool_calls=None) -> MagicMock:
    """Groq API ChatCompletion 응답 mock 객체를 생성한다."""
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    r = MagicMock()
    r.choices = [MagicMock()]
    r.choices[0].message = msg
    return r


def _make_search_results(items: list[dict]) -> dict:
    return {"ok": True, "data": items, "error": ""}


def _ok(data=None) -> dict:
    return {"ok": True, "data": data, "error": ""}


def _fail(error: str) -> dict:
    return {"ok": False, "data": None, "error": error}


# ── 시나리오 1: 조사 → 텍스트 저장 ─────────────────────────────────────────

def test_e2e_research_and_save_text() -> None:
    """'파이썬 기초 개념 조사해줘'

    에이전트 흐름:
      턴1  report + search
      턴2  open_url + get_all_text
      턴3  save_text
      턴4  최종 답변 (도구 호출 없음)

    검증:
      - SkillResult.success is True
      - Groq API 4회 호출
      - search / open_url / get_all_text / save_text 각 1회 호출
      - 최종 speech에 완료 의미 포함
    """
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    groq_seq = [
        # 턴1
        _resp(tool_calls=[
            _tc("c1", "report", {"message": "파이썬 기초 개념을 조사하겠습니다"}),
            _tc("c2", "search", {"query": "파이썬 기초 개념", "max_results": 5}),
        ]),
        # 턴2
        _resp(tool_calls=[
            _tc("c3", "open_url", {"url": "https://python.org/tutorial"}),
            _tc("c4", "get_all_text", {}),
        ]),
        # 턴3
        _resp(tool_calls=[
            _tc("c5", "save_text", {"content": "파이썬 학습 정리 내용", "filename": "python_basics.txt"}),
        ]),
        # 턴4: 최종 답변
        _resp(content="파이썬 기초 개념 조사가 완료되었습니다. python_basics.txt에 저장했습니다.", tool_calls=None),
    ]

    search_mock = MagicMock(return_value=_make_search_results([
        {"title": "파이썬 튜토리얼", "url": "https://python.org/tutorial", "summary": "기초 설명"},
    ]))
    open_url_mock = MagicMock(return_value=_ok("https://python.org/tutorial"))
    get_all_text_mock = MagicMock(return_value=_ok("파이썬은 범용 인터프리터 언어입니다..."))
    save_text_mock = MagicMock(return_value=_ok("C:\\Users\\CEO\\Desktop\\python_basics.txt"))
    report_mock = MagicMock(return_value=_ok("msg"))

    with patch("skills.skill_agent.Groq") as mock_groq_cls, \
         patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}), \
         patch("skills.agent_tools.reporter_tool.report", report_mock), \
         patch("skills.agent_tools.search_tool.search", search_mock), \
         patch("skills.agent_tools.browser_tool.open_url", open_url_mock), \
         patch("skills.agent_tools.browser_tool.get_all_text", get_all_text_mock), \
         patch("skills.agent_tools.file_tool.save_text", save_text_mock):

        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = groq_seq

        result = skill.execute("파이썬 기초 개념 조사해줘", {"history": [], "data": {}})

    # SkillResult 검증
    assert result.success is True, f"success=False: {result.speech}"
    assert "완료" in result.speech, f"최종 답변에 '완료' 없음: {result.speech}"

    # API 호출 횟수 검증
    assert mock_client.chat.completions.create.call_count == 4, (
        f"예상 4회, 실제 {mock_client.chat.completions.create.call_count}회"
    )

    # 도구 호출 검증
    search_mock.assert_called_once_with("파이썬 기초 개념", 5)
    open_url_mock.assert_called_once_with("https://python.org/tutorial")
    get_all_text_mock.assert_called_once()
    save_text_mock.assert_called_once_with("파이썬 학습 정리 내용", "python_basics.txt")
    report_mock.assert_called_once_with("파이썬 기초 개념을 조사하겠습니다")

    print("[E2E-1] research + save_text: 4 turns, all tools called OK")


# ── 시나리오 2: 뉴스 수집 + 엑셀 저장 ───────────────────────────────────────

def test_e2e_news_to_excel() -> None:
    """'삼성전자 최신 뉴스 찾아서 엑셀로 저장해줘'

    에이전트 흐름:
      턴1  report + search (3건 반환)
      턴2  save_xlsx (검색 결과를 행으로 변환)
      턴3  최종 답변 (도구 호출 없음)

    검증:
      - SkillResult.success is True
      - Groq API 3회 호출
      - save_xlsx 1회 호출 (rows가 비어 있지 않음)
      - 최종 speech에 '저장' 또는 '엑셀' 포함
    """
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    news_items = [
        {"title": "삼성전자 신제품 발표", "url": "https://news1.com", "summary": "신제품 출시"},
        {"title": "삼성전자 실적 발표",  "url": "https://news2.com", "summary": "호실적"},
        {"title": "삼성전자 해외 공장",  "url": "https://news3.com", "summary": "베트남 증설"},
    ]
    expected_rows = [
        ["삼성전자 신제품 발표", "https://news1.com", "신제품 출시"],
        ["삼성전자 실적 발표",  "https://news2.com", "호실적"],
        ["삼성전자 해외 공장",  "https://news3.com", "베트남 증설"],
    ]

    groq_seq = [
        # 턴1
        _resp(tool_calls=[
            _tc("c1", "report", {"message": "삼성전자 뉴스를 검색합니다"}),
            _tc("c2", "search", {"query": "삼성전자 최신 뉴스", "max_results": 5}),
        ]),
        # 턴2
        _resp(tool_calls=[
            _tc("c3", "save_xlsx", {
                "rows": expected_rows,
                "headers": ["제목", "URL", "요약"],
                "filename": "samsung_news.xlsx",
            }),
        ]),
        # 턴3: 최종 답변
        _resp(content="삼성전자 뉴스 3건을 samsung_news.xlsx 파일로 저장했습니다.", tool_calls=None),
    ]

    search_mock = MagicMock(return_value=_make_search_results(news_items))
    save_xlsx_mock = MagicMock(return_value=_ok("C:\\Users\\CEO\\Desktop\\samsung_news.xlsx"))
    report_mock = MagicMock(return_value=_ok("msg"))

    with patch("skills.skill_agent.Groq") as mock_groq_cls, \
         patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}), \
         patch("skills.agent_tools.reporter_tool.report", report_mock), \
         patch("skills.agent_tools.search_tool.search", search_mock), \
         patch("skills.agent_tools.file_tool.save_xlsx", save_xlsx_mock):

        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = groq_seq

        result = skill.execute("삼성전자 최신 뉴스 찾아서 엑셀로 저장해줘", {"history": [], "data": {}})

    # SkillResult 검증
    assert result.success is True, f"success=False: {result.speech}"
    assert any(kw in result.speech for kw in ["저장", "엑셀", "완료"]), (
        f"최종 답변에 저장/엑셀/완료 없음: {result.speech}"
    )

    # API 호출 횟수 검증
    assert mock_client.chat.completions.create.call_count == 3, (
        f"예상 3회, 실제 {mock_client.chat.completions.create.call_count}회"
    )

    # 도구 호출 검증
    search_mock.assert_called_once_with("삼성전자 최신 뉴스", 5)
    save_xlsx_mock.assert_called_once_with(expected_rows, ["제목", "URL", "요약"], "samsung_news.xlsx")

    # save_xlsx에 전달된 rows가 비어 있지 않은지 재확인
    actual_rows = save_xlsx_mock.call_args[0][0]
    assert len(actual_rows) == 3, f"rows 개수 오류: {len(actual_rows)}"

    print("[E2E-2] news + save_xlsx: 3 turns, 3 rows OK")


# ── 시나리오 3: 도구 실패 복구 ──────────────────────────────────────────────

def test_e2e_tool_failure_recovery() -> None:
    """'AI 최신 논문 수집해줘' — open_url 실패 시 에이전트가 저장 단계로 진행하는지 검증.

    에이전트 흐름:
      턴1  report + search
      턴2  open_url → {"ok": False, "error": "연결 시간 초과"} 반환
      턴3  에이전트가 실패를 인지하고 save_text로 전환
      턴4  최종 답변 (도구 호출 없음)

    검증:
      - SkillResult.success is True  (도구 실패가 스킬 전체를 죽이면 안 됨)
      - Groq API 4회 호출
      - open_url은 1회 호출, ok=False 반환
      - save_text는 1회 호출 (복구 완료)
      - 루프가 예외 없이 끝까지 실행됨
    """
    from skills.skill_agent import AgentSkill
    skill = AgentSkill()

    groq_seq = [
        # 턴1
        _resp(tool_calls=[
            _tc("c1", "report", {"message": "AI 논문을 수집하겠습니다"}),
            _tc("c2", "search", {"query": "AI 최신 논문 2024", "max_results": 5}),
        ]),
        # 턴2: open_url 시도
        _resp(tool_calls=[
            _tc("c3", "open_url", {"url": "https://arxiv.org/abs/2412.00001"}),
        ]),
        # 턴3: open_url 실패 결과를 받은 에이전트가 검색 결과만으로 저장
        _resp(tool_calls=[
            _tc("c4", "save_text", {
                "content": "페이지 접근 실패. 검색 결과 요약:\n- Paper A\n- Paper B",
                "filename": "ai_papers.txt",
            }),
        ]),
        # 턴4: 최종 답변
        _resp(
            content="일부 페이지 접근에 실패했지만 검색 결과를 바탕으로 ai_papers.txt에 저장했습니다.",
            tool_calls=None,
        ),
    ]

    search_mock = MagicMock(return_value=_make_search_results([
        {"title": "Attention is All You Need", "url": "https://arxiv.org/abs/2412.00001", "summary": "트랜스포머"},
        {"title": "GPT-4 Technical Report",    "url": "https://arxiv.org/abs/2412.00002", "summary": "GPT-4"},
    ]))
    # open_url이 실패를 반환한다 — ok=False
    open_url_mock = MagicMock(return_value=_fail("연결 시간 초과: arxiv.org"))
    save_text_mock = MagicMock(return_value=_ok("C:\\Users\\CEO\\Desktop\\ai_papers.txt"))
    report_mock = MagicMock(return_value=_ok("msg"))

    with patch("skills.skill_agent.Groq") as mock_groq_cls, \
         patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}), \
         patch("skills.agent_tools.reporter_tool.report", report_mock), \
         patch("skills.agent_tools.search_tool.search", search_mock), \
         patch("skills.agent_tools.browser_tool.open_url", open_url_mock), \
         patch("skills.agent_tools.file_tool.save_text", save_text_mock):

        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = groq_seq

        result = skill.execute("AI 최신 논문 수집해줘", {"history": [], "data": {}})

    # SkillResult 검증 — 도구 실패가 스킬 전체를 죽이면 안 됨
    assert result.success is True, f"success=False: {result.speech}"

    # API 호출 횟수 검증
    assert mock_client.chat.completions.create.call_count == 4, (
        f"예상 4회, 실제 {mock_client.chat.completions.create.call_count}회"
    )

    # open_url이 호출되고 ok=False를 반환했는지 확인
    open_url_mock.assert_called_once_with("https://arxiv.org/abs/2412.00001")

    # 실패 후 save_text가 정상 호출됐는지 확인 (복구 완료)
    save_text_mock.assert_called_once()
    saved_content = save_text_mock.call_args[0][0]
    assert len(saved_content) > 0, "save_text에 내용이 없음"

    # Groq에 전달된 messages에 open_url 실패 결과가 포함됐는지 확인
    # (3번째 API 호출 시 messages의 tool 역할 메시지에 ok=False가 있어야 함)
    third_call_kwargs = mock_client.chat.completions.create.call_args_list[2][1]
    third_messages = third_call_kwargs.get("messages", [])
    tool_msgs = [m for m in third_messages if m.get("role") == "tool"]
    assert any("false" in m["content"].lower() for m in tool_msgs), (
        "3번째 Groq 호출 시 open_url 실패 결과가 messages에 없음"
    )

    print("[E2E-3] tool failure recovery: 4 turns, open_url fail handled, save_text OK")


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== skill_agent E2E tests ===\n")

    print("--- Scenario 1: Research + Text Save ---")
    test_e2e_research_and_save_text()

    print("\n--- Scenario 2: News Collection + Excel Save ---")
    test_e2e_news_to_excel()

    print("\n--- Scenario 3: Tool Failure Recovery ---")
    test_e2e_tool_failure_recovery()

    print("\n=== ALL E2E TESTS PASSED ===")


if __name__ == "__main__":
    main()
