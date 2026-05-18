# Date Parsing Rules

Rules for resolving natural language date references prefixed with `~` in Mnemo notes. On save, each `~expression` is resolved to an absolute ISO date or datetime and stored in the note body.

**Week anchor:** weeks run Monday–Sunday. "This week" always refers to the week containing today.

---

## Stored and display formats

| Type | Raw (user input) | Stored (normalised) | Displayed |
|---|---|---|---|
| Date | `~Friday` | `~{2026-05-22}` | `22 May 2026` |
| Date + time | `~Friday 15:00` | `~{2026-05-22T15:00}` | `22 May 2026 15:00` |

The `~` prefix marks a raw expression that needs parsing. The `~{}` wrapper marks an already-normalised value that is interpreted directly without re-parsing.

---

## Rules

### Rule 1 — Bare day name → this week

A day name alone refers to that day within the current week, regardless of whether that day has already passed. Both full names and 3-letter abbreviations are accepted, case-insensitive.

| Input | Today | Resolves to |
|---|---|---|
| `~Friday` | Mon 2026-05-18 | `~{2026-05-22}` |
| `~Fri` | Mon 2026-05-18 | `~{2026-05-22}` |
| `~Monday` | Wed 2026-05-20 | `~{2026-05-18}` *(already passed — still this week)* |
| `~mon` | Wed 2026-05-20 | `~{2026-05-18}` |
| `~Sunday` | Mon 2026-05-18 | `~{2026-05-24}` |

Accepted abbreviations: `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun`.

---

### Rule 2 — `last [day]` → previous week

`last` followed by a day name refers to that day in the week immediately before the current week.

| Input | Today | Resolves to |
|---|---|---|
| `~last Friday` | Mon 2026-05-18 | `~{2026-05-15}` |
| `~last Monday` | Wed 2026-05-20 | `~{2026-05-11}` |
| `~last Sunday` | Mon 2026-05-18 | `~{2026-05-17}` |

---

### Rule 3 — `next [day]` → next week

`next` followed by a day name refers to that day in the week immediately after the current week.

| Input | Today | Resolves to |
|---|---|---|
| `~next Friday` | Mon 2026-05-18 | `~{2026-05-29}` |
| `~next Monday` | Wed 2026-05-20 | `~{2026-05-25}` |
| `~next Sunday` | Mon 2026-05-18 | `~{2026-05-31}` |

---

### Rule 4 — `today`

Resolves to the current date.

| Input | Today | Resolves to |
|---|---|---|
| `~today` | 2026-05-18 | `~{2026-05-18}` |

---

### Rule 5 — `tomorrow`

Resolves to the day after today. The common misspelling `tommorrow` is also accepted.

| Input | Today | Resolves to |
|---|---|---|
| `~tomorrow` | 2026-05-18 | `~{2026-05-19}` |
| `~tommorrow` | 2026-05-18 | `~{2026-05-19}` |

---

### Rule 6 — `yesterday`

Resolves to the day before today.

| Input | Today | Resolves to |
|---|---|---|
| `~yesterday` | 2026-05-18 | `~{2026-05-17}` |

---

### Rule 7 — Time suffix

Any rule above can be suffixed with a time (`HH:MM`, 24-hour) to produce a datetime.

| Input | Today | Resolves to |
|---|---|---|
| `~Friday 14:30` | Mon 2026-05-18 | `~{2026-05-22T14:30}` |
| `~next Monday 09:00` | Mon 2026-05-18 | `~{2026-05-25T09:00}` |
| `~today 08:00` | 2026-05-18 | `~{2026-05-18T08:00}` |

---

### Rule 8 — Ordinal day → this month

An ordinal day number refers to that date in the current month, regardless of whether it has already passed.

| Input | Today | Resolves to |
|---|---|---|
| `~the 10th` | 2026-05-18 | `~{2026-05-10}` |
| `~the 3rd` | 2026-05-18 | `~{2026-05-03}` |
| `~the 31st` | 2026-05-18 | `~{2026-05-31}` |

