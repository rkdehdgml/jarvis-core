# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

jarvis-core is a Windows-native Korean-language personal AI assistant ("자비스"/J.A.R.V.I.S). It uses the
**Claude Code CLI** (`claude -p ...`) as its only AI engine — there is no direct Anthropic API call anywhere
in this codebase. Voice input/output is optional; everything also works in a text-only mode.

The full design rationale and step-by-step build plan live in `JARVIS_PLUGIN_DESIGN.md`. Read it if you need
the "why" behind a structural decision — this file only covers the "what" and "how".

## Commands

```powershell
# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run (voice mode: wakeword "자비스" → STT → route/dispatch → TTS)
python main.py

# Run (text-only mode, no mic — also the debug/fallback path)
python main.py --text

# Run the web dashboard (separate process, separate port)
uvicorn ui.server:app --host 127.0.0.1 --port 8765

# Frontend (ui/web — React + TS + Vite)
cd ui/web
npm install
npm run dev         # Vite dev server, http://localhost:5173
npm run build       # tsc -b && vite build
npm run typecheck   # tsc --noEmit

# Tests (no pytest — plain assert-based scripts run as modules)
python -m tests.test_skills_step5
```

There is no linter/formatter configured. There is no `pytest`; tests are standalone scripts under `tests/`
that `assert` and print results, invoked with `python -m tests.<module>`.

## Architecture

### The core rule: `core/` is frozen, `skills/` is where everything happens

The entire system is designed around one constraint: **`core/` is built once and essentially never touched
again.** All new functionality is added by dropping a new `skills/skill_<name>.py` file — no registration
step, no edits to existing files. Removing a feature means deleting its file. When asked to add a feature,
the default move is "write a new skill file", not "extend the router/dispatcher".

`voice/` (audio I/O) and `ui/` (web dashboard) are likewise kept fully decoupled from `core/`: core only
emits text in/out and status events, and never knows whether the input came from a microphone or a chat box.

### Pipeline

```
input text -> Router.route() -> Skill | None -> Dispatcher.dispatch() -> SkillResult
```

- **`core/registry.py`** (`SkillRegistry`) — glob-scans `skills/skill_*.py` on startup, `exec_module`s each
  file, and instantiates every concrete `Skill` subclass found. A broken skill file is caught and logged
  without affecting the others. `reload()` re-scans at runtime.
- **`core/router.py`** (`Router`) — calls `can_handle(intent, text) -> float` on every loaded skill and picks
  the highest score. If the best score is below the threshold (`_DEFAULT_THRESHOLD = 0.4` in `router.py`,
  *not* currently read from `config/settings.yaml` — see Gotchas below), it returns `None` to signal "AI
  fallback needed".
- **`core/dispatcher.py`** (`Dispatcher`) — runs the chosen skill's `execute()`, catching exceptions so one
  skill failing never crashes the loop. If `Router` returned `None`, it falls back to whichever skill is
  named `"ai_chat"` (see `skills/skill_ai_chat.py`). Emits `StatusEvent`s (`processing` → `responded`) via
  the global `broadcaster`.
- **`core/skill_base.py`** — the `Skill` ABC and `SkillResult` dataclass. This is the contract every skill
  must satisfy:

  ```python
  class MySkill(Skill):
      name = "my_skill"               # lowercase_with_underscores, unique
      description = "one-line description for the router"
      triggers = ["키워드1", "키워드2"]
      examples = ["예시 문장"]

      def can_handle(self, intent: str, text: str) -> float:  # 0.0–1.0 confidence
          ...

      def execute(self, text: str, context: dict) -> SkillResult:
          return SkillResult(speech="...", success=True, data={}, follow_up=False)
  ```
  `context` is `ConversationContext.to_dict()`: `{"history": [Turn, ...], "data": {...}}`. `follow_up=True`
  on the result tells the voice loop to skip waiting for the wakeword on the next turn (multi-turn exchange).
- **`core/context.py`** (`ConversationContext`) — shared turn history (capped, default 20) plus a free-form
  `dict` for cross-skill session state (`get`/`set`/`delete`). One instance is shared by `Router`/`Dispatcher`
  for the lifetime of a run.
