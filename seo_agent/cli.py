"""Command line for the SEO experiment agent.

  python -m seo_agent audit
  python -m seo_agent fetch --start 2026-10-01 --end 2026-11-30
  python -m seo_agent new EXP_ID --hypothesis "..." --change faq=true [--group minutes ...]
  python -m seo_agent start EXP_ID
  python -m seo_agent analyze EXP_ID
  python -m seo_agent stop EXP_ID keep|revert
  python -m seo_agent power --rate 2

After new/start/stop, rebuild the site (python -m generator.build) and commit.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from generator.build import DEFAULT_KNOBS, ROOT
from generator.catalog import CATALOG

from . import analyze, audit, experiment, gsc, power

SITE_PROPERTY = "sc-domain:vip-ul.codes"
DATA = ROOT / "data" / "gsc_pages.csv"
REPORTS = ROOT / "reports"


def _parse_value(key, raw):
    default = DEFAULT_KNOBS[key]
    if isinstance(default, bool):
        if raw.lower() not in ("true", "false"):
            raise SystemExit(f"{key} must be true or false")
        return raw.lower() == "true"
    if isinstance(default, int):
        return int(raw)
    return raw


def cmd_audit(args):
    pages = audit.audit_site(ROOT)
    problems = 0
    for p in sorted(pages, key=lambda p: p.path):
        if p.issues or args.verbose:
            print(f"{p.path}  title={p.title_len}c meta={p.meta_len}c words={p.words} "
                  f"in={p.internal_in} out={p.internal_out} jsonld={p.jsonld_types}")
            for i in p.issues:
                print(f"    - {i}")
                problems += 1
    print(f"\n{len(pages)} pages audited, {problems} issues")


def cmd_fetch(args):
    end = args.end or (date.today() - timedelta(days=3)).isoformat()
    rows = list(gsc.fetch(SITE_PROPERTY, args.start, end))
    gsc.save_csv(rows, DATA)
    print(f"saved {len(rows)} rows to {DATA.relative_to(ROOT)}")


def _baseline_impressions():
    if not DATA.exists():
        return {}
    totals = defaultdict(float)
    for r in gsc.load_csv(DATA):
        slug = analyze._page_key(r["page"])
        if slug:
            totals[slug] += r["impressions"]
    return totals


def _pages_in_running_experiments():
    busy = set()
    for path in experiment.EXPERIMENTS_DIR.glob("*.json"):
        exp = json.loads(path.read_text())
        if exp["status"] in ("draft", "running"):
            busy |= set(exp["control"]) | set(exp["treatment"])
    return busy


def cmd_new(args):
    changes = {}
    for item in args.change:
        key, _, raw = item.partition("=")
        if key not in DEFAULT_KNOBS:
            raise SystemExit(f"unknown knob {key}; allowed: {', '.join(DEFAULT_KNOBS)}")
        changes[key] = _parse_value(key, raw)
    busy = _pages_in_running_experiments()
    pages = [e.slug for e in CATALOG if (not args.group or e.group in args.group) and e.slug not in busy]
    if len(pages) < 10:
        raise SystemExit(f"only {len(pages)} free pages; need at least 10 for a meaningful test")
    exp = experiment.create(args.exp_id, args.hypothesis, changes, pages,
                            baseline=_baseline_impressions(), seed=args.seed, metric=args.metric)
    print(f"created experiments/{exp['id']}.json: {len(exp['treatment'])} treatment, "
          f"{len(exp['control'])} control pages")


def cmd_start(args):
    exp = experiment.start(args.exp_id)
    print(f"{exp['id']} running from {exp['start_date']}. Rebuild the site and deploy now.")


def cmd_stop(args):
    exp = experiment.stop(args.exp_id, args.decision)
    print(f"{exp['id']} ended ({exp['decision']}). Rebuild the site and deploy now.")


def cmd_analyze(args):
    exp = experiment.load(args.exp_id)
    if not exp["start_date"]:
        raise SystemExit("experiment has not started")
    rows = gsc.load_csv(args.data or DATA)
    result = analyze.analyze(exp, rows, pre_days=args.pre, post_days=args.post, burn_in_days=args.burn_in)
    report = analyze.format_report(exp, result)
    REPORTS.mkdir(exist_ok=True)
    out = REPORTS / f"{exp['id']}.md"
    out.write_text(report)
    print(report)
    print(f"Primary metric ({exp['primary_metric']}): "
          f"{analyze.verdict(result, exp['primary_metric'])}. Report saved to {out.relative_to(ROOT)}")


def cmd_power(args):
    print(f"{args.pages} pages, {args.pre}d before, {args.burn_in}d burn-in, {args.post}d after, "
          f"{args.sims} simulations each")
    for uplift in args.uplift:
        pw = power.power(n_pages=args.pages, median_rate=args.rate, uplift=uplift, pre_days=args.pre,
                         post_days=args.post, burn_in=args.burn_in, sims=args.sims)
        print(f"  median {args.rate}/page/day, true uplift {uplift:+.0%}: detected {pw:.0%} of the time")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="seo_agent")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="on-page audit of the built site")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=cmd_audit)

    f = sub.add_parser("fetch", help="download Search Console data per page per day")
    f.add_argument("--start", required=True)
    f.add_argument("--end")
    f.set_defaults(fn=cmd_fetch)

    n = sub.add_parser("new", help="create a draft experiment with a matched split")
    n.add_argument("exp_id")
    n.add_argument("--hypothesis", required=True)
    n.add_argument("--change", action="append", required=True, metavar="KNOB=VALUE")
    n.add_argument("--group", action="append", help="limit to catalog groups")
    n.add_argument("--metric", default="clicks", choices=analyze.METRICS)
    n.add_argument("--seed", type=int, default=0)
    n.set_defaults(fn=cmd_new)

    s = sub.add_parser("start")
    s.add_argument("exp_id")
    s.set_defaults(fn=cmd_start)

    st = sub.add_parser("stop")
    st.add_argument("exp_id")
    st.add_argument("decision", choices=["keep", "revert"])
    st.set_defaults(fn=cmd_stop)

    an = sub.add_parser("analyze", help="difference-in-differences report")
    an.add_argument("exp_id")
    an.add_argument("--data", type=Path)
    an.add_argument("--pre", type=int, default=28)
    an.add_argument("--post", type=int, default=28)
    an.add_argument("--burn-in", type=int, default=7)
    an.set_defaults(fn=cmd_analyze)

    pw = sub.add_parser("power", help="simulate how large an effect a test can detect")
    pw.add_argument("--rate", type=float, default=2.0, help="median clicks (or impressions) per page per day")
    pw.add_argument("--uplift", type=float, action="append", default=None)
    pw.add_argument("--pages", type=int, default=len(CATALOG))
    pw.add_argument("--pre", type=int, default=28)
    pw.add_argument("--post", type=int, default=28)
    pw.add_argument("--burn-in", type=int, default=7)
    pw.add_argument("--sims", type=int, default=60)
    pw.set_defaults(fn=cmd_power)

    args = ap.parse_args(argv)
    if args.cmd == "power" and not args.uplift:
        args.uplift = [0.1, 0.2, 0.3, 0.5]
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
