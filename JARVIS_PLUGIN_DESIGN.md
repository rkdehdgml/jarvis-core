# jarvis-core — 플러그인/스킬 기반 개인 AI 비서 설계서

> Windows 네이티브 · 무료 · Claude Code CLI 단일 엔진
> 핵심 원칙: **본체는 절대 안 건드린다. 기능은 파일 하나(skill)로 추가한다.**
> 프로젝트명: jarvis-core

---

## 1. 설계 철학

자비스를 "기능 모음"이 아니라 **"기능을 꽂는 틀"**로 만든다.

- 본체(Core)는 입력 → 라우팅 → 실행 → 출력의 **파이프라인만** 담당한다.
- 실제 기능(가계부, Git, 볼륨조절 등)은 전부 **스킬 파일**로 분리한다.
- 화면(UI)도 본체에서 분리한다. 본체는 "상태 이벤트"만 던지고, 화면은 그걸 받아 그린다.
- 입력 채널(음성/채팅)도 본체에서 분리한다. 본체는 "텍스트가 들어왔다"는
  사실만 알면 되고, 그게 STT를 거친 음성인지 채팅창 입력인지는 구분하지 않는다.
- 스킬은 폴더에 파일을 넣으면 **자동 등록**된다. 본체 코드 수정 없음.
- 새 기능 추가 = 새 파일 1개 작성. 기능 제거 = 파일 삭제.

이건 JHipster에서 쓰던 공유 컴포넌트 아키텍처와 같은 발상이다.
컴포넌트를 갈아끼우듯, 스킬을 갈아끼운다.

---

## 2. 전체 아키텍처

```
┌──────────────────────────────────────────────┐
│                   CORE (본체)                   │
│                                                │
│   입력 → 인텐트 라우터 → 스킬 디스패처 → 출력      │
│                            │                    │
│                   ┌────────┴────────┐           │
│                   │  스킬 레지스트리   │           │
│                   │ (자동 로딩/등록)   │           │
│                   └────────┬────────┘           │
│                            │                    │
│                   상태 이벤트 발행 ───────┐        │
└────────────────────────────┼────────────┼───────┘
                             │            │
        ┌────────────────────┼──────┐     ▼
        │                    │      │  ┌──────────┐
   ┌────▼────┐         ┌─────▼─────┐│  │ UI 레이어  │
   │ skill_  │         │  skill_   ││  │(미니멀/풀) │
   │ volume  │         │  git      ││  └──────────┘
   │ .py     │         │  .py      ││
   └─────────┘         └───────────┘│  ...계속 추가
```

핵심은 가운데 **스킬 레지스트리**다.
이게 `skills/` 폴더를 스캔해서 모든 스킬을 자동으로 읽어들인다.

복잡한 자연어 추론이 필요하면 **Claude Code CLI** 하나로 처리한다.
별도 로컬 모델이나 외부 API는 쓰지 않는다. 엔진은 Claude Code 단일.

화면도 같은 원칙으로 분리된다. 본체는 "지금 듣는 중", "이 응답 표시해" 같은
상태 이벤트만 발행하고, UI 레이어가 그걸 구독해서 화면에 그린다.

---

## 3. 스킬의 표준 구조 (계약/Interface)

모든 스킬은 똑같은 모양을 가진다. 이 "약속"만 지키면 본체가 알아서 인식한다.

```python
# skills/skill_example.py

from core.skill_base import Skill, SkillResult

class ExampleSkill(Skill):
    # 1) 메타데이터 — 라우터가 이걸로 어떤 스킬인지 판단
    name = "example"
    description = "이 스킬이 무슨 일을 하는지 한 줄 설명"
    triggers = ["예시", "테스트", "example"]   # 매칭 키워드
    examples = ["예시 실행해줘", "테스트 해봐"]   # 라우팅 학습용 예문

    # 2) 이 명령을 내가 처리할 수 있는지 판단
    def can_handle(self, intent: str, text: str) -> float:
        # 0.0 ~ 1.0 사이 신뢰도 반환. 높을수록 "내가 처리함"
        ...

    # 3) 실제 실행
    def execute(self, text: str, context: dict) -> SkillResult:
        # 작업 수행 후 결과 반환
        return SkillResult(
            speech="작업을 완료했습니다",   # 음성으로 말할 내용
            data={...},                    # 부가 데이터
            success=True
        )
```

이 4가지(메타데이터, can_handle, execute, 반환형)만 지키면
어떤 기능이든 자비스에 꽂힌다.

---

## 4. 폴더 구조

