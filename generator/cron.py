"""Minimal, dependency-free cron engine for standard 5-field (Vixie) cron.

Used by the site generator to compute facts shown on each page (field
meanings, example run times, platform translations, gotchas), so nothing on
a page is hand-typed guesswork. Tests cross-check it against croniter.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

MONTH_NAMES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
               "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DOW_NAMES = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
DOW_FULL = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
MONTH_FULL = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]

# name, min, max
FIELDS = [
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day of month", 1, 31),
    ("month", 1, 12),
    ("day of week", 0, 7),
]


class CronError(ValueError):
    pass


def _value(token, idx):
    token = token.upper()
    if idx == 3 and token in MONTH_NAMES:
        return MONTH_NAMES.index(token) + 1
    if idx == 4 and token in DOW_NAMES:
        return DOW_NAMES.index(token)
    if not token.isdigit():
        raise CronError(f"bad value {token!r} in {FIELDS[idx][0]} field")
    return int(token)


def parse_field(text, idx):
    """Return the sorted set of values a field matches."""
    name, lo, hi = FIELDS[idx]
    values = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            if not step_s.isdigit() or int(step_s) == 0:
                raise CronError(f"bad step in {name} field")
            step = int(step_s)
        if part == "*":
            start, end = lo, hi
            if idx == 4:
                end = 6
        elif "-" in part:
            a, b = part.split("-", 1)
            start, end = _value(a, idx), _value(b, idx)
        else:
            start = _value(part, idx)
            # "5/15" means 5,20,35,50 (start then step to the field max)
            end = (6 if idx == 4 else hi) if step > 1 else start
        if not (lo <= start <= hi and lo <= end <= hi) or start > end:
            raise CronError(f"{part!r} out of range for {name} ({lo}-{hi})")
        values.update(range(start, end + 1, step))
    if idx == 4 and 7 in values:
        values.discard(7)
        values.add(0)
    return sorted(values)


@dataclass
class Cron:
    expr: str
    fields: list  # raw field strings
    minutes: list
    hours: list
    doms: list
    months: list
    dows: list

    @property
    def dom_restricted(self):
        return not self.fields[2].startswith("*")

    @property
    def dow_restricted(self):
        return not self.fields[4].startswith("*")

    def matches(self, dt):
        if dt.minute not in self.minutes or dt.hour not in self.hours:
            return False
        if dt.month not in self.months:
            return False
        dom_ok = dt.day in self.doms
        dow_ok = (dt.isoweekday() % 7) in self.dows
        # Vixie cron: if both day fields are restricted, a match on either runs the job.
        if self.dom_restricted and self.dow_restricted:
            return dom_ok or dow_ok
        return dom_ok and dow_ok

    def next_runs(self, start, count):
        """Next `count` run times strictly after `start` (naive datetimes)."""
        runs = []
        dt = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = start + timedelta(days=366 * 40)
        while len(runs) < count:
            if dt > limit:
                break
            if dt.month not in self.months:
                dt = _first_of_next_month(dt)
                continue
            if not self._day_ok(dt):
                dt = (dt + timedelta(days=1)).replace(hour=0, minute=0)
                continue
            if dt.hour not in self.hours:
                dt = (dt + timedelta(hours=1)).replace(minute=0)
                continue
            if dt.minute in self.minutes:
                runs.append(dt)
            dt += timedelta(minutes=1)
        return runs

    def _day_ok(self, dt):
        dom_ok = dt.day in self.doms
        dow_ok = (dt.isoweekday() % 7) in self.dows
        if self.dom_restricted and self.dow_restricted:
            return dom_ok or dow_ok
        return dom_ok and dow_ok


def _first_of_next_month(dt):
    if dt.month == 12:
        return dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0)
    return dt.replace(month=dt.month + 1, day=1, hour=0, minute=0)


def parse(expr):
    parts = expr.split()
    if len(parts) != 5:
        raise CronError(f"expected 5 fields, got {len(parts)}")
    sets = [parse_field(p, i) for i, p in enumerate(parts)]
    return Cron(expr, parts, *sets)


# ─── Plain-English field descriptions ────────────────────────────────

def _label(v, idx):
    if idx == 3:
        return MONTH_FULL[v - 1]
    if idx == 4:
        return DOW_FULL[v]
    if idx == 1:
        return f"{v:02d}:00–{v:02d}:59"
    return str(v)


def describe_field(text, idx):
    name, lo, hi = FIELDS[idx]
    if text == "*":
        return f"every {name}"
    values = parse_field(text, idx)
    if text.startswith("*/"):
        step = int(text[2:])
        shown = ", ".join(_label(v, idx) for v in values[:4])
        more = ", …" if len(values) > 4 else ""
        return f"every {step}{_ordinal_suffix(step)} {name} ({shown}{more})"
    if len(values) == 1:
        return f"only {_label(values[0], idx)}"
    if "-" in text and "," not in text and "/" not in text:
        return f"{_label(values[0], idx)} through {_label(values[-1], idx)}"
    return ", ".join(_label(v, idx) for v in values)


def _ordinal_suffix(n):
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


# ─── Gotchas computed from the expression itself ─────────────────────

def gotchas(cron):
    notes = []
    m = cron.fields[0]
    if m.startswith("*/"):
        step = int(m[2:])
        if 60 % step:
            notes.append(
                f"<code>*/{step}</code> in the minute field does not mean “every {step} minutes” "
                f"forever: it restarts at the top of each hour. It matches minutes "
                f"{', '.join(map(str, cron.minutes))}, so the gap between the last run of one hour "
                f"and the first run of the next is only {60 - cron.minutes[-1]} minutes.")
    h = cron.fields[1]
    if h.startswith("*/"):
        step = int(h[2:])
        if 24 % step:
            notes.append(
                f"<code>*/{step}</code> in the hour field restarts at midnight: it matches hours "
                f"{', '.join(map(str, cron.hours))}, so the gap across midnight is "
                f"{24 - cron.hours[-1]} hours, not {step}.")
    if m == "*" and h != "*":
        notes.append(
            "The minute field is <code>*</code>, so this runs <em>every minute</em> during the "
            "matching hours, not once. Use <code>0</code> in the minute field to run once per hour.")
    if cron.dom_restricted and cron.dow_restricted:
        notes.append(
            "Both day-of-month and day-of-week are set, so standard cron runs the job when "
            "<em>either</em> matches (OR), not when both match.")
    if cron.dom_restricted and max(cron.doms) > 28:
        notes.append(
            "Months without the selected day are skipped entirely (for example, day 31 never "
            "runs in April, June, September or November).")
    return notes


def min_gap_minutes(cron, start):
    runs = cron.next_runs(start, 200)
    if len(runs) < 2:
        return None
    return min((b - a).total_seconds() / 60 for a, b in zip(runs, runs[1:]))


# ─── Platform translations ───────────────────────────────────────────

def _quartz_like_field(text, idx):
    """Rewrite a field into Quartz/AWS syntax (names for weekdays, 0/n steps)."""
    if text == "*":
        return text
    if text.startswith("*/"):
        start = 1 if idx in (2, 3) else 0
        return f"{start}/{text[2:]}"
    if idx == 4:
        out = []
        for part in text.split(","):
            if "/" in part:
                return None
            if "-" in part:
                a, b = part.split("-", 1)
                out.append(f"{DOW_NAMES[_value(a, 4) % 7]}-{DOW_NAMES[_value(b, 4) % 7]}")
            else:
                out.append(DOW_NAMES[_value(part, 4) % 7])
        return ",".join(out)
    if "/" in text:
        return None
    return text


def to_aws(cron):
    """AWS EventBridge: cron(min hour dom month dow year); one day field must be '?'."""
    if cron.dom_restricted and cron.dow_restricted:
        return None
    f = [_quartz_like_field(t, i) for i, t in enumerate(cron.fields)]
    if None in f:
        return None
    if cron.dow_restricted:
        f[2] = "?"
    else:
        f[4] = "?"
    return f"cron({' '.join(f)} *)"


def to_quartz(cron):
    """Quartz scheduler: sec min hour dom month dow; one day field must be '?'."""
    aws = to_aws(cron)
    if aws is None:
        return None
    return "0 " + aws[5:-3]


def to_spring(cron):
    """Spring @Scheduled: 6 fields with seconds first; otherwise standard syntax."""
    if cron.dom_restricted and cron.dow_restricted:
        return None
    return "0 " + cron.expr


# ─── Frequency facts ─────────────────────────────────────────────────

def frequency(cron, year=2026):
    """Run counts and gaps between runs, computed over a whole calendar year."""
    from datetime import date as _date
    per_day = len(cron.minutes) * len(cron.hours)
    days = []
    d = _date(year, 1, 1)
    while d.year == year:
        if d.month in cron.months and cron._day_ok(datetime(d.year, d.month, d.day)):
            days.append(d)
        d += timedelta(days=1)
    runs_per_year = per_day * len(days)
    # Gaps: sample enough runs to cover every pattern (a week for sub-daily, a year otherwise).
    start = datetime(year, 1, 1) - timedelta(minutes=1)
    sample = cron.next_runs(start, min(runs_per_year, 3000) + 1)
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(sample, sample[1:])]
    return {
        "runs_per_matching_day": per_day,
        "matching_days_per_year": len(days),
        "runs_per_year": runs_per_year,
        "min_gap_min": min(gaps) if gaps else None,
        "max_gap_min": max(gaps) if gaps else None,
    }


def human_minutes(m):
    m = int(round(m))
    if m < 60:
        return f"{m} minute{'s' if m != 1 else ''}"
    if m % 1440 == 0:
        d = m // 1440
        return f"{d} day{'s' if d != 1 else ''}"
    if m % 60 == 0:
        h = m // 60
        return f"{h} hour{'s' if h != 1 else ''}"
    return f"{m // 60} h {m % 60} min"
