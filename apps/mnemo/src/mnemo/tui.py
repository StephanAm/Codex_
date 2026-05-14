"""Interactive curses TUI for note-taker."""

from __future__ import annotations

import curses
import re
from enum import Enum, auto

from .models import Note
from .store import add_note, delete_note, get_default_tags, list_notes, search_notes, set_default_tags, update_note

# ── colour pair indices ───────────────────────────────────────────────────────
_C_HEADER = 1  # white on blue
_C_STATUS = 2  # black on white
_C_SEL    = 3  # black on cyan  (selected list row)
_C_TAG    = 4  # yellow         (#tags)
_C_ENTITY = 5  # cyan           (@entities)

_MIN_W, _MIN_H = 60, 10


class _Mode(Enum):
    BROWSE      = auto()
    ADD         = auto()
    EDIT        = auto()
    SEARCH      = auto()
    CONFIRM_DEL = auto()
    CONFIG_TAGS = auto()


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
        self.sel    = 0   # index into self.notes
        self.scroll = 0   # first visible row in list pane
        self.mode   = _Mode.BROWSE
        self.query  = ""  # live search filter
        self.ed: _Editor | None = None
        self._edit_id: int | None = None
        self._tag_buf = ""   # input buffer for CONFIG_TAGS mode
        self._tag_cur = 0    # cursor position within _tag_buf

    # ── setup ─────────────────────────────────────────────────────────────────

    def _init_colors(self) -> None:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(_C_HEADER, curses.COLOR_WHITE,  curses.COLOR_BLUE)
        curses.init_pair(_C_STATUS, curses.COLOR_BLACK,  curses.COLOR_WHITE)
        curses.init_pair(_C_SEL,    curses.COLOR_BLACK,  curses.COLOR_CYAN)
        curses.init_pair(_C_TAG,    curses.COLOR_YELLOW, -1)
        curses.init_pair(_C_ENTITY, curses.COLOR_CYAN,   -1)

    # ── run loop ──────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._init_colors()
        self.scr.keypad(True)
        curses.raw()          # disable flow control so Ctrl+S reaches the app
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
        if defaults:
            tag_line = " ".join(f"#{t}" for t in defaults)
            ed = _Editor("\n" + tag_line)
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
        dw = w - lw - 1       # detail pane width

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
        elif self.mode == _Mode.CONFIG_TAGS:
            self._draw_config_tags_pane(h, lw + 1, dw)
        else:
            self._draw_detail_pane(h, lw + 1, dw)

        self._draw_status(h - 1, w)

        # Must be last — status bar drawing moves the cursor away from the caret
        if self.mode in (_Mode.EDIT, _Mode.ADD):
            self._place_cursor(h, lw + 1, dw)
        elif self.mode == _Mode.CONFIG_TAGS:
            self._place_tag_cursor(h, lw + 1, dw)

    # ── header ────────────────────────────────────────────────────────────────

    def _draw_header(self, w: int) -> None:
        title = " note-taker"
        n = len(self.notes)
        right = f" {n} note{'s' if n != 1 else ''} "
        if self.query:
            right = f"  search: {self.query!r}" + right
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
            y   = i + 1
            if idx >= len(self.notes):
                self._put(y, 0, " " * w)
                continue
            note   = self.notes[idx]
            is_sel = idx == self.sel
            attr   = curses.color_pair(_C_SEL) | curses.A_BOLD if is_sel else curses.A_NORMAL
            prefix = "> " if is_sel else "  "
            ts     = note.created_at.strftime("%m-%d %H:%M")
            first  = note.body.splitlines()[0] if note.body else ""
            meta   = f"#{note.id:<3} {ts}"
            gap    = w - len(prefix) - len(meta) - 2
            if gap > 4:
                meta += "  " + first[:gap]
            self._put(y, 0, (prefix + meta)[: w].ljust(w), attr)

    # ── detail pane ───────────────────────────────────────────────────────────

    def _draw_detail_pane(self, h: int, x: int, w: int) -> None:
        note = self._current
        if note is None:
            self._put(2, x + 2, "No notes.  Press 'a' to add one.")
            return

        ts = note.created_at.strftime("%Y-%m-%d %H:%M")
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

        if note.entities and y < h - 1:
            self._put(y, x + 2, "ent:   ")
            cx = x + 9
            for ent in note.entities:
                s = f"@{ent}  "
                self._put(y, cx, s, curses.color_pair(_C_ENTITY) | curses.A_BOLD)
                cx += len(s)

    def _draw_body(self, start_y: int, x: int, w: int, h: int, body: str) -> int:
        """Render body text with coloured #tags and @entities. Returns next free y."""
        y     = start_y
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
                    attr = curses.color_pair(_C_ENTITY) | curses.A_BOLD
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

    # ── config tags pane ─────────────────────────────────────────────────────

    def _draw_config_tags_pane(self, h: int, x: int, w: int) -> None:
        self._put(1, x + 2, "── default tags ──  Enter save   Esc cancel", curses.A_BOLD)
        self._put(3, x + 2, "Space-separated tag names (without #):", curses.A_DIM)

        # render buffer with # colouring
        field_y = 5
        cx = x + 2
        tokens = self._tag_buf.split(" ")
        for i, tok in enumerate(tokens):
            if tok:
                display = f"#{tok}"
                self._put(field_y, cx, display, curses.color_pair(_C_TAG) | curses.A_BOLD)
                cx += len(display)
            if i < len(tokens) - 1:
                self._put(field_y, cx, " ")
                cx += 1

    def _place_tag_cursor(self, h: int, x: int, w: int) -> None:
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        # compute screen column matching _tag_cur in the buffer
        prefix = self._tag_buf[: self._tag_cur]
        # each non-space char gets a # prepended when rendered
        col = x + 2
        tokens_before = prefix.split(" ")
        for i, tok in enumerate(tokens_before):
            if tok:
                col += len(tok) + 1  # +1 for the '#'
            if i < len(tokens_before) - 1:
                col += 1  # space separator
        if 0 < 5 < h - 1 and col < x + w:
            try:
                self.scr.move(5, col)
            except curses.error:
                pass

    # ── status bar ────────────────────────────────────────────────────────────

    def _draw_status(self, y: int, w: int) -> None:
        bars: dict[_Mode, str] = {
            _Mode.BROWSE:      "  up/down navigate   Enter/e edit   a add   d delete   / search   t tags   q quit",
            _Mode.CONFIRM_DEL: "  Delete this note?   y yes   n / Esc no",
            _Mode.SEARCH:      f"  Search: {self.query}▌   Enter keep   Esc clear",
            _Mode.EDIT:        "  Ctrl+S save   Esc cancel",
            _Mode.ADD:         "  Ctrl+S save   Esc cancel",
            _Mode.CONFIG_TAGS: "  Enter save   Esc cancel",
        }
        bar = bars.get(self.mode, "")
        self._put(y, 0, bar.ljust(w)[: w], curses.color_pair(_C_STATUS))

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
                    self.sel = next(
                        i for i, n in enumerate(self.notes) if n.id == note.id
                    )
                except StopIteration:
                    self.sel = 0
            else:
                assert self._edit_id is not None
                update_note(self._edit_id, text)
                self._reload()
        self._exit_editor()

    def _editor(self, key: int) -> bool:
        assert self.ed is not None

        if key in (19, curses.KEY_LEFT):  # Ctrl+S or Left arrow — save
            self._commit_editor()

        elif key == 27:  # Esc — cancel
            self._exit_editor()

        elif key == curses.KEY_UP:       self.ed.up()
        elif key == curses.KEY_DOWN:     self.ed.down()
        elif key == curses.KEY_RIGHT:    self.ed.right()
        elif key == curses.KEY_HOME:     self.ed.home()
        elif key == curses.KEY_END:      self.ed.end()
        elif key in (curses.KEY_BACKSPACE, 127, 8): self.ed.backspace()
        elif key == curses.KEY_DC:       self.ed.delete()
        elif key in (10, 13):            self.ed.newline()
        elif 32 <= key <= 126:           self.ed.insert(chr(key))

        return True

    def _exit_editor(self) -> None:
        self.ed = None
        self._edit_id = None
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
