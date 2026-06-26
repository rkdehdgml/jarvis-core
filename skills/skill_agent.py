"""Groq native tool-calling 루프로 멀티스텝 조사·수집·저장 작업을 수행하는 에이전트 스킬.

'자비스 인공지능 트렌드 조사해줘' 같은 복합 태스크를 받아
search → open_url → get_all_text → save_xlsx 등 도구 체인을 최대 10턴 자동 실행한다.
core/는 일절 수정하지 않는다.
"""
import json
import logging
import os

from dotenv import load_dotenv
from groq import Groq

from core.skill_base import Skill, SkillResult
from skills.agent_tools import browser_tool, file_tool, reporter_tool, search_tool

load_dotenv()
logger = logging.getLogger(__name__)

_MODEL = "llama-3.3-70b-versatile"
_MAX_TURNS = 10
_MAX_TOKENS = 2048
_TIMEOUT = 60
_MAX_TOOL_OUTPUT = 2000  # 도구 결과 최대 길이 — 컨텍스트 과부하 방지

# ── 라우팅 키워드 ──────────────────────────────────────────────────────────────
# 단독으로도 멀티스텝 태스크를 명확히 암시하는 단어
_STRONG_TRIGGERS = ["조사해줘", "조사해서", "수집해줘", "수집해서", "에이전트로"]
# "찾아서/검색해서 + 파일 저장 키워드" 조합도 멀티스텝으로 인식
_MULTI_STEP_ACTIONS = ["찾아서", "검색해서"]
_SAVE_KEYWORDS = ["저장해줘", "엑셀로", "파일로 만들어줘", "파일로 정리"]

_SYSTEM_PROMPT = (
    "너는 자비스 에이전트야. 사용자의 요청을 분석하고 주어진 도구를 단계적으로 사용해서 작업을 완료해줘.\n\n"
    "규칙:\n"
    "1. 작업 시작 전 report 도구로 무엇을 할지 간단히 알려줘\n"
    "2. 검색이 필요하면 search, 페이지 내용이 필요하면 open_url → get_all_text 순서로 사용해\n"
    "3. 결과를 파일로 저장할 때는 내용에 따라 save_text · save_json · save_xlsx 중 선택해\n"
    "4. 모든 작업이 끝나면 최종 결과를 한 문단으로 요약해서 알려줘\n"
    "5. 모든 응답과 report 메시지는 반드시 한국어로 해"
)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "DuckDuckGo로 웹을 검색한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어"},
                    "max_results": {"type": "integer", "description": "결과 수 (기본 5)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "URL 페이지를 열어 내용을 세션에 저장한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "열 URL"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_all_text",
            "description": "현재 열린 페이지의 본문 텍스트 전체를 가져온다",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_links",
            "description": "현재 열린 페이지의 링크 목록을 가져온다",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS 선택자 (비워두면 전체)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_text",
            "description": "텍스트를 txt 파일로 바탕화면에 저장한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "저장할 내용"},
                    "filename": {"type": "string", "description": "파일명 (비워두면 자동 생성)"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_json",
            "description": "데이터를 JSON 파일로 바탕화면에 저장한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"description": "저장할 데이터 (object 또는 array)"},
                    "filename": {"type": "string", "description": "파일명 (비워두면 자동 생성)"},
                },
                "required": ["data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_xlsx",
            "description": "데이터를 xlsx(엑셀) 파일로 바탕화면에 저장한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {"type": "array"},
                        "description": "데이터 행 목록 [[값, ...], ...]",
                    },
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "헤더 행 (선택)",
                    },
                    "filename": {"type": "string", "description": "파일명 (비워두면 자동 생성)"},
                },
                "required": ["rows"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "report",
            "description": "현재 진행 상황을 사용자에게 보고한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "보고할 내용"},
                },
                "required": ["message"],
            },
        },
    },
]