```
jarvis-core/
├── main.py                  # 진입점
├── config/
│   ├── settings.yaml        # 전역 설정
│   └── persona.md           # 자비스 말투/성격 프롬프트
│
├── core/                    # ⚠️ 본체 — 거의 안 건드림
│   ├── skill_base.py        # Skill 추상 클래스, SkillResult 정의
│   ├── registry.py          # skills/ 폴더 자동 스캔·로딩
│   ├── router.py            # 어느 스킬이 처리할지 결정
│   ├── dispatcher.py        # 선택된 스킬 실행
│   ├── context.py           # 대화 맥락/세션 메모리
│   ├── status_events.py     # UI로 보낼 상태 이벤트 정의/발행
│   ├── input_channel.py     # 입력 채널 추상화 (음성/채팅 → 동일한 텍스트로 통합)
│   └── engines/
│       └── claude_code.py   # Claude Code CLI subprocess 호출 (단일 엔진)
│
├── voice/                   # 음성 입출력 레이어
│   ├── stt.py               # 음성 인식 (faster-whisper)
│   ├── tts.py                # 음성 합성 (edge-tts)
│   ├── wakeword.py           # 핫워드 "자비스" (openWakeWord)
│   └── text_input.py         # 텍스트 입력(개발/디버그용, CLI 콘솔)
│
├── ui/                       # 화면 레이어 (웹 대시보드)
│   ├── server.py             # FastAPI + WebSocket, 상태 이벤트 푸시 + 채팅 입력 수신
│   └── web/                  # React + TS 프론트엔드
│       ├── hooks/
│       │   └── useJarvisStatus.ts   # 공유 상태 훅 (두 모드가 같이 구독)
│       └── components/
│           ├── JarvisMinimal.tsx    # 미니멀 모드 (작은 패널, 클릭 시 펼침)
│           ├── JarvisFull.tsx       # 풀 모드 (중앙 원형 코어 + 좌우 패널)
│           └── ChatInput.tsx        # 풀 모드 대화 로그 하단 입력창
│
├── skills/                   # ⭐ 여기에 파일만 넣으면 기능 추가됨
│   ├── skill_volume.py
│   ├── skill_app_launch.py
│   ├── skill_git.py
│   ├── skill_ledger.py
│   ├── skill_weather.py
│   ├── skill_ai_chat.py      # 폴백: 아무도 못 잡으면 Claude Code로
│   └── ...
│
└── data/                      # 스킬들이 쓰는 저장소 (가계부 DB 등)
```

**`core/`와 `voice/`는 한 번 만들면 거의 안 건드린다.**
일상은 전부 `skills/`에 파일을 추가하는 작업이다.

---

## 5. 라우팅 동작 방식 (핵심 메커니즘)

명령이 들어오면 본체는 이렇게 처리한다:

```
1. 입력 수신:  "깃 커밋해줘"
        │
2. 레지스트리의 모든 스킬에게 물어봄:
     skill_volume.can_handle()  → 0.0
     skill_git.can_handle()     → 0.9   ← 당첨
     skill_ledger.can_handle()  → 0.1
        │
3. 가장 높은 점수 스킬 선택 (단, 임계값 미달이면 → AI 폴백)
        │
4. skill_git.execute() 실행
        │
5. SkillResult.speech 를 TTS로 음성 출력 + 상태 이벤트로 UI에도 전달
```

**2단계 라우팅 전략:**

| 우선순위 | 방식 | 처리 대상 |
|---------|------|----------|
| 1차 | 키워드/규칙 매칭 | "볼륨 올려" 같은 명확한 명령 → 즉시 로컬 실행 |
| 폴백 | Claude Code CLI | 아무도 못 잡거나 복잡한 작업 → AI에게 위임 |

명확한 명령은 키워드로 즉시 로컬 처리해 빠르게 응답하고,
애매하거나 복잡한 자연어만 Claude Code 폴백으로 넘긴다.
이렇게 하면 단순 명령의 응답 속도를 살리면서 Claude Code 사용량도 아낀다.

---

## 6. 화면(UI) 레이어 설계

영화 자비스의 시각적 정체성을 살리기 위해 두 가지 모드를 만든다.
둘은 완전히 다른 화면이 아니라, **같은 상태 데이터를 다르게 그리는 두 개의 뷰**다.

### 6-1. 미니멀 모드

- 평소 화면 한 귀퉁이에 항상 떠 있는 작은 패널.
- 작은 원형 코어 아이콘 + 상태 텍스트 한 줄로 구성.
- 클릭하면 같은 패널이 아래로 펼쳐져 엔진 상태, 최근 대화, 스킬 목록을 보여줌.
- 다시 클릭하면 접혀서 원래 크기로 돌아감.
- 펼침/접힘은 순수 UI 상태(로컬 state)이며 본체와 무관하다.

### 6-2. 풀 모드

- 자세히 들여다보고 싶을 때 여는 메인 화면. 영화 속 메인 HUD 느낌.
- 레이아웃: 좌측 정보 패널 — 중앙 원형 코어 — 우측 정보 패널, 그 아래 음성 파형, 그 아래 대화 로그.
- 좌측 패널: 자비스 자체 상태 (엔진 연결 상태, 사용량 게이지, 활성 스킬 수).
- 중앙 원형 코어: 회전하는 이중 링 + 상태 텍스트. 점 등 불필요한 장식 요소는 넣지 않는다.
  중앙 텍스트는 상태에 따라 동적으로 바뀐다:

  | 본체 상태 | 메인 텍스트 | 서브 텍스트 |
  |----------|-----------|-----------|
  | idle | 대기 중 | STANDBY |
  | listening | 듣고 있습니다 | LISTENING |
  | processing | 처리 중... | PROCESSING |
  | responded | (마지막 응답 요약) | DONE |

  링 회전 속도/펄스 강도도 상태에 맞춰 변한다 (listening은 빠르게, processing은 강한 펄스, idle은 느긋하게).
- 우측 패널: 시스템·결과 정보 (CPU, 메모리, 마지막 응답).
- 파형: 음성 입력 시각화. 평소엔 잔잔하고 실제 듣는 중엔 막대가 움직인다.
- 대화 로그: 파형 바로 아래. **사용자 발화는 오른쪽 회색 버블, 자비스 응답은 왼쪽 사이언 버블.**
  스크롤 가능한 영역으로 두어 대화가 길어져도 전체 패널 높이는 고정된다.

