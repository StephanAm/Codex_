"""Tests for date expression normalisation (rules/dateparsingrules.md)."""

import csv
from datetime import date
from pathlib import Path

import pytest

from note_taker.dates import normalize_dates


def norm(text: str, today: date) -> str:
    return normalize_dates(text, today=today).text


MON = date(2026, 5, 18)  # Monday
WED = date(2026, 5, 20)  # Wednesday


# ── Rule 1: bare day name → this week ────────────────────────────────────────

def test_r1_friday_from_monday() -> None:
    assert norm("~Friday", MON) == "~{2026-05-22}"

def test_r1_monday_from_wednesday() -> None:
    assert norm("~Monday", WED) == "~{2026-05-18}"

def test_r1_sunday_from_monday() -> None:
    assert norm("~Sunday", MON) == "~{2026-05-24}"


# ── Rule 2: last [day] → previous week ───────────────────────────────────────

def test_r2_last_friday_from_monday() -> None:
    assert norm("~last Friday", MON) == "~{2026-05-15}"

def test_r2_last_monday_from_wednesday() -> None:
    assert norm("~last Monday", WED) == "~{2026-05-11}"

def test_r2_last_sunday_from_monday() -> None:
    assert norm("~last Sunday", MON) == "~{2026-05-17}"


# ── Rule 3: next [day] → next week ───────────────────────────────────────────

def test_r3_next_friday_from_monday() -> None:
    assert norm("~next Friday", MON) == "~{2026-05-29}"

def test_r3_next_monday_from_wednesday() -> None:
    assert norm("~next Monday", WED) == "~{2026-05-25}"

def test_r3_next_sunday_from_monday() -> None:
    assert norm("~next Sunday", MON) == "~{2026-05-31}"


# ── Rule 4: today ─────────────────────────────────────────────────────────────

def test_r4_today() -> None:
    assert norm("~today", MON) == "~{2026-05-18}"


# ── Rule 5: tomorrow ─────────────────────────────────────────────────────────

def test_r5_tomorrow() -> None:
    assert norm("~tomorrow", MON) == "~{2026-05-19}"


# ── Rule 6: yesterday ────────────────────────────────────────────────────────

def test_r6_yesterday() -> None:
    assert norm("~yesterday", MON) == "~{2026-05-17}"


# ── Rule 7: time suffix ───────────────────────────────────────────────────────

def test_r7_friday_with_time() -> None:
    assert norm("~Friday 14:30", MON) == "~{2026-05-22T14:30}"

def test_r7_next_monday_with_time() -> None:
    assert norm("~next Monday 09:00", MON) == "~{2026-05-25T09:00}"

def test_r7_today_with_time() -> None:
    assert norm("~today 08:00", MON) == "~{2026-05-18T08:00}"


# ── Rule 8: ordinal day → this month ─────────────────────────────────────────

def test_r8_10th() -> None:
    assert norm("~the 10th", MON) == "~{2026-05-10}"

def test_r8_3rd() -> None:
    assert norm("~the 3rd", MON) == "~{2026-05-03}"

def test_r8_31st() -> None:
    assert norm("~the 31st", MON) == "~{2026-05-31}"

def test_r8_ordinal_with_time() -> None:
    assert norm("~the 10th 09:00", MON) == "~{2026-05-10T09:00}"

def test_r8_invalid_day_leaves_unchanged() -> None:
    assert norm("~the 32nd", MON) == "~the 32nd"


# ── Rule 9: bare time → today ─────────────────────────────────────────────────

def test_r9_bare_time() -> None:
    assert norm("~14:30", MON) == "~{2026-05-18T14:30}"

def test_r9_bare_time_zero_prefix() -> None:
    assert norm("~09:00", MON) == "~{2026-05-18T09:00}"


# ── Rule 10: COB → 17:00 ─────────────────────────────────────────────────────

def test_r10_cob_lowercase() -> None:
    assert norm("~cob", MON) == "~{2026-05-18T17:00}"

def test_r10_cob_uppercase() -> None:
    assert norm("~COB", MON) == "~{2026-05-18T17:00}"

def test_r10_cob_dotted() -> None:
    assert norm("~c.o.b", MON) == "~{2026-05-18T17:00}"

def test_r10_friday_cob() -> None:
    assert norm("~Friday cob", MON) == "~{2026-05-22T17:00}"

