"""Date expression normaliser for Mnemo notes.

Finds ~expressions in note text and resolves them to ISO dates/datetimes
per designdocs/dateparsingrules.md. Resolved forms are stored as ~YYYY-MM-DD or
~YYYY-MM-DDTHH:MM. Unresolvable expressions are left unchanged.
"""

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

# ── week helpers ──────────────────────────────────────────────────────────────

_WEEKDAYS: dict[str, int] = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}

_MONTHS: dict[str, int] = {
    "january": 1,  "jan": 1,
    "february": 2, "feb": 2,
    "march": 3,    "mar": 3,
    "april": 4,    "apr": 4,
    "may": 5,
    "june": 6,     "jun": 6,
    "july": 7,     "jul": 7,
    "august": 8,   "aug": 8,
    "september": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_COB_TIME = "17:00"


def _week_monday(today: date) -> date:
    return today - timedelta(days=today.weekday())


# ── regex ─────────────────────────────────────────────────────────────────────

_DAY       = r"(?:monday|mon|tuesday|tue|wednesday|wed|thursday|thu|friday|fri|saturday|sat|sunday|sun)"
_TIME      = r"\d{1,2}:\d{2}"
_AMPM_PAT  = r"\d{1,2}(?::\d{2})?(?:am|pm)"
_COB       = r"(?:cob|c\.o\.b)"
_EOW_EOM   = r"(?:eow|e\.o\.w|eom|e\.o\.m)"
_TIME_PART = rf"(?:{_AMPM_PAT}|{_TIME}|{_COB}|noon|midnight)"
_MONTH_NAME    = r"(?:january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|october|oct|november|nov|december|dec)"
_DAY_NUM       = r"\d{1,2}(?:st|nd|rd|th)?"
_MONTH_DAY     = rf"(?:{_MONTH_NAME}\s+{_DAY_NUM}|{_DAY_NUM}[-\s]{_MONTH_NAME})"
_EXPLICIT_YMD  = r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
_EXPLICIT_DMY  = r"\d{1,2}[-/]\d{1,2}[-/]\d{4}"
_EXPLICIT_DATE = rf"(?:{_EXPLICIT_YMD}|{_EXPLICIT_DMY})"
_DATE_PART = (
    rf"(?:today|tomm?orrow|yesterday"
    rf"|{_EOW_EOM}"
    rf"|(?:this|last|next)\s+{_DAY}"
    rf"|{_DAY}"
    rf"|the\s+\d{{1,2}}(?:st|nd|rd|th)\s+of\s+{_MONTH_NAME}"
    rf"|the\s+\d{{1,2}}(?:st|nd|rd|th)"
    rf"|{_MONTH_DAY}"
    rf"|\d{{1,2}}(?:st|nd|rd|th)"
    rf"|{_EXPLICIT_DATE}"
    rf"|in\s+\d+\s+(?:days?|weeks?)"
    rf"|\d+\s+(?:days?|weeks?)\s+ago)"
)

# Group 1: already-normalised ~~ISO forms — pass through without parsing.
# Group 2: raw ~expressions — parse and resolve.
# Catch-all in group 2 captures any remaining ~word so failed expressions
# can be flagged to the user rather than silently ignored.
_EXPR_RE = re.compile(
    rf"(~\{{\d{{4}}-\d{{2}}-\d{{2}}(?:T\d{{2}}:\d{{2}})?\}})"
    rf"|~({_TIME_PART}\s+{_DATE_PART}"
    rf"|{_DATE_PART}\s+{_TIME_PART}"
    rf"|{_DATE_PART}"
    rf"|{_TIME_PART}"
    rf"|\S+)",
    re.IGNORECASE,
)

_ORDINAL_RE = re.compile(r"^the\s+(\d{1,2})(?:st|nd|rd|th)$", re.IGNORECASE)
_MONTH_DAY_RE = re.compile(
    rf"^(?:(?P<mn>{_MONTH_NAME})\s+(?P<dn1>{_DAY_NUM})|(?P<dn2>{_DAY_NUM})[-\s](?P<mn2>{_MONTH_NAME}))$",
    re.IGNORECASE,
)
_EXPLICIT_DATE_RE = re.compile(
    r"^(?:(?P<y1>\d{4})[-/](?P<m1>\d{1,2})[-/](?P<d1>\d{1,2})"
    r"|(?P<d2>\d{1,2})[-/](?P<m2>\d{1,2})[-/](?P<y2>\d{4}))$"
)
_BARE_ORDINAL_RE = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)$", re.IGNORECASE)
_ORDINAL_OF_MONTH_RE = re.compile(
    rf"^the\s+(\d{{1,2}})(?:st|nd|rd|th)\s+of\s+({_MONTH_NAME})$",
    re.IGNORECASE,
)
_FUTURE_OFFSET_RE = re.compile(r"^in\s+(\d+)\s+(days?|weeks?)$", re.IGNORECASE)
_PAST_OFFSET_RE   = re.compile(r"^(\d+)\s+(days?|weeks?)\s+ago$", re.IGNORECASE)
_AMPM_RE = re.compile(r"^(\d{1,2})(?::(\d{2}))?([ap]m)$", re.IGNORECASE)