### 6-3. 공유 상태 구조

두 모드는 같은 데이터를 구독한다. 모드 전환 시 데이터를 다시 불러오지 않는다.

```
useJarvisStatus()  ← 공유 훅, 모든 상태를 들고 있음
   ├── engineStatus      (Claude Code 연결 여부)
   ├── usageToday        (사용량 %)
   ├── activeSkills       (등록된 스킬 목록)
   ├── systemInfo         (CPU/메모리)
   ├── currentState       (idle | listening | processing | responded)
   ├── lastResponse       (마지막 응답 텍스트)
   └── conversationLog    (대화 기록 배열)
        │
   ┌────┴────┐
   │         │
JarvisMinimal  JarvisFull   ← 같은 훅을 구독, 다르게 배치만 함
```

본체(`core/status_events.py`)는 이 데이터를 WebSocket으로 푸시하기만 하고,
어떤 모드로 보여줄지는 전적으로 프론트엔드가 결정한다.

---

## 7. 입력 채널 설계 (음성 + 채팅)

마이크가 없거나, STT가 실패하거나, 조용히 작업해야 하는 상황을 위해
음성 외에 채팅으로도 명령을 입력할 수 있게 한다. 핵심은 본체가
입력 출처를 구분하지 않도록 만드는 것이다.

### 7-1. 입력 채널 추상화

```
        음성 경로                    채팅 경로
   마이크 → wakeword → STT      ChatInput.tsx → ui/server.py
            │                              │
            └──────────┬───────────────────┘
                        ▼
              core/input_channel.py
              (channel: "voice" | "chat" 태그만 붙여 통일)
                        │
                        ▼
                   Router / Dispatcher
              (channel 태그는 거의 신경 안 씀)
```

`core/input_channel.py`는 어디서 들어온 텍스트든
`{ text: str, channel: "voice" | "chat" }` 형태로 통일해서 Router에 넘긴다.
Router·Dispatcher·스킬은 channel 값을 거의 사용하지 않는다.
필요한 경우(예: 채팅으로 들어온 명령엔 TTS 음성 출력을 생략하고
텍스트 응답만 준다)에만 참고용으로 쓴다.

### 7-2. 음성 ↔ 채팅 전환

두 가지 전환 방식을 모두 지원한다.

- **자동 감지**: 마이크 권한이 없거나, STT 호출이 일정 횟수
  (예: 연속 3회) 실패하면 자동으로 채팅 모드로 전환하고
  상태 이벤트로 "음성 인식을 사용할 수 없어 채팅 모드로
  전환합니다" 를 UI에 알린다.
- **수동 토글**: 화면(미니멀/풀 모드 공통)에 마이크/채팅 아이콘을
  두어 사용자가 언제든 직접 전환할 수 있게 한다. 이건 자동 감지가
  실패하거나 사용자가 의도적으로 조용히 쓰고 싶을 때의 백업이다.

전환 상태도 `core/status_events.py`의 상태 이벤트에 포함시켜,
화면이 현재 입력 모드(음성 대기 중 / 채팅 모드)를 표시할 수 있게 한다.

### 7-3. 채팅 입력창 위치

풀 모드(`JarvisFull.tsx`)의 대화 로그 영역 바로 아래에 입력창을 둔다.
입력창에서 보낸 메시지는 대화 로그에 사용자 발화(오른쪽 회색 버블)로
즉시 추가되고, 같은 channel="chat" 태그로 본체에 전달된다.
응답이 오면 평소처럼 왼쪽 사이언 버블로 표시된다.

미니멀 모드는 펼쳤을 때도 입력창을 따로 두지 않는다. 명령을 직접
입력해야 할 정도로 자세히 다루고 싶다면 풀 모드를 열도록 유도한다.
화면이 두 개로 쪼개지는 느낌을 피하기 위한 의도적인 단순화다.

---

## 8. 왜 이 구조가 강력한가

- **확장성**: 기능 100개여도 본체 코드는 그대로. `skills/`에 파일만 쌓임.
- **격리성**: 한 스킬이 터져도 다른 스킬·본체는 멀쩡. (개별 try/except)
- **재사용성**: 스킬 파일 하나를 다른 프로젝트로 복붙 가능.
- **테스트 용이**: 스킬 하나만 떼서 단독 테스트 가능.
- **화면 교체 자유**: 미니멀 ↔ 풀 모드는 같은 상태를 다르게 그리는 것뿐이라, 본체를 안 건드리고 화면을 마음대로 바꿀 수 있다.
- **입력 채널 자유**: 음성이 안 되는 환경에서도 채팅 하나만으로 동일하게 동작한다. 입력 경로가 늘어나도 Router/Dispatcher는 그대로다.
- **AI 친화적**: Claude Code에게 "skill_xxx.py 새로 만들어줘"라고 시키면
  본체를 모른 채로도 기능 추가 가능. 이게 가장 큰 장점.

마지막 항목이 핵심이다. 표준 구조가 정해져 있으니
**자비스 스스로 자기 기능을 추가하는 것**도 가능해진다.

---

## 9. 단계별 구현 프롬프트

아래는 Claude Code에게 순서대로 던질 프롬프트다.
각 단계는 이전 단계가 끝난 뒤 실행한다. **한 번에 다 던지지 말 것.**

먼저 이 설계서 자체를 프로젝트 폴더에 두고, Claude Code를 그 폴더에서 실행한 뒤
첫 명령으로 이렇게 던지는 것을 권장한다:

```
이 폴더의 JARVIS_PLUGIN_DESIGN.md 를 읽어줘. 앞으로 이 설계서를
기준으로 단계별로 구현할 거야. 지금은 STEP 0만 진행해줘.
```

---

### STEP 0 — 프로젝트 뼈대 생성

```
Windows 네이티브 환경(Python 3.11+)에서 동작하는 개인 AI 비서
"jarvis-core" 의 프로젝트 뼈대를 만들어줘. 다음 폴더 구조를 생성하고
각 폴더에 빈 __init__.py 와 역할을 적은 주석만 넣어줘. 아직 로직은
구현하지 마.

jarvis-core/
├── main.py
├── config/ (settings.yaml, persona.md)
├── core/ (skill_base.py, registry.py, router.py, dispatcher.py,
│          context.py, status_events.py, engines/claude_code.py)
├── voice/ (stt.py, tts.py, wakeword.py, text_input.py)
├── ui/ (server.py, web/)
├── skills/
└── data/

requirements.txt 도 만들되, 지금 단계에서 확실한 의존성만 넣어줘.
가상환경(venv) 생성 및 활성화 방법을 README.md에 Windows PowerShell
기준으로 적어줘.
```

---

### STEP 1 — 스킬 계약(Interface) 정의

```
core/skill_base.py 를 구현해줘. 모든 스킬이 상속할 추상 클래스 Skill 과
실행 결과를 담는 SkillResult 데이터클래스를 정의한다.

Skill 클래스 요구사항:
- 클래스 속성: name(str), description(str), triggers(list[str]),
  examples(list[str])
- 추상 메서드 can_handle(self, intent: str, text: str) -> float
  (0.0~1.0 신뢰도 반환)
- 추상 메서드 execute(self, text: str, context: dict) -> SkillResult

SkillResult 요구사항:
- speech(str): 음성으로 말할 내용
- data(dict): 부가 데이터, 기본 빈 dict
- success(bool): 성공 여부
- follow_up(bool): 이어서 대화 대기할지 여부, 기본 False

타입힌트와 docstring을 충실히 달아줘. 이 파일은 본체의 핵심 계약이라
나중에 거의 안 바뀔 거야.
```

---

### STEP 2 — 스킬 자동 로딩 레지스트리

```
core/registry.py 를 구현해줘. skills/ 폴더를 스캔해서 Skill 을 상속한
모든 클래스를 자동으로 import 하고 인스턴스화해 리스트로 보관하는
SkillRegistry 클래스를 만든다.

요구사항:
- skills/ 안의 skill_*.py 파일을 동적 import (importlib 사용)
- 각 모듈에서 Skill 하위 클래스를 찾아 인스턴스 생성
- 한 스킬 로딩이 실패해도 나머지는 정상 로딩 (개별 try/except + 로그)
- get_all_skills() 로 등록된 스킬 목록 반환
- reload() 로 런타임 중 재스캔 가능 (스킬 추가 시 재시작 불필요)

본체를 안 건드리고 파일만 추가하면 기능이 늘어나는 게 이 파일의 목적이야.
```

---

### STEP 3 — 라우터 + 디스패처

```
core/router.py 와 core/dispatcher.py 를 구현해줘.

router.py - Router 클래스:
- 입력 텍스트를 받아 레지스트리의 모든 스킬에 can_handle() 을 호출
- 가장 높은 신뢰도의 스킬을 선택
- 최고 점수가 임계값(예: 0.4) 미만이면 None 반환 (→ AI 폴백 대상)

dispatcher.py - Dispatcher 클래스:
- router 가 고른 스킬의 execute() 를 호출
- 스킬 실행이 예외를 던져도 본체가 죽지 않게 감싸기
- 선택된 스킬이 없으면 폴백 스킬(skill_ai_chat)로 넘김
- 실행 결과 SkillResult 를 반환

두 클래스 모두 context(dict) 를 주고받아 대화 맥락을 유지할 수 있게 해줘.
```

---

### STEP 4 — Claude Code 엔진 래퍼 (폴백 두뇌)

```
core/engines/claude_code.py 를 구현해줘. Claude Code CLI 를 headless 모드로
subprocess 호출하는 ClaudeCodeEngine 클래스를 만든다.

요구사항:
- claude -p "프롬프트" 형태로 호출 (Windows 네이티브 PowerShell 환경)
- 표준출력으로 응답 텍스트를 받아 반환
- 타임아웃 설정 (예: 60초)
- 환경변수 격리: 필요한 키만 화이트리스트로 전달하고 나머지는 차단
- 호출 실패/타임아웃 시 graceful 한 에러 메시지 반환
- config/persona.md 의 자비스 말투 프롬프트를 시스템 컨텍스트로 앞에 붙임

이건 키워드 스킬이 아무도 못 잡았을 때 쓰는 최종 폴백 두뇌야.
jarvis-core 의 유일한 AI 엔진이다.
```

---

### STEP 5 — 첫 스킬 2개 (검증용)

