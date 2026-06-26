import calendar
import json
import queue
import re
import threading
import tkinter as tk
from datetime import date, datetime
from pathlib import Path

from core.skill_base import Skill, SkillResult

try:
    import holidays as _hlib
    _HAS_HOLIDAYS = True
except ImportError:
    _HAS_HOLIDAYS = False

# ── Jarvis 스타일 팔레트 ─────────────────────────────────────
_BG = "#0d1117"
_PANEL_BG = "#0a1929"
_TEXT = "#c9d1d9"
_ACCENT = "#00d4ff"
_TODAY_BG = "#1e3a5f"
_TODAY_FG = "#00ff99"
_WEEKEND_FG = "#ff7b7b"
_HOLIDAY_FG = "#ffaa44"       # 평일 공휴일 (주황)
_HOLWKND_FG = "#ff6b35"       # 주말 겹침 공휴일 (진주황)
_SCHED_FG  = "#58a6ff"        # 일정 표시 (소프트 블루)
_HDR_FG = "#8b949e"
_BTN_BG = "#161b22"
_BTN_ACTIVE = "#21262d"
_SEP = "#30363d"

_WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"]

_MONTH_RE = re.compile(r"(?:(\d{4})년\s*)?(\d{1,2})월")
_DATE_RE  = re.compile(r"(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일")
_YEAR_RE  = re.compile(r"(\d{4})년")


def _kr_holidays(year: int) -> dict[date, str]:
    """해당 연도의 한국 공휴일·대체공휴일 dict {date: 이름}을 반환한다."""
    if not _HAS_HOLIDAYS:
        return {}
    try:
        return dict(_hlib.KR(years=year, language="ko_KR"))
    except Exception:
        try:
            return dict(_hlib.KR(years=year))
        except Exception:
            return {}


_SCHEDULE_PATH = Path(__file__).parent.parent / "data" / "schedule.json"


def _load_schedule_map(year: int, month: int) -> dict[str, list[dict]]:
    """해당 년월의 일정을 {날짜ISO: [항목]} 형태로 반환한다."""
    smap: dict[str, list[dict]] = {}
    try:
        prefix = f"{year:04d}-{month:02d}"
        items = json.loads(_SCHEDULE_PATH.read_text(encoding="utf-8"))
        for item in items:
            if item.get("date", "").startswith(prefix):
                smap.setdefault(item["date"], []).append(item)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return smap


def _shorten(name: str) -> str:
    """셀 안에 표시할 공휴일 이름을 최대 4자로 축약한다."""
    return name.replace(" ", "")[:4]


