import calendar
import re
import threading
import tkinter as tk
from datetime import datetime

from core.skill_base import Skill, SkillResult

# ── Jarvis 스타일 팔레트 ──────────────────────────────────
_BG = "#0d1117"
_PANEL_BG = "#0a1929"
_TEXT = "#c9d1d9"
_ACCENT = "#00d4ff"
_TODAY_BG = "#1e3a5f"
_TODAY_FG = "#00ff99"
_WEEKEND_FG = "#ff7b7b"
_HDR_FG = "#8b949e"
_BTN_BG = "#161b22"
_BTN_ACTIVE = "#21262d"
_SEP = "#30363d"

_WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"]

_MONTH_RE = re.compile(r"(?:(\d{4})년\s*)?(\d{1,2})월")
_YEAR_RE = re.compile(r"(\d{4})년")


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
            y_match = _YEAR_RE.search(text)
            if y_match:
                year = int(y_match.group(1))

        with self._lock:
            if self._window is not None:
                try:
                    self._window.lift()
                    self._window.focus_force()
                    return SkillResult(speech="달력 창을 앞으로 가져왔습니다.", success=True)
                except tk.TclError:
                    self._window = None

        t = threading.Thread(target=self._run_window, args=(year, month), daemon=True)
        t.start()
        return SkillResult(
            speech=f"{year}년 {month}월 달력을 열었습니다.",
            success=True,
            data={"year": year, "month": month},
        )

    def _run_window(self, year: int, month: int) -> None:
        root = tk.Tk()
        root.title("◈ JARVIS · 달력")
        root.configure(bg=_BG)
        root.resizable(False, False)

        w, h = 440, 430
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        with self._lock:
            self._window = root

        today = datetime.now()
        state = {"year": year, "month": month}
        cells: list[tk.Widget] = []

        # ── 타이틀 헤더 ─────────────────────────────────
        tk.Label(
            root,
            text="◈  J . A . R . V . I . S  ·  C A L E N D A R  ◈",
            bg=_PANEL_BG, fg=_ACCENT,
            font=("Consolas", 11, "bold"),
            pady=9,
        ).pack(fill="x")
        tk.Frame(root, bg=_SEP, height=1).pack(fill="x")

        # ── 월 탐색 바 ──────────────────────────────────
        nav = tk.Frame(root, bg=_BG, pady=10)
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

        # ── 달력 그리드 ─────────────────────────────────
        grid = tk.Frame(root, bg=_BG)
        grid.pack(fill="both", expand=True, padx=20, pady=12)
        for col in range(7):
            grid.columnconfigure(col, weight=1, uniform="col")

        def _render() -> None:
            for widget in cells:
                widget.destroy()
            cells.clear()

            y, m = state["year"], state["month"]
            month_lbl.config(text=f"{y}년 {m:02d}월")

            # 요일 헤더 (일~토)
            for col, wd in enumerate(_WEEKDAYS):
                fg = _WEEKEND_FG if col in (0, 6) else _HDR_FG
                lbl = tk.Label(
                    grid, text=wd, bg=_BG, fg=fg,
                    font=("Consolas", 11, "bold"), anchor="center",
                )
                lbl.grid(row=0, column=col, sticky="nsew", pady=(0, 6))
                cells.append(lbl)

            # 날짜 — calendar.monthcalendar은 월요일 기준이므로 일요일 기준으로 변환
            for row_idx, week in enumerate(calendar.monthcalendar(y, m), start=1):
                # [Mon, Tue, Wed, Thu, Fri, Sat, Sun] → [Sun, Mon, ..., Sat]
                sun_first = [week[6]] + week[:6]
                for col, day in enumerate(sun_first):
                    if day == 0:
                        lbl = tk.Label(grid, text="", bg=_BG)
                    else:
                        is_today = (
                            day == today.day
                            and m == today.month
                            and y == today.year
                        )
                        is_wknd = col in (0, 6)
                        if is_today:
                            bg, fg, fnt = _TODAY_BG, _TODAY_FG, ("Consolas", 12, "bold")
                        elif is_wknd:
                            bg, fg, fnt = _BG, _WEEKEND_FG, ("Consolas", 11)
                        else:
                            bg, fg, fnt = _BG, _TEXT, ("Consolas", 11)
                        lbl = tk.Label(
                            grid, text=str(day),
                            bg=bg, fg=fg, font=fnt, anchor="center",
                            relief="groove" if is_today else "flat",
                            bd=1 if is_today else 0,
                        )
                    lbl.grid(row=row_idx, column=col, sticky="nsew", pady=3, padx=2)
                    cells.append(lbl)

        # ── 오늘 날짜 하단 표시 ─────────────────────────
        tk.Frame(root, bg=_SEP, height=1).pack(fill="x", padx=20)
        wd_str = _WEEKDAYS[today.isoweekday() % 7]  # isoweekday: 1=Mon…7=Sun → %7: 0=Sun…6=Sat
        tk.Label(
            root,
            text=f"오늘 :  {today.year}년 {today.month}월 {today.day}일  ({wd_str}요일)",
            bg=_PANEL_BG, fg=_HDR_FG,
            font=("Consolas", 10), pady=7,
        ).pack(fill="x")

        def _on_close() -> None:
            with self._lock:
                self._window = None
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", _on_close)
        _render()
        root.mainloop()

        with self._lock:
            self._window = None
