"""jarvis-core 진입점.

현재는 텍스트 입출력만 지원하는 MVP다.
음성(voice/stt.py, voice/tts.py)과 화면(ui/)은 이후 STEP에서 이 자리에 끼워진다.
"""
import logging

from core.registry import SkillRegistry
from core.router import Router
from core.dispatcher import Dispatcher
from core.context import ConversationContext
from core.status_events import broadcaster
from core.input_channel import normalize_input
from voice.text_input import get_input

_EXIT_WORD = "종료"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    registry = SkillRegistry()
    router = Router(registry)
    dispatcher = Dispatcher(registry)
    context = ConversationContext()

    print(f"자비스가 준비됐습니다. ('{_EXIT_WORD}'을 입력하면 종료)")
    broadcaster.emit(state="idle")

    while True:
        broadcaster.emit(state="listening")
        text = get_input()

        if not text:
            continue
        if text == _EXIT_WORD:
            print("자비스를 종료합니다.")
            broadcaster.emit(state="idle")
            break

        # 콘솔 입력은 음성 루프의 토대이므로 channel="voice"로 통일한다.
        # STT 연동 전까지는 print()가 tts.speak()의 자리를 대신한다.
        event = normalize_input(text, channel="voice")
        skill = router.route(event.text)
        result = dispatcher.dispatch(skill, event.text, context, channel=event.channel)
        print(result.speech)


if __name__ == "__main__":
    main()
