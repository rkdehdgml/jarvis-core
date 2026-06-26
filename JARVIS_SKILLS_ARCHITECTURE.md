# JARVIS_SKILLS_ARCHITECTURE.md

> 이 문서는 **설계 문서**다. 코드는 인터페이스 시그니처/스텁 수준까지만 포함하며, 실제 로직 구현은
> 다음 단계의 구현자 에이전트가 맡는다. `JARVIS_PLUGIN_DESIGN.md`가 코어 파이프라인(라우터/디스패처/
> 레지스트리)의 설계 근거를 다루는 문서라면, 이 문서는 그 위에 신규 기능 6개 카테고리를 얹기 위한
> 확장 설계를 다룬다.

## 0. 전제와 범위

- **전제(주어진 컨텍스트 그대로 채택)**: `main.py`(또는 그 후속 엔트리포인트)가 **WSL2(Ubuntu)** 안에서
  Python으로 실행되고, Claude Code CLI도 같은 WSL 세션 안에 설치되어 subprocess로 호출된다. OS 종속
  기능(볼륨/전원/스크린샷/녹화 등)은 WSL에서 직접 실행할 수 없으므로 **Windows 네이티브로 위임**한다.
- **이 전제는 현재 저장소의 실제 런타임과 다르다.** 현재 `CLAUDE.md`/`JARVIS_PLUGIN_DESIGN.md`는
  "jarvis-core는 Windows-native 어시스턴트"라고 명시하고, `skill_volume.py`는 `pycaw`로 Windows COM을
  **직접** 호출한다(WSL Python에서는 동작 불가). 이 불일치는 임의로 한쪽으로 정리하지 않고
  [8. 결정 필요](#8-결정-필요) #1, #2에 질문으로 남긴다. 이 문서의 나머지 부분은 "주어진 컨텍스트(WSL2
  + Windows 위임)"를 전제로 신규 기능만 설계한다.
- **범위 밖**: 기존 4개 스킬(`skill_volume`, `skill_window`, `skill_app_launch`, `skill_app_control`)의
  재작성. 이미 동작하는 코드이므로 이번 설계에서 건드리지 않는다 — 단, WSL 전제와의 충돌은 결정 필요
  항목으로 남긴다.
- **core/는 수정하지 않는다.** `core/skill_base.py`, `core/registry.py` 등 기존 계약은 그대로 두고,
  이 문서에서 추가하는 모든 메타데이터/규약은 "ABC가 강제하지 않는 서브클래스 차원의 관례"로 얹는다.

---

## 1. 디렉터리 구조

```
jarvis-core/
├── .env                            # (gitignore) 모든 API 키 — 신규 키는 §6 참고
├── .env.example
├── core/                           # 절대 수정 없음
│   ├── skill_base.py               #   Skill ABC, SkillResult — 그대로
│   ├── registry.py                 #   skills/ glob 스캔 — 그대로
│   ├── router.py / dispatcher.py   #   그대로
│   ├── context.py                  #   그대로
│   ├── engines/                    #   그대로 (claude_code.py, groq_engine.py)
│   └── ...
├── commands/                       # ★ 신규 — OS 위임 + dict 기반 명령 매핑 전용 레이어
│   ├── __init__.py
│   ├── registry.py                 #   COMMAND_MAP 단일 dict(CommandSpec) + register()
│   ├── windows_bridge.py           #   WSL→Windows 호출의 유일한 통로 (run_command, run_powershell 등)
│   └── specs/                      #   카테고리별 CommandSpec 정의 (registry.py가 이걸 모아 등록)
│       ├── power_specs.py          #     전원(종료/재시작/절전)
│       ├── capture_specs.py        #     스크린샷/화면녹화/음성녹음/웹캠 캡처
│       ├── browser_specs.py        #     URL/유튜브재생/SNS/쇼핑/구글앱 열기
│       └── system_specs.py         #     CPU/RAM/디스크 조회
├── skills/                         # 기존 패턴 그대로 — skill_*.py만 추가하면 auto-discovery 대상
│   │                               #   (기존 8개: ai_chat, app_control, app_launch, clipboard,
│   │                               #              system_info, volume, weather, web_search, window)
│   ├── skill_power.py              # 신규 — 카테고리 1
│   ├── skill_screenshot.py         # 신규 — 카테고리 1
│   ├── skill_screen_record.py      # 신규 — 카테고리 1
│   ├── skill_voice_record.py       # 신규 — 카테고리 1
│   ├── skill_datetime.py           # 신규 — 카테고리 2
│   ├── skill_ip_info.py            # 신규 — 카테고리 2
│   ├── skill_speedtest.py          # 신규 — 카테고리 2
│   ├── skill_system_status.py      # 신규 — 카테고리 2 (CPU/RAM/디스크, Windows 위임 — §8 #2 참고)
│   ├── skill_location.py           # 신규 — 카테고리 2
│   ├── skill_youtube.py            # 신규 — 카테고리 3
│   ├── skill_browser.py            # 신규 — 카테고리 3 (검색/URL/구글앱/SNS/쇼핑 열기)
│   ├── skill_wikipedia.py          # 신규 — 카테고리 3
│   ├── skill_news.py               # 신규 — 카테고리 3
│   ├── skill_howto.py              # 신규 — 카테고리 3 ("~하는 방법", AI 폴백 경유)
│   ├── skill_email.py              # 신규 — 카테고리 4
│   ├── skill_whatsapp.py           # 신규 — 카테고리 4 (§8 #5 참고)
│   ├── skill_pdf_reader.py         # 신규 — 카테고리 5
│   ├── skill_qr.py                 # 신규 — 카테고리 5
│   ├── skill_contacts.py           # 신규 — 카테고리 5
│   ├── skill_camera.py             # 신규 — 카테고리 5
│   ├── skill_joke.py               # 신규 — 카테고리 5
│   ├── skill_schedule.py           # 신규 — 카테고리 5
│   ├── skill_timer.py              # 신규 — 카테고리 5
│   └── skill_sleep_mode.py         # 신규 — 카테고리 5 (§8 #8 참고)
├── data/
│   ├── contacts.json               # 신규 — skill_contacts 로컬 저장
│   ├── schedule.json                # 신규 — skill_schedule 로컬 저장
│   └── qr/                          # 신규 — 생성된 QR 이미지 출력 폴더
├── voice/, ui/                      # 변경 없음
└── tests/
    └── test_commands_registry.py    # 신규 — COMMAND_MAP 무결성(중복 키, 필수 필드) 검사
```

### 카테고리 → 모듈 매핑