class CalendarSkill(Skill):
    """'달력 띄워줘', '6월 달력 보여줘' 명령으로 Jarvis 전용 달력 창을 연다."""

    name = "calendar"
    description = "Jarvis 전용 달력 창을 새 창으로 띄운다"
    triggers = ["달력", "캘린더"]
    examples = ["달력 띄워줘", "이번 달 달력", "6월 달력 보여줘", "2025년 3월 달력"]

    def __init__(self) -> None:
        self._window: tk.Tk | None = None
        self._lock = threading.Lock()
        self._nav_queue: queue.Queue = queue.Queue()

    def can_handle(self, intent: str, text: str) -> float:
        if "달력" in text or "캘린더" in text:
            return 0.9
        # 달력이 열려 있을 때 날짜 이동 명령(년/월 포함)도 처리
        if self._window is not None and (_MONTH_RE.search(text) or _YEAR_RE.search(text)):
            return 0.85
        return 0.0

    @staticmethod
    def _parse_target(text: str) -> tuple[int | None, int | None, int | None]:
        """텍스트에서 (year, month, day) 를 파싱한다. 없으면 None."""
        dm = _DATE_RE.search(text)
        if dm:
            y = int(dm.group(1)) if dm.group(1) else None
            return y, int(dm.group(2)), int(dm.group(3))
        mm = _MONTH_RE.search(text)
        if mm:
            y = int(mm.group(1)) if mm.group(1) else None
            return y, int(mm.group(2)), None
        ym = _YEAR_RE.search(text)
        if ym:
            return int(ym.group(1)), None, None
        return None, None, None

    def execute(self, text: str, context: dict) -> SkillResult:
        now = datetime.now()
        t_year, t_month, t_day = self._parse_target(text)

        with self._lock:
            if self._window is not None:
                try:
                    self._window.lift()
                    self._window.focus_force()
                    # 이동할 날짜가 명시된 경우 Queue로 tkinter 루프에 전달
                    if t_year or t_month:
                        cur_year  = t_year  if t_year  else now.year
                        cur_month = t_month if t_month else now.month
                        self._nav_queue.put((cur_year, cur_month, t_day))
                        label = f"{cur_year}년 {cur_month}월"
                        if t_day:
                            label += f" {t_day}일"
                        return SkillResult(speech=f"달력을 {label}로 이동했습니다.", success=True)
                    return SkillResult(speech="달력 창을 앞으로 가져왔습니다.", success=True)
                except tk.TclError:
                    self._window = None

        year  = t_year  if t_year  else now.year
        month = t_month if t_month else now.month
        threading.Thread(target=self._run_window, args=(year, month, t_day), daemon=True).start()
        label = f"{year}년 {month}월"
        if t_day:
            label += f" {t_day}일"
        return SkillResult(
            speech=f"{label} 달력을 열었습니다.",
            success=True,
            data={"year": year, "month": month, "day": t_day},
        )

    def _run_window(self, year: int, month: int, day: int | None = None) -> None:  # noqa: PLR0912, PLR0915
        root = tk.Tk()
        root.title("◈ JARVIS · 달력")
        root.configure(bg=_BG)
        root.resizable(False, False)
        root.attributes("-topmost", True)   # 항상 최상위 — 작업표시줄 클릭 없이 즉시 표시

        w, h = 462, 580
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        with self._lock:
            self._window = root

        today = datetime.now()
        state = {"year": year, "month": month, "day": day}
        cells: list[tk.Widget] = []

        # ── 타이틀 헤더 ─────────────────────────────────────
        tk.Label(
            root,
            text="◈  J . A . R . V . I . S  ·  C A L E N D A R  ◈",
            bg=_PANEL_BG, fg=_ACCENT,
            font=("Consolas", 11, "bold"),
            pady=9,
        ).pack(fill="x")
        tk.Frame(root, bg=_SEP, height=1).pack(fill="x")

        # ── 월 탐색 바 ───────────────────────────────────────
        nav = tk.Frame(root, bg=_BG, pady=8)
        nav.pack(fill="x", padx=20)

        def _btn(parent: tk.Frame, text: str, cmd) -> tk.Button:
            return tk.Button(
                parent, text=text, command=cmd,
                bg=_BTN_BG, fg=_ACCENT, relief="flat",
                font=("Consolas", 13, "bold"), padx=14, pady=2,
                activebackground=_BTN_ACTIVE, activeforeground=_ACCENT,
                cursor="hand2", bd=0,
            )

        month_lbl = tk.Label(nav, text="", bg=_BG, fg=_TEXT, font=("Consolas", 14, "bold"))

        def prev_month() -> None:
            m, y = state["month"] - 1, state["year"]
            if m < 1:
                m, y = 12, y - 1
            state["month"], state["year"] = m, y
            _render()

        def next_month() -> None:
            m, y = state["month"] + 1, state["year"]
            if m > 12:
                m, y = 1, y + 1
            state["month"], state["year"] = m, y
            _render()

        _btn(nav, "◀", prev_month).pack(side="left")
        month_lbl.pack(side="left", expand=True)
        _btn(nav, "▶", next_month).pack(side="right")

        tk.Frame(root, bg=_SEP, height=1).pack(fill="x", padx=20)

        # ── 달력 그리드 ──────────────────────────────────────
        grid = tk.Frame(root, bg=_BG)
        grid.pack(fill="both", expand=True, padx=14, pady=(10, 4))
        for col in range(7):
            grid.columnconfigure(col, weight=1, uniform="col")
        for row in range(7):   # 요일 헤더 1 + 날짜 행 최대 6
            grid.rowconfigure(row, weight=1)

        # ── 공휴일 hover 표시 바 ─────────────────────────────
        tk.Frame(root, bg=_SEP, height=1).pack(fill="x", padx=20)
        holiday_bar = tk.Label(
            root, text="",
            bg=_PANEL_BG, fg=_TEXT,
            font=("Consolas", 9), pady=5,
            anchor="w", padx=14,
        )
        holiday_bar.pack(fill="x")

        # ── 오늘 날짜 ────────────────────────────────────────
        tk.Frame(root, bg=_SEP, height=1).pack(fill="x", padx=20)
        wd_str = _WEEKDAYS[today.isoweekday() % 7]   # isoweekday 1=월…7=일 → %7: 0=일…6=토
        tk.Label(
            root,
            text=f"  오늘 :  {today.year}년 {today.month}월 {today.day}일  ({wd_str}요일)",
            bg=_PANEL_BG, fg=_HDR_FG,
            font=("Consolas", 10), pady=6, anchor="w",
        ).pack(fill="x")

        # ── 렌더링 ───────────────────────────────────────────
        def _render() -> None:
            for widget in cells:
                widget.destroy()
            cells.clear()
            holiday_bar.config(text="")

            y, m = state["year"], state["month"]
            month_lbl.config(text=f"{y}년 {m:02d}월")
            kr_hols = _kr_holidays(y)
            smap = _load_schedule_map(y, m)

            # 요일 헤더 (일~토)
            for col, wd in enumerate(_WEEKDAYS):
                fg = _WEEKEND_FG if col in (0, 6) else _HDR_FG
                lbl = tk.Label(
                    grid, text=wd, bg=_BG, fg=fg,
                    font=("Consolas", 11, "bold"), anchor="center",
                )
                lbl.grid(row=0, column=col, sticky="nsew", pady=(0, 2))
                cells.append(lbl)

            # 날짜 — calendar.monthcalendar은 월요일 기준 → 일요일 기준으로 재배열
            for row_idx, week in enumerate(calendar.monthcalendar(y, m), start=1):
                sun_first = [week[6]] + week[:6]
                for col, day in enumerate(sun_first):
                    if day == 0:
                        spacer = tk.Label(grid, text="", bg=_BG)
                        spacer.grid(row=row_idx, column=col, sticky="nsew", padx=2, pady=2)
                        cells.append(spacer)
                        continue

                    d = date(y, m, day)
                    is_today    = (d == today.date())
                    is_selected = (state.get("day") == day) and not is_today
                    is_wknd  = col in (0, 6)
                    hol_name = kr_hols.get(d, "")
                    is_hol   = bool(hol_name)

                    # 배경·숫자 색상 결정 (우선순위: 오늘 > 선택일 > 공휴일평일 > 주말/공휴일주말 > 평일)
                    if is_today:
                        bg, num_fg, num_font = _TODAY_BG, _TODAY_FG, ("Consolas", 12, "bold")
                    elif is_selected:
                        bg, num_fg, num_font = "#1a2a1a", _ACCENT, ("Consolas", 12, "bold")
                    elif is_hol and not is_wknd:
                        bg, num_fg, num_font = _BG, _HOLIDAY_FG, ("Consolas", 11, "bold")
                    elif is_hol and is_wknd:
                        bg, num_fg, num_font = _BG, _HOLWKND_FG, ("Consolas", 11, "bold")
                    elif is_wknd:
                        bg, num_fg, num_font = _BG, _WEEKEND_FG, ("Consolas", 11)
                    else:
                        bg, num_fg, num_font = _BG, _TEXT, ("Consolas", 11)

                    # 셀 프레임
                    cell = tk.Frame(
                        grid, bg=bg,
                        highlightbackground=_ACCENT if (is_today or is_selected) else _BG,
                        highlightthickness=1 if (is_today or is_selected) else 0,
                    )
                    cell.grid(row=row_idx, column=col, sticky="nsew", padx=2, pady=2)

                    num_lbl = tk.Label(
                        cell, text=str(day),
                        bg=bg, fg=num_fg, font=num_font, anchor="center",
                    )
                    num_lbl.pack(fill="x")

                    hover_widgets: list[tk.Widget] = [cell, num_lbl]
                    hover_parts: list[str] = []

                    if is_hol:
                        hol_fg = _HOLIDAY_FG if not (is_today or is_wknd) else (_TODAY_FG if is_today else _HOLWKND_FG)
                        hol_lbl = tk.Label(
                            cell, text=_shorten(hol_name),
                            bg=bg, fg=hol_fg,
                            font=("Consolas", 7), anchor="center",
                        )
                        hol_lbl.pack(fill="x")
                        hover_widgets.append(hol_lbl)
                        hover_parts.append(f"◈ {hol_name}")

                    # 일정 표시 (최대 2개, 초과분은 +N)
                    day_scheds = smap.get(d.isoformat(), [])
                    for s_item in day_scheds[:2]:
                        s_lbl = tk.Label(
                            cell, text=s_item["title"][:5],
                            bg=bg, fg=_SCHED_FG,
                            font=("Consolas", 7), anchor="center",
                        )
                        s_lbl.pack(fill="x")
                        hover_widgets.append(s_lbl)
                        t_str = s_item.get("time") or ""
                        t_prefix = f"{t_str} " if t_str else ""
                        hover_parts.append(f"● {t_prefix}{s_item['title']}")
                    if len(day_scheds) > 2:
                        more_lbl = tk.Label(
                            cell, text=f"+{len(day_scheds) - 2}",
                            bg=bg, fg=_SCHED_FG,
                            font=("Consolas", 7), anchor="center",
                        )
                        more_lbl.pack(fill="x")
                        hover_widgets.append(more_lbl)

                    # 공휴일·일정 통합 hover: 하단 info bar에 상세 표시
                    if hover_parts:
                        hover_text = "   ".join(hover_parts)
                        def _enter(e, txt=hover_text) -> None:
                            holiday_bar.config(text=f"  {txt}")
                        def _leave(e) -> None:
                            holiday_bar.config(text="")
                        for w in hover_widgets:
                            w.bind("<Enter>", _enter)
                            w.bind("<Leave>", _leave)

                    cells.append(cell)

        def _poll_nav() -> None:
            """메인/다른 스레드가 넣은 이동 명령을 tkinter 루프 안에서 안전하게 처리한다."""
            try:
                y, m, d = self._nav_queue.get_nowait()
                state["year"], state["month"], state["day"] = y, m, d
                _render()
            except queue.Empty:
                pass
            root.after(150, _poll_nav)

        def _on_close() -> None:
            # 잔여 이동 명령 비우기
            while not self._nav_queue.empty():
                try:
                    self._nav_queue.get_nowait()
                except queue.Empty:
                    break
            with self._lock:
                self._window = None
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", _on_close)
        root.after(150, _poll_nav)
        _render()
        root.mainloop()

        with self._lock:
            self._window = None