```
플러그인 구조가 동작하는지 검증하기 위해 스킬 2개를 만들어줘.
core/skill_base.py 의 Skill 인터페이스를 정확히 따라야 해.

1) skills/skill_app_launch.py
   - "크롬 열어", "메모장 실행" 같은 명령으로 Windows 앱 실행
   - triggers: ["열어", "실행", "켜줘"]
   - subprocess 로 앱 실행, 성공 시 "OO 실행했습니다" 음성 반환

2) skills/skill_ai_chat.py  (폴백 스킬)
   - can_handle 은 항상 낮은 점수(0.1) 반환 → 최후의 수단
   - execute 에서 STEP 4의 ClaudeCodeEngine 을 호출해 자연어 응답
   - 어떤 명령도 못 잡혔을 때 이 스킬이 받아 처리

두 스킬을 skills/ 에 넣기만 하면 registry 가 자동 인식하는지 확인할 수 있게
간단한 테스트 코드도 같이 만들어줘.
```

---

### STEP 6 — 텍스트 기반 메인 루프 (MVP)

```
main.py 를 구현해줘. 아직 음성과 화면은 빼고, 텍스트 입출력으로만 도는
자비스 MVP 를 완성한다. 이 텍스트 입력은 단순 디버그용이 아니라,
나중에 채팅 채널의 토대가 될 정식 입력 경로다.

흐름:
1. SkillRegistry 로 모든 스킬 로딩
2. 콘솔에서 사용자 텍스트 입력 받기 (voice/text_input.py)
3. Router 로 처리할 스킬 선택
4. Dispatcher 로 실행
5. SkillResult.speech 를 일단 print 로 출력
6. "종료"라고 입력할 때까지 반복

이 단계가 끝나면 텍스트로 명령 → 스킬 실행 → 응답이 도는
완전한 뼈대가 완성돼. 음성과 화면은 다음 단계에서 이 자리에
끼우면 돼.
```

---

### STEP 7 — 음성 입출력 끼우기

