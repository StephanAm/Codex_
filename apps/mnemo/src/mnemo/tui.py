"""Interactive curses TUI for note-taker."""

from __future__ import annotations

import curses
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from codex_core.models import Note
from codex_core.session import clear_session_context, get_session_context, set_session_context
from codex_core.store import (
    add_note,
    delete_note,
    get_default_tags,
    get_sync_adapter,
    get_sync_folder,
    get_sync_local_path,
    list_notes,
    search_notes,
    set_default_tags,
    set_sync_adapter,
    set_sync_folder,
    set_sync_local_path,
    update_note,
)
from codex_core.sync.adapter import StorageAdapter

# ── colour pair indices ───────────────────────────────────────────────────────
_C_HEADER = 1  # white on blue
_C_STATUS = 2  # black on white
_C_SEL = 3  # black on cyan  (selected list row)
_C_TAG = 4  # yellow         (#tags)
_C_REFERENCE = 5  # cyan           (@references)

_MIN_W, _MIN_H = 60, 10


class _Mode(Enum):
    BROWSE = auto()
    ADD = auto()
    EDIT = auto()
    SEARCH = auto()
    CONFIRM_DEL = auto()
    CONFIG = auto()
    SESSION = auto()
    SYNC_RESULT = auto()


_CFG_LABEL_W = 16  # fixed label column width in the config pane


@dataclass
class _CfgField:
    label: str
    hint: str
    buf: str
    save: Callable[[str], None]
    cur: int = field(default=0, init=False)


# ── editor buffer ─────────────────────────────────────────────────────────────


class _Editor:
    """Minimal multi-line editor backed by a list of strings."""

    def __init__(self, text: str = "") -> None:
        self.lines: list[str] = text.splitlines() if text else [""]
        if not self.lines:
            self.lines = [""]
        self.row = len(self.lines) - 1
        self.col = len(self.lines[self.row])

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def insert(self, ch: str) -> None:
        ln = self.lines[self.row]
        self.lines[self.row] = ln[: self.col] + ch + ln[self.col :]
        self.col += 1

    def newline(self) -> None:
        ln = self.lines[self.row]
        self.lines[self.row] = ln[: self.col]
        self.lines.insert(self.row + 1, ln[self.col :])
        self.row += 1
        self.col = 0

    def backspace(self) -> None:
        if self.col > 0:
            ln = self.lines[self.row]
            self.lines[self.row] = ln[: self.col - 1] + ln[self.col :]
            self.col -= 1
        elif self.row > 0:
            prev = self.lines[self.row - 1]
            self.col = len(prev)
            self.lines[self.row - 1] = prev + self.lines[self.row]
            del self.lines[self.row]
            self.row -= 1

    def delete(self) -> None:
        ln = self.lines[self.row]
        if self.col < len(ln):
            self.lines[self.row] = ln[: self.col] + ln[self.col + 1 :]
        elif self.row < len(self.lines) - 1:
            self.lines[self.row] = ln + self.lines[self.row + 1]
            del self.lines[self.row + 1]

    def left(self) -> None:
        if self.col > 0:
            self.col -= 1
        elif self.row > 0:
            self.row -= 1
            self.col = len(self.lines[self.row])

    def right(self) -> None:
        if self.col < len(self.lines[self.row]):
            self.col += 1
        elif self.row < len(self.lines) - 1:
            self.row += 1
            self.col = 0

    def up(self) -> None:
        if self.row > 0:
            self.row -= 1
            self.col = min(self.col, len(self.lines[self.row]))

    def down(self) -> None:
        if self.row < len(self.lines) - 1:
            self.row += 1
            self.col = min(self.col, len(self.lines[self.row]))

    def home(self) -> None:
        self.col = 0

    def end(self) -> None:
        self.col = len(self.lines[self.row])


# ── main application ──────────────────────────────────────────────────────────