- **`core/input_channel.py`** — normalizes voice STT output and chat text into the same `InputEvent`. Also
  tracks consecutive STT failures (`record_stt_failure()`); after 3 (`_STT_FAIL_LIMIT`) it signals (via a
  status event) that the caller should fall back to chat mode. Voice failing must never stop the assistant —
  this is a deliberate design invariant, not an incidental detail.
- **`core/status_events.py`** — `StatusBroadcaster` (singleton instance `broadcaster`) is the *only* channel
  through which `core/` talks to the UI layer: it emits `idle | listening | processing | responded` events.
  `ui/server.py` subscribes to it and relays over WebSocket. Nothing in `core/` imports from `ui/`.
- **`core/engines/claude_code.py`** (`ClaudeCodeEngine`) — the only AI engine. Shells out to
  `claude -p <prompt> --output-format json` with an environment variable **whitelist** (`_ENV_WHITELIST`),
  injects `config/persona.md` as a system-style preamble, parses the JSON result, and records
  `total_cost_usd` via `core/usage.py` into `data/usage.json` (used for the daily-budget usage gauge in the
  UI, default budget `$1.00/day`). Never raises outward — all failure modes (timeout, missing `claude` on
  PATH, non-zero exit, bad JSON) degrade to a Korean error string.

### Two independent runtime entry points

`main.py` (voice/text loop) and `ui/server.py` (FastAPI dashboard, run via `uvicorn`) each construct their
**own** `SkillRegistry` / `Router` / `Dispatcher` / `ConversationContext`. They are not the same process and
do not share conversation state — running both gives you two independent "sessions" against the same skill
set. `ui/server.py`'s docstring notes that wiring uvicorn into `main.py`'s process (e.g. as an asyncio task)
is an intentional non-goal of that file.

### Skill routing/scoring convention

Skills score themselves defensively, not just by keyword presence — e.g. `skill_app_control.py` deliberately
returns a low score (0.3) for ambiguous "꺼줘" without a known app name so that a more specific skill (like
volume's "소리 꺼줘") can win instead. `skill_ai_chat.py` always returns `0.1`, low enough to never be picked
directly, only reached via the `Router -> None -> Dispatcher fallback` path. Follow this pattern for new
skills: prefer returning a low/zero score over guessing, and let the AI fallback handle genuine ambiguity.

### Voice layer (`voice/`, Windows-native only)

- `stt.py` — `silero-vad` detects speech boundaries, `faster-whisper` ("base" model, Korean) transcribes.
  Input device is picked by matching `"mic"` in the device name (Korean driver names get mangled by
  PortAudio but the English suffix survives) since the OS default input device is unreliable on this setup.
  Audio is captured at the device's native sample rate via callback stream (WDM-KS backend requirement) and
  resampled to 16kHz for VAD/Whisper.
- `wakeword.py` — `openWakeWord`'s pretrained `"hey_jarvis"` ("Hey Jarvis") English model. A Korean "자비스"
  wakeword model does not exist yet (would need custom training) — `_WAKEWORD_NAME` is the single swap point
  for when one is trained.
- `tts.py` — `edge-tts` synthesis.
- `text_input.py` — console input used by `--text` mode.

### UI layer (`ui/`)

- `ui/server.py` — FastAPI app exposing `GET /api/status` (snapshot), `POST /api/chat` (text in,
  `channel="chat"` so TTS is never invoked for it), and `WS /ws` (live status push). CORS is locked to the
  Vite dev origins (`localhost:5173`).
- `ui/web/` — separate npm project (React 18 + TypeScript + Vite). `useJarvisStatus.ts` is the shared hook
  both UI modes (`JarvisMinimal`, `JarvisFull`) subscribe to for live state.

## Gotchas

- **`config/settings.yaml` is not actually read by any code yet.** Values like `router.threshold`,
  `voice.stt_fail_limit`, `engine.timeout` exist there but the real values are hardcoded as module-level
  constants in `core/router.py`, `core/input_channel.py`, `core/engines/claude_code.py`, etc. Treat the YAML
  as a (currently aspirational) reference, not the source of truth — if you change a tunable, change the
  constant in code, and consider whether wiring it through `settings.yaml` is actually in scope.
- Several skills (`skill_volume.py`, `skill_window.py`) depend on Windows-only packages (`pycaw`,
  `pygetwindow`) and import them lazily inside `execute()` so the rest of the app still loads if those
  packages are missing.
- `__pycache__` directories at the repo root and inside packages are stale build artifacts, not source.
