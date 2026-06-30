# jarvis-core

Windows 네이티브 한국어 개인 AI 비서. 음성("Hey Jarvis" 또는 박수 두 번) 또는 웹 대시보드 텍스트로 조작합니다.

**AI 엔진**: Groq (`llama-3.3-70b-versatile`) — 빠른 응답, 무료 티어 제공  
**스킬**: 33개 (자동 등록 — `skills/skill_*.py` 파일만 추가하면 됨)

---

## 요구 사항

- Python 3.11 이상 (Windows)
- Groq API 키 ([console.groq.com](https://console.groq.com) 에서 무료 발급)
- ffmpeg — 화면 녹화·음성 녹음·카메라 사용 시 PATH에 등록 필요
- nircmd — 볼륨 제어 사용 시 PATH에 등록 필요

---

## 설치 및 실행

```powershell
# 1. 가상환경 생성 및 활성화
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# (실행 정책 오류 시: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser)

# 2. 의존성 설치
pip install -r requirements.txt

# 3. 환경변수 설정
copy .env.example .env
# .env 파일을 열어 GROQ_API_KEY 입력 (필수)
# 나머지 키는 해당 스킬을 쓸 때만 필요

# 4. 실행 — 음성 + 웹 대시보드 동시 실행 (기본)
python main.py

# 4'. 실행 — 텍스트 + 웹 대시보드 (마이크 없이)
python main.py --text

# 4''. 실행 — 웹 대시보드 없이 음성만
python main.py --no-web
```

> `python main.py` 하나로 **음성 루프와 웹 대시보드(포트 8765)가 동시에 실행**됩니다.  
> 두 프로세스가 같은 `broadcaster`를 공유하므로 음성 명령 결과가 브라우저에 실시간 반영됩니다.

### 웹 대시보드 프론트엔드

```powershell
cd ui\web
npm install
npm run dev        # Vite 개발 서버: http://localhost:5173
npm run build      # 프로덕션 빌드
npm run typecheck  # 타입 검사
```

빌드 후에는 `http://localhost:8765` 로 바로 접속 가능합니다.

---

## 환경변수 (.env)

| 변수 | 필수 | 설명 |
|------|------|------|
| `GROQ_API_KEY` | **필수** | Groq API 키 |
| `DAEJEON_BUS_API_KEY` | 선택 | 대전광역시 버스 정보 스킬 (data.go.kr 공공데이터포털) |
| `NEWSAPI_KEY` | 선택 | 뉴스 스킬 (NewsAPI.org 무료 티어, 없으면 안내 문구) |
| `BRAVE_SEARCH_API_KEY` | 선택 | 웹 검색을 Brave로 전환 (없으면 DuckDuckGo 사용) |
| `GMAIL_ADDRESS` | 선택 | 이메일 스킬용 Gmail 주소 |
| `GMAIL_APP_PASSWORD` | 선택 | Gmail 앱 비밀번호 (계정 비밀번호 아님, 2단계 인증 필요) |
| `WHATSAPP_DEFAULT_COUNTRY_CODE` | 선택 | WhatsApp 기본 국가코드 (기본값: `+82`) |

---

## 기능 목록

### AI 대화 & 검색

| 스킬 | 예시 발화 | 비고 |
|------|-----------|------|
| AI 대화 | "파이썬 리스트와 튜플 차이 알려줘" | Groq Llama 3.3 70B, 다른 스킬이 못 처리하면 자동 폴백 |
| 웹 검색 | "환율 검색해줘", "요즘 주가 찾아줘" | DuckDuckGo 기본, Brave Search 선택 |
| 위키백과 | "아인슈타인 알려줘", "블랙홀 위키백과" | MediaWiki REST API, 한국어 요약 TTS |
| 방법 안내 | "파이썬 설치 방법", "엑셀 단축키 알려줘" | AI 기반 방법론 안내 |
| **에이전트** | "AI 트렌드 조사해줘", "삼성전자 뉴스 찾아서 엑셀로 저장해줘" | Groq tool-calling 루프, 최대 10턴 자동 실행 |

### 날씨 & 정보

| 스킬 | 예시 발화 | 비고 |
|------|-----------|------|
| 날씨 | "서울 날씨", "내일 대전 기온", "강수확률" | Open-Meteo (무료, 키 불필요), 주요 한국 도시 지원 |
| 뉴스 | "오늘 뉴스", "최신 기술 뉴스" | NewsAPI 필요 |
| 날짜·시간 | "지금 몇 시야", "오늘 날짜" | 시스템 시간 기준 |
| IP 정보 | "내 IP 알려줘", "IP 주소" | 공인 IP + 위치 정보 |
| 위치 | "내 위치 알려줘" | IP 기반 위치 |
| 인터넷 속도 | "속도 측정", "인터넷 빠른지 확인해줘" | Cloudflare 엔드포인트, 키 불필요 |

### 대전광역시 버스 정보

`DAEJEON_BUS_API_KEY` 필요 (data.go.kr 공공데이터포털 발급)

| 발화 | 동작 |
|------|------|
| "샘머리아파트정류장 버스 정보 알려줘" | 해당 정류장 도착 예정 버스 목록 표시 |
| "① 추적해줘" / "102번 추적해줘" | 목록에서 선택한 버스를 정류장 도착까지 반복 추적 |
| "911 버스 위치 정보 알려줘" | 버스 번호만으로 즉시 추적 시작 (저장된 정류소 자동 탐색) |
| "911번 버스 현재 위치는 어디야" | 911번 버스 현재 정류소 위치 1회 조회 |
| "버스 추적 중단" | 진행 중인 추적 중지 |
| "정류소 저장 갈마역 8001234" | 정류소 ID 저장 (이후 이름으로 바로 조회 가능) |

**추적 알림 방식**
- 추적 시작 시 현황 1회 표시 (현재 위치, 남은 정류장 수, 예상 도착 시간)
- 버스가 이동해 정류장 수가 바뀔 때마다 `[버스 알림]` 표시
- `OO정류소에서 XX정류소로 이동 중` 형식으로 이동 경로 표시
- 버스가 도착하면 자동으로 추적 종료
- 웹 대시보드에 실시간 반영 (WebSocket)

**정류소 등록 방법**
1. 카카오버스·네이버 지도 앱에서 정류소 검색 → ID 확인
2. "정류소 저장 [이름] [ID]" 발화로 등록
3. 이후 이름만으로 조회 가능 (자동 저장)

### PC 제어

| 스킬 | 예시 발화 | 비고 |
|------|-----------|------|
| 앱 실행 | "크롬 열어", "메모장 실행", "계산기 켜줘" | ShellExecute — App Paths 레지스트리 참조 |
| 앱 종료 | "크롬 꺼줘", "메모장 종료" | pygetwindow |
| 볼륨 | "볼륨 올려줘", "소리 50으로", "음소거" | pycaw (Windows 전용) |
| 창 제어 | "창 최소화", "최대화해줘" | pygetwindow |
| 클립보드 | "클립보드 뭐야", "복사된 내용 알려줘" | pyperclip |
| 시스템 정보 | "CPU 몇 퍼센트야", "메모리 확인", "배터리" | psutil |
| 시스템 상태 | "디스크 용량", "저장공간 확인", "시스템 상태" | PowerShell Get-CimInstance |
| 전원 관리 | "컴퓨터 종료", "재시작해줘", "절전 모드" | ⚠️ 즉시 실행 (미저장 작업 주의) |
| 슬립 모드 | "슬립 모드", "자비스 잠깐 꺼줘" | 음성인식만 일시 중단, PC는 켜진 상태 유지 |

### 브라우저 & 인터넷

| 스킬 | 예시 발화 | 비고 |
|------|-----------|------|
| 브라우저 열기 | "지메일 열어줘", "쿠팡 열어", "네이버 열어" | 기본 브라우저로 실행 (os.startfile) |
| 사이트 검색 | "구글에서 라면 맛집 검색해줘", "네이버에서 날씨 검색해줘" | 구글·네이버 검색 결과 페이지로 이동 |
| URL 열기 | "https://github.com 열어줘" | 직접 URL 입력 지원 |
| 유튜브 | "유튜브에서 재즈 찾아줘", "lofi 다운로드해줘" | 검색은 브라우저, 다운로드는 yt-dlp |

지원 사이트 바로가기: 지메일, 구글맵/구글 지도, 구글드라이브, 인스타그램, 페이스북, 트위터, 쿠팡, 네이버쇼핑, 네이버

### 미디어 캡처 (ffmpeg 필요)

| 스킬 | 예시 발화 | 저장 위치 |
|------|-----------|-----------|
| 스크린샷 | "스크린샷 찍어줘", "화면 캡처" | `data/captures/screenshot_YYYYMMDD_HHMMSS.png` |
| 화면 녹화 | "화면 녹화해줘", "30초 녹화" | `data/captures/screen_YYYYMMDD_HHMMSS.mp4` |
| 음성 녹음 | "녹음해줘", "30초 녹음" | `data/captures/voice_YYYYMMDD_HHMMSS.wav` |
| 카메라 촬영 | "사진 찍어줘", "셀카 찍어" | `data/captures/camera_YYYYMMDD_HHMMSS.png` |

### 생산성 & 유틸리티

| 스킬 | 예시 발화 | 비고 |
|------|-----------|------|
| 달력 | "달력 띄워줘", "6월 달력", "2025년 3월 달력" | Jarvis 전용 UI 창, 한국 공휴일·대체공휴일·음력 연휴 표시 |
| 타이머 | "3분 타이머", "30초 후 알려줘", "1시간 타이머" | 백그라운드 실행, 완료 시 비프음 알림 |
| 일정 관리 | "내일 오후 3시 회의 등록해줘", "오늘 일정 알려줘" | 로컬 JSON (`data/schedule.json`) |
| 연락처 | "홍길동 전화번호 알려줘", "연락처 추가해줘" | 로컬 JSON (`data/contacts.json`) |
| 이메일 발송 | "홍길동한테 메일 보내줘" | Gmail SMTP ⚠️ 실제 발송 |
| WhatsApp 발송 | "홍길동한테 왓츠앱 보내줘" | pywhatkit ⚠️ WhatsApp Web 로그인 필요 |
| PDF 읽기 | "보고서.pdf 읽어줘" | pypdf 파싱 + edge-tts 음성 출력 |
| QR 코드 | "QR 코드 만들어줘" | `data/qr/` 에 PNG 저장 |
| 농담 | "농담 해줘", "웃긴 거 알려줘" | pyjokes |

---

## 에이전트 상세

"AI 트렌드 조사해줘" 같은 복합 태스크를 Groq Llama의 native tool-calling으로 자동 수행합니다.

### 트리거 조건

| 패턴 | 예시 |
|------|------|
| `~조사해줘 / ~수집해줘` | "최신 AI 논문 수집해줘", "파이썬 라이브러리 조사해줘" |
| `찾아서/검색해서 + 저장 키워드` | "삼성전자 뉴스 찾아서 엑셀로 저장해줘" |
| `에이전트로 ~` | "에이전트로 처리해줘" |

### 내장 도구 8종

| 도구 | 동작 |
|------|------|
| `search` | DuckDuckGo 웹 검색 (최대 5건) |
| `open_url` | URL 페이지 열기 (requests + BeautifulSoup4) |
| `get_all_text` | 현재 페이지 본문 추출 |
| `get_links` | 현재 페이지 링크 목록 추출 |
| `save_text` | 바탕화면에 txt 저장 |
| `save_json` | 바탕화면에 JSON 저장 |
| `save_xlsx` | 바탕화면에 엑셀 저장 (openpyxl) |
| `report` | 진행 상황 TTS 보고 |

- **저장 위치**: 항상 바탕화면 (`~/Desktop`). 파일명을 지정하지 않으면 `jarvis_YYYYMMDD_HHMMSS.확장자` 자동 생성
- **도구 실패 복구**: 특정 페이지 접근 실패(ok=False) 시 에이전트가 스스로 대안을 찾아 계속 진행
- **출력 절삭**: 도구 결과는 2000자로 잘라 컨텍스트 과부하를 방지

---

## 달력 상세

"달력 띄워줘" 명령으로 Jarvis 전용 달력 창이 열립니다.

- **항상 최상위**: 다른 창 위에 즉시 표시 (작업표시줄 클릭 불필요)
- **한국 공휴일 자동 표시**: 설날·추석(음력 자동 계산), 삼일절, 어린이날, 현충일, 광복절, 개천절, 한글날, 크리스마스 등
- **대체공휴일 포함**: "삼일절 대체 휴일", "광복절 대체 휴일" 등 자동 반영
- **색상 구분**: 오늘(초록) / 평일 공휴일(주황) / 주말+공휴일(진주황) / 주말(빨강)
- **공휴일 이름**: 셀 안에 4자 축약 표시, 마우스 오버 시 하단에 전체 이름
- **월 탐색**: ◀ ▶ 버튼으로 이전/다음 달 이동
- **특정 월 지정**: "6월 달력", "2025년 3월 달력" 형식 지원

---

## 음성 모드

| 동작 | 방법 |
|------|------|
| 활성화 | "Hey Jarvis" (웨이크워드) 또는 박수 두 번 |
| 비활성화 | "자비스 오프" 또는 "자비스 종료" |
| 슬립 (일시 중단) | "슬립 모드" 또는 "자비스 잠깐 꺼줘" → 웨이크워드 대기로 복귀 |
| 프로그램 종료 | "종료" |

- **STT**: faster-whisper (`base` 모델, 한국어)
- **TTS**: edge-tts (`ko-KR-SunHiNeural`)
- **웨이크워드**: openWakeWord 사전학습 모델 "hey_jarvis" (영어 발음)

> 한국어 "자비스" 전용 웨이크워드 모델은 현재 없습니다. 학습 후 `voice/wakeword.py`의 `_WAKEWORD_NAME`만 바꾸면 교체됩니다.

마이크 인식 불가 시: Windows 설정 → 시스템 → 소리 → 입력에서 장치 "사용" 상태 확인.

---

## 프로젝트 구조

```
jarvis-core/
├── main.py                    # 진입점 (음성+웹 동시 실행, --text / --no-web 플래그)
├── config/
│   ├── settings.yaml          # 설정 참조 (주요 값은 코드 상수로 관리)
│   └── persona.md             # 자비스 성격·응답 지침 (AI 시스템 프롬프트)
├── core/                      # ⚠️ 핵심 엔진 — 수정 금지
│   ├── engines/
│   │   ├── groq_engine.py     # 현재 활성 엔진 (Groq llama-3.3-70b)
│   │   └── claude_code.py     # 대체 엔진 (Claude Code CLI)
│   ├── registry.py            # 스킬 자동 등록 (glob 스캔)
│   ├── router.py              # 라우팅 (can_handle 최고 점수 ≥ 0.4 선택)
│   ├── dispatcher.py          # 스킬 실행 + 예외 격리
│   ├── context.py             # 대화 맥락 (최근 20턴)
│   ├── skill_base.py          # Skill ABC, SkillResult 정의
│   ├── bus_client.py          # 대전 버스 도착정보 API (getArrInfoByStopID)
│   ├── buspos_client.py       # 대전 버스 실시간 위치 API (getBusPosByRtid)
│   └── busstop_client.py      # 대전 버스정류소 검색 API + BIS 캐시
├── commands/                  # Windows OS 위임 카탈로그
│   ├── registry.py            # COMMAND_MAP + register()
│   ├── windows_bridge.py      # subprocess·shell·ffmpeg 래퍼
│   └── specs/                 # 명령 명세 (power/browser/system/capture)
├── voice/                     # 음성 입출력 (Windows 전용)
│   ├── stt.py                 # faster-whisper STT
│   ├── tts.py                 # edge-tts TTS
│   ├── wakeword.py            # openWakeWord + ClapDetector 레이스
│   └── clap_detector.py       # 박수 감지 (독립 유닛)
├── ui/
│   ├── server.py              # FastAPI (GET /api/status, POST /api/chat, WS /ws)
│   └── web/                   # React 18 + TypeScript + Vite 프론트엔드
├── skills/                    # ⭐ 기능 파일 — 여기에만 추가 (33개)
│   ├── agent_tools/           # 에이전트 전용 도구 패키지
│   ├── skill_bus_tracker.py   # 대전 버스 도착정보·실시간 위치 추적
│   ├── skill_agent.py         # Groq tool-calling 에이전트
│   ├── skill_ai_chat.py       # AI 대화 폴백
│   ├── skill_web_search.py    # 웹 검색
│   ├── skill_weather.py       # 날씨
│   ├── skill_news.py          # 뉴스
│   ├── skill_datetime.py      # 날짜·시간
│   ├── skill_browser.py       # 브라우저 제어
│   ├── skill_youtube.py       # 유튜브
│   ├── skill_app_launch.py    # 앱 실행
│   ├── skill_app_control.py   # 앱 종료
│   ├── skill_power.py         # 전원 관리
│   ├── skill_sleep_mode.py    # 음성인식 슬립
│   ├── skill_timer.py         # 타이머
│   ├── skill_calendar.py      # Jarvis 달력 UI
│   ├── skill_screenshot.py    # 스크린샷
│   ├── skill_screen_record.py # 화면 녹화
│   ├── skill_voice_record.py  # 음성 녹음
│   ├── skill_camera.py        # 카메라
│   ├── skill_system_info.py   # CPU·메모리·배터리
│   ├── skill_system_status.py # 디스크·시스템 상태
│   ├── skill_volume.py        # 볼륨
│   ├── skill_window.py        # 창 제어
│   ├── skill_clipboard.py     # 클립보드
│   ├── skill_schedule.py      # 일정
│   ├── skill_contacts.py      # 연락처
│   ├── skill_email.py         # 이메일
│   ├── skill_whatsapp.py      # WhatsApp
│   ├── skill_pdf_reader.py    # PDF 읽기
│   ├── skill_wikipedia.py     # 위키백과
│   ├── skill_howto.py         # 방법 안내
│   ├── skill_qr.py            # QR 코드
│   └── skill_joke.py          # 농담
├── tests/                     # assert 기반 단위 테스트
├── data/                      # 런타임 데이터
│   ├── contacts.json          # 연락처
│   ├── schedule.json          # 일정
│   ├── bus_config.json        # 저장된 버스 정류소 목록
│   ├── daejeon_bis_stops.json # 대전 BIS 정류소 캐시
│   └── groq_usage.json        # Groq 토큰 사용량
├── .env.example               # 환경변수 템플릿
├── requirements.txt
└── CLAUDE.md                  # Claude Code 전용 개발 지침
```

---

## 새 기능 추가

`skills/` 폴더에 `skill_<이름>.py` 파일 하나만 추가하면 자동 등록됩니다. `core/` 수정 불필요.

```python
from core.skill_base import Skill, SkillResult

class MySkill(Skill):
    name = "my_skill"
    description = "한 줄 설명"
    triggers = ["키워드"]
    examples = ["예시 발화"]

    def can_handle(self, intent: str, text: str) -> float:
        return 0.9 if "키워드" in text else 0.0

    def execute(self, text: str, context: dict) -> SkillResult:
        return SkillResult(speech="응답 텍스트", success=True)
```

라우터 임계값 **0.4** — `can_handle`이 0.4 미만이면 AI 대화 폴백으로 넘어갑니다.

---

## 테스트 실행

```powershell
# 개별 스킬 테스트 (pytest 없음 — assert 기반 스크립트)
python -m tests.test_skill_calendar
python -m tests.test_skill_timer
python -m tests.test_skill_browser
python -m tests.test_skill_email
# ... 등 tests/ 아래 test_*.py 전부 동일 방식

# 에이전트 테스트 3종
python -m tests.test_agent_tools    # 도구 단위 테스트 20개
python -m tests.test_skill_agent    # 스킬 단위 테스트 15개
python -m tests.test_agent_e2e      # 엔드투엔드 시나리오 3개
```

---

## 주의사항

- **전원 종료·재시작**: 미저장 작업이 모두 손실됩니다. 실행 전 저장 여부를 반드시 확인하세요.
- **이메일·WhatsApp 발송**: 실제로 전송됩니다. 테스트 시 수신자를 확인하세요.
- **화면 녹화·녹음·카메라**: ffmpeg이 PATH에 없으면 기능이 비활성화됩니다.
- **Gmail 앱 비밀번호**: 구글 계정 비밀번호가 아닌 "앱 비밀번호"를 사용하세요 (2단계 인증 필요).
- **슬립 모드**: 음성인식만 중단됩니다. 재활성화하려면 "Hey Jarvis" 또는 박수 두 번을 사용하세요.
- **에이전트 파일 저장**: 에이전트가 생성한 파일은 바탕화면에 저장됩니다. 불필요한 경우 직접 삭제하세요.
- **버스 스킬**: `DAEJEON_BUS_API_KEY` 없이 실행해도 다른 기능에는 영향 없습니다. 버스 관련 발화 시에만 안내 메시지가 표시됩니다.
