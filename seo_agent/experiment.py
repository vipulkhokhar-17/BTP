"""SEO split tests: pick pages, split them into matched control/treatment groups,
start, stop, and keep or revert.

An experiment is a JSON file in experiments/. While its status is "running",
the generator applies `changes` (knobs) to the treatment pages only.
"""

import json
import random
from datetime import date
from pathlib import Path

from generator.build import DEFAULT_KNOBS, ROOT

EXPERIMENTS_DIR = ROOT / "experiments"
SITE_CONFIG = ROOT / "generator" / "site_config.json"


def matched_split(pages, baseline, seed):
    """Sort pages by baseline impressions, pair neighbours, and randomly send
    one of each pair to treatment. Keeps the two groups balanced on traffic."""
    rng = random.Random(seed)
    ordered = sorted(pages, key=lambda p: (-baseline.get(p, 0.0), p))
    control, treatment = [], []
    for i in range(0, len(ordered) - 1, 2):
        a, b = ordered[i], ordered[i + 1]
        if rng.random() < 0.5:
            a, b = b, a
        control.append(a)
        treatment.append(b)
    if len(ordered) % 2:
        control.append(ordered[-1])
    return sorted(control), sorted(treatment)


def create(exp_id, hypothesis, changes, pages, baseline=None, seed=0, metric="clicks"):
    unknown = set(changes) - set(DEFAULT_KNOBS)
    if unknown:
        raise ValueError(f"unknown knobs: {sorted(unknown)}; allowed: {sorted(DEFAULT_KNOBS)}")
    path = EXPERIMENTS_DIR / f"{exp_id}.json"
    if path.exists():
        raise FileExistsError(path)
    control, treatment = matched_split(pages, baseline or {}, seed)
    exp = {
        "id": exp_id,
        "hypothesis": hypothesis,
        "changes": changes,
        "primary_metric": metric,
        "seed": seed,
        "status": "draft",
        "start_date": None,
        "end_date": None,
        "control": control,
        "treatment": treatment,
        "decision": None,
    }
    _save(exp)
    return exp


def load(exp_id):
    return json.loads((EXPERIMENTS_DIR / f"{exp_id}.json").read_text())


def _save(exp):
    EXPERIMENTS_DIR.mkdir(exist_ok=True)
    (EXPERIMENTS_DIR / f"{exp['id']}.json").write_text(json.dumps(exp, indent=2) + "\n")


def start(exp_id, on=None):
    exp = load(exp_id)
    if exp["status"] != "draft":
        raise ValueError(f"{exp_id} is {exp['status']}, not draft")
    exp["status"] = "running"
    exp["start_date"] = (on or date.today()).isoformat()
    _save(exp)
    return exp


def stop(exp_id, decision, on=None):
    """decision: 'keep' promotes the change to every page; 'revert' drops it."""
    if decision not in ("keep", "revert"):
        raise ValueError("decision must be keep or revert")
    exp = load(exp_id)
    if exp["status"] != "running":
        raise ValueError(f"{exp_id} is not running")
    exp["status"] = "ended"
    exp["end_date"] = (on or date.today()).isoformat()
    exp["decision"] = decision
    _save(exp)
    if decision == "keep":
        config = json.loads(SITE_CONFIG.read_text()) if SITE_CONFIG.exists() else {}
        config.update(exp["changes"])
        SITE_CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    return exp