Supports ordinal suffixes: `st`, `nd`, `rd`, `th`. Time suffix (Rule 7) applies: `~the 10th 09:00` → `~{2026-05-10T09:00}`.

---

### Rule 9 — Bare time → today

A time alone with no date reference assumes today as the date.

| Input | Today | Resolves to |
|---|---|---|
| `~14:30` | 2026-05-18 | `~{2026-05-18T14:30}` |
| `~09:00` | 2026-05-18 | `~{2026-05-18T09:00}` |

---

### Rule 10 — COB (close of business) → 17:00

`cob`, `COB`, and `c.o.b` are treated as a time alias for `17:00`. Follows Rule 9 (bare time assumes today) and combines with any date rule. The time component may appear before or after the date expression — order is interchangeable.

| Input | Today | Resolves to |
|---|---|---|
| `~cob` | 2026-05-18 | `~{2026-05-18T17:00}` |
| `~COB` | 2026-05-18 | `~{2026-05-18T17:00}` |
| `~c.o.b` | 2026-05-18 | `~{2026-05-18T17:00}` |
| `~Friday cob` | Mon 2026-05-18 | `~{2026-05-22T17:00}` |
| `~cob Friday` | Mon 2026-05-18 | `~{2026-05-22T17:00}` |
| `~next Monday COB` | Mon 2026-05-18 | `~{2026-05-25T17:00}` |
| `~COB next Monday` | Mon 2026-05-18 | `~{2026-05-25T17:00}` |

---

### Rule 11 — Month name + day number → specific date

A month name paired with a day number resolves to that date in the named month of the current year. Order is interchangeable (month-first or day-first). The day number may be bare (`3`) or ordinal (`3rd`). Month names may be full or 3-letter abbreviations, case-insensitive. A hyphen may be used as a separator in place of a space for the day-first form.

| Input | Today | Resolves to |
|---|---|---|
| `~May 10` | 2026-05-18 | `~{2026-05-10}` |
| `~April 3rd` | 2026-05-01 | `~{2026-04-03}` |
| `~10th May` | 2026-05-18 | `~{2026-05-10}` |
| `~3 April` | 2026-05-01 | `~{2026-04-03}` |
| `~3-April` | 2026-05-01 | `~{2026-04-03}` |
| `~Apr 4` | 2026-05-18 | `~{2026-04-04}` |

Time suffix (Rule 7) applies: `~April 3rd 09:00` → `~{2026-04-03T09:00}`.

---

### Rule 12 — Explicit numeric date

A fully numeric date with a `/` or `-` separator. The position of the 4-digit year determines the order:

- **Year first** (`YYYY/MM/DD` or `YYYY-MM-DD`) — e.g. `2026/12/16`
- **Year last** (`DD/MM/YYYY` or `DD-MM-YYYY`) — e.g. `12/03/2025`

Separators may be mixed. The date is resolved to the exact calendar date regardless of `today`.

| Input | Resolves to |
|---|---|
| `~2026/12/16` | `~{2026-12-16}` |
| `~2026-12-16` | `~{2026-12-16}` |
| `~12/03/2025` | `~{2025-03-12}` |
| `~12-03-2025` | `~{2025-03-12}` |

---

### Rule 13 — Single-digit hours

Hours in `HH:MM` format do not require a leading zero.

| Input | Today | Resolves to |
|---|---|---|
| `~9:00` | 2026-05-18 | `~{2026-05-18T09:00}` |
| `~Friday 9:00` | Mon 2026-05-18 | `~{2026-05-22T09:00}` |

---

### Rule 14 — AM/PM time format

Times may be expressed in 12-hour AM/PM format. The minutes part is optional. `12pm` = noon (12:00); `12am` = midnight (00:00).