> ⚠️ **Windows 네이티브 필수**: 이 STEP은 WSL에서 코드만 작성해도
> 실제 마이크/스피커 동작 검증이 불가능하다. WSL에서 개발 중이라면
> STEP 9~14를 먼저 끝내고, 이 STEP은 Windows 네이티브 환경으로
> 전환한 뒤 진행할 것 (자세한 이유는 섹션 10의 "WSL ↔ Windows
> 네이티브 작업 분리" 참고).

```
voice/stt.py 와 voice/tts.py 를 구현하고 main.py 에 연결해줘.

voice/stt.py - faster-whisper 사용:
- base 모델로 마이크 입력을 한국어 텍스트로 변환
- silero-vad 로 발화 구간만 잘라 처리 (CPU 동작 전제)

voice/tts.py - edge-tts 사용:
- 한국어 음성으로 텍스트를 읽어줌
- 자연스러운 한국어 보이스 선택

main.py 수정:
- 텍스트 input() 자리에 stt.listen() 을 끼움
- print() 자리에 tts.speak() 를 끼움
- 단, 디버그용으로 텍스트 모드도 플래그로 전환 가능하게 유지

본체/스킬은 전혀 안 건드리고 입출력 레이어만 교체하는 거야.
```

---

### STEP 8 — 핫워드 "자비스" 상시 대기

> ⚠️ **Windows 네이티브 필수**: STEP 7과 같은 이유로, 마이크 상시
> 감지는 WSL에서 검증할 수 없다. STEP 7과 묶어서 Windows 네이티브
> 환경으로 전환한 뒤 함께 진행할 것.

```
voice/wakeword.py 를 구현하고 main.py 에 연결해줘.

요구사항:
- openWakeWord 로 "자비스" 웨이크워드 상시 감지
- 평소엔 웨이크워드만 듣다가, 감지되면 STT 활성화
- 호출 → 명령 수행 → 다시 대기 상태로 복귀
- SkillResult.follow_up 이 True 면 웨이크워드 없이 이어서 듣기

이게 끝나면 "자비스" 부르고 명령하는 영화 같은 경험이 완성돼.
```

---

### STEP 9 — 상태 이벤트 발행 (화면 연결 준비)

```
core/status_events.py 를 구현해줘. 본체가 화면(UI)에 던질 상태 이벤트를
정의하고 발행하는 모듈이다.

요구사항:
- StatusEvent 데이터클래스: state(idle|listening|processing|responded),
  lastResponse(str, optional), timestamp
- StatusBroadcaster 클래스: 이벤트를 구독자(WebSocket 등)에게 전달
- Dispatcher, STT/TTS, wakeword 호출 지점에서 적절한 시점에
  status_events.emit(state=...) 호출하도록 연결
  (예: 웨이크워드 감지 시 listening, 스킬 실행 시작 시 processing,
   SkillResult 반환 시 responded)
- 화면이 아직 없어도 콘솔에 상태 변화를 로그로 찍어 동작 확인 가능하게

이 STEP은 본체가 "지금 무슨 상태인지"를 외부에 알릴 수 있게 만드는
준비 단계야. 다음 STEP에서 이걸 실제 화면에 연결할 거야.
```

---

### STEP 10 — UI 서버 (FastAPI + WebSocket)

```
ui/server.py 를 구현해줘. FastAPI 로 로컬 웹서버를 띄우고, WebSocket
엔드포인트로 core/status_events.py 의 StatusBroadcaster 가 발행하는
이벤트를 프론트엔드에 실시간으로 푸시한다.

요구사항:
- /ws 엔드포인트: 연결되면 현재 상태를 즉시 한 번 보내고,
  이후 상태 변화마다 push
- /api/status 엔드포인트: 현재 상태 스냅샷을 REST로도 조회 가능하게
  (스킬 목록, 엔진 연결 여부, 사용량, 시스템 정보 포함)
- CORS 설정으로 로컬 프론트엔드(React dev server)에서 접근 가능하게
- main.py 와 함께 별도 프로세스로 실행되거나, 같은 프로세스 내
  백그라운드 태스크로 떠 있게 구성

본체 로직은 건드리지 않고, status_events 가 발행하는 데이터를
받아서 외부로 중계만 하는 역할이야.
```

---

### STEP 11 — 공유 상태 훅 (useJarvisStatus)

```
ui/web/hooks/useJarvisStatus.ts 를 구현해줘. React + TypeScript 환경에서
ui/server.py 의 WebSocket(/ws)에 연결해 실시간 상태를 구독하는
커스텀 훅이다.

반환해야 하는 상태:
- engineStatus (Claude Code 연결 여부)
- usageToday (사용량 %)
- activeSkills (등록된 스킬 목록)
- systemInfo (CPU/메모리)
- currentState ('idle' | 'listening' | 'processing' | 'responded')
- lastResponse (마지막 응답 텍스트)
- conversationLog (사용자/자비스 발화 배열, 각 항목은 { role, text, timestamp })

요구사항:
- WebSocket 연결이 끊기면 자동 재연결 시도
- 초기 로딩 시 /api/status REST 호출로 스냅샷을 먼저 채우고,
  이후 WebSocket push로 갱신
- 이 훅 하나를 JarvisMinimal과 JarvisFull 컴포넌트가 동일하게 구독한다.
  두 컴포넌트는 이 훅이 반환하는 데이터를 다르게 배치만 하면 돼.
```

---

### STEP 12 — 미니멀 모드 컴포넌트

```
ui/web/components/JarvisMinimal.tsx 를 구현해줘. useJarvisStatus() 훅을
구독하는 작은 패널 컴포넌트다.

요구사항:
- 평소: 작은 원형 코어 아이콘(회전하는 점선 링 + 중앙 작은 원)과
  상태 텍스트 한 줄만 표시. currentState 에 따라 텍스트가
  "대기 중" / "듣고 있습니다" / "처리 중..." / lastResponse 로 바뀜
- 클릭하면 같은 패널 아래로 펼쳐져서 엔진 상태, 활성 스킬 목록,
  최근 대화 일부를 보여줌 (로컬 useState 로 펼침 여부 관리,
  본체와는 무관한 순수 UI 상태)
- 다시 클릭하면 접힘
- 디자인: 어두운 네이비 배경(#050a12 계열), 사이언 블루(#2dd4ee) 발광,
  모노스페이스 폰트
- prefers-reduced-motion 사용자를 위해 애니메이션 비활성화 옵션 포함

이 컴포넌트는 화면 한 귀퉁이에 항상 떠 있는 용도로 쓸 거야.
```

---

### STEP 13 — 풀 모드 컴포넌트

```
ui/web/components/JarvisFull.tsx 를 구현해줘. useJarvisStatus() 훅을
구독하는 메인 화면 컴포넌트다.

레이아웃 (위에서 아래로):
1. 상단 라벨: "J.A.R.V.I.S — FULL MODE" + 현재 시각
2. 3단 그리드: 좌측 정보 패널 / 중앙 원형 코어 / 우측 정보 패널
   - 좌측: 엔진 연결 상태, 사용량 게이지(바), 활성 스킬 수
   - 중앙: 이중 회전 링 SVG (회전 방향 반대로 두 겹) + 중앙 텍스트.
     중앙 텍스트는 currentState 에 따라 동적으로 바뀜
     (idle→대기 중/STANDBY, listening→듣고 있습니다/LISTENING,
      processing→처리 중.../PROCESSING, responded→lastResponse/DONE).
     링 회전 속도와 펄스 강도도 상태에 따라 달라짐
     (listening 빠르게, processing 강한 펄스, idle 느긋하게).
     중앙에 점 같은 장식 요소는 넣지 않음.
   - 우측: CPU, 메모리, 마지막 응답 요약
3. 음성 파형 바 (currentState가 listening일 때 막대가 움직이고,
   그 외엔 잔잔하게 표시)
4. 대화 로그: conversationLog 를 스크롤 가능한 영역에 표시.
   사용자 발화는 오른쪽 회색 버블, 자비스 응답은 왼쪽 사이언 버블.

디자인: 어두운 네이비/블랙 배경, 사이언 블루 발광, 모노스페이스 폰트,
JarvisMinimal과 동일한 색상 톤을 유지해 같은 제품처럼 보이게 함.
prefers-reduced-motion 대응 포함.
```

---

### STEP 14 — 입력 채널 통합 + 채팅 입력창

```
core/input_channel.py 를 구현하고, ui/server.py 와
ui/web/components/ChatInput.tsx 를 추가해줘. 음성과 채팅을
동일한 입력 경로로 통합하는 STEP이다.

core/input_channel.py:
- InputEvent 데이터클래스: text(str), channel("voice" | "chat")
- normalize_input() 함수: STT 결과든 채팅 텍스트든 InputEvent 로
  통일해서 Router 에 넘김
- Router/Dispatcher 는 channel 값을 거의 신경 안 쓰지만,
  channel="chat" 인 경우 TTS 음성 출력은 생략하고 텍스트 응답만
  반환하도록 Dispatcher 에 조건 분기 추가
- STT 가 연속 3회 이상 실패하거나 마이크 권한이 없으면 자동으로
  channel 을 "chat" 으로 전환하고, status_events 로
  "음성 인식을 사용할 수 없어 채팅 모드로 전환합니다" 이벤트 발행

ui/server.py 추가:
- /api/chat POST 엔드포인트: { text: string } 를 받아
  input_channel.normalize_input(text, channel="chat") 으로 처리하고
  결과를 반환 (WebSocket 으로도 동일한 응답을 push)

ui/web/components/ChatInput.tsx:
- JarvisFull.tsx 의 대화 로그 영역 바로 아래에 위치하는 입력창
- 메시지 전송 시 즉시 대화 로그에 사용자 발화(오른쪽 회색 버블)로
  추가하고, /api/chat 으로 전송
- 응답이 오면 왼쪽 사이언 버블로 추가
- 미니멀/풀 모드 공통으로 마이크/채팅 아이콘 토글 버튼도 추가해서
  사용자가 수동으로 입력 모드를 전환할 수 있게 함 (자동 감지의 백업)

이 STEP이 끝나면 마이크 없이도, 또는 음성 인식이 실패하는 환경에서도
채팅만으로 자비스의 모든 기능을 동일하게 쓸 수 있어.
```

---

### STEP 15+ — 스킬 무한 확장 (반복 작업)

```
이제부터는 본체를 안 건드리고 skills/ 에 파일만 추가한다.
새 기능이 필요할 때마다 아래 템플릿으로 Claude Code 에 요청:

"core/skill_base.py 의 Skill 인터페이스를 따르는 새 스킬
 skills/skill_<기능명>.py 를 만들어줘. 기능: <설명>.
 triggers 와 examples 를 적절히 채우고, execute 에서 <동작> 을 수행해줘."

추가하고 싶은 스킬 예시 목록 (괄호 끝의 [WSL]/[Windows] 는 검증 환경):
- skill_volume      : 볼륨 조절 (pycaw) [Windows 필수]
- skill_window      : 창 전환/정렬 (pygetwindow) [Windows 필수]
- skill_git         : git 커밋/푸시/상태 (subprocess) [WSL 가능]
- skill_ledger      : 가계부 음성 기록 (data/ 에 저장) [WSL 가능]
- skill_weather     : 날씨 브리핑 (무료 API) [WSL 가능]
- skill_timer       : 알람/타이머 (APScheduler) [WSL 가능]
- skill_file        : 파일 검색/정리 [경로 차이 있어 Windows에서 재검증]
- skill_clipboard   : 클립보드 자동화 [Windows 필수]
- skill_calendar    : 일정 관리 (Google Calendar API) [WSL 가능]
- skill_briefing    : 모닝 브리핑 (날씨+일정+할일 통합) [WSL 가능]
- skill_email       : 메일 요약/초안 (Gmail API) [WSL 가능]
- skill_system      : CPU/메모리/배터리 상태 보고 (psutil) [Windows에서 재검증 권장]

각 스킬은 독립적이라 순서 상관없이, 필요한 것부터 하나씩 추가하면 돼.
다만 [Windows 필수] 로 표시된 스킬은 WSL에서 작성해도 동작 검증이
안 되니, 그 부분은 Windows 네이티브 환경으로 넘어간 뒤에 작성하거나
최소한 거기서 다시 확인해야 해.
새 스킬을 추가해도 ui/web/hooks/useJarvisStatus.ts 의 activeSkills 목록에
자동으로 반영되므로, 화면(미니멀/풀 모드)도 따로 손댈 필요 없다.
```

---

## 10. 구현 순서 요약

| 단계 | 내용 | 결과물 | 본체 수정? | 검증 환경 |
|------|------|--------|-----------|----------|
| STEP 0 | 뼈대 생성 | 폴더 구조 | - | WSL 가능 |
| STEP 1 | 스킬 계약 정의 | skill_base.py | ✅ (1회) | WSL 가능 |
| STEP 2 | 자동 로딩 | registry.py | ✅ (1회) | WSL 가능 |
| STEP 3 | 라우팅 | router/dispatcher | ✅ (1회) | WSL 가능 |
| STEP 4 | AI 폴백 | claude_code.py | ✅ (1회) | WSL 가능 |
| STEP 5 | 첫 스킬 2개 | 검증 | ❌ | WSL 가능 |
| STEP 6 | 텍스트 MVP | 동작하는 뼈대 | ✅ (마지막) | WSL 가능 |
| STEP 9 | 상태 이벤트 | status_events.py | ⚠️ (core 소폭) | WSL 가능 |
| STEP 10 | UI 서버 | FastAPI/WebSocket | ❌ (ui만) | WSL 가능 (단, pip 설치 가능해야) |
| STEP 11 | 공유 상태 훅 | useJarvisStatus | ❌ (ui만) | WSL 가능 |
| STEP 12 | 미니멀 모드 | JarvisMinimal | ❌ (ui만) | WSL 가능 |
| STEP 13 | 풀 모드 | JarvisFull | ❌ (ui만) | WSL 가능 |
| STEP 14 | 입력 채널 통합 | input_channel.py + 채팅창 | ⚠️ (core 소폭 + ui) | WSL 가능 |
| STEP 7 | 음성 입출력 | 음성 자비스 | ⚠️ (voice만) | **Windows 네이티브 필수** |
| STEP 8 | 핫워드 | "자비스" 호출 | ⚠️ (voice만) | **Windows 네이티브 필수** |
| STEP 15+ | 스킬 확장 | 무한 기능 | ❌ 영원히 | 스킬별 다름 (아래 참고) |

> "WSL 가능"으로 표시된 STEP도 fastapi·uvicorn·psutil 등 외부
> 패키지가 필요하면 그 WSL 세션에 pip 설치 권한이 있어야 실제
> 동작 검증이 가능하다. pip/sudo 가 막혀 있는 경우의 대응은
> 아래 "WSL 개발 환경의 패키지 설치 제약" 항목을 참고할 것.

**STEP 6 이후로는 본체를 거의 안 건드린다.**
STEP 9와 STEP 14는 각각 상태 이벤트와 입력 채널 통합을 위해
core를 살짝 끼워넣는 두 차례의 예외이고, STEP 10~13은 전부
`ui/` 폴더 안에서만 작업한다.
STEP 15부터는 평생 `skills/` 폴더에 파일만 추가하는 작업이다.

### WSL ↔ Windows 네이티브 작업 분리

코딩은 WSL에서, 실제 운영은 Windows 네이티브에서 하는 경우
(예: 평소 개발은 WSL이 익숙하지만 자비스는 Windows에서 돌리는 경우),
**표의 STEP 번호 순서가 아니라 "검증 환경" 기준으로 순서를 재배치**한다.

```
WSL에서 먼저 진행:
  STEP 0 → 1 → 2 → 3 → 4 → 5 → 6 → 9 → 10 → 11 → 12 → 13 → 14
  (텍스트+채팅으로 자비스가 완전히 동작하는 상태까지 완성)

Windows 네이티브로 전환 후:
  STEP 7 → 8
  (음성, 핫워드)
  + skill_volume, skill_window 등 Windows 전용 라이브러리(pycaw,
    pygetwindow 등)를 쓰는 스킬들도 이 시점에 작성/검증
```

이렇게 순서를 바꾸는 이유는 단순하다. `pycaw`, `pygetwindow` 같은
Windows 전용 라이브러리는 WSL에 설치조차 안 되고, faster-whisper의
오디오 장치 접근 방식도 WSL과 Windows에서 다르게 동작한다.
WSL에서 STEP 7~8을 미리 진행하면 "코드는 작성됐지만 실제로는
아무것도 검증되지 않은" 상태가 되어, Windows로 옮긴 뒤 다시
뜯어고치게 될 위험이 크다.

반대로 텍스트/채팅 경로(STEP 9~14)는 OS에 의존하지 않는 순수
파이썬/타입스크립트 로직이라 WSL에서 짜도 Windows에서 그대로 동작한다.
이 부분을 WSL에서 끝까지 완성해 둔 뒤, 음성과 PC 제어 계열만
Windows 네이티브로 넘어가서 마무리하는 것이 가장 효율적인 분리다.

### WSL 개발 환경의 패키지 설치 제약

위 분리는 "WSL에서는 텍스트/채팅 경로를 실제로 동작 검증할 수 있다"는
전제를 깔고 있다. 하지만 사용 중인 WSL 인스턴스에 pip이 설치되어
있지 않거나 sudo 권한이 막혀 있으면, fastapi·uvicorn·psutil 같은
패키지 자체를 설치할 수 없어 이 전제가 깨진다. 이건 자비스 설계의
문제가 아니라 그 WSL 세션 고유의 제약이므로, 막혔을 때 설계서를
다시 고치려 하지 말고 아래 순서로 대응한다.

1. 먼저 sudo 없이 사용자 영역 설치가 되는지 시도한다:
   `pip install --user fastapi uvicorn psutil` 또는
   pip이 없다면 `python3 -m ensurepip --user` 로 pip 자체를
   사용자 영역에 먼저 설치할 수 있는지 확인한다.
2. 그래도 막히면, 해당 STEP은 **"코드만 작성하고 실행/패키지 검증은
   생략"** 으로 진행한다. ast 문법 검사 같은 우회적 확인은 실제
   동작 보증이 거의 없어 시간 대비 효과가 낮으므로 권장하지 않는다.
   본격적인 동작 검증은 Windows 네이티브로 전환하는 시점(STEP 7~8과
   동시)에 venv + pip 으로 한꺼번에 진행한다.
3. 이 제약이 확인되면 해당 시점의 모든 패키지 의존 STEP(특히
   STEP 10 UI 서버, STEP 15+ 의 psutil 등 외부 라이브러리를 쓰는
   스킬들)에 동일하게 적용한다. STEP마다 다시 설치를 시도하며
   시간을 낭비하지 않는다.

---

## 11. 핵심 원칙 4가지

1. **음성·화면보다 텍스트 MVP 먼저** — 파이프라인이 텍스트로 돌면
   음성과 화면은 입출력만 갈아끼우면 된다. 거꾸로 하면 디버깅 지옥.

2. **본체와 스킬/화면/입력채널을 절대 섞지 마라** — 본체는 "틀",
   스킬은 "내용물", 화면은 "보여주는 방식", 입력채널은 "전달 방식"일
   뿐이다. 기능 로직이나 화면 로직, 입력 분기 로직이 core/ 안에서
   서로 엉키기 시작하면 구조가 무너진다.

3. **스킬은 작게, 하나의 일만** — skill_git 이 가계부까지 하면 안 된다.
   하나의 스킬 = 하나의 책임. 그래야 떼고 붙이기가 자유롭다.

4. **음성이 실패해도 자비스는 멈추지 않는다** — 마이크가 없거나
   STT가 흔들려도 채팅으로 똑같이 동작해야 한다. 입력 경로가
   하나뿐이면 그 경로가 막히는 순간 자비스 전체가 멈춘다.