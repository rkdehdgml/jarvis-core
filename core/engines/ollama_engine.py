"""Ollama 로컬 LLM 서버를 호출하는 AI 폴백 엔진.

GroqEngine과 동일한 인터페이스(ask / generate / describe)를 구현해
skill_ai_chat.py의 _FallbackEngine 또는 단독 엔진으로 사용할 수 있다.

Ollama OpenAI-호환 API(/v1/chat/completions)를 requests로 직접 호출한다.
openai SDK는 불필요하다.

환경변수:
  OLLAMA_HOST  — Ollama 서버 주소 (기본: localhost:11434)
  OLLAMA_MODEL — 사용할 모델명   (기본: qwen2.5:7b)
"""
import logging
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_PERSONA_PATH = Path(__file__).parent.parent.parent / "config" / "persona.md"

_DEFAULT_HOST  = "localhost:11434"
_DEFAULT_MODEL = "qwen2.5:7b"
_MAX_TOKENS    = 1024
_TIMEOUT       = 60

_FOREIGN_SCRIPT = re.compile("[一-鿿㐀-䶿぀-ゟ゠-ヿ]")


class OllamaEngine:
    """jarvis-core의 로컬 AI 폴백 엔진 (Ollama 버전)."""

    def __init__(self) -> None:
        raw_host = os.getenv("OLLAMA_HOST", _DEFAULT_HOST)
        self._host = raw_host if raw_host.startswith("http") else f"http://{raw_host}"
        self._model = os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)
        self._persona = self._load_persona()

    def ask(self, text: str) -> str:
        """사용자 입력을 Ollama에 전달해 응답 텍스트를 받는다 (시스템 프롬프트=persona.md)."""
        return self._complete(text, system=self._persona)

    def generate(self, prompt: str, system: str | None = None) -> str:
        """persona.md에 system을 보강해 Ollama를 호출한다."""
        if system and self._persona:
            combined = f"{self._persona}\n\n{system}"
        else:
            combined = system or self._persona
        return self._complete(prompt, system=combined)

    def _complete(self, text: str, system: str) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": text})

        try:
            resp = requests.post(
                f"{self._host}/v1/chat/completions",
                json={
                    "model": self._model,
                    "messages": messages,
                    "max_tokens": _MAX_TOKENS,
                    "stream": False,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            content: str = resp.json()["choices"][0]["message"]["content"] or ""
            content = _FOREIGN_SCRIPT.sub("", content).strip()
            return content or "응답이 비어 있습니다."
        except requests.exceptions.ConnectionError:
            logger.error(f"Ollama 연결 실패: {self._host}")
            return (
                f"Ollama 서버에 연결할 수 없습니다. "
                f"데스크탑에서 'ollama serve'를 실행했는지 확인해주세요. "
                f"(설정 호스트: {self._host})"
            )
        except requests.exceptions.Timeout:
            logger.error("Ollama 응답 타임아웃")
            return "Ollama 응답 시간이 초과됐습니다. 모델이 로딩 중이거나 서버가 바쁜 상태입니다."
        except Exception as exc:
            logger.error(f"OllamaEngine 오류: {exc}")
            return f"Ollama 엔진 오류: {exc}"

    def describe(self) -> dict:
        """UI 패널에 보여줄 엔진 식별 정보."""
        connected = False
        try:
            r = requests.get(f"{self._host}/api/tags", timeout=3)
            connected = r.status_code == 200
        except Exception:
            pass
        return {
            "provider": "Ollama",
            "model": self._model,
            "connected": connected,
            "usagePercent": 0,
        }

    def _load_persona(self) -> str:
        try:
            return _PERSONA_PATH.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            logger.warning(f"persona.md 를 찾을 수 없습니다: {_PERSONA_PATH}")
            return ""
