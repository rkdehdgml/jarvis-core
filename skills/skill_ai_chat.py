from core.skill_base import Skill, SkillResult
# [ROLLBACK] from core.engines.claude_code import ClaudeCodeEngine as Engine
from core.engines.groq_engine import GroqEngine
from core.engines.ollama_engine import OllamaEngine

# GroqEngine이 RateLimitError 발생 시 반환하는 문자열 (groq_engine.py:141)
_RATE_LIMIT_SIGNAL = "Groq API 요청 한도를 초과했습니다"


class _FallbackEngine:
    """Groq 토큰 소진 시 Ollama로 자동 전환하는 래퍼 엔진.

    GroqEngine.ask()가 _RATE_LIMIT_SIGNAL 문자열을 반환하면
    그 즉시 OllamaEngine으로 전환하고 세션 내 복원하지 않는다.
    (당일 토큰 소진 = 자정까지 Ollama 유지)
    """

    def __init__(self) -> None:
        self._groq = GroqEngine()
        self._ollama: OllamaEngine | None = None  # lazy — Ollama 미사용 시 연결 불필요
        self._use_ollama = False

    def _get_ollama(self) -> OllamaEngine:
        if self._ollama is None:
            self._ollama = OllamaEngine()
        return self._ollama

    def ask(self, text: str) -> str:
        if self._use_ollama:
            return self._get_ollama().ask(text)
        result = self._groq.ask(text)
        if _RATE_LIMIT_SIGNAL in result:
            self._use_ollama = True
            return self._get_ollama().ask(text)
        return result

    def generate(self, prompt: str, system: str | None = None) -> str:
        if self._use_ollama:
            return self._get_ollama().generate(prompt, system)
        result = self._groq.generate(prompt, system)
        if _RATE_LIMIT_SIGNAL in result:
            self._use_ollama = True
            return self._get_ollama().generate(prompt, system)
        return result

    def describe(self) -> dict:
        if self._use_ollama:
            return self._get_ollama().describe()
        return self._groq.describe()


class AiChatSkill(Skill):
    """어떤 스킬도 처리하지 못한 입력을 AI 엔진(Groq → Ollama 자동 폴백)에게 위임한다."""

    name = "ai_chat"
    description = "다른 스킬이 처리하지 못한 자연어 요청을 AI로 응답한다"
    triggers = []
    examples = []

    def __init__(self) -> None:
        self._engine = _FallbackEngine()

    def can_handle(self, intent: str, text: str) -> float:
        # 항상 낮은 점수 → Router 임계값에 못 미쳐 폴백으로만 선택됨
        return 0.1

    def execute(self, text: str, context: dict) -> SkillResult:
        response = self._engine.ask(text)
        return SkillResult(speech=response, success=True)