| 카테고리 | skill 파일 | `commands/specs/*` 사용 여부 |
|---|---|---|
| 1. 시스템 제어 | `skill_power`, `skill_screenshot`, `skill_screen_record`, `skill_voice_record` | `power_specs`, `capture_specs` |
| 2. 정보 제공 | `skill_datetime`, `skill_ip_info`, `skill_speedtest`, `skill_system_status`, `skill_location` | `system_specs` (system_status만) |
| 3. 웹/미디어 | `skill_youtube`, `skill_browser`, `skill_wikipedia`, `skill_news`, `skill_howto` | `browser_specs` (youtube 재생, browser만) |
| 4. 커뮤니케이션 | `skill_email`, `skill_whatsapp` | 없음 — `skill_whatsapp`은 Windows 보조 프로세스(§8 #5) |
| 5. 유틸리티 | `skill_pdf_reader`, `skill_qr`, `skill_contacts`, `skill_camera`, `skill_joke`, `skill_schedule`, `skill_timer`, `skill_sleep_mode` | `capture_specs` (camera만) |

`commands/`를 쓰지 않는 스킬(날짜/IP/위키피디아/뉴스/이메일/QR/연락처/농담/일정 등)은 전부 **WSL
네이티브에서 그대로 실행 가능** — 순수 Python 로직 또는 외부 REST API 호출이라 OS 위임이 필요 없다.

---

## 2. Skill 인터페이스 계약

`core/skill_base.py`의 `Skill` ABC(`name`/`description`/`triggers`/`examples`/`can_handle()`/`execute()`)는
**그대로 유지**한다. 아래 필드는 ABC가 강제하지 않는, 이 설계에서 새로 도입하는 **서브클래스 관례**다 —
Python은 추가 클래스 속성을 자유롭게 허용하므로 `core/`를 건드리지 않고도 적용할 수 있다.

```python
# skills/skill_<name>.py 공통 관례 (core/skill_base.py는 수정하지 않음)

class Skill(ABC):  # 기존 계약, 참고용 재게시
    name: str
    description: str
    triggers: list[str]
    examples: list[str]

    # --- 이 설계가 추가하는 선택적 관례 ---
    command_ids: tuple[str, ...] = ()
    """이 스킬이 Windows로 위임하는 commands.registry.COMMAND_MAP 키 목록.
    비어 있으면 OS 위임이 필요 없는 순수 WSL 로직(예: skill_joke)이라는 뜻.
    문서화 용도 + tests/test_commands_registry.py 가 "스킬이 참조하는 모든
    command_id가 COMMAND_MAP에 실재하는지" 검증할 때 쓴다."""
```

OS 위임이 필요한 스킬의 표준 형태(예: `skill_power.py` 스텁):

```python
from core.skill_base import Skill, SkillResult
from commands.windows_bridge import run_command

# "자연어 명령 → command_id" 매핑. 이 스킬이 다루는 하위 명령이 여러 개일 때
# if/elif 체인 대신 dict로 분기한다 (§3의 COMMAND_MAP과는 별개의, 스킬 로컬 dict).
_PHRASE_TO_COMMAND: dict[str, str] = {
    "종료": "POWER_SHUTDOWN",
    "꺼줘": "POWER_SHUTDOWN",
    "재시작": "POWER_RESTART",
    "재부팅": "POWER_RESTART",
    "절전": "POWER_SLEEP",
}

class PowerSkill(Skill):
    name = "power"
    description = "컴퓨터를 종료/재시작/절전 모드로 전환한다"
    triggers = ["종료", "재시작", "절전", "재부팅"]
    examples = ["컴퓨터 종료해줘", "재시작해줘", "절전모드로 바꿔줘"]
    command_ids = ("POWER_SHUTDOWN", "POWER_RESTART", "POWER_SLEEP")

    def can_handle(self, intent: str, text: str) -> float: ...
        # 기존 app_control.py와 동일한 패턴: 모호하면 낮은 점수, 명확하면 0.9

    def _resolve_command_id(self, text: str) -> str | None: ...
        # _PHRASE_TO_COMMAND 순회, 가장 먼저 매칭되는 키워드의 command_id 반환

    def execute(self, text: str, context: dict) -> SkillResult:
        command_id = self._resolve_command_id(text)
        if command_id is None:
            return SkillResult(speech="어떤 동작인지 알 수 없습니다.", success=False)
        result = run_command(command_id)   # commands/windows_bridge.py 진입점, 예외를 던지지 않음
        return SkillResult(speech=..., success=result.ok, data={"command_id": command_id})
```

이 패턴이 모든 OS-위임 스킬(`skill_screenshot`, `skill_screen_record`, `skill_voice_record`,
`skill_system_status`, `skill_browser`, `skill_youtube`(재생), `skill_camera`)에 동일하게 적용된다.

---

## 3. 명령어 라우팅 dict 스펙 (`commands/registry.py`)

2단계 dict 구조로 "확장 시 한 곳만 건드린다"를 만족시킨다.

1. **1단계 (스킬 로컬)**: 위 `_PHRASE_TO_COMMAND` — 자연어 트리거 키워드 → `command_id`. 스킬 파일에
   귀속되므로 `skills-only` 확장 원칙과 충돌하지 않는다.
2. **2단계 (중앙 집중)**: `commands/registry.py`의 `COMMAND_MAP` — `command_id` → "어떻게 위임할지"
   (`CommandSpec`). **기존 카테고리에 새 명령을 추가할 때는 해당 `commands/specs/<category>_specs.py`
   파일 한 곳만 건드린다.** 새 카테고리를 통째로 추가할 때만 `registry.py`에 `register()` 호출 한 줄이
   추가된다.

```python
# commands/registry.py (스텁)
from dataclasses import dataclass
from typing import Callable, Literal

Runner = Literal["windows_bridge"]  # 현재는 위임 전용. WSL native 스킬은 이 레이어를 거치지 않는다.
BridgeKind = Literal["exe", "powershell", "ffmpeg"]

@dataclass(frozen=True)
class CommandSpec:
    command_id: str
    description: str
    bridge: BridgeKind
    binary: str | None = None                          # bridge="exe"일 때 호출할 실행 파일
    script: str | None = None                          # bridge="powershell"일 때 인라인 스크립트(또는 .ps1 경로)
    build_args: Callable[[dict], list[str]] | None = None  # kwargs → 인자 리스트
    timeout: int = 15

COMMAND_MAP: dict[str, CommandSpec] = {}

def register(specs: dict[str, CommandSpec]) -> None:
    """commands/specs/*.py 가 자신의 CommandSpec들을 COMMAND_MAP에 등록하는 단일 진입점.
    중복 command_id가 들어오면 조용히 덮어쓰지 않고 ValueError로 즉시 실패시킨다."""
    for command_id, spec in specs.items():
        if command_id in COMMAND_MAP:
            raise ValueError(f"중복 command_id: {command_id}")
        COMMAND_MAP[command_id] = spec

# 파일 하단에서 각 카테고리 spec을 등록 (여기만 보면 전체 명령 목록의 "목차"가 됨)
from commands.specs import power_specs, capture_specs, browser_specs, system_specs
register(power_specs.SPECS)
register(capture_specs.SPECS)
register(browser_specs.SPECS)
register(system_specs.SPECS)
```

```python
# commands/specs/power_specs.py (스텁) — 카테고리 1개 추가 시 건드릴 "한 곳"
from commands.registry import CommandSpec

SPECS: dict[str, CommandSpec] = {
    "POWER_SHUTDOWN": CommandSpec(
        command_id="POWER_SHUTDOWN", description="시스템 종료",
        bridge="exe", binary="shutdown.exe", build_args=lambda kw: ["/s", "/t", "0"],
    ),
    "POWER_RESTART": CommandSpec(
        command_id="POWER_RESTART", description="시스템 재시작",
        bridge="exe", binary="shutdown.exe", build_args=lambda kw: ["/r", "/t", "0"],
    ),
    "POWER_SLEEP": CommandSpec(
        command_id="POWER_SLEEP", description="절전 모드 진입",
        bridge="exe", binary="rundll32.exe",
        build_args=lambda kw: ["powrprof.dll,SetSuspendState", "0,1,0"],
    ),
}
```

`commands/windows_bridge.py`는 기존 `ClaudeCodeEngine`/`GroqEngine`의 "절대 예외를 던지지 않는다" 원칙을
그대로 따른다 — OS 위임은 실패 모드가 더 많기 때문(바이너리 없음, 권한 없음, WSL↔Windows 경로 문제 등).

```python
# commands/windows_bridge.py (스텁)
from dataclasses import dataclass
from commands.registry import COMMAND_MAP

@dataclass(frozen=True)
class CommandResult:
    ok: bool
    stdout: str
    stderr: str
    exit_code: int

def run_command(command_id: str, **kwargs) -> CommandResult:
    """COMMAND_MAP[command_id]를 찾아 bridge 종류에 맞는 내부 함수로 위임한다.
    command_id가 없거나 실행 자체가 실패해도 예외를 던지지 않고 ok=False로 반환한다."""

def _run_exe(binary: str, args: list[str], timeout: int) -> CommandResult: ...
def _run_powershell(script: str, timeout: int) -> CommandResult: ...
def _run_ffmpeg(args: list[str], timeout: int) -> CommandResult: ...
```

---

## 4. OS 종속 기능의 위임 전략

| 기능 | 실행 위치 | 추천 방식 | 호출 형태 | 사유 / 대안 |
|---|---|---|---|---|
| 볼륨 조절·음소거 | Windows 위임 | **nircmd.exe** | `nircmd.exe setsysvolume <0-65535>` / `mutesysvolume 1` | Windows에 볼륨 제어용 표준 CLI가 없음(Core Audio API는 COM). nircmd가 가장 가벼움. 대안: PowerShell Gallery `AudioDeviceCmdlets`(서명된 모듈, 설치 필요) — 서명 신뢰도는 높지만 모듈 설치 단계가 추가됨. **결정 필요 #4** |
| 전원: 종료/재시작 | Windows 위임 | **shutdown.exe** | `/s /t 0`, `/r /t 0` | OS 내장, 추가 설치 불필요 |
| 전원: 절전 | Windows 위임 | **rundll32.exe + powrprof.dll** | `powrprof.dll,SetSuspendState 0,1,0` | shutdown.exe는 절전을 지원하지 않음. OS 내장 |
| 앱 실행 | Windows 위임 | **powershell.exe Start-Process** | `Start-Process notepad` | 기존 `skill_app_launch.py`는 WSL에서 직접 실행 불가 — 위임 시 동일 패턴 적용(§8 #1) |
| 앱 종료 | Windows 위임 | **taskkill.exe** | `/IM notepad.exe /F` | OS 내장, 단순. 기존 `skill_app_control.py`(psutil 직접 종료)와 동등 기능 |
| 스크린샷 | Windows 위임 | **PowerShell + .NET (`System.Drawing`)** | 인라인 스크립트 1개 | OS 내장만으로 충분, 추가 바이너리 불필요. 대안: `nircmd savescreenshot` |
| 화면녹화 + 음성 | Windows 위임 | **ffmpeg (`gdigrab` + `dshow`)** | `ffmpeg -f gdigrab -i desktop -f dshow -i audio="마이크" out.mp4` | 성숙하고 무료. yt-dlp도 내부적으로 ffmpeg에 의존하므로 의존성을 재사용. 대안: OBS CLI(더 무거움, 사전 설정 필요) |
| 음성만 녹음 | Windows 위임 | **ffmpeg (`dshow` 오디오만)** | `ffmpeg -f dshow -i audio="마이크" out.wav` | 화면녹화와 동일 의존성 재사용 |
| 웹캠 캡처(로컬 디바이스) | Windows 위임 | **ffmpeg (`dshow` 비디오)** | `ffmpeg -f dshow -i video="카메라" -frames:v 1 out.png` | 카메라 디바이스는 WSL 패스스루가 거의 불가능 |
| 모바일 카메라(IP 스트림) | **WSL native** | `opencv-python` 또는 `requests`로 스트림 URL 수신 | — | 네트워크 스트림이라 로컬 디바이스 접근이 필요 없음 — 위임 불필요 |
| CPU/RAM/디스크 | Windows 위임 | **PowerShell `Get-CimInstance`** | `Win32_Processor`, `Win32_OperatingSystem`, `Win32_LogicalDisk` | WSL2의 psutil은 WSL VM 자체 리소스를 보고하므로 호스트 값과 다름(§8 #2). CIM/WMI는 OS 내장 |
| 인터넷 속도 | WSL native (1차) | `speedtest` 파이썬 패키지 | — | 구현 단순. WSL2 NAT로 인해 체감과 오차 가능 — **결정 필요 #6** |
| 브라우저 검색 / URL / 구글앱 / SNS / 쇼핑 열기 | Windows 위임 | **PowerShell `Start-Process <url>`** | 기본 브라우저·프로토콜 핸들러로 위임 | 브라우저 종류를 신경 쓸 필요 없음, OS 내장 |
| 유튜브 다운로드 | WSL native | **yt-dlp** | — | 파일시스템 작업이라 위임 불필요 (pytube는 deprecated) |
| 유튜브 "재생"(GUI로 열기) | Windows 위임 | **PowerShell `Start-Process <url>`** | browser_specs와 동일 경로 재사용 | 재생은 화면 출력이 필요한 GUI 동작 |
| PDF 음성 재생(합성된 mp3) | Windows 위임 | **PowerShell `Start-Process <mp3경로>`** | 기본 연결 프로그램으로 재생 | `Media.SoundPlayer`는 wav만 지원 — mp3 변환 없이 가장 단순한 경로 |
| WhatsApp 발신 | Windows 위임(보조 프로세스) | **Windows에 설치된 `python.exe` + `pywhatkit`** | WSL → `powershell.exe -Command "python C:\...\whatsapp_sender.py ..."` | pywhatkit이 내부적으로 `pyautogui` GUI 자동화를 쓰므로 단순 바이너리 호출이 아니라 별도 Python 실행 환경이 필요함 — **결정 필요 #5** |
| 타이머 알림 | WSL native (TTS) | 기존 음성 출력 파이프라인 재사용 | — | 토스트 알림까지는 불필요하다고 판단(옵션 — §8 #9) |

---

## 5. 의존성 목록

### WSL(Linux) 측 신규 Python 패키지

| 패키지 | 용도 | 비고 |
|---|---|---|
| `yt-dlp>=2024.1` | 유튜브 다운로드 | `pytube` deprecated 대체 |
| `pypdf>=4.0` | PDF 텍스트 추출 | `PyPDF2` deprecated 대체 |
| `qrcode[pil]>=7.4` | QR 이미지 생성 | |
| `pyjokes>=0.6.0` | 프로그래밍 농담 | |
| `speedtest>=1.0` (`speedtest-cli` 후속 유지보수 패키지명 확인 필요) | 인터넷 속도 측정 | **결정 필요 #6** |
| `requests` | 뉴스/IP/위치/위키 REST 호출 | 이미 `requirements.txt`에 있음, 재사용 |
| `python-dotenv` | `.env` 로딩 | 이미 있음, 재사용 |

### Windows 측 (pip이 아닌 바이너리/도구)

| 도구 | 용도 | 설치 방식 가정 |
|---|---|---|
| `ffmpeg.exe` | 화면녹화/음성녹음/웹캠 캡처 | winget/choco로 사전 설치, PATH 등록 — **결정 필요 #7** |
| `nircmd.exe` | 볼륨 제어 | 사전 다운로드 + PATH 등록 — **결정 필요 #4** |
| `shutdown.exe` / `rundll32.exe` / `taskkill.exe` / `powershell.exe` | 전원/앱 제어 | OS 내장, 추가 설치 없음 |
| Windows용 `python.exe` + `pywhatkit` | WhatsApp 발신 | 별도 설치 — **결정 필요 #5** |

### Deprecated → 대체 매핑

| 기존/흔한 선택 | 상태 | 대체 | 비고 |
|---|---|---|---|
| `pytube` | 유지보수 단절 | `yt-dlp` | 지침에 이미 명시 |
| `PyPDF2` | deprecated | `pypdf` | 지침에 이미 명시 |
| `duckduckgo_search` | deprecated | `ddgs` | 이미 적용됨(`core/search_engine.py`) |
| `speedtest-cli`(파이썬, 2020년 이후 업데이트 희소) | 유지보수 느림 | Ookla 공식 `speedtest` CLI(Windows 위임) 또는 활성 유지보수 패키지 확인 | **결정 필요 #6** |
| `wikipedia`(파이썬, abandonware 추정) | 유지보수 느림 | `wikipedia-api` 또는 MediaWiki REST API 직접 호출 | **결정 필요 #10** |

---

## 6. `.env` 키 명세

| 키 | 용도 | 필수/선택 |
|---|---|---|
| `GROQ_API_KEY` | (기존) AI 폴백 엔진 | 기존 |
| `BRAVE_SEARCH_API_KEY` | (기존) 웹검색 폴백 | 기존, 선택 |
| `NEWSAPI_KEY` | 최신 뉴스(NewsAPI.org) 조회 | 신규, 뉴스 기능 사용 시 필수 |
| `GMAIL_ADDRESS` | Gmail SMTP 발신 계정 | 신규, 이메일 기능 시 필수 |
| `GMAIL_APP_PASSWORD` | Gmail 앱 비밀번호(2단계 인증 기반 — 계정 비밀번호 아님) | 신규, 이메일 기능 시 필수 |
| `WHATSAPP_DEFAULT_COUNTRY_CODE` | pywhatkit 발신 시 기본 국가코드(예: `+82`) | 신규, 선택 |
| `GOOGLE_CALENDAR_CREDENTIALS_PATH` | (선택) Google Calendar OAuth 클라이언트 파일 경로 — 일정을 로컬 JSON 대신 캘린더로 연동할 때만 | 신규, 선택 — **결정 필요 #9** |

> 참고: 날씨(Open-Meteo)·IP 기반 위치(`ip-api.com` 등)는 무료·무키 한도 내에서 충분해 별도 키가
> 필요 없다고 가정했다. 호출량이 한도를 넘으면 추가 키가 필요할 수 있다.

> **`ANTHROPIC_API_KEY` 관련**: 주어진 컨텍스트는 "subprocess 환경에 절대 주입하지 않는다"고 명시했지만,
> 현재 `core/engines/claude_code.py`의 `_ENV_WHITELIST`에는 이미 포함되어 있다. `core/`를 수정하지
> 않는다는 원칙과 충돌하므로 새 키를 추가하지 않고 **결정 필요 #3**으로 남긴다.

---

## 7. 구현 배치 계획

의존성 낮은 것부터, 위험한 것(전원 제어)과 무거운 설치 요구사항(WhatsApp)은 뒤로 배치했다.

| 배치 | 내용 | 완료 기준 |
|---|---|---|
| **1. 기반 레이어** | `commands/registry.py`, `windows_bridge.py` 골격 + 빈 `COMMAND_MAP` | `python -c "from commands.registry import COMMAND_MAP"` 임포트 성공, `tests/test_commands_registry.py`가 빈 dict에 대해 통과 |
| **2. 순수 WSL 정보/유틸 스킬** | `skill_datetime`, `skill_joke`, `skill_qr`, `skill_contacts`, `skill_schedule`(로컬 JSON) | 각 스킬을 단독 실행해 한국어 응답 텍스트가 정상 출력되는지 assert (기존 `tests/test_skills_step5` 패턴) |
| **3. 외부 무료 API 스킬** | `skill_ip_info`, `skill_location`, `skill_wikipedia`, `skill_news`, `skill_howto` | `.env`에 `NEWSAPI_KEY` 설정 후 각 스킬 실제 네트워크 호출 1회씩 수동 실행, 응답 확인 |
| **4. Windows 위임 브릿지 검증** | `windows_bridge.py`의 `_run_powershell`/`_run_exe` 실제 구현 + `skill_power`(절전/재시작부터) | WSL에서 `powershell.exe -Command "echo test"`가 stdout을 정상 반환하는지 확인 → 사용자 승인 하에 `POWER_RESTART` 1회 수동 트리거해 실제 재시작되는지 확인 |
| **5. 미디어 캡처** | `skill_screenshot`, `skill_screen_record`, `skill_voice_record`, `skill_camera` | 각 실행 후 결과 파일(png/mp4/wav)이 0바이트가 아닌지 확인, 화면녹화는 5초 분량을 직접 재생해 화면+음성이 잡혔는지 눈으로 확인 |
| **6. 브라우저/유튜브/시스템상태** | `skill_browser`, `skill_youtube`, `skill_system_status`, `skill_speedtest` | 브라우저가 실제로 열리는지, yt-dlp 다운로드 파일 생성 확인, `system_status` 값을 Windows 작업 관리자와 대조해 WSL 내부 값이 아님을 확인 |
| **7. 커뮤니케이션 + PDF** | `skill_email`, `skill_whatsapp`(Windows 보조 프로세스), `skill_pdf_reader`(+TTS 재생) | 본인 메일로 테스트 발송 성공, 본인 번호로 WhatsApp 테스트 메시지 1회 발송 확인, PDF 한 페이지가 TTS로 들리는지 확인 |
| **8. 타이머/슬립모드 + 통합 검증** | `skill_timer`, `skill_sleep_mode` + `COMMAND_MAP` 전체 무결성 재검증 | "5분 후 깨워줘" 발화 후 실제 알림 발생 확인, "슬립모드" 발화 후 "wake up" 전까지 무응답 확인, `COMMAND_MAP` 중복 키 없음 검증 |

---

## 8. 결정 필요

아래는 코드/대화만으로 결론 낼 수 없어 사용자 확인이 필요한 지점이다.

1. **실행 환경 불일치**: 현재 4개 스킬(`skill_volume`, `skill_app_launch`, `skill_app_control`,
   `skill_window`)은 Windows 네이티브 프로세스 안에서 `pycaw`/`pygetwindow`로 OS를 **직접** 제어한다.
   주어진 전제(메인 프로세스가 WSL2에서 실행)대로면 이 4개는 더 이상 동작하지 않는다(WSL Python은
   Windows COM에 접근 불가). 이 4개를 `commands/windows_bridge` 위임 방식으로 다시 설계할지, 아니면
   메인 프로세스를 계속 Windows 네이티브로 유지하고 이번 신규 기능만 "향후 WSL 전환 대비 옵션
   설계"로 둘지?
2. **같은 이유로 시스템 정보**: 기존 `skill_system_info.py`(psutil 기반)도 WSL 안에서 돌면 WSL 가상머신
   자체의 CPU/RAM을 보고한다(Windows 호스트 값 아님). 신규 `skill_system_status.py`(Windows 위임판)와
   기존 것을 둘 다 유지할지, 기존 것을 위임 방식으로 교체할지?
3. **`ANTHROPIC_API_KEY` 화이트리스트 충돌**: `core/engines/claude_code.py`의 `_ENV_WHITELIST`에 이미
   포함되어 있어 "subprocess 환경에 절대 주입하지 않는다"는 원칙과 충돌한다. 새 기능에만 이 원칙을
   적용하고 기존 `claude_code.py`는 그대로 둘지, 아니면 `core/` 수정이 필요한 별도 작업으로 분리할지?
4. **nircmd 설치 가정 가능 여부**: 볼륨 위임에 추천한 `nircmd.exe`는 서명되지 않은 서드파티 바이너리라
   SmartScreen/안티바이러스 경고가 뜰 수 있다. 사전 설치를 가정해도 될지, 서명된 PowerShell 모듈
   `AudioDeviceCmdlets`(설치 단계 추가)로 대체할지?
5. **WhatsApp 발신의 무거운 설치 요구사항**: `pywhatkit`은 GUI 자동화(`pyautogui`)가 필수라 WSL에서
   실행할 수 없다. Windows 쪽에 별도 Python 환경 + `pywhatkit`을 설치해 그쪽에서 실행하는 구조를
   가정해도 될지?
6. **인터넷 속도 측정 정확도**: WSL2 NAT 네트워킹 특성상 측정값이 Windows 호스트 체감과 다를 수 있다.
   WSL native(구현 간단, 정확도 낮을 가능성)로 시작할지, 처음부터 Windows 위임(Ookla 공식 CLI, 정확도
   높음, 설치 부담 추가)으로 갈지?
7. **ffmpeg 사전 설치 가정**: 화면녹화/음성녹음/웹캠 캡처가 모두 ffmpeg(Windows 빌드)를 전제한다.
   PATH에 설치되어 있다고 가정해도 될지, 설치 확인/안내 로직까지 설계 범위에 포함해야 할지?
8. **슬립 모드의 구현 위치**: "wake up까지 유지"는 `SkillResult.follow_up` 한 턴짜리 플래그로 표현되지
   않는, "리스닝 자체를 한동안 억제"하는 동작이다. 스킬의 `context.data` 상태만으로 충분한지, 아니면
   `main.py`(이건 `core/`가 아니므로 수정 가능하다고 해석했는데 맞는지?)의 음성 루프 쪽 로직 변경이
   필요한지?
9. **뉴스/일정의 외부 의존도**: NewsAPI 무료 티어는 하루 100회 호출 제한이 있다. 이 한도로 충분한지,
   일정 기능을 로컬 JSON으로만 둘지 Google Calendar API 연동까지 포함할지?
10. **wikipedia 패키지의 유지보수 상태**: "deprecated 라이브러리 금지" 원칙에 따라, 업데이트가 뜸한
    `wikipedia` 패키지 대신 MediaWiki REST API를 `requests`로 직접 호출하는 방식으로 대체할지?

---

## 부록 A. PC 화면 제어 에이전트 설계 (2026-06-26 추가)

> 이 부록은 기존 6개 카테고리 확장과 별개로, **PC 화면을 직접 제어하는 멀티스텝 에이전트** 기능을
> 추가하기 위한 설계다. 구현 대상은 4개 파일이다.

### A.0 새 파일 목록

```
core/
└── engines/
    └── ollama_engine.py          # [신규] Ollama 로컬 LLM 엔진 (GroqEngine 인터페이스 준수)

skills/
├── skill_ai_chat.py              # [수정] Groq→Ollama 자동 폴백 로직 추가
├── agent_tools/
│   └── screen_tool.py            # [신규] 8개 화면 제어 도구 함수
└── skill_screen_agent.py         # [신규] 화면 제어 에이전트 스킬 (Groq tool-calling 루프)
```

---

### A.1 `core/engines/ollama_engine.py` 명세

**목적**: Ollama 로컬 서버의 OpenAI 호환 엔드포인트를 `requests`로 직접 호출해 `GroqEngine`과
동일한 `ask/generate/describe` 인터페이스를 제공한다. `openai` SDK는 사용하지 않는다.

**설계 근거**:
- `requests`는 이미 `requirements.txt`에 있다 — 추가 의존성 없음.
- `openai` SDK를 쓰면 패키지 크기와 초기화 비용이 늘지만, OpenAI-호환 JSON 스펙은
  `requests` + `json` 수준에서 완전히 처리 가능하다.
- timeout 기본값 120초 (로컬 추론은 Groq API보다 느림).

```python
# core/engines/ollama_engine.py — 시그니처/스텁 수준

import logging
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_PERSONA_PATH = Path(__file__).parent.parent.parent / "config" / "persona.md"

_DEFAULT_HOST  = "localhost:11434"   # OLLAMA_HOST 환경변수로 재정의
_DEFAULT_MODEL = "qwen2.5:7b"        # OLLAMA_MODEL 환경변수로 재정의
_DEFAULT_TIMEOUT = 120               # 로컬 추론 지연 감안, 초 단위
_FOREIGN_SCRIPT = re.compile("[一-鿿㐀-䶿぀-ゟ゠-ヿ]")  # groq_engine.py와 동일


class OllamaEngine:
    """Ollama 로컬 서버를 호출하는 AI 엔진. GroqEngine과 동일한 인터페이스를 따른다."""

    def __init__(self) -> None:
        self._host  = os.getenv("OLLAMA_HOST",  _DEFAULT_HOST)
        self._model = os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)
        self._persona = self._load_persona()
        # base_url: http:// 스킴이 없으면 자동 추가
        if not self._host.startswith("http"):
            self._base_url = f"http://{self._host}"
        else:
            self._base_url = self._host

    # ── 공개 인터페이스 (GroqEngine과 동일) ─────────────────────────────────

    def ask(self, text: str) -> str:
        """사용자 입력을 Ollama에 전달해 응답 텍스트를 반환한다.
        persona.md를 system 메시지로 고정한다. 실패 시 예외 대신 한국어 에러 문자열 반환."""
        return self._complete(text, system=self._persona)

    def generate(self, prompt: str, system: str | None = None) -> str:
        """persona.md에 system을 덧붙여 호출한다. GroqEngine.generate()와 동일한 규약."""
        if system and self._persona:
            combined = f"{self._persona}\n\n{system}"
        else:
            combined = system or self._persona
        return self._complete(prompt, system=combined)

    def describe(self) -> dict:
        """ui/server.py가 읽는 엔진 식별 정보. usagePercent는 항상 0 (로컬, 할당량 없음)."""
        return {
            "provider": "Ollama",
            "model": self._model,
            "connected": self._is_reachable(),
            "usagePercent": 0,
        }

    # ── 내부 구현 ────────────────────────────────────────────────────────────

    def _complete(self, text: str, system: str) -> str:
        """실제 HTTP 요청. 모든 예외를 잡아 한국어 에러 메시지로 변환한다."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": text})

        try:
            resp = requests.post(
                f"{self._base_url}/v1/chat/completions",
                json={
                    "model":       self._model,
                    "messages":    messages,
                    "temperature": 0.7,
                    "max_tokens":  1024,
                },
                timeout=_DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.ConnectionError:
            logger.error("Ollama 서버에 연결할 수 없습니다.")
            return "Ollama 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요."
        except requests.Timeout:
            logger.error("Ollama 응답 타임아웃")
            return "Ollama 응답 시간이 초과됐습니다."
        except requests.HTTPError as e:
            logger.error(f"Ollama HTTP 오류: {e}")
            return f"Ollama 오류: {e}"
        except Exception as e:
            logger.error(f"Ollama 엔진 오류: {e}")
            return f"Ollama 엔진 오류: {e}"

        content: str = resp.json()["choices"][0]["message"]["content"] or ""

        # 한자/가나 잔류 시 제거 (groq_engine.py와 동일한 후처리)
        if _FOREIGN_SCRIPT.search(content):
            logger.warning("Ollama 응답에 한자/가나 포함 — 제거 후 반환")
            content = _FOREIGN_SCRIPT.sub("", content)
            content = re.sub(r"\s+", " ", content)

        return content.strip() or "응답이 비어 있습니다."

    def _is_reachable(self) -> bool:
        """GET /api/tags 로 서버 생존 여부를 확인한다. 실패 시 False."""
        try:
            r = requests.get(f"{self._base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def _load_persona(self) -> str:
        try:
            return _PERSONA_PATH.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            logger.warning(f"persona.md를 찾을 수 없습니다: {_PERSONA_PATH}")
            return ""
```

---

### A.2 `skills/skill_ai_chat.py` 수정 명세 (Groq → Ollama 폴백)

**핵심 제약**: `core/engines/groq_engine.py`는 수정하지 않는다. `GroqEngine._complete()`는
`RateLimitError`를 내부에서 잡아 한국어 에러 문자열(`"Groq API 요청 한도를 초과했습니다. ..."`)로
반환하므로, 스킬 레벨에서는 **응답 문자열 검사**로 한도 초과를 감지한다.

**검출 방식 선택 근거**:
- `groq` SDK의 `RateLimitError`를 스킬 레벨에서 직접 잡으려면 `GroqEngine._complete()`의 except
  블록을 수정하거나, 스킬이 `groq` SDK에 직접 의존해야 한다. 전자는 frozen 위반, 후자는 엔진 캡슐화
  파괴이므로 채택하지 않는다.
- 문자열 감지는 `groq_engine.py`의 에러 메시지 변경 시 깨질 수 있는 약점이 있다. 이 취약점을
  완화하기 위해 상수 `_GROQ_RATE_LIMIT_SIGNAL`을 한 곳에 두고, 에러 메시지 변경 시 상수만
  갱신하면 되도록 설계한다.

**변경 전후 비교**:

```python
# 변경 전 (현재)
from core.engines.groq_engine import GroqEngine as Engine

class AiChatSkill(Skill):
    def __init__(self) -> None:
        self._engine = Engine()

    def execute(self, text: str, context: dict) -> SkillResult:
        response = self._engine.ask(text)
        return SkillResult(speech=response, success=True)
```

```python
# 변경 후 — 함수 시그니처/구조 수준 스텁

import logging
from core.skill_base import Skill, SkillResult
# [ROLLBACK] from core.engines.claude_code import ClaudeCodeEngine as _GroqCls
from core.engines.groq_engine import GroqEngine as _GroqCls
from core.engines.ollama_engine import OllamaEngine as _OllamaCls

logger = logging.getLogger(__name__)

# groq_engine.py 의 RateLimitError 응답 문자열 — 변경 시 이 상수만 갱신
_GROQ_RATE_LIMIT_SIGNAL = "Groq API 요청 한도를 초과했습니다"


class AiChatSkill(Skill):
    name        = "ai_chat"
    description = "다른 스킬이 처리하지 못한 자연어 요청을 AI로 응답한다"
    triggers    = []
    examples    = []

    def __init__(self) -> None:
        self._groq   = _GroqCls()
        self._ollama: _OllamaCls | None = None
        self._use_ollama: bool = False   # 세션 내 전환 후 복원 안 함

    # ui/server.py의 _engine_descriptor()가 self._engine.describe()를 호출하므로
    # property로 현재 활성 엔진을 노출한다.
    @property
    def _engine(self):
        if self._use_ollama:
            if self._ollama is None:
                self._ollama = _OllamaCls()
            return self._ollama
        return self._groq

    def can_handle(self, intent: str, text: str) -> float:
        return 0.1   # 항상 낮은 점수 — Router 임계값 미달, 폴백 전용

    def execute(self, text: str, context: dict) -> SkillResult:
        response = self._engine.ask(text)

        # Groq 한도 초과 감지 → Ollama로 전환 후 즉시 재시도
        if not self._use_ollama and _GROQ_RATE_LIMIT_SIGNAL in response:
            logger.warning("Groq 일일 한도 소진 — 이 세션은 Ollama로 전환합니다.")
            self._use_ollama = True
            response = self._engine.ask(text)   # _engine property가 이제 Ollama 반환

        return SkillResult(speech=response, success=True)
```

**`_engine` property 도입 이유**: `ui/server.py`의 `_engine_descriptor()`는
`skill._engine.describe()`를 호출해 대시보드 엔진 패널을 채운다. property로 현재 활성 엔진
객체를 동적으로 반환하면 Groq→Ollama 전환 시 대시보드에도 자동으로 반영된다.

---

### A.3 `skills/agent_tools/screen_tool.py` 명세

**목적**: 8개 화면 제어 도구 함수. `skill_screen_agent.py`의 tool-calling 루프가 호출하며,
`agent_tools/` 패키지의 기존 관례(`{"ok": bool, "data": ..., "error": str}` 반환, 예외 미방출)를
그대로 따른다.

**의존 패키지** (신규 설치 필요):
- `pyautogui>=0.9.54` — 마우스/키보드 제어
- `pytesseract>=0.3.10` — OCR (Tesseract 바이너리 별도 설치 필요 — A.8 참고)
- `Pillow>=10.0` — 스크린샷 이미지 처리 (pyautogui 의존성으로 보통 함께 설치됨)

이미 `requirements.txt`에 있어 재사용 가능한 패키지:
- `pyperclip>=1.8.2` — 클립보드 (한국어 텍스트 입력용)
- `pygetwindow>=0.0.9` — 창 관리

```python
# skills/agent_tools/screen_tool.py — 시그니처/스텁 수준

"""PC 화면 제어 도구 8개.

모든 함수는 {"ok": bool, "data": ..., "error": str} 형식을 반환하고 예외를 던지지 않는다.
skill_screen_agent.py의 Groq/Ollama tool-calling 루프에서 호출된다.
"""
import logging
import subprocess
import webbrowser
from typing import Any

logger = logging.getLogger(__name__)

# ── pyautogui 안전 설정 (모듈 최상단에서 한 번만) ──────────────────────────
# import는 함수 내부에서 지연(lazy) — pyautogui가 없어도 나머지 앱이 로드되도록
# 단, 설정은 최초 import 시점에 적용되어야 하므로 _get_pyautogui() 헬퍼로 처리
def _get_pyautogui():
    """pyautogui를 지연 임포트하고 안전 설정을 적용한다."""
    import pyautogui
    pyautogui.FAILSAFE = True   # 마우스를 화면 모서리로 이동하면 AbortException 발생
    pyautogui.PAUSE    = 0.2    # 각 액션 사이 최소 0.2초 대기 (빠른 연속 동작 방지)
    return pyautogui


# ① screenshot_read ─────────────────────────────────────────────────────────
def screenshot_read() -> dict[str, Any]:
    """현재 화면을 캡처하고 OCR로 텍스트 요소와 좌표를 반환한다.

    Returns:
        data: {"elements": [{"id": int, "text": str, "x": int, "y": int,
                              "w": int, "h": int}, ...]}
        신뢰도 60 미만 OCR 결과는 제외된다.
    """
    ...


# ② mouse_click ─────────────────────────────────────────────────────────────
def mouse_click(x: int, y: int, button: str = "left") -> dict[str, Any]:
    """지정 좌표를 클릭한다.

    Args:
        x, y:   화면 좌표 (픽셀). 화면 범위 밖이면 ok=False.
        button: "left" | "right" | "middle"
    """
    ...


# ③ keyboard_type ───────────────────────────────────────────────────────────
def keyboard_type(text: str) -> dict[str, Any]:
    """텍스트를 입력한다. 한국어 포함 모든 텍스트에 클립보드+Ctrl+V 방식을 사용한다.

    주의: pyautogui.write()는 한국어를 입력하지 못한다(ASCII 전용). 이 함수는
    pyperclip.copy(text) → pyautogui.hotkey('ctrl', 'v') 로 항상 처리한다.
    """
    ...


# ④ keyboard_key ────────────────────────────────────────────────────────────
def keyboard_key(key: str) -> dict[str, Any]:
    """단일 키 또는 복합 키를 입력한다.

    Args:
        key: "enter", "tab", "esc", "ctrl+c", "ctrl+v", "alt+f4" 등.
             "+" 구분자로 복합 키를 표현한다.
    """
    ...


# ⑤ mouse_scroll ────────────────────────────────────────────────────────────
def mouse_scroll(
    direction: str,
    amount: int = 3,
    x: int | None = None,
    y: int | None = None,
) -> dict[str, Any]:
    """마우스 휠을 스크롤한다.

    Args:
        direction: "up" 또는 "down"
        amount:    클릭 수 (pyautogui clicks 인자). 기본 3.
        x, y:      스크롤할 위치. None이면 현재 포인터 위치.
    """
    ...


# ⑥ get_windows ─────────────────────────────────────────────────────────────
def get_windows() -> dict[str, Any]:
    """열려 있는 창 목록을 반환한다.

    Returns:
        data: [{"title": str, "x": int, "y": int, "w": int, "h": int}, ...]
        빈 제목(title="")의 창은 제외한다.
    """
    ...


# ⑦ focus_window ────────────────────────────────────────────────────────────
def focus_window(title: str) -> dict[str, Any]:
    """제목이 일치하는 창을 앞으로 가져온다.

    부분 일치(title이 창 제목의 substring)를 지원한다.
    일치하는 창이 없으면 ok=False.
    """
    ...


# ⑧ open_app ────────────────────────────────────────────────────────────────
def open_app(target: str) -> dict[str, Any]:
    """URL이면 기본 브라우저로 열고, 앱 이름/경로면 subprocess로 실행한다.

    URL 판별: target이 "http://", "https://"로 시작하거나 "www."를 포함하면 URL.
    앱 실행: subprocess.Popen(target, shell=True) — shell=True로 PATH 탐색 허용.
    """
    ...
```

**각 함수의 핵심 구현 포인트** (로직 힌트, 완전한 구현은 구현자 에이전트가 담당):

| 함수 | 핵심 포인트 |
|---|---|
| `screenshot_read` | `pytesseract.image_to_data(img, lang='kor+eng', output_type=Output.DICT)` → `conf > 60`인 행만 필터링. `left`, `top`, `width`, `height` 컬럼이 좌표 소스. 같은 블록(`block_num`)에 속한 단어들을 하나의 요소로 묶으면 노이즈가 줄어든다. |
| `keyboard_type` | `pyperclip.copy(text)` 후 `pyautogui.hotkey('ctrl', 'v')`. 한국어뿐 아니라 특수문자도 안전하게 처리된다. `pyautogui.PAUSE` 덕분에 클립보드가 세팅되기 전에 붙여넣기가 실행되는 타이밍 문제를 최소화할 수 있으나, 필요 시 `time.sleep(0.05)` 추가 고려. |
| `keyboard_key` | `key.split('+')` → 요소가 1개면 `pyautogui.press()`, 2개 이상이면 `pyautogui.hotkey(*parts)`. "enter"→"return" 등 pyautogui 키 이름 별칭 매핑 테이블을 두는 것이 안전하다. |
| `focus_window` | `pygetwindow.getWindowsWithTitle(title)` + 부분 일치 fallback: `[w for w in pygetwindow.getAllWindows() if title.lower() in w.title.lower()]`. `.activate()`는 일부 앱에서 `pygetwindow.PyGetWindowException`을 던질 수 있으므로 try-except 필수. |
| `open_app` (앱) | `subprocess.Popen(target, shell=True)` 실행 후 `Popen` 객체만 저장하고 완료를 기다리지 않는다 (`wait()` 미호출). 에러 발생 여부는 `OSError`로 잡는다. |

---

### A.4 `skills/skill_screen_agent.py` 명세

**목적**: 화면 캡처→분석→클릭/타이핑 등을 자동으로 수행하는 멀티스텝 에이전트.
`skill_agent.py` (웹 조사 에이전트)의 구조를 그대로 따르되, 도구 셋이 screen_tool의 8개 함수로
교체되고, **Groq RateLimitError 발생 시 루프 내에서 즉시 Ollama로 전환**한다.

**Groq→Ollama 루프 내 전환 전략**:
- `skill_agent.py`에서는 Groq SDK 예외가 루프 밖(`_run_agent()` 전체)에서 처리된다.
- 이 스킬에서는 루프 내부에서 `groq.RateLimitError`를 직접 잡아 `use_ollama = True`로
  플래그를 세우고 즉시 Ollama로 재시도한다.
- Ollama는 `requests`로 `/v1/chat/completions`를 호출한다 (OpenAI-호환 형식).
  Groq SDK 응답 객체(`.choices[0].message.tool_calls`)와 Ollama JSON 응답
  (`["choices"][0]["message"]["tool_calls"]`)은 구조가 다르므로, 이를 통일하는
  내부 메서드 `_call_llm()`이 양쪽을 정규화한다.

```python
# skills/skill_screen_agent.py — 시그니처/스텁 수준

"""화면 제어 에이전트. Groq tool-calling 루프 + Ollama 자동 폴백."""
import json
import logging
import os
import re

from dotenv import load_dotenv
from groq import Groq, RateLimitError

from core.skill_base import Skill, SkillResult
from skills.agent_tools import reporter_tool
from skills.agent_tools import screen_tool

load_dotenv()
logger = logging.getLogger(__name__)

_FOREIGN_SCRIPT = re.compile("[一-鿿㐀-䶿぀-ゟ゠-ヿ]")
_MODEL_GROQ   = "llama-3.3-70b-versatile"
_MAX_TURNS    = 20
_MAX_TOKENS   = 4096
_TIMEOUT_GROQ = 60
_TIMEOUT_OLLAMA = 120
_MAX_TOOL_OUTPUT = 4000

# ── 트리거 상수 ────────────────────────────────────────────────────────────
_TRIGGERS_VERY_STRONG = ["화면 제어", "화면 에이전트", "직접 제어"]   # 0.95
_TRIGGERS_STRONG      = ["화면에서", "화면으로"]                       # + 동사 있으면 0.9
_STRONG_VERBS         = ["해줘", "해봐", "수집", "찾아", "클릭"]
_TRIGGERS_COMBO_OPEN  = ["켜서", "열어서"]                             # 조합: 0.85
_TRIGGERS_COMBO_ACT   = ["수집", "저장"]

_SYSTEM_PROMPT = (
    "You are Jarvis, a personal AI assistant controlling the user's PC screen.\n\n"
    "Workflow:\n"
    "1. Use 'report' first to announce what you are about to do.\n"
    "2. Use 'screenshot_read' to see on-screen text elements and their coordinates.\n"
    "3. Use 'mouse_click', 'keyboard_type', 'keyboard_key', 'mouse_scroll' to interact.\n"
    "4. Use 'get_windows' and 'focus_window' to manage open windows.\n"
    "5. Use 'open_app' to launch apps or URLs.\n"
    "6. Use 'report' after each major step to update the user.\n\n"
    "Respond to the user in friendly, natural Korean. "
    "Always confirm with 'report' before clicking or typing."
)

# Groq tool-calling 형식 정의 — screen_tool 8개 + report
_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "screenshot_read",
            "description": "현재 화면을 캡처하고 OCR로 텍스트 요소와 좌표를 반환한다",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_click",
            "description": "지정 좌표를 마우스로 클릭한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "x":      {"type": "integer", "description": "X 좌표 (픽셀)"},
                    "y":      {"type": "integer", "description": "Y 좌표 (픽셀)"},
                    "button": {"type": "string",  "description": "left | right | middle"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_type",
            "description": "텍스트를 입력한다 (한국어 포함)",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "입력할 텍스트"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "keyboard_key",
            "description": "특수키 또는 단축키를 누른다 (예: enter, ctrl+c, alt+f4)",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "키 이름 또는 조합 (+ 구분자)"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mouse_scroll",
            "description": "마우스 휠을 스크롤한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string",  "description": "up 또는 down"},
                    "amount":    {"type": "integer", "description": "스크롤 클릭 수 (기본 3)"},
                    "x":         {"type": "integer", "description": "스크롤 위치 X (선택)"},
                    "y":         {"type": "integer", "description": "스크롤 위치 Y (선택)"},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_windows",
            "description": "현재 열린 창 목록과 위치/크기를 반환한다",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "focus_window",
            "description": "제목으로 창을 찾아 포커스를 맞춘다",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "창 제목 (부분 일치 허용)"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "앱 이름/경로 또는 URL을 열다",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "앱 이름, 경로, 또는 URL"},
                },
                "required": ["target"],
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
                    "message": {"type": "string", "description": "보고 내용"},
                },
                "required": ["message"],
            },
        },
    },
]


class ScreenAgentSkill(Skill):
    """PC 화면 제어 에이전트 스킬 (Groq tool-calling + Ollama 폴백)."""

    name        = "screen_agent"
    description = "화면을 직접 제어해 클릭·입력·창 관리 등 멀티스텝 작업을 자동 수행한다"
    triggers    = ["화면 제어", "화면 에이전트", "직접 제어", "화면으로"]
    examples    = [
        "화면 에이전트로 크롬 열어서 유튜브 검색해줘",
        "화면 제어로 메모장에 안녕하세요 입력해줘",
        "직접 제어해서 바탕화면 스크린샷 찍어줘",
    ]

    def can_handle(self, intent: str, text: str) -> float:
        if any(t in text for t in _TRIGGERS_VERY_STRONG):
            return 0.95
        if any(t in text for t in _TRIGGERS_STRONG):
            if any(v in text for v in _STRONG_VERBS):
                return 0.9
        if any(o in text for o in _TRIGGERS_COMBO_OPEN):
            if any(a in text for a in _TRIGGERS_COMBO_ACT):
                return 0.85
        return 0.0

    def execute(self, text: str, context: dict) -> SkillResult:
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

        answer = self._run_agent(api_key, text)
        return SkillResult(speech=answer, success=True, data={"task": text})

    # ── 에이전트 루프 ────────────────────────────────────────────────────────

    def _run_agent(self, api_key: str, task: str) -> str:
        """Groq tool-calling 루프. RateLimitError 발생 시 Ollama로 전환한다."""
        groq_client = Groq(api_key=api_key)
        use_ollama  = False

        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": task},
        ]

        for turn in range(_MAX_TURNS):
            try:
                msg = self._call_llm(groq_client, messages, use_ollama)
            except RateLimitError:
                logger.warning(f"Groq RateLimitError (턴 {turn + 1}) — Ollama로 전환")
                use_ollama = True
                try:
                    msg = self._call_llm(groq_client, messages, use_ollama=True)
                except Exception as exc:
                    return f"에이전트 실행 오류: {exc}"
            except Exception as exc:
                logger.error(f"ScreenAgent 호출 실패 (턴 {turn + 1}): {exc}")
                return f"에이전트 실행 오류: {exc}"

            # tool_calls 없음 → 최종 응답
            if not msg["tool_calls"]:
                content = msg["content"] or "작업을 완료했습니다."
                return _FOREIGN_SCRIPT.sub("", content).strip()

            # assistant 메시지 기록
            messages.append(msg["assistant_msg"])

            # 도구 순차 실행
            for tc in msg["tool_calls"]:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    fn_args = {}
                result     = self._dispatch_tool(fn_name, fn_args)
                result_str = json.dumps(result, ensure_ascii=False)[:_MAX_TOOL_OUTPUT]
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc["id"],
                    "content":      result_str,
                })

        logger.warning(f"ScreenAgent: {_MAX_TURNS}턴 초과 — 태스크: {task!r}")
        return "최대 반복 횟수에 도달했습니다. 작업 일부만 완료됐을 수 있습니다."

    def _call_llm(
        self,
        groq_client: Groq,
        messages: list[dict],
        use_ollama: bool = False,
    ) -> dict:
        """LLM을 호출하고 정규화된 응답 dict를 반환한다.

        Returns:
            {
                "content":      str | None,
                "tool_calls":   [{"id": str, "function": {"name": str, "arguments": str}}, ...],
                "assistant_msg": dict,  # messages 배열에 추가할 assistant 역할 dict
            }
        Raises:
            groq.RateLimitError: Groq 한도 초과 시 (use_ollama=False일 때만 발생 가능)
            requests.RequestException: Ollama 연결 실패 시 (use_ollama=True일 때만)
            Exception: 기타 오류
        """
        if not use_ollama:
            return self._call_groq(groq_client, messages)
        else:
            return self._call_ollama(messages)

    def _call_groq(self, client: Groq, messages: list[dict]) -> dict:
        """Groq SDK 호출 → 정규화된 dict 반환."""
        response = client.chat.completions.create(
            model       = _MODEL_GROQ,
            messages    = messages,
            tools       = _TOOLS,
            tool_choice = "auto",
            max_tokens  = _MAX_TOKENS,
            timeout     = _TIMEOUT_GROQ,
        )
        msg = response.choices[0].message
        tool_calls = []
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name":      tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]
        assistant_msg = {
            "role":       "assistant",
            "content":    msg.content,
            "tool_calls": [
                {"id": tc["id"], "type": "function", "function": tc["function"]}
                for tc in tool_calls
            ],
        }
        return {"content": msg.content, "tool_calls": tool_calls, "assistant_msg": assistant_msg}

    def _call_ollama(self, messages: list[dict]) -> dict:
        """Ollama OpenAI-호환 API 호출 (requests) → 정규화된 dict 반환."""
        import requests as _req
        host  = os.getenv("OLLAMA_HOST",  "localhost:11434")
        model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
        if not host.startswith("http"):
            host = f"http://{host}"

        resp = _req.post(
            f"{host}/v1/chat/completions",
            json={
                "model":       model,
                "messages":    messages,
                "tools":       _TOOLS,
                "tool_choice": "auto",
                "max_tokens":  _MAX_TOKENS,
            },
            timeout=_TIMEOUT_OLLAMA,
        )
        resp.raise_for_status()
        data = resp.json()
        msg_dict   = data["choices"][0]["message"]
        raw_tcs    = msg_dict.get("tool_calls") or []
        tool_calls = [
            {
                "id": tc.get("id", f"ollama_{i}"),
                "function": {
                    "name":      tc["function"]["name"],
                    "arguments": (
                        tc["function"]["arguments"]
                        if isinstance(tc["function"]["arguments"], str)
                        else json.dumps(tc["function"]["arguments"], ensure_ascii=False)
                    ),
                },
            }
            for i, tc in enumerate(raw_tcs)
        ]
        assistant_msg = {
            "role":       "assistant",
            "content":    msg_dict.get("content"),
            "tool_calls": [
                {"id": tc["id"], "type": "function", "function": tc["function"]}
                for tc in tool_calls
            ],
        }
        return {
            "content":       msg_dict.get("content"),
            "tool_calls":    tool_calls,
            "assistant_msg": assistant_msg,
        }

    def _dispatch_tool(self, name: str, args: dict) -> dict:
        """도구 이름으로 screen_tool / reporter_tool 함수를 호출한다."""
        dispatch = {
            "screenshot_read": lambda: screen_tool.screenshot_read(),
            "mouse_click":     lambda: screen_tool.mouse_click(
                                    args.get("x", 0), args.get("y", 0),
                                    args.get("button", "left")),
            "keyboard_type":   lambda: screen_tool.keyboard_type(args.get("text", "")),
            "keyboard_key":    lambda: screen_tool.keyboard_key(args.get("key", "")),
            "mouse_scroll":    lambda: screen_tool.mouse_scroll(
                                    args.get("direction", "down"),
                                    args.get("amount", 3),
                                    args.get("x"), args.get("y")),
            "get_windows":     lambda: screen_tool.get_windows(),
            "focus_window":    lambda: screen_tool.focus_window(args.get("title", "")),
            "open_app":        lambda: screen_tool.open_app(args.get("target", "")),
            "report":          lambda: reporter_tool.report(args.get("message", "")),
        }
        fn = dispatch.get(name)
        if fn is None:
            logger.warning(f"알 수 없는 도구: {name}")
            return {"ok": False, "data": None, "error": f"알 수 없는 도구: {name}"}
        try:
            return fn()
        except Exception as exc:
            logger.error(f"도구 실행 오류 ({name}): {exc}")
            return {"ok": False, "data": None, "error": str(exc)}
```

---

### A.5 `requirements.txt` 추가 패키지

기존 `requirements.txt` 끝에 아래 블록을 추가한다.

```text
# PC 화면 제어 에이전트 (skills/skill_screen_agent.py + skills/agent_tools/screen_tool.py)
pyautogui>=0.9.54        # 마우스·키보드 제어
pytesseract>=0.3.10      # OCR (Tesseract 바이너리 별도 설치 필요 — 아래 주의사항 참고)
Pillow>=10.0             # 스크린샷 이미지 처리 (pyautogui 가 보통 함께 설치하지만 명시)
# pyperclip, pygetwindow는 이미 requirements.txt에 있음 — 재사용
```

**설치 명령 (참고)**:
```powershell
pip install pyautogui pytesseract Pillow
# Tesseract OCR 바이너리 (Windows): winget install --id UB-Mannheim.TesseractOCR
```

---

### A.6 `.env` 신규 키

| 키 | 용도 | 필수/선택 | 기본값 |
|---|---|---|---|
| `OLLAMA_HOST` | Ollama 서버 주소 | 선택 | `localhost:11434` |
| `OLLAMA_MODEL` | Ollama 사용 모델 | 선택 | `qwen2.5:7b` |
| `TESSERACT_PATH` | Tesseract 실행 파일 경로 (screen_tool 내부에서 `pytesseract.pytesseract.tesseract_cmd` 설정) | 선택 | `C:\Program Files\Tesseract-OCR\tesseract.exe` |

**`.env.example`에 추가할 내용**:
```dotenv
# Ollama 로컬 LLM (core/engines/ollama_engine.py)
OLLAMA_HOST=localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# Tesseract OCR 경로 (skills/agent_tools/screen_tool.py)
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

### A.7 주의사항

#### 1. 한국어 텍스트 입력

`pyautogui.write("안녕하세요")`는 **동작하지 않는다**. `write()`는 내부적으로 ASCII 키코드를
사용하므로 한국어(IME 경유 입력)를 처리하지 못한다.

`keyboard_type()`은 반드시 **클립보드 경유(paste) 방식**을 써야 한다:

```python
import pyperclip
import pyautogui
pyperclip.copy(text)
pyautogui.hotkey('ctrl', 'v')
```

단, 이 방식은 포커스된 창이 `Ctrl+V`를 붙여넣기로 처리해야 동작한다. 터미널/셸 창에서는
`Ctrl+Shift+V`가 필요한 경우가 있으므로 구현 시 `PASTE_KEY` 환경변수나 설정으로 커스터마이징
가능하도록 설계를 고려한다.

#### 2. Tesseract 경로 설정

`pytesseract`는 Tesseract 바이너리의 위치를 자동으로 찾지 못하는 경우가 많다. `screen_tool.py`
모듈 최상단(또는 `screenshot_read()` 첫 호출 시점)에서 아래를 설정해야 한다:

```python
import pytesseract
import os
_TESSERACT_PATH = os.getenv(
    "TESSERACT_PATH",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
pytesseract.pytesseract.tesseract_cmd = _TESSERACT_PATH
```

한국어 OCR을 위해 Tesseract 설치 시 **한국어 언어 팩(`kor`)**이 함께 설치되어 있어야 한다.
winget 설치 기준: `winget install --id UB-Mannheim.TesseractOCR` 에서 설치 옵션으로 Korean을
체크해야 한다.

#### 3. pyautogui FAILSAFE와 AbortException

`pyautogui.FAILSAFE = True`(기본값)가 활성화된 상태에서 마우스가 화면 모서리로 이동하면
`pyautogui.FailSafeException`이 발생해 에이전트 루프가 중단된다. 이는 의도된 안전장치다.
에이전트가 예상치 못한 좌표로 마우스를 이동시킬 때 사람이 개입할 수 있는 탈출 방법이다.
`FAILSAFE = False`로 비활성화하지 말 것.

`_run_agent()` 루프의 `except Exception` 블록에서 이 예외를 잡아 명확한 한국어 메시지
("안전장치 발동: 마우스가 모서리로 이동됐습니다. 에이전트를 종료합니다.")와 함께 루프를
종료하도록 구현한다.

#### 4. Ollama tool-calling 모델 선택

Ollama에서 tool-calling을 지원하는 모델은 제한적이다. `qwen2.5:7b`는 OpenAI 호환 tool-calling을
지원하며 한국어 능력도 양호하다. `llama3.2:3b`도 tool-calling을 지원하나 품질이 낮다.
`OLLAMA_MODEL`을 변경할 경우 반드시 tool-calling 지원 여부를 먼저 확인해야 한다.

Ollama가 반환하는 `tool_calls`의 `arguments` 필드가 문자열이 아닌 dict 객체인 경우가 있다
(모델 구현에 따라 다름). `_call_ollama()` 의 `isinstance` 체크(`str` vs dict)가 이를 처리한다.

#### 5. pygetwindow의 `.activate()` 신뢰성

`pygetwindow`의 `.activate()` 메서드는 Windows에서 일부 앱(특히 UWP 앱)에 대해 실패하거나
창을 최소화에서 복원하지 못하는 경우가 있다. 실패 시 fallback으로
`win32gui.SetForegroundWindow()` (pywin32 패키지) 사용을 고려하나, `pywin32`는 현재
`requirements.txt`에 없으므로 구현자 에이전트가 실제 테스트 후 결정한다.

#### 6. Ollama와 같은 프로세스 내 메모리 경합

화면 에이전트가 Ollama로 전환된 동안 로컬 추론 모델이 상당한 메모리를 사용한다(qwen2.5:7b는
약 5~6 GB VRAM 또는 RAM). Groq가 복구(한도 리셋)되더라도 세션 내 Ollama 전환은 복원하지 않는
설계이므로, Ollama 사용 기간 동안 시스템 부하가 높아질 수 있음을 사용자에게 안내한다.

---

### A.8 구현 배치 계획

| 배치 | 내용 | 완료 기준 |
|---|---|---|
| **A-1. Ollama 엔진** | `core/engines/ollama_engine.py` 구현 | `python -c "from core.engines.ollama_engine import OllamaEngine; e=OllamaEngine(); print(e.describe())"` — `connected: True/False`가 JSON으로 출력. `OLLAMA_HOST`가 없어도 임포트 성공. |
| **A-2. ai_chat 폴백 수정** | `skills/skill_ai_chat.py` 수정 | (1) `GROQ_API_KEY`를 비활성화한 상태에서 에이전트 실행 시 Ollama로 동작하는지 확인. (2) `_engine` property가 `describe()` dict를 반환하는지 `assert`. |
| **A-3. screen_tool 구현** | `skills/agent_tools/screen_tool.py` 8개 함수 | `python -c "from skills.agent_tools import screen_tool; print(screen_tool.get_windows())"` — 열린 창 목록이 `ok: true` dict로 출력. `screenshot_read()` 실행 후 `data.elements`가 비어 있지 않음을 확인. |
| **A-4. skill_screen_agent 구현** | `skills/skill_screen_agent.py` | `python main.py --text`에서 "화면 에이전트로 메모장 열어줘" 입력 → 메모장이 실제로 열리고, 에이전트가 한국어 완료 메시지를 응답하는지 확인. |
| **A-5. Ollama 폴백 통합 테스트** | Groq 한도 소진 시나리오 시뮬레이션 | `_GROQ_RATE_LIMIT_SIGNAL`을 임시로 짧은 문자열로 바꿔 첫 응답에서 폴백이 트리거되도록 한 뒤, Ollama 응답이 정상 반환되는지 확인 후 상수 복원. |