class _App:
    def __init__(self, stdscr: curses.window) -> None:
        self.scr = stdscr
        self.notes: list[Note] = []
        self.sel = 0  # index into self.notes
        self.scroll = 0  # first visible row in list pane
        self.mode = _Mode.BROWSE
        self.query = ""  # live search filter
        self.ed: _Editor | None = None
        self._edit_id: int | None = None
        self._cfg_fields: list[_CfgField] = []
        self._cfg_sel = 0
        self._sync_msg = ""
        self._session_buf = ""  # input buffer for SESSION mode (free text with #/@)
        self._session_cur = 0

    # ── setup ─────────────────────────────────────────────────────────────────

    def _init_colors(self) -> None:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(_C_HEADER, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(_C_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(_C_SEL, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(_C_TAG, curses.COLOR_YELLOW, -1)
        curses.init_pair(_C_REFERENCE, curses.COLOR_CYAN, -1)

    # ── run loop ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._init_colors()
        self.scr.keypad(True)
        curses.raw()  # disable flow control so Ctrl+S reaches the app
        curses.set_escdelay(25)  # don't wait 1s after ESC before dispatching it
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self._reload()
        while True:
            h, w = self.scr.getmaxyx()
            self.scr.erase()
            if h < _MIN_H or w < _MIN_W:
                self._put(0, 0, f"Terminal too small (need {_MIN_W}x{_MIN_H})")
                self.scr.refresh()
                if self.scr.getch() in (ord("q"), 27):
                    break
                continue
            self._draw(h, w)
            self.scr.refresh()
            if not self._dispatch(self.scr.getch()):
                break

    # ── data ──────────────────────────────────────────────────────────────────

    def _reload(self) -> None:
        self.notes = search_notes(self.query) if self.query else list_notes(limit=500)
        self.sel = min(self.sel, max(0, len(self.notes) - 1))

    def _new_editor(self) -> _Editor:
        defaults = get_default_tags()
        s_tags, s_references = get_session_context()
        all_tags = list(dict.fromkeys(defaults + s_tags))
        context_parts = [f"#{t}" for t in all_tags] + [f"@{r}" for r in s_references]
        if context_parts:
            ed = _Editor("\n" + " ".join(context_parts))
            ed.row = 0
            ed.col = 0
            return ed
        return _Editor()

    @property
    def _current(self) -> Note | None:
        return self.notes[self.sel] if self.notes else None

    # ── safe write ────────────────────────────────────────────────────────────

    def _put(self, y: int, x: int, text: str, attr: int = 0) -> None:
        h, w = self.scr.getmaxyx()
        if y < 0 or y >= h or x < 0 or x >= w:
            return
        try:
            self.scr.addstr(y, x, text[: w - x], attr)
        except curses.error:
            pass

    # ── layout ────────────────────────────────────────────────────────────────

    def _draw(self, h: int, w: int) -> None:
        lw = max(w // 3, 22)  # list pane width
        dw = w - lw - 1  # detail pane width

        self._draw_header(w)

        self._draw_list(h, lw)

        # vertical divider
        for y in range(1, h - 1):
            try:
                self.scr.addch(y, lw, curses.ACS_VLINE)
            except curses.error:
                pass

        if self.mode in (_Mode.EDIT, _Mode.ADD):
            self._draw_editor_pane(h, lw + 1, dw)
        elif self.mode == _Mode.CONFIG:
            self._draw_config_pane(h, lw + 1, dw)
        elif self.mode == _Mode.SESSION:
            self._draw_session_pane(h, lw + 1, dw)
        elif self.mode == _Mode.SYNC_RESULT:
            self._draw_sync_result_pane(h, lw + 1, dw)
        else:
            self._draw_detail_pane(h, lw + 1, dw)

        self._draw_status(h - 1, w)

        # Must be last — status bar drawing moves the cursor away from the caret
        if self.mode in (_Mode.EDIT, _Mode.ADD):
            self._place_cursor(h, lw + 1, dw)
        elif self.mode == _Mode.CONFIG:
            self._place_config_cursor(h, lw + 1, dw)
        elif self.mode == _Mode.SESSION:
            self._place_session_cursor(h, lw + 1, dw)

    # ── header ────────────────────────────────────────────────────────────────

    def _draw_header(self, w: int) -> None:
        title = " note-taker"
        n = len(self.notes)
        right = f" {n} note{'s' if n != 1 else ''} "
        if self.query:
            right = f"  search: {self.query!r}" + right
        s_tags, s_references = get_session_context()
        if s_tags or s_references:
            parts = [f"#{t}" for t in s_tags] + [f"@{r}" for r in s_references]
            right = f"  [{' '.join(parts)}]" + right
        bar = (title + right.rjust(w - len(title)))[:w]
        self._put(0, 0, bar.ljust(w), curses.color_pair(_C_HEADER) | curses.A_BOLD)

    # ── list pane ─────────────────────────────────────────────────────────────

    def _draw_list(self, h: int, w: int) -> None:
        rows = h - 2  # rows available between header and status
        # keep selected row visible
        if self.sel < self.scroll:
            self.scroll = self.sel
        elif self.sel >= self.scroll + rows:
            self.scroll = self.sel - rows + 1

        for i in range(rows):
            idx = i + self.scroll
            y = i + 1
            if idx >= len(self.notes):
                self._put(y, 0, " " * w)
                continue
            note = self.notes[idx]
            is_sel = idx == self.sel
            attr = curses.color_pair(_C_SEL) | curses.A_BOLD if is_sel else curses.A_NORMAL
            prefix = "> " if is_sel else "  "
            ts = note.created_at.astimezone().strftime("%m-%d %H:%M")
            first = note.body.splitlines()[0] if note.body else ""
            meta = f"#{note.id:<3} {ts}"
            gap = w - len(prefix) - len(meta) - 2
            if gap > 4:
                meta += "  " + first[:gap]
            self._put(y, 0, (prefix + meta)[:w].ljust(w), attr)

    # ── detail pane ───────────────────────────────────────────────────────────

    def _draw_detail_pane(self, h: int, x: int, w: int) -> None:
        note = self._current
        if note is None:
            self._put(2, x + 2, "No notes.  Press 'a' to add one.")
            return

        ts = note.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
        self._put(1, x + 2, f"#{note.id}  {ts}", curses.A_BOLD)

        y = self._draw_body(3, x, w, h, note.body)

        y += 1
        if note.tags and y < h - 1:
            self._put(y, x + 2, "tags:  ")
            cx = x + 9
            for tag in note.tags:
                s = f"#{tag}  "
                self._put(y, cx, s, curses.color_pair(_C_TAG) | curses.A_BOLD)
                cx += len(s)
            y += 1

        if note.references and y < h - 1:
            self._put(y, x + 2, "ref:   ")
            cx = x + 9
            for ref in note.references:
                s = f"@{ref}  "
                self._put(y, cx, s, curses.color_pair(_C_REFERENCE) | curses.A_BOLD)
                cx += len(s)

    def _draw_body(self, start_y: int, x: int, w: int, h: int, body: str) -> int:
        """Render body text with coloured #tags and @references. Returns next free y."""
        y = start_y
        right = x + w - 1
        for raw_line in body.splitlines():
            if y >= h - 2:
                break
            cx = x + 2
            for part in re.split(r"(\s+)", raw_line):
                if not part:
                    continue
                if part.isspace():
                    cx += len(part)
                    continue
                if re.match(r"#\w", part):
                    attr: int = curses.color_pair(_C_TAG) | curses.A_BOLD
                elif re.match(r"@\w", part):
                    attr = curses.color_pair(_C_REFERENCE) | curses.A_BOLD
                else:
                    attr = curses.A_NORMAL
                # wrap to next line if needed
                if cx + len(part) > right and cx > x + 2:
                    y += 1
                    cx = x + 2
                    if y >= h - 2:
                        break
                try:
                    self.scr.addstr(y, cx, part[: right - cx], attr)
                except curses.error:
                    pass
                cx += len(part)
            y += 1
        return y

    # ── editor pane ───────────────────────────────────────────────────────────

    def _draw_editor_pane(self, h: int, x: int, w: int) -> None:
        assert self.ed is not None
        action = "edit" if self.mode == _Mode.EDIT else "new note"
        self._put(1, x + 2, f"── {action} ──  Ctrl+S save   Esc cancel", curses.A_BOLD)

        ed_top = 3
        for i, line in enumerate(self.ed.lines):
            y = ed_top + i
            if y >= h - 1:
                break
            self._put(y, x + 2, line[: w - 3])

    def _place_cursor(self, h: int, x: int, w: int) -> None:
        """Move the terminal cursor to the editor caret. Called after all drawing."""
        assert self.ed is not None
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        ed_top = 3
        cursor_y = ed_top + self.ed.row
        cursor_x = x + 2 + self.ed.col
        if 0 < cursor_y < h - 1 and cursor_x < x + w:
            try:
                self.scr.move(cursor_y, cursor_x)
            except curses.error:
                pass

    # ── config pane ───────────────────────────────────────────────────────────

    def _enter_config(self) -> None:
        self._cfg_fields = [
            _CfgField(
                label="Default tags",
                hint="Space-separated tag names (without #)",
                buf=" ".join(get_default_tags()),
                save=lambda v: set_default_tags([t for t in v.split() if t]),
            ),
            _CfgField(
                label="Drive folder",
                hint="Google Drive folder used for sync",
                buf=get_sync_folder(),
                save=set_sync_folder,
            ),
            _CfgField(
                label="Sync adapter",
                hint="'google_drive' or 'local_folder'",
                buf=get_sync_adapter(),
                save=set_sync_adapter,
            ),
            _CfgField(
                label="Local sync path",
                hint="Folder path (used when adapter is local_folder)",
                buf=get_sync_local_path(),
                save=set_sync_local_path,
            ),
        ]
        self._cfg_sel = 0
        self._cfg_fields[0].cur = len(self._cfg_fields[0].buf)
        self.mode = _Mode.CONFIG

    def _draw_config_pane(self, h: int, x: int, w: int) -> None:
        self._put(1, x + 2, "── configuration ──  Ctrl+S save   Esc cancel", curses.A_BOLD)

        for i, f in enumerate(self._cfg_fields):
            y = 3 + i
            if y >= h - 2:
                break
            is_sel = i == self._cfg_sel
            label = f.label.ljust(_CFG_LABEL_W)
            prefix = "▸ " if is_sel else "  "
            attr = curses.A_BOLD if is_sel else curses.A_NORMAL
            self._put(y, x + 2, prefix + label + f.buf, attr)

        hint_y = 3 + len(self._cfg_fields) + 1
        if hint_y < h - 1 and self._cfg_fields:
            self._put(hint_y, x + 2, self._cfg_fields[self._cfg_sel].hint, curses.A_DIM)

    def _place_config_cursor(self, h: int, x: int, w: int) -> None:
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        if not self._cfg_fields:
            return
        row_y = 3 + self._cfg_sel
        col = x + 2 + 2 + _CFG_LABEL_W + self._cfg_fields[self._cfg_sel].cur
        if 0 < row_y < h - 1 and col < x + w:
            try:
                self.scr.move(row_y, col)
            except curses.error:
                pass

    def _config_input(self, key: int) -> bool:
        if not self._cfg_fields:
            return True
        f = self._cfg_fields[self._cfg_sel]

        if key == 19:  # Ctrl+S — save all and exit
            for field in self._cfg_fields:
                field.save(field.buf)
            self._exit_config()
        elif key == 27:  # Esc — discard
            self._exit_config()
        elif key == curses.KEY_UP and self._cfg_sel > 0:
            self._cfg_sel -= 1
            self._cfg_fields[self._cfg_sel].cur = len(self._cfg_fields[self._cfg_sel].buf)
        elif key == curses.KEY_DOWN and self._cfg_sel < len(self._cfg_fields) - 1:
            self._cfg_sel += 1
            self._cfg_fields[self._cfg_sel].cur = len(self._cfg_fields[self._cfg_sel].buf)
        elif key == curses.KEY_LEFT:
            f.cur = max(0, f.cur - 1)
        elif key == curses.KEY_RIGHT:
            f.cur = min(len(f.buf), f.cur + 1)
        elif key == curses.KEY_HOME:
            f.cur = 0
        elif key == curses.KEY_END:
            f.cur = len(f.buf)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if f.cur > 0:
                f.buf = f.buf[: f.cur - 1] + f.buf[f.cur :]
                f.cur -= 1
        elif key == curses.KEY_DC:
            if f.cur < len(f.buf):
                f.buf = f.buf[: f.cur] + f.buf[f.cur + 1 :]
        elif 32 <= key <= 126:
            ch = chr(key)
            f.buf = f.buf[: f.cur] + ch + f.buf[f.cur :]
            f.cur += 1
        return True

    def _exit_config(self) -> None:
        self._cfg_fields = []
        self.mode = _Mode.BROWSE
        try:
            curses.curs_set(0)
        except curses.error:
            pass

    # ── status bar ────────────────────────────────────────────────────────────

    def _draw_status(self, y: int, w: int) -> None:
        bars: dict[_Mode, str] = {
            _Mode.BROWSE: (
                "  up/down navigate   Enter/e edit   a add   d delete"
                "   / search   c config   s session   S sync   q quit"
            ),
            _Mode.SYNC_RESULT: "  Press any key to continue",
            _Mode.CONFIRM_DEL: "  Delete this note?   y yes   n / Esc no",
            _Mode.SEARCH: f"  Search: {self.query}▌   Enter keep   Esc clear",
            _Mode.EDIT: "  Ctrl+S save   Esc cancel",
            _Mode.ADD: "  Ctrl+S save   Esc cancel",
            _Mode.CONFIG: "  up/down select field   Ctrl+S save   Esc cancel",
            _Mode.SESSION: "  Enter save   Esc cancel   Ctrl+X clear session",
        }
        bar = bars.get(self.mode, "")
        self._put(y, 0, bar.ljust(w)[:w], curses.color_pair(_C_STATUS))

    # ── input dispatch ────────────────────────────────────────────────────────

    def _dispatch(self, key: int) -> bool:
        if self.mode == _Mode.BROWSE:
            return self._browse(key)
        if self.mode in (_Mode.EDIT, _Mode.ADD):
            return self._editor(key)
        if self.mode == _Mode.SEARCH:
            return self._search_input(key)
        if self.mode == _Mode.CONFIRM_DEL:
            return self._confirm_del(key)
        if self.mode == _Mode.CONFIG:
            return self._config_input(key)
        if self.mode == _Mode.SESSION:
            return self._session_input(key)
        if self.mode == _Mode.SYNC_RESULT:
            self.mode = _Mode.BROWSE
            return True
        return True

    # ── browse ────────────────────────────────────────────────────────────────

    def _browse(self, key: int) -> bool:
        if key in (ord("q"), ord("Q"), 3):  # 3 = Ctrl+C (raw mode disables SIGINT)
            return False

        if key == curses.KEY_UP and self.sel == 0:
            self.ed = self._new_editor()
            self._edit_id = None
            self.mode = _Mode.ADD
        elif key == curses.KEY_UP and self.sel > 0:
            self.sel -= 1
        elif key == curses.KEY_DOWN and self.sel < len(self.notes) - 1:
            self.sel += 1
        elif key == curses.KEY_PPAGE:
            self.sel = max(0, self.sel - 10)
        elif key == curses.KEY_NPAGE:
            self.sel = min(max(0, len(self.notes) - 1), self.sel + 10)

        elif key == ord("a"):
            self.ed = self._new_editor()
            self._edit_id = None
            self.mode = _Mode.ADD

        elif key in (ord("e"), 10, 13, curses.KEY_RIGHT) and self._current:
            self.ed = _Editor(self._current.body)
            self._edit_id = self._current.id
            self.mode = _Mode.EDIT

        elif key == ord("d") and self._current:
            self.mode = _Mode.CONFIRM_DEL

        elif key == ord("/"):
            self.query = ""
            self.sel = 0
            self._reload()
            self.mode = _Mode.SEARCH

        elif key in (ord("c"), ord("C")):
            self._enter_config()

        elif key == ord("s"):
            s_tags, s_references = get_session_context()
            parts = [f"#{t}" for t in s_tags] + [f"@{r}" for r in s_references]
            self._session_buf = " ".join(parts)
            self._session_cur = len(self._session_buf)
            self.mode = _Mode.SESSION

        elif key == ord("S"):
            self._run_sync()

        elif key == 27:  # Esc — clear active search
            if self.query:
                self.query = ""
                self.sel = 0
                self._reload()

        return True

    # ── editor ────────────────────────────────────────────────────────────────

    def _commit_editor(self) -> None:
        assert self.ed is not None
        text = self.ed.text.strip()
        if text:
            if self.mode == _Mode.ADD:
                note = add_note(text)
                self._reload()
                try:
                    self.sel = next(i for i, n in enumerate(self.notes) if n.id == note.id)
                except StopIteration:
                    self.sel = 0
            else:
                assert self._edit_id is not None
                update_note(self._edit_id, text)
                self._reload()
        self._exit_editor()

    def _editor(self, key: int) -> bool:
        assert self.ed is not None

        if key == 19:  # Ctrl+S — save
            self._commit_editor()

        elif key == 27:  # Esc — cancel
            self._exit_editor()

        elif key == curses.KEY_UP:
            self.ed.up()
        elif key == curses.KEY_DOWN:
            self.ed.down()
        elif key == curses.KEY_LEFT:
            self.ed.left()
        elif key == curses.KEY_RIGHT:
            self.ed.right()
        elif key == curses.KEY_HOME:
            self.ed.home()
        elif key == curses.KEY_END:
            self.ed.end()
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self.ed.backspace()
        elif key == curses.KEY_DC:
            self.ed.delete()
        elif key in (10, 13):
            self.ed.newline()
        elif 32 <= key <= 126:
            self.ed.insert(chr(key))

        return True

    def _exit_editor(self) -> None:
        self.ed = None
        self._edit_id = None
        self.mode = _Mode.BROWSE
        try:
            curses.curs_set(0)
        except curses.error:
            pass

    # ── sync ──────────────────────────────────────────────────────────────────

    def _run_sync(self) -> None:
        h, w = self.scr.getmaxyx()
        lw = max(w // 3, 22)
        self._put(2, lw + 3, "Syncing…", curses.A_BOLD)
        self.scr.refresh()
        self._sync_msg = self._do_sync()
        self._reload()
        self.mode = _Mode.SYNC_RESULT

    def _do_sync(self) -> str:
        from pathlib import Path

        from codex_core.db import connect, get_db_path
        from codex_core.sync.device import get_device_id
        from codex_core.sync.merge import merge_remote

        try:
            sync_adapter = get_sync_adapter()
            if sync_adapter == "local_folder":
                from codex_core.sync.local_folder import LocalFolderAdapter

                raw = get_sync_local_path()
                if not raw:
                    return "Sync failed: local folder path is not configured."
                adapter: StorageAdapter = LocalFolderAdapter(Path(raw))
            else:
                from codex_core.sync.google_drive import GoogleDriveAdapter

                auth_dir = Path.home() / ".codex_"
                adapter = GoogleDriveAdapter(
                    auth_dir / "credentials.json",
                    auth_dir / "token.json",
                    folder_name=get_sync_folder(),
                )
            device_id = get_device_id()
            db_path = get_db_path()
            adapter.upload(device_id, db_path)
            devices = [d for d in adapter.list_devices() if d != device_id]
            if not devices:
                return "Push complete — no other devices to pull from."
            local_conn = connect(db_path)
            added = updated = deleted = 0
            for d in devices:
                result = merge_remote(local_conn, adapter.download(d))
                added += result.added
                updated += result.updated
                deleted += result.deleted
            return f"Sync complete — {added} added, {updated} updated, {deleted} deleted."
        except Exception as exc:
            return f"Sync failed: {exc}"

    def _draw_sync_result_pane(self, h: int, x: int, w: int) -> None:
        self._put(1, x + 2, "── sync ──", curses.A_BOLD)
        self._put(3, x + 2, self._sync_msg)

    # ── session context ───────────────────────────────────────────────────────

    def _draw_session_pane(self, h: int, x: int, w: int) -> None:
        self._put(1, x + 2, "── session context ──  Enter save   Esc cancel   Ctrl+X clear", curses.A_BOLD)
        self._put(3, x + 2, "Type #tags and @mentions (applies to all new notes this session):", curses.A_DIM)

        field_y = 5
        cx = x + 2
        for token in self._session_buf.split():
            if token.startswith("#"):
                attr: int = curses.color_pair(_C_TAG) | curses.A_BOLD
            elif token.startswith("@"):
                attr = curses.color_pair(_C_REFERENCE) | curses.A_BOLD
            else:
                attr = curses.A_NORMAL
            self._put(field_y, cx, token, attr)
            cx += len(token) + 1

    def _place_session_cursor(self, h: int, x: int, w: int) -> None:
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        col = x + 2 + self._session_cur
        # Adjust for spaces between tokens (each space is 1 char in the buffer)
        if 0 < 5 < h - 1 and col < x + w:
            try:
                self.scr.move(5, col)
            except curses.error:
                pass

    def _session_input(self, key: int) -> bool:
        if key in (10, 13):  # Enter — save
            from codex_core.parser import parse as _parse

            parsed = _parse(self._session_buf)
            if parsed.tags or parsed.references:
                set_session_context(parsed.tags, parsed.references)
            else:
                clear_session_context()
            self._exit_session()
        elif key == 24:  # Ctrl+X — clear
            clear_session_context()
            self._session_buf = ""
            self._session_cur = 0
            self._exit_session()
        elif key == 27:  # Esc — cancel
            self._exit_session()
        elif key == curses.KEY_LEFT:
            self._session_cur = max(0, self._session_cur - 1)
        elif key == curses.KEY_RIGHT:
            self._session_cur = min(len(self._session_buf), self._session_cur + 1)
        elif key == curses.KEY_HOME:
            self._session_cur = 0
        elif key == curses.KEY_END:
            self._session_cur = len(self._session_buf)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if self._session_cur > 0:
                self._session_buf = self._session_buf[: self._session_cur - 1] + self._session_buf[self._session_cur :]
                self._session_cur -= 1
        elif key == curses.KEY_DC:
            if self._session_cur < len(self._session_buf):
                self._session_buf = self._session_buf[: self._session_cur] + self._session_buf[self._session_cur + 1 :]
        elif 32 <= key <= 126:
            ch = chr(key)
            self._session_buf = self._session_buf[: self._session_cur] + ch + self._session_buf[self._session_cur :]
            self._session_cur += 1
        return True

    def _exit_session(self) -> None:
        self.mode = _Mode.BROWSE
        try:
            curses.curs_set(0)
        except curses.error:
            pass

    # ── search ────────────────────────────────────────────────────────────────

    def _search_input(self, key: int) -> bool:
        if key == 27:  # Esc — clear and return
            self.query = ""
            self.sel = 0
            self._reload()
            self.mode = _Mode.BROWSE
        elif key in (10, 13):  # Enter — keep filter, return to browse
            self.mode = _Mode.BROWSE
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self.query = self.query[:-1]
            self.sel = 0
            self._reload()
        elif 32 <= key <= 126:
            self.query += chr(key)
            self.sel = 0
            self._reload()
        return True

    # ── delete confirm ────────────────────────────────────────────────────────

    def _confirm_del(self, key: int) -> bool:
        if key in (ord("y"), ord("Y")):
            note = self._current
            if note:
                delete_note(note.id)
                self.sel = max(0, self.sel - 1)
                self._reload()
        self.mode = _Mode.BROWSE
        return True


# ── entry point ───────────────────────────────────────────────────────────────


def launch() -> None:
    """Start the interactive TUI."""
    curses.wrapper(_run)


def _run(stdscr: curses.window) -> None:
    _App(stdscr).run()