def test_r10_cob_friday() -> None:
    assert norm("~cob Friday", MON) == "~{2026-05-22T17:00}"

def test_r10_next_monday_cob() -> None:
    assert norm("~next Monday COB", MON) == "~{2026-05-25T17:00}"

def test_r10_cob_next_monday() -> None:
    assert norm("~COB next Monday", MON) == "~{2026-05-25T17:00}"


# ── Rule 11: month name + day number → specific date ─────────────────────────

def test_r11_month_first_full() -> None:
    assert norm("~April 3rd", MON) == "~{2026-04-03}"

def test_r11_month_first_abbrev() -> None:
    assert norm("~Apr 4", MON) == "~{2026-04-04}"

def test_r11_month_first_bare_number() -> None:
    assert norm("~May 10", MON) == "~{2026-05-10}"

def test_r11_day_first_space() -> None:
    assert norm("~3 April", MON) == "~{2026-04-03}"

def test_r11_day_first_ordinal() -> None:
    assert norm("~10th May", MON) == "~{2026-05-10}"

def test_r11_day_first_hyphen() -> None:
    assert norm("~3-April", MON) == "~{2026-04-03}"

def test_r11_with_time() -> None:
    assert norm("~April 3rd 09:00", MON) == "~{2026-04-03T09:00}"


# ── Rule 12: explicit numeric date ────────────────────────────────────────────

def test_r12_ymd_slash() -> None:
    assert norm("~2026/12/16", MON) == "~{2026-12-16}"

def test_r12_ymd_dash() -> None:
    assert norm("~2026-12-16", MON) == "~{2026-12-16}"

def test_r12_dmy_slash() -> None:
    assert norm("~12/03/2025", MON) == "~{2025-03-12}"

def test_r12_dmy_dash() -> None:
    assert norm("~12-03-2025", MON) == "~{2025-03-12}"

def test_r12_invalid_day_leaves_unchanged() -> None:
    assert norm("~32/01/2025", MON) == "~32/01/2025"


# ── Unresolvable expressions ──────────────────────────────────────────────────

def test_unresolvable_left_unchanged() -> None:
    result = normalize_dates("~gibberish", today=MON)
    assert result.text == "~gibberish"
    assert result.unresolved == ["~gibberish"]


# ── Integration: expressions embedded in note text ───────────────────────────

def test_expression_in_sentence() -> None:
    text = "Follow up with @someone on ~Friday about the proposal."
    assert norm(text, MON) == "Follow up with @someone on ~{2026-05-22} about the proposal."

def test_multiple_expressions_in_text() -> None:
    text = "Meeting ~today 10:00, follow-up ~next Friday cob."
    assert norm(text, MON) == "Meeting ~{2026-05-18T10:00}, follow-up ~{2026-05-29T17:00}."

def test_already_resolved_expression_untouched() -> None:
    assert norm("~{2026-05-22}", MON) == "~{2026-05-22}"

def test_already_resolved_datetime_untouched() -> None:
    assert norm("~{2026-05-22T14:30}", MON) == "~{2026-05-22T14:30}"


# ── Rule 13: single-digit hours ──────────────────────────────────────────────

def test_r13_bare_single_digit_hour() -> None:
    assert norm("~9:00", MON) == "~{2026-05-18T09:00}"

def test_r13_single_digit_with_day() -> None:
    assert norm("~Friday 9:00", MON) == "~{2026-05-22T09:00}"


# ── Rule 14: AM/PM time format ────────────────────────────────────────────────

def test_r14_pm_no_minutes() -> None:
    assert norm("~3pm", MON) == "~{2026-05-18T15:00}"

def test_r14_am_no_minutes() -> None:
    assert norm("~3am", MON) == "~{2026-05-18T03:00}"

def test_r14_am_with_minutes() -> None:
    assert norm("~9:30am", MON) == "~{2026-05-18T09:30}"

def test_r14_pm_with_minutes() -> None:
    assert norm("~3:30pm", MON) == "~{2026-05-18T15:30}"

def test_r14_12pm_is_noon() -> None:
    assert norm("~12pm", MON) == "~{2026-05-18T12:00}"

def test_r14_12am_is_midnight() -> None:
    assert norm("~12am", MON) == "~{2026-05-18T00:00}"