# ── date resolution ───────────────────────────────────────────────────────────

def _resolve_date(expr: str, today: date) -> date | None:
    expr = expr.strip().lower()

    em = _EXPLICIT_DATE_RE.match(expr)
    if em:
        if em.group("y1"):
            y, mo, d = int(em.group("y1")), int(em.group("m1")), int(em.group("d1"))
        else:
            y, mo, d = int(em.group("y2")), int(em.group("m2")), int(em.group("d2"))
        try:
            return date(y, mo, d)
        except ValueError:
            return None

    if expr == "today":
        return today
    if expr in ("tomorrow", "tommorrow"):
        return today + timedelta(days=1)
    if expr == "yesterday":
        return today - timedelta(days=1)
    if expr == "eow":
        return _week_monday(today) + timedelta(days=4)
    if expr == "eom":
        return today.replace(day=calendar.monthrange(today.year, today.month)[1])
    if expr in _WEEKDAYS:
        return _week_monday(today) + timedelta(days=_WEEKDAYS[expr])

    parts = expr.split(None, 1)
    if len(parts) == 2:
        prefix, rest = parts
        if prefix == "this" and rest in _WEEKDAYS:
            return _week_monday(today) + timedelta(days=_WEEKDAYS[rest])
        if prefix in ("last", "next") and rest in _WEEKDAYS:
            base = _week_monday(today)
            offset = timedelta(weeks=-1) if prefix == "last" else timedelta(weeks=1)
            return base + offset + timedelta(days=_WEEKDAYS[rest])
        m = _ORDINAL_RE.match(expr)
        if m:
            try:
                return today.replace(day=int(m.group(1)))
            except ValueError:
                return None

    m = _BARE_ORDINAL_RE.match(expr)
    if m:
        try:
            return today.replace(day=int(m.group(1)))
        except ValueError:
            return None

    m = _ORDINAL_OF_MONTH_RE.match(expr)
    if m:
        month = _MONTHS.get(m.group(2).lower())
        if month is None:
            return None
        try:
            return today.replace(month=month, day=int(m.group(1)))
        except ValueError:
            return None

    m = _FUTURE_OFFSET_RE.match(expr)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower().rstrip("s")
        return today + (timedelta(days=n) if unit == "day" else timedelta(weeks=n))

    m = _PAST_OFFSET_RE.match(expr)
    if m:
        n, unit = int(m.group(1)), m.group(2).lower().rstrip("s")
        return today - (timedelta(days=n) if unit == "day" else timedelta(weeks=n))

    m = _MONTH_DAY_RE.match(expr)
    if m:
        if m.group("mn"):
            month_str, day_str = m.group("mn"), m.group("dn1")
        else:
            month_str, day_str = m.group("mn2"), m.group("dn2")
        month = _MONTHS.get(month_str)
        day = int(re.sub(r"(?:st|nd|rd|th)$", "", day_str))
        if month is None:
            return None
        try:
            return today.replace(month=month, day=day)
        except ValueError:
            return None

    return None


def _as_time(token: str) -> str | None:
    t = token.lower()
    if t == "cob":      return _COB_TIME
    if t == "noon":     return "12:00"
    if t == "midnight": return "00:00"
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    m = _AMPM_RE.match(token)
    if m:
        h, mins, mer = int(m.group(1)), m.group(2) or "00", m.group(3).lower()
        if mer == "pm" and h != 12: h += 12
        elif mer == "am" and h == 12: h = 0
        return f"{h:02d}:{mins}"
    return None


def _parse_expr(raw: str, today: date) -> str | None:
    normalised = re.sub(r"c\.o\.b", "cob", raw, flags=re.IGNORECASE)
    normalised = re.sub(r"e\.o\.w", "eow", normalised, flags=re.IGNORECASE)
    normalised = re.sub(r"e\.o\.m", "eom", normalised, flags=re.IGNORECASE)

    time_val: str | None = None
    date_tokens: list[str] = []

    for token in normalised.split():
        t = _as_time(token)
        if t is not None:
            time_val = t
        else:
            date_tokens.append(token)

    date_expr = " ".join(date_tokens)
    resolved = _resolve_date(date_expr, today) if date_expr else today

    if resolved is None:
        return None

    return f"~{{{resolved.isoformat()}T{time_val}}}" if time_val else f"~{{{resolved.isoformat()}}}"


# ── public API ────────────────────────────────────────────────────────────────

@dataclass
class NormalizeResult:
    text: str
    unresolved: list[str] = field(default_factory=list)


def normalize_dates(text: str, today: date | None = None) -> NormalizeResult:
    """Replace ~expressions in text with ISO date/datetime forms.

    Pass `today` explicitly in tests; defaults to date.today() in production.
    """
    if today is None:
        today = date.today()

    unresolved: list[str] = []

    def replace(m: re.Match[str]) -> str:
        if m.group(1) is not None:   # already-normalised ~~ISO — pass through
            return m.group(1)
        raw = m.group(2)
        result = _parse_expr(raw, today)
        if result is None:
            unresolved.append("~" + raw)
            return "~" + raw
        return result

    return NormalizeResult(text=_EXPR_RE.sub(replace, text), unresolved=unresolved)
