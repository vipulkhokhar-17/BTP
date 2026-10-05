import random
from datetime import date, timedelta

from generator import build
from generator.catalog import CATALOG
from seo_agent import analyze, experiment

SLUGS = [e.slug for e in CATALOG]


def synthetic_rows(treatment, effect, start, days_before=35, days_after=40, seed=1):
    """Daily GSC-like rows. Every page shares a site-wide trend; treatment pages
    get `effect` extra clicks per day after the start date."""
    rng = random.Random(seed)
    base = {p: rng.uniform(2, 20) for p in SLUGS}
    rows = []
    for i in range(-days_before, days_after):
        d = start + timedelta(days=i)
        trend = 1.0 + 0.01 * i  # the whole site grows, which DiD must cancel out
        for p in SLUGS:
            clicks = base[p] * trend + rng.gauss(0, 1.5)
            if i >= 0 and p in treatment:
                clicks += effect
            clicks = max(clicks, 0)
            rows.append({"date": d.isoformat(), "page": f"https://vip-ul.codes/cron/{p}/",
                         "clicks": clicks, "impressions": clicks * 20, "position": 12.0})
    return rows


def make_exp(start):
    control, treatment = experiment.matched_split(SLUGS, {}, seed=3)
    return {"id": "t", "hypothesis": "h", "changes": {}, "primary_metric": "clicks",
            "start_date": start.isoformat(), "control": control, "treatment": treatment}


def test_detects_real_effect():
    start = date(2026, 11, 1)
    exp = make_exp(start)
    res = analyze.analyze(exp, synthetic_rows(set(exp["treatment"]), 3.0, start))
    clicks = res["metrics"]["clicks"]
    assert 2.0 < clicks["effect"] < 4.0
    assert clicks["p_value"] < 0.01
    assert analyze.verdict(res, "clicks") == "improved"


def test_detects_degradation():
    start = date(2026, 11, 1)
    exp = make_exp(start)
    res = analyze.analyze(exp, synthetic_rows(set(exp["treatment"]), -3.0, start))
    assert analyze.verdict(res, "clicks") == "degraded"


def test_no_false_positive_without_effect():
    start = date(2026, 11, 1)
    exp = make_exp(start)
    res = analyze.analyze(exp, synthetic_rows(set(exp["treatment"]), 0.0, start, seed=7))
    assert res["metrics"]["clicks"]["p_value"] > 0.05


def test_matched_split_is_balanced_and_disjoint():
    baseline = {p: float(i) for i, p in enumerate(SLUGS)}
    control, treatment = experiment.matched_split(SLUGS, baseline, seed=0)
    assert not set(control) & set(treatment)
    assert set(control) | set(treatment) == set(SLUGS)
    assert abs(len(control) - len(treatment)) <= 1
    tot = lambda g: sum(baseline[p] for p in g) / len(g)
    assert abs(tot(control) - tot(treatment)) < 2.0


def test_running_experiment_changes_only_treatment(tmp_path, monkeypatch):
    exp_dir = tmp_path / "experiments"
    exp_dir.mkdir()
    (exp_dir / "x.json").write_text(
        '{"id": "x", "status": "running", "changes": {"faq": true},'
        ' "control": ["every-hour"], "treatment": ["every-5-minutes"]}')
    monkeypatch.setattr(build, "EXPERIMENTS_DIR", exp_dir)
    build.build(tmp_path)
    assert "FAQPage" in (tmp_path / "cron/every-5-minutes/index.html").read_text()
    assert "FAQPage" not in (tmp_path / "cron/every-hour/index.html").read_text()
