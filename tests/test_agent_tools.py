"""agent_tools 4종 단위 테스트 (mock 기반 — 실제 네트워크/파일 I/O 없음).

실행: python -m tests.test_agent_tools
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── browser_tool ─────────────────────────────────────────────────────────────

def test_browser_open_url_success() -> None:
    mock_resp = MagicMock()
    mock_resp.text = "<html><body><p>Hello World</p></body></html>"
    mock_resp.apparent_encoding = "utf-8"
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from skills.agent_tools import browser_tool
        browser_tool._state["soup"] = None
        result = browser_tool.open_url("https://example.com")

    assert result["ok"] is True, f"ok가 False: {result}"
    assert result["data"] == "https://example.com"
    assert result["error"] == ""
    print("[browser_tool] open_url SUCCESS OK")


def test_browser_open_url_failure() -> None:
    with patch("requests.get", side_effect=Exception("연결 실패")):
        from skills.agent_tools import browser_tool
        browser_tool._state["soup"] = None
        result = browser_tool.open_url("https://bad-url.invalid")

    assert result["ok"] is False
    assert result["data"] is None
    assert "연결 실패" in result["error"]
    print("[browser_tool] open_url FAILURE OK")


def test_browser_get_all_text() -> None:
    from bs4 import BeautifulSoup
    from skills.agent_tools import browser_tool
    browser_tool._state["soup"] = BeautifulSoup(
        "<html><body><p>테스트 내용입니다</p></body></html>", "html.parser"
    )
    result = browser_tool.get_all_text()
    assert result["ok"] is True
    assert "테스트 내용입니다" in result["data"]
    print("[browser_tool] get_all_text OK")


def test_browser_get_text_no_selector() -> None:
    """selector=""이면 get_all_text()와 동일하게 동작한다."""
    from bs4 import BeautifulSoup
    from skills.agent_tools import browser_tool
    browser_tool._state["soup"] = BeautifulSoup("<p>내용</p>", "html.parser")
    result = browser_tool.get_text("")
    assert result["ok"] is True
    assert "내용" in result["data"]
    print("[browser_tool] get_text (selector='') -> get_all_text OK")


def test_browser_get_text_no_page() -> None:
    from skills.agent_tools import browser_tool
    browser_tool._state["soup"] = None
    result = browser_tool.get_text(".content")
    assert result["ok"] is False
    assert "open_url" in result["error"]
    print("[browser_tool] get_text (no page) OK")


def test_browser_get_text_with_selector() -> None:
    from bs4 import BeautifulSoup
    from skills.agent_tools import browser_tool
    browser_tool._state["soup"] = BeautifulSoup(
        '<div class="main"><p>선택된 내용</p></div><p>다른 내용</p>', "html.parser"
    )
    result = browser_tool.get_text(".main")
    assert result["ok"] is True
    assert "선택된 내용" in result["data"]
    print("[browser_tool] get_text (CSS selector) OK")


def test_browser_get_links() -> None:
    from bs4 import BeautifulSoup
    from skills.agent_tools import browser_tool
    browser_tool._state["soup"] = BeautifulSoup(
        '<a href="https://a.com">링크A</a><a href="https://b.com">링크B</a>',
        "html.parser",
    )
    result = browser_tool.get_links()
    assert result["ok"] is True
    assert len(result["data"]) == 2
    assert result["data"][0]["href"] == "https://a.com"
    assert result["data"][0]["text"] == "링크A"
    print("[browser_tool] get_links OK")


def test_browser_get_links_no_page() -> None:
    from skills.agent_tools import browser_tool
    browser_tool._state["soup"] = None
    result = browser_tool.get_links()
    assert result["ok"] is False
    print("[browser_tool] get_links (no page) OK")


# ── search_tool ───────────────────────────────────────────────────────────────

def test_search_success() -> None:
    mock_results = [
        {"title": "테스트 결과", "href": "https://example.com", "body": "내용입니다"},
    ]
    mock_ddgs_inst = MagicMock()
    mock_ddgs_inst.__enter__ = MagicMock(return_value=mock_ddgs_inst)
    mock_ddgs_inst.__exit__ = MagicMock(return_value=False)
    mock_ddgs_inst.text = MagicMock(return_value=mock_results)

    with patch("ddgs.DDGS", return_value=mock_ddgs_inst):
        from skills.agent_tools import search_tool
        result = search_tool.search("테스트 검색어")

    assert result["ok"] is True, f"ok가 False: {result}"
    assert len(result["data"]) == 1
    assert result["data"][0]["title"] == "테스트 결과"
    assert result["data"][0]["url"] == "https://example.com"
    assert result["data"][0]["summary"] == "내용입니다"
    print("[search_tool] search SUCCESS OK")


def test_search_empty_results() -> None:
    mock_ddgs_inst = MagicMock()
    mock_ddgs_inst.__enter__ = MagicMock(return_value=mock_ddgs_inst)
    mock_ddgs_inst.__exit__ = MagicMock(return_value=False)
    mock_ddgs_inst.text = MagicMock(return_value=[])

    with patch("ddgs.DDGS", return_value=mock_ddgs_inst):
        from skills.agent_tools import search_tool
        result = search_tool.search("결과없는쿼리")

    assert result["ok"] is True
    assert result["data"] == []
    print("[search_tool] search EMPTY OK")


def test_search_failure() -> None:
    with patch("ddgs.DDGS", side_effect=Exception("네트워크 오류")):
        from skills.agent_tools import search_tool
        result = search_tool.search("실패 쿼리")

    assert result["ok"] is False
    assert result["data"] == []
    assert "네트워크 오류" in result["error"]
    print("[search_tool] search FAILURE OK")


# ── file_tool ─────────────────────────────────────────────────────────────────

def test_file_save_text() -> None:
    with patch("pathlib.Path.write_text") as mock_write:
        from skills.agent_tools import file_tool
        result = file_tool.save_text("안녕하세요", "test_output.txt")

    assert result["ok"] is True, f"ok가 False: {result}"
    assert "test_output.txt" in result["data"]
    mock_write.assert_called_once()
    print("[file_tool] save_text OK")


def test_file_save_text_auto_filename() -> None:
    with patch("pathlib.Path.write_text"):
        from skills.agent_tools import file_tool
        result = file_tool.save_text("자동 파일명 테스트")
    assert result["ok"] is True
    assert "jarvis_" in Path(result["data"]).name
    assert result["data"].endswith(".txt")
    print("[file_tool] save_text auto filename OK")


def test_file_save_json() -> None:
    with patch("pathlib.Path.write_text") as mock_write:
        from skills.agent_tools import file_tool
        result = file_tool.save_json({"key": "값", "list": [1, 2, 3]}, "test_data.json")

    assert result["ok"] is True
    assert "test_data.json" in result["data"]
    call_args = mock_write.call_args
    written = call_args[0][0]
    assert "key" in written
    assert "값" in written
    print("[file_tool] save_json OK")


def test_file_save_xlsx() -> None:
    mock_wb = MagicMock()
    mock_ws = MagicMock()
    mock_wb.active = mock_ws

    mock_openpyxl = MagicMock()
    mock_openpyxl.Workbook.return_value = mock_wb

    with patch.dict(sys.modules, {"openpyxl": mock_openpyxl}):
        from skills.agent_tools import file_tool
        result = file_tool.save_xlsx(
            rows=[["홍길동", 30], ["김철수", 25]],
            headers=["이름", "나이"],
            filename="test_report.xlsx",
        )

    assert result["ok"] is True, f"ok가 False: {result}"
    assert "test_report.xlsx" in result["data"]
    assert mock_ws.append.call_count == 3  # 헤더 1행 + 데이터 2행
    print("[file_tool] save_xlsx OK")


def test_file_save_xlsx_no_headers() -> None:
    mock_wb = MagicMock()
    mock_ws = MagicMock()
    mock_wb.active = mock_ws
    mock_openpyxl = MagicMock()
    mock_openpyxl.Workbook.return_value = mock_wb

    with patch.dict(sys.modules, {"openpyxl": mock_openpyxl}):
        from skills.agent_tools import file_tool
        result = file_tool.save_xlsx(rows=[["A", "B"]], filename="no_header.xlsx")

    assert result["ok"] is True
    assert mock_ws.append.call_count == 1  # 데이터 1행만
    print("[file_tool] save_xlsx no-headers OK")


def test_file_save_failure() -> None:
    with patch("pathlib.Path.write_text", side_effect=PermissionError("접근 거부")):
        from skills.agent_tools import file_tool
        result = file_tool.save_text("내용", "fail.txt")
    assert result["ok"] is False
    assert "접근 거부" in result["error"]
    print("[file_tool] save_text FAILURE OK")


# ── reporter_tool ─────────────────────────────────────────────────────────────

def test_reporter_default() -> None:
    from skills.agent_tools import reporter_tool
    reporter_tool._callback = None
    result = reporter_tool.report("테스트 진행 중입니다")
    assert result["ok"] is True
    assert result["data"] == "테스트 진행 중입니다"
    assert result["error"] == ""
    print("[reporter_tool] report no-callback OK")


def test_reporter_with_callback() -> None:
    from skills.agent_tools import reporter_tool
    mock_tts = MagicMock()
    reporter_tool.set_callback(mock_tts)

    result = reporter_tool.report("에이전트 작업 완료")

    assert result["ok"] is True
    mock_tts.assert_called_once_with("에이전트 작업 완료")
    reporter_tool.set_callback(None)
    print("[reporter_tool] report with-callback OK")


def test_reporter_callback_failure() -> None:
    from skills.agent_tools import reporter_tool
    reporter_tool.set_callback(MagicMock(side_effect=Exception("TTS 오류")))
    result = reporter_tool.report("콜백 실패해도 ok=True")
    assert result["ok"] is True  # 콜백 실패해도 report 자체는 성공
    reporter_tool.set_callback(None)
    print("[reporter_tool] report callback-failure OK")


def test_reporter_set_callback_none() -> None:
    from skills.agent_tools import reporter_tool
    reporter_tool.set_callback(MagicMock())
    reporter_tool.set_callback(None)
    assert reporter_tool._callback is None
    result = reporter_tool.report("None 복원 후 동작")
    assert result["ok"] is True
    print("[reporter_tool] set_callback(None) OK")


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== agent_tools unit tests ===\n")

    print("--- browser_tool ---")
    test_browser_open_url_success()
    test_browser_open_url_failure()
    test_browser_get_all_text()
    test_browser_get_text_no_selector()
    test_browser_get_text_no_page()
    test_browser_get_text_with_selector()
    test_browser_get_links()
    test_browser_get_links_no_page()

    print("\n--- search_tool ---")
    test_search_success()
    test_search_empty_results()
    test_search_failure()

    print("\n--- file_tool ---")
    test_file_save_text()
    test_file_save_text_auto_filename()
    test_file_save_json()
    test_file_save_xlsx()
    test_file_save_xlsx_no_headers()
    test_file_save_failure()

    print("\n--- reporter_tool ---")
    test_reporter_default()
    test_reporter_with_callback()
    test_reporter_callback_failure()
    test_reporter_set_callback_none()

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    main()