def test_r14_with_day_date_first() -> None:
    assert norm("~Friday 3pm", MON) == "~{2026-05-22T15:00}"

def test_r14_with_day_time_first() -> None:
    assert norm("~3pm Friday", MON) == "~{2026-05-22T15:00}"


# ── Rule 15: noon / midnight ──────────────────────────────────────────────────

def test_r15_noon() -> None:
    assert norm("~noon", MON) == "~{2026-05-18T12:00}"

def test_r15_midnight() -> None:
    assert norm("~midnight", MON) == "~{2026-05-18T00:00}"

def test_r15_noon_with_day() -> None:
    assert norm("~Friday noon", MON) == "~{2026-05-22T12:00}"

def test_r15_noon_day_time_first() -> None:
    assert norm("~noon Friday", MON) == "~{2026-05-22T12:00}"


# ── Rule 16: "this [day]" → this week ────────────────────────────────────────

def test_r16_this_friday_from_monday() -> None:
    assert norm("~this Friday", MON) == "~{2026-05-22}"

def test_r16_this_monday_from_wednesday() -> None:
    assert norm("~this Monday", WED) == "~{2026-05-18}"


# ── Rule 17: bare ordinal → this month ───────────────────────────────────────

def test_r17_bare_ordinal_10th() -> None:
    assert norm("~10th", MON) == "~{2026-05-10}"

def test_r17_bare_ordinal_3rd() -> None:
    assert norm("~3rd", MON) == "~{2026-05-03}"

def test_r17_bare_ordinal_with_time() -> None:
    assert norm("~10th 09:00", MON) == "~{2026-05-10T09:00}"


# ── Rule 18: "the Nth of [month]" → specific month ───────────────────────────

def test_r18_the_nth_of_month_full() -> None:
    assert norm("~the 10th of April", MON) == "~{2026-04-10}"

def test_r18_the_nth_of_month_abbrev() -> None:
    assert norm("~the 3rd of Jan", MON) == "~{2026-01-03}"


# ── Rule 19: "in N days/weeks" → future relative ─────────────────────────────

def test_r19_in_3_days() -> None:
    assert norm("~in 3 days", MON) == "~{2026-05-21}"

def test_r19_in_2_weeks() -> None:
    assert norm("~in 2 weeks", MON) == "~{2026-06-01}"

def test_r19_in_1_day_singular() -> None:
    assert norm("~in 1 day", MON) == "~{2026-05-19}"

def test_r19_in_1_week_singular() -> None:
    assert norm("~in 1 week", MON) == "~{2026-05-25}"


# ── Rule 20: "N days/weeks ago" → past relative ──────────────────────────────

def test_r20_3_days_ago() -> None:
    assert norm("~3 days ago", MON) == "~{2026-05-15}"

def test_r20_2_weeks_ago() -> None:
    assert norm("~2 weeks ago", MON) == "~{2026-05-04}"


# ── Rule 21: EOW / EOM ────────────────────────────────────────────────────────

def test_r21_eow_uppercase() -> None:
    assert norm("~EOW", MON) == "~{2026-05-22}"

def test_r21_eom_uppercase() -> None:
    assert norm("~EOM", MON) == "~{2026-05-31}"

def test_r21_eow_lowercase() -> None:
    assert norm("~eow", MON) == "~{2026-05-22}"

def test_r21_eom_lowercase() -> None:
    assert norm("~eom", MON) == "~{2026-05-31}"

def test_r21_eow_dotted() -> None:
    assert norm("~e.o.w", MON) == "~{2026-05-22}"

def test_r21_eom_dotted() -> None:
    assert norm("~e.o.m", MON) == "~{2026-05-31}"

def test_r21_eow_with_time() -> None:
    assert norm("~EOW 15:00", MON) == "~{2026-05-22T15:00}"


# ── CSV-driven parameterized tests ────────────────────────────────────────────

_CASES_CSV = Path(__file__).parent / "test_dates_cases.csv"

def _load_cases() -> list[tuple[str, str, str]]:
    with _CASES_CSV.open() as f:
        return [(r["input_text"], r["today"], r["expected_result"]) for r in csv.DictReader(f)]

@pytest.mark.parametrize("input_text,today_str,expected", _load_cases())
def test_csv_cases(input_text: str, today_str: str, expected: str) -> None:
    assert normalize_dates(input_text, today=date.fromisoformat(today_str)).text == expected
