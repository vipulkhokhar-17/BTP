"""Power analysis by simulation: how big an effect can a split test on this
site detect, given how much traffic its pages get?

Each simulated page gets a baseline daily rate (log-normal across pages, as
search traffic is), daily counts are Poisson, the whole site drifts, and
treatment pages get a relative uplift after the start date. We then run the
real analysis (analyze.analyze) and count how often it reports p < alpha.
"""

import math
import random
from datetime import date, timedelta

from . import analyze, experiment


def _poisson(rng, lam):
    if lam > 50:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def simulate_once(rng, n_pages, median_rate, uplift, pre_days, post_days, burn_in, spread=1.0):
    pages = [f"p{i}" for i in range(n_pages)]
    base = {p: median_rate * math.exp(rng.gauss(0, spread)) for p in pages}
    control, treatment = experiment.matched_split(pages, base, seed=rng.randrange(1 << 30))
    tset = set(treatment)
    start = date(2026, 11, 1)
    rows = []
    for i in range(-pre_days, burn_in + post_days):
        d = (start + timedelta(days=i)).isoformat()
        trend = 1.0 + 0.005 * i
        for p in pages:
            lam = base[p] * trend * (1 + uplift if (i >= burn_in and p in tset) else 1)
            n = _poisson(rng, lam)
            if n:
                rows.append({"date": d, "page": f"https://vip-ul.codes/cron/{p}/",
                             "clicks": n, "impressions": n, "position": 10.0})
    exp = {"start_date": start.isoformat(), "control": control, "treatment": treatment}
    res = analyze.analyze(exp, rows, pre_days=pre_days, post_days=post_days, burn_in_days=burn_in, n_perm=400)
    return res["metrics"]["clicks"]["p_value"]


def power(n_pages=46, median_rate=1.0, uplift=0.2, pre_days=28, post_days=28, burn_in=7,
          sims=60, alpha=0.05, seed=0):
    rng = random.Random(seed)
    hits = 0
    for _ in range(sims):
        p = simulate_once(rng, n_pages, median_rate, uplift, pre_days, post_days, burn_in)
        if p is not None and p < alpha:
            hits += 1
    return hits / sims
