import calendar
import re
import threading
import tkinter as tk
from datetime import date, datetime

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
_HDR_FG = "#8b949e"
_BTN_BG = "#161b22"
_BTN_ACTIVE = "#21262d"
_SEP = "#30363d"

_WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"]

_MONTH_RE = re.compile(r"(?:(\d{4})년\s*)?(\d{1,2})월")
_YEAR_RE = re.compile(r"(\d{4})년")


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

    def can_handle(self, intent: str, text: str) -> float:
        if "달력" in text or "캘린더" in text:
            return 0.9
        return 0.0

    def execute(self, text: str, context: dict) -> SkillResult:
        now = datetime.now()
        year, month = now.year, now.month

        m = _MONTH_RE.search(text)
        if m:
            if m.group(1):
                year = int(m.group(1))
            month = int(m.group(2))
        else:
            y_m = _YEAR_RE.search(text)
            if y_m:
                year = int(y_m.group(1))

        with self._lock:
            if self._window is not None:
                try:
                    self._window.lift()
                    self._window.focus_force()
                    return SkillResult(speech="달력 창을 앞으로 가져왔습니다.", success=True)
                except tk.TclError:
                    self._window = None

        threading.Thread(target=self._run_window, args=(year, month), daemon=True).start()
        return SkillResult(
            speech=f"{year}년 {month}월 달력을 열었습니다.",
            success=True,
            data={"year": year, "month": month},
        )

    def _run_window(self, year: int, month: int) -> None:  # noqa: PLR0912, PLR0915
        root = tk.Tk()
        root.title("◈ JARVIS · 달력")
        root.configure(bg=_BG)
        root.resizable(False, False)
        root.attributes("-topmost", True)   # 항상 최상위 — 작업표시줄 클릭 없이 즉시 표시

        w, h = 462, 530
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        with self._lock:
            self._window = root

        today = datetime.now()
        state = {"year": year, "month": month}
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
            bg=_PANEL_BG, fg=_HOLIDAY_FG,
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
                    is_today = (d == today.date())
                    is_wknd = col in (0, 6)
                    hol_name = kr_hols.get(d, "")
                    is_hol = bool(hol_name)

                    # 배경·숫자 색상 결정 (우선순위: 오늘 > 공휴일평일 > 주말/공휴일주말 > 평일)
                    if is_today:
                        bg, num_fg, num_font = _TODAY_BG, _TODAY_FG, ("Consolas", 12, "bold")
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
                        highlightbackground=_ACCENT if is_today else _BG,
                        highlightthickness=1 if is_today else 0,
                    )
                    cell.grid(row=row_idx, column=col, sticky="nsew", padx=2, pady=2)

                    num_lbl = tk.Label(
                        cell, text=str(day),
                        bg=bg, fg=num_fg, font=num_font, anchor="center",
                    )
                    num_lbl.pack(fill="x")

                    if is_hol:
                        hol_fg = _HOLIDAY_FG if not (is_today or is_wknd) else (_TODAY_FG if is_today else _HOLWKND_FG)
                        hol_lbl = tk.Label(
                            cell, text=_shorten(hol_name),
                            bg=bg, fg=hol_fg,
                            font=("Consolas", 7), anchor="center",
                        )
                        hol_lbl.pack(fill="x")

                        # 마우스 오버 시 전체 이름 표시
                        def _enter(e, n=hol_name) -> None:
                            holiday_bar.config(text=f"  ◈  {n}")

                        def _leave(e) -> None:
                            holiday_bar.config(text="")

                        for widget in (cell, num_lbl, hol_lbl):
                            widget.bind("<Enter>", _enter)
                            widget.bind("<Leave>", _leave)

                    cells.append(cell)

        def _on_close() -> None:
            with self._lock:
                self._window = None
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", _on_close)
        _render()
        root.mainloop()

        with self._lock:
            self._window = None
