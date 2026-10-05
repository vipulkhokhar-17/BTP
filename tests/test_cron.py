import random
from datetime import datetime

import pytest
from croniter import croniter

from generator import cron
from generator.catalog import CATALOG

EXPRS = [
    "* * * * *", "*/5 * * * *", "*/7 * * * *", "*/45 * * * *", "0 * * * *",
    "0 */6 * * *", "0 */5 * * *", "30 9 * * 1-5", "0 0 1 * *", "0 0 1,15 * *",
    "0 0 1 1,4,7,10 *", "0 9 * * MON", "0 17 * * 5", "*/15 9-17 * * 1-5",
    "0 0 13 * 5", "0 12 * * 0,6", "0 0 31 * *", "5/15 * * * *", "0 0 * * 7",
    "0 0 29 2 *",
] + [e.expr for e in CATALOG]


@pytest.mark.parametrize("expr", sorted(set(EXPRS)))
def test_next_runs_match_croniter(expr):
    rng = random.Random(expr)
    c = cron.parse(expr)
    for _ in range(5):
        start = datetime(2026, 1, 1) + (datetime(2027, 12, 1) - datetime(2026, 1, 1)) * rng.random()
        start = start.replace(second=0, microsecond=0)
        ours = c.next_runs(start, 8)
        it = croniter(expr, start)
        theirs = [it.get_next(datetime) for _ in range(8)]
        assert ours == theirs, (expr, start)


def test_rejects_bad_expressions():
    for bad in ["* * * *", "60 * * * *", "* 24 * * *", "*/0 * * * *", "* * 0 * *", "5-1 * * * *"]:
        with pytest.raises(cron.CronError):
            cron.parse(bad)


def test_describe_field():
    assert cron.describe_field("*", 0) == "every minute"
    assert cron.describe_field("*/15", 0) == "every 15th minute (0, 15, 30, 45)"
    assert cron.describe_field("1-5", 4) == "Monday through Friday"
    assert cron.describe_field("0", 1) == "only 00:00–00:59"


def test_platform_translations():
    c = cron.parse("*/15 9-17 * * 1-5")
    assert cron.to_aws(c) == "cron(0/15 9-17 ? * MON-FRI *)"
    assert cron.to_quartz(c) == "0 0/15 9-17 ? * MON-FRI"
    assert cron.to_spring(c) == "0 */15 9-17 * * 1-5"
    assert cron.to_aws(cron.parse("0 0 1 * *")) == "cron(0 0 1 * ? *)"
    assert cron.to_aws(cron.parse("0 0 13 * 5")) is None


def test_gotchas_flag_uneven_steps():
    assert any("restarts at the top of each hour" in g for g in cron.gotchas(cron.parse("*/45 * * * *")))
    assert not cron.gotchas(cron.parse("*/15 * * * *"))
    assert any("every minute" in g for g in cron.gotchas(cron.parse("* 9 * * *")))


@pytest.mark.parametrize("expr", ["0 9 * * 1-5", "*/15 9-17 * * 1-5", "0 0 31 * *", "0 */5 * * *",
                                  "0 0 1 1,4,7,10 *", "*/45 * * * *", "0 0 13 * 5"])
def test_frequency_matches_croniter(expr):
    f = cron.frequency(cron.parse(expr))
    it = croniter(expr, datetime(2025, 12, 31, 23, 59))
    runs = []
    while True:
        r = it.get_next(datetime)
        if r.year > 2026:
            break
        runs.append(r)
    gaps = [(b - a).total_seconds() / 60 for a, b in zip(runs, runs[1:])]
    assert f["runs_per_year"] == len(runs)
    assert f["min_gap_min"] == min(gaps)
    assert f["max_gap_min"] == max(gaps)