| Input | Today | Resolves to |
|---|---|---|
| `~3pm` | 2026-05-18 | `~{2026-05-18T15:00}` |
| `~9:30am` | 2026-05-18 | `~{2026-05-18T09:30}` |
| `~12pm` | 2026-05-18 | `~{2026-05-18T12:00}` |
| `~12am` | 2026-05-18 | `~{2026-05-18T00:00}` |
| `~Friday 3pm` | Mon 2026-05-18 | `~{2026-05-22T15:00}` |

Order is interchangeable: `~3pm Friday` = `~Friday 3pm`.

---

### Rule 15 — `noon` / `midnight` time aliases

`noon` resolves to 12:00; `midnight` resolves to 00:00. Follows Rule 9 (bare time assumes today). Combines with any date rule.

| Input | Today | Resolves to |
|---|---|---|
| `~noon` | 2026-05-18 | `~{2026-05-18T12:00}` |
| `~midnight` | 2026-05-18 | `~{2026-05-18T00:00}` |
| `~Friday noon` | Mon 2026-05-18 | `~{2026-05-22T12:00}` |

---

### Rule 16 — `this [day]` → this week

`this` followed by a day name is an explicit form of Rule 1 — same semantics, same result.

| Input | Today | Resolves to |
|---|---|---|
| `~this Friday` | Mon 2026-05-18 | `~{2026-05-22}` |
| `~this Monday` | Wed 2026-05-20 | `~{2026-05-18}` |

---

### Rule 17 — Bare ordinal → this month

An ordinal day number without the leading `the` (e.g. `10th`, `3rd`) refers to that date in the current month. Same semantics as Rule 8.

| Input | Today | Resolves to |
|---|---|---|
| `~10th` | 2026-05-18 | `~{2026-05-10}` |
| `~3rd` | 2026-05-18 | `~{2026-05-03}` |
| `~10th 09:00` | 2026-05-18 | `~{2026-05-10T09:00}` |

---

### Rule 18 — `the Nth of [month]` → specific month

An ordinal day with an explicit `of [month]` clause resolves to that date in the named month of the current year.

| Input | Today | Resolves to |
|---|---|---|
| `~the 10th of April` | 2026-05-18 | `~{2026-04-10}` |
| `~the 3rd of Jan` | 2026-05-18 | `~{2026-01-03}` |

---

### Rule 19 — `in N days/weeks` → future relative

Resolves to a date N days or weeks from today.

| Input | Today | Resolves to |
|---|---|---|
| `~in 3 days` | 2026-05-18 | `~{2026-05-21}` |
| `~in 2 weeks` | 2026-05-18 | `~{2026-06-01}` |
| `~in 1 day` | 2026-05-18 | `~{2026-05-19}` |
| `~in 1 week` | 2026-05-18 | `~{2026-05-25}` |

---

### Rule 20 — `N days/weeks ago` → past relative

Resolves to a date N days or weeks before today.

| Input | Today | Resolves to |
|---|---|---|
| `~3 days ago` | 2026-05-18 | `~{2026-05-15}` |
| `~2 weeks ago` | 2026-05-18 | `~{2026-05-04}` |

---

### Rule 21 — `EOW` / `EOM`

`EOW` (end of week) resolves to Friday of the current week. `EOM` (end of month) resolves to the last day of the current month. Dotted forms (`e.o.w`, `e.o.m`) and lowercase are accepted. Time suffix applies.

| Input | Today | Resolves to |
|---|---|---|
| `~EOW` | Mon 2026-05-18 | `~{2026-05-22}` |
| `~EOM` | Mon 2026-05-18 | `~{2026-05-31}` |
| `~e.o.w` | Mon 2026-05-18 | `~{2026-05-22}` |
| `~e.o.m` | Mon 2026-05-18 | `~{2026-05-31}` |
| `~EOW 15:00` | Mon 2026-05-18 | `~{2026-05-22T15:00}` |

---

## Unresolvable expressions

If an expression cannot be parsed, it is left unchanged in the note body and flagged to the user.
