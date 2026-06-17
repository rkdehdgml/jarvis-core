# jarvis-core

Windows 네이티브 개인 AI 비서. Claude Code CLI 단일 엔진.

## 요구 사항

- Python 3.11 이상
- Claude Code CLI 설치 및 로그인 완료

## 가상환경 설정 (Windows PowerShell)

```powershell
# 1. 가상환경 생성
python -m venv .venv

# 2. 가상환경 활성화
.\.venv\Scripts\Activate.ps1

# 실행 정책 오류 시 먼저 실행:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 실행 (STEP 6 이후)
python main.py

# 텍스트 모드로 실행 (음성 없이)
python main.py --text

# 5. 가상환경 비활성화
deactivate
```

## 프로젝트 구조

```
jarvis-core/
├── main.py                  # 진입점
├── config/                  # 전역 설정, 자비스 성격 프롬프트
├── core/                    # ⚠️ 본체 — 거의 수정하지 않음
├── voice/                   # 음성 입출력 (STT, TTS, 핫워드)
├── ui/                      # 웹 UI (FastAPI + React)
├── skills/                  # ⭐ 기능 추가 시 여기에 파일만 넣기
└── data/                    # 스킬 데이터 저장소
```

## 새 기능 추가

`skills/` 폴더에 `skill_<이름>.py` 파일을 추가하면 자동으로 등록됩니다.
본체 코드(`core/`) 수정은 필요 없습니다.