class AgentSkill(Skill):
    """멀티스텝 조사·수집·저장 에이전트 (Groq native tool-calling 기반)."""

    name = "agent"
    description = "웹 조사·수집·파일 저장 등 멀티스텝 작업을 에이전트가 자동 수행한다"
    triggers = ["조사", "수집", "에이전트"]
    examples = [
        "자비스 인공지능 트렌드 조사해줘",
        "삼성전자 최신 뉴스 찾아서 엑셀로 저장해줘",
        "파이썬 유용한 라이브러리 10개 수집해줘",
    ]

    def can_handle(self, intent: str, text: str) -> float:
        if any(t in text for t in _STRONG_TRIGGERS):
            return 0.9
        # "찾아서/검색해서" + 파일 저장 키워드 조합 → 멀티스텝 명확
        if any(a in text for a in _MULTI_STEP_ACTIONS) and any(s in text for s in _SAVE_KEYWORDS):
            return 0.9
        return 0.0

    def execute(self, text: str, context: dict) -> SkillResult:
        # TTS 콜백 연결 — voice/ 임포트 실패 시(텍스트 전용 모드) print만 사용
        try:
            from voice import tts as _tts
            reporter_tool.set_callback(_tts.speak)
        except Exception:
            reporter_tool.set_callback(None)

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return SkillResult(
                speech="GROQ API 키가 없습니다. .env 파일에 GROQ_API_KEY를 설정해주세요.",
                success=False,
            )

        final_answer = self._run_agent(api_key, text)
        return SkillResult(speech=final_answer, success=True, data={"task": text})

    def _run_agent(self, api_key: str, task: str) -> str:
        """Groq native tool-calling 루프. 최대 _MAX_TURNS 턴 실행."""
        client = Groq(api_key=api_key)
        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": task},
        ]

        for turn in range(_MAX_TURNS):
            try:
                response = client.chat.completions.create(
                    model=_MODEL,
                    messages=messages,
                    tools=_TOOLS,
                    tool_choice="auto",
                    max_tokens=_MAX_TOKENS,
                    timeout=_TIMEOUT,
                )
            except Exception as exc:
                logger.error(f"AgentSkill Groq 호출 실패 (턴 {turn + 1}): {exc}")
                return f"에이전트 실행 중 오류가 발생했습니다: {exc}"

            msg = response.choices[0].message

            # 도구 호출 없음 → 최종 응답
            if not msg.tool_calls:
                return msg.content or "작업을 완료했습니다."

            # assistant 메시지를 dict로 변환해서 messages에 추가
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            # 각 도구 호출 실행
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                result = self._dispatch_tool(fn_name, fn_args)
                # 2000자 절삭 — 컨텍스트 과부하 방지
                result_str = json.dumps(result, ensure_ascii=False)[:_MAX_TOOL_OUTPUT]
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

        logger.warning(f"AgentSkill: {_MAX_TURNS}턴 초과 — 태스크: {task!r}")
        return "최대 반복 횟수에 도달했습니다. 작업 일부만 완료됐을 수 있습니다."

    def _dispatch_tool(self, name: str, args: dict) -> dict:
        """도구 이름으로 실제 함수를 호출하고 결과를 반환한다."""
        if name == "search":
            return search_tool.search(args.get("query", ""), args.get("max_results", 5))
        if name == "open_url":
            return browser_tool.open_url(args.get("url", ""))
        if name == "get_all_text":
            return browser_tool.get_all_text()
        if name == "get_links":
            return browser_tool.get_links(args.get("selector", ""))
        if name == "save_text":
            return file_tool.save_text(args.get("content", ""), args.get("filename", ""))
        if name == "save_json":
            return file_tool.save_json(args.get("data", {}), args.get("filename", ""))
        if name == "save_xlsx":
            return file_tool.save_xlsx(
                args.get("rows", []),
                args.get("headers"),
                args.get("filename", ""),
            )
        if name == "report":
            return reporter_tool.report(args.get("message", ""))
        logger.warning(f"AgentSkill: 알 수 없는 도구 '{name}'")
        return {"ok": False, "data": None, "error": f"알 수 없는 도구: {name}"}
