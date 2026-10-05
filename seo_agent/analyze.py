"""Difference-in-differences analysis of an SEO split test.

For each page we compare its average daily metric after the change with its
average before. The effect estimate is the mean change in treatment pages
minus the mean change in control pages, so site-wide movement (Google updates,
seasonality, the site getting older) cancels out.

Significance comes from a permutation test: shuffle which pages are
"treatment" thousands of times and see how often a random split produces an
effect at least as large. That makes no distribution assumptions, which
matters with a few dozen pages and noisy search data.
"""

import random
from collections import defaultdict
from datetime import date, timedelta
from statistics import mean

METRICS = ("clicks", "impressions", "ctr", "position")


def _page_key(url):
    """Map a GSC page URL to a catalog slug when possible."""
    marker = "/cron/"
    if marker in url:
        return url.split(marker, 1)[1].strip("/") or None
    return None


def page_period_metrics(rows, pages, start, end):
    """Daily-average metrics per page for start <= date < end.
    Days without a row count as zero clicks/impressions."""
    days = (end - start).days
    totals = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "pos_weighted": 0.0})
    for r in rows:
        d = date.fromisoformat(r["date"])
        slug = _page_key(r["page"])
        if slug in pages and start <= d < end:
            t = totals[slug]
            t["clicks"] += r["clicks"]
            t["impressions"] += r["impressions"]
            t["pos_weighted"] += r["position"] * r["impressions"]
    out = {}
    for p in pages:
        t = totals[p]
        imp = t["impressions"]
        out[p] = {
            "clicks": t["clicks"] / days,
            "impressions": imp / days,
            "ctr": t["clicks"] / imp if imp else None,
            "position": t["pos_weighted"] / imp if imp else None,
        }
    return out


def did(changes, treatment, control):
    t = [changes[p] for p in treatment if changes.get(p) is not None]
    c = [changes[p] for p in control if changes.get(p) is not None]
    if not t or not c:
        return None
    return mean(t) - mean(c)


def permutation_p(changes, treatment, control, observed, n=5000, seed=0):
    pages = [p for p in treatment + control if changes.get(p) is not None]
    k = len([p for p in treatment if changes.get(p) is not None])
    if observed is None or k == 0 or k == len(pages):
        return None
    rng = random.Random(seed)
    hits = 0
    for _ in range(n):
        rng.shuffle(pages)
        est = mean(changes[p] for p in pages[:k]) - mean(changes[p] for p in pages[k:])
        if abs(est) >= abs(observed) - 1e-12:
            hits += 1
    return (hits + 1) / (n + 1)


def analyze(exp, rows, pre_days=28, post_days=28, burn_in_days=7, end=None):
    """Compare [start - pre_days, start) with [start + burn_in, start + burn_in + post_days).

    The burn-in skips the days Google needs to recrawl the changed pages.
    """
    start = date.fromisoformat(exp["start_date"])
    pre = (start - timedelta(days=pre_days), start)
    post_start = start + timedelta(days=burn_in_days)
    post_end = post_start + timedelta(days=post_days)
    if end is not None:
        post_end = min(post_end, end)
    if post_end <= post_start:
        raise ValueError("no post-period data yet")
    pages = set(exp["control"]) | set(exp["treatment"])
    before = page_period_metrics(rows, pages, *pre)
    after = page_period_metrics(rows, pages, post_start, post_end)

    results = {}
    for m in METRICS:
        changes = {}
        for p in pages:
            b, a = before[p][m], after[p][m]
            changes[p] = None if b is None or a is None else a - b
        est = did(changes, exp["treatment"], exp["control"])
        results[m] = {
            "effect": est,
            "p_value": permutation_p(changes, exp["treatment"], exp["control"], est),
            "n_treatment": sum(changes[p] is not None for p in exp["treatment"]),
            "n_control": sum(changes[p] is not None for p in exp["control"]),
            "treatment_before": _avg(before, exp["treatment"], m),
            "treatment_after": _avg(after, exp["treatment"], m),
            "control_before": _avg(before, exp["control"], m),
            "control_after": _avg(after, exp["control"], m),
        }
    return {"pre": [d.isoformat() for d in pre],
            "post": [post_start.isoformat(), post_end.isoformat()],
            "metrics": results}


def _avg(period, pages, m):
    vals = [period[p][m] for p in pages if period[p][m] is not None]
    return mean(vals) if vals else None


def verdict(result, metric, alpha=0.05):
    r = result["metrics"][metric]
    if r["effect"] is None or r["p_value"] is None:
        return "inconclusive (not enough data)"
    # For position, lower is better.
    better = r["effect"] < 0 if metric == "position" else r["effect"] > 0
    if r["p_value"] >= alpha:
        return "no significant difference"
    return "improved" if better else "degraded"


def format_report(exp, result):
    lines = [f"# Experiment {exp['id']}", "",
             f"**Hypothesis:** {exp['hypothesis']}", "",
             f"**Change on treatment pages:** `{exp['changes']}`", "",
             f"Pre-period {result['pre'][0]} → {result['pre'][1]}, "
             f"post-period {result['post'][0]} → {result['post'][1]}", "",
             "| Metric | Treatment before → after | Control before → after | DiD effect | p-value | Verdict |",
             "|---|---|---|---|---|---|"]

    def f(x):
        return "–" if x is None else f"{x:.3f}"
    for m, r in result["metrics"].items():
        lines.append(f"| {m} | {f(r['treatment_before'])} → {f(r['treatment_after'])} | "
                     f"{f(r['control_before'])} → {f(r['control_after'])} | {f(r['effect'])} | "
                     f"{f(r['p_value'])} | {verdict(result, m)} |")
    lines += ["", "Clicks and impressions are per page per day. Position: lower is better."]
    return "\n".join(lines) + "\n"
