"""Build the static cron reference pages, homepage, sitemap and robots.txt.

    python -m generator.build

Page features are controlled by "knobs" (see DEFAULT_KNOBS). Experiments in
experiments/*.json with status "running" override knobs for their treatment
pages only; this is how the agent applies a change and how it is reverted.
"""

import html
import json
from datetime import datetime
from pathlib import Path

from . import cron
from .catalog import BY_SLUG, CATALOG, GROUP_TITLES

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://vip-ul.codes"
EXPERIMENTS_DIR = ROOT / "experiments"

# A fixed reference time keeps example run times stable between builds, so a
# rebuild never changes a page that no experiment touched.
EXAMPLE_FROM = datetime(2026, 1, 7, 10, 17)  # Wednesday

# The agent's action space. Every value here is a legitimate presentation
# choice; none of them adds facts that are not computed from the expression.
DEFAULT_KNOBS = {
    "title_style": "phrase_first",  # phrase_first | expr_first | question
    "meta_style": "summary",        # summary | runs
    "related_links": 6,             # 0 disables the related section
    "faq": False,                   # visible FAQ + FAQPage JSON-LD
    "breadcrumbs": True,            # visible breadcrumbs + BreadcrumbList JSON-LD
    "platforms": True,              # GitHub Actions / k8s / AWS / Spring / Quartz snippets
}

e = html.escape


# ─── Shared layout ───────────────────────────────────────────────────

def nav(active):
    def item(href, label, key):
        cls = "nav-link active" if key == active else "nav-link"
        return f'<li><a class="{cls}" href="{href}">{label}</a></li>'
    return f"""<nav class="navbar" id="navbar">
<div class="nav-container">
<a class="nav-logo" href="/"><span class="logo-bracket">&lt;</span><span class="logo-text">Vipul</span><span class="logo-dot">.</span><span class="logo-text-alt">codes</span><span class="logo-bracket">/&gt;</span></a>
<ul class="nav-menu" id="nav-menu">
{item("/", "Home", "home")}
{item("/cron/", "Cron reference", "cron")}
{item("/about.html", "About", "about")}
{item("/contact.html", "Contact", "contact")}
</ul>
<button aria-label="Toggle navigation" class="nav-toggle" id="nav-toggle"><span></span><span></span><span></span></button>
</div>
</nav>"""


FOOTER = """<footer class="footer">
<div class="container">
<div class="footer-bottom">
<p>© 2026 Vipul Codes</p>
<p class="footer-note">Run times on every page are computed from the expression, not typed by hand.</p>
</div>
</div>
</footer>
<script src="/js/main.js"></script>"""


def page(*, title, description, canonical, body, active, jsonld=(), og_type="article"):
    scripts = "\n".join(
        f'<script type="application/ld+json">{json.dumps(d, ensure_ascii=False)}</script>' for d in jsonld)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Vipul Codes">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/css/style.css">
{scripts}
</head>
<body>
{nav(active)}
{body}
{FOOTER}
</body>
</html>
"""


# ─── Cron page ───────────────────────────────────────────────────────

def page_title(entry, knobs):
    style = knobs["title_style"]
    if style == "expr_first":
        return f"{entry.expr} — Cron {entry.phrase.capitalize()}"
    if style == "question":
        return f"How to Run a Cron Job {entry.phrase.capitalize()} ({entry.expr})"
    title = f"Cron {entry.phrase.capitalize()}: {entry.expr} Explained"
    return title if len(title) <= 60 else title.removesuffix(" Explained")


def meta_description(entry, c, knobs):
    if knobs["meta_style"] == "runs":
        runs = c.next_runs(EXAMPLE_FROM, 3)
        times = ", ".join(r.strftime("%a %H:%M") for r in runs)
        return (f"Cron expression {entry.expr} runs {entry.phrase}. Example runs: {times}. "
                f"Copy-ready syntax for crontab, GitHub Actions, Kubernetes and AWS.")
    for desc in (f"{entry.expr} is the cron expression for {entry.phrase}. {entry.summary} "
                 f"Syntax for crontab, GitHub Actions, Kubernetes and AWS.",
                 f"{entry.expr} is the cron expression for {entry.phrase}. {entry.summary}",
                 f"{entry.expr}: cron {entry.phrase}, with example run times and syntax "
                 f"for crontab, GitHub Actions, Kubernetes and AWS."):
        if len(desc) <= 160:
            return desc
    return desc


def related(entry, n):
    same = [x for x in CATALOG if x.group == entry.group and x.slug != entry.slug]
    other = [x for x in CATALOG if x.group != entry.group]
    # Deterministic: neighbours in the catalog first, then other groups.
    idx = CATALOG.index(entry)
    same.sort(key=lambda x: abs(CATALOG.index(x) - idx))
    return (same + other)[:n]


def platform_section(entry, c):
    gap = cron.min_gap_minutes(c, EXAMPLE_FROM)
    gh_note = ""
    if gap is not None and gap < 5:
        gh_note = ("<p class=\"note\">GitHub Actions runs scheduled workflows at most once every "
                   "5 minutes, so this schedule will not run as often there as it does in crontab.</p>")
    parts = [f"""<h2>Use it on your platform</h2>
<h3>Linux crontab</h3>
<pre class="snippet"><code>{e(entry.expr)} /path/to/command</code></pre>
<p>Edit with <code>crontab -e</code>. Cron uses the server's local time zone.</p>
<h3>GitHub Actions</h3>
<pre class="snippet"><code>on:
  schedule:
    - cron: '{e(entry.expr)}'</code></pre>
<p>Schedules are evaluated in UTC, and runs can start late when GitHub is busy.</p>
{gh_note}
<h3>Kubernetes CronJob</h3>
<pre class="snippet"><code>apiVersion: batch/v1
kind: CronJob
metadata:
  name: my-job
spec:
  schedule: "{e(entry.expr)}"
  timeZone: "Etc/UTC"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: my-job
              image: busybox
              command: ["sh", "-c", "date"]
          restartPolicy: OnFailure</code></pre>
<p>Without <code>timeZone</code>, the schedule follows the time zone of the kube-controller-manager.</p>"""]
    aws = cron.to_aws(c)
    if aws:
        parts.append(f"""<h3>AWS EventBridge</h3>
<pre class="snippet"><code>{e(aws)}</code></pre>
<p>AWS uses six fields (the last is the year), needs <code>?</code> in either day-of-month or
day-of-week, and counts weekdays from 1 = Sunday, so names like <code>MON</code> are safer than numbers.
EventBridge rules run in UTC; EventBridge Scheduler lets you choose a time zone.</p>""")
    spring = cron.to_spring(c)
    if spring:
        parts.append(f"""<h3>Spring <code>@Scheduled</code></h3>
<pre class="snippet"><code>@Scheduled(cron = "{e(spring)}")</code></pre>
<p>Spring adds a seconds field at the start, so prepend <code>0</code> to run at second zero.</p>""")
    quartz = cron.to_quartz(c)
    if quartz:
        parts.append(f"""<h3>Quartz</h3>
<pre class="snippet"><code>{e(quartz)}</code></pre>
<p>Quartz also starts with seconds and, like AWS, requires <code>?</code> in one of the day fields.</p>""")
    return "\n".join(parts)


def faq_items(entry, c):
    runs = c.next_runs(EXAMPLE_FROM, 2)
    items = [
        (f"What is the cron expression for {entry.phrase}?",
         f"{entry.expr}. {entry.summary}"),
        ("Which time zone does this schedule use?",
         "Linux cron uses the server's local time zone. GitHub Actions uses UTC. Kubernetes uses "
         "spec.timeZone if set, otherwise the controller manager's time zone."),
    ]
    if len(runs) == 2:
        items.append((f"When would {entry.expr} run next after {EXAMPLE_FROM:%A %H:%M}?",
                      f"At {runs[0]:%A %d %b %H:%M}, then {runs[1]:%A %d %b %H:%M}."))
    return items


def render_cron_page(entry, knobs):
    c = cron.parse(entry.expr)
    url = f"{SITE}/cron/{entry.slug}/"
    title = page_title(entry, knobs)
    desc = meta_description(entry, c, knobs)

    rows = "\n".join(
        f"<tr><td><code>{e(f)}</code></td><td>{e(name)}</td><td>{e(cron.describe_field(f, i))}</td></tr>"
        for i, (f, (name, _, _)) in enumerate(zip(c.fields, cron.FIELDS)))
    runs = "\n".join(f"<li>{r:%a %d %b %Y, %H:%M}</li>" for r in c.next_runs(EXAMPLE_FROM, 6))
    freq = cron.frequency(c)
    gap_text = ""
    if freq["min_gap_min"] is not None:
        if freq["min_gap_min"] == freq["max_gap_min"]:
            gap_text = f"<li>Runs are always exactly {cron.human_minutes(freq['min_gap_min'])} apart.</li>"
        else:
            gap_text = (f"<li>The gap between runs varies from {cron.human_minutes(freq['min_gap_min'])} "
                        f"to {cron.human_minutes(freq['max_gap_min'])}.</li>")
    per_day = freq["runs_per_matching_day"]
    freq_html = f"""<h2>How often it runs</h2>
<ul class="runs-facts">
<li>{per_day:,} run{"s" if per_day != 1 else ""} on each day it is active.</li>
<li>Active on {freq["matching_days_per_year"]} of the 365 days in 2026, for {freq["runs_per_year"]:,} runs that year.</li>
{gap_text}
</ul>"""
    gotchas = cron.gotchas(c)
    gotcha_html = ""
    if gotchas:
        gotcha_html = "<h2>Watch out</h2>\n<ul class=\"gotchas\">" + "".join(
            f"<li>{g}</li>" for g in gotchas) + "</ul>"

    jsonld = [{
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": title,
        "description": desc,
        "url": url,
        "author": {"@type": "Person", "name": "Vipul Khokhar", "url": f"{SITE}/about.html"},
    }]

    crumbs = ""
    if knobs["breadcrumbs"]:
        crumbs = (f'<nav class="breadcrumbs" aria-label="Breadcrumb"><a href="/">Home</a> › '
                  f'<a href="/cron/">Cron reference</a> › <span>{e(entry.phrase)}</span></nav>')
        jsonld.append({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": "Cron reference", "item": f"{SITE}/cron/"},
                {"@type": "ListItem", "position": 3, "name": entry.phrase.capitalize(), "item": url},
            ],
        })

    faq_html = ""
    if knobs["faq"]:
        items = faq_items(entry, c)
        faq_html = "<h2>FAQ</h2>\n" + "\n".join(
            f"<h3>{e(q)}</h3>\n<p>{e(a)}</p>" for q, a in items)
        jsonld.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": q,
                            "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items],
        })

    related_html = ""
    if knobs["related_links"]:
        links = "".join(
            f'<li><a href="/cron/{x.slug}/">Cron {e(x.phrase)}</a> <code>{e(x.expr)}</code></li>'
            for x in related(entry, int(knobs["related_links"])))
        related_html = f"<h2>Related schedules</h2>\n<ul class=\"related\">{links}</ul>"

    body = f"""<header class="page-hero cron-hero">
<div class="hero-bg"><div class="hero-grid"></div><div class="hero-glow"></div></div>
<div class="hero-content">
{crumbs}
<h1>Cron {e(entry.phrase)}</h1>
<div class="cron-expr"><code>{e(entry.expr)}</code></div>
<p class="hero-subtitle">{e(entry.summary)}</p>
</div>
</header>
<main>
<article class="section cron-article">
<div class="container">
<h2>What each field means</h2>
<table class="fields">
<thead><tr><th>Field</th><th>Position</th><th>Meaning</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<h2>Example run times</h2>
<p>Starting from {EXAMPLE_FROM:%A %d %b %Y, %H:%M}, the next runs are:</p>
<ul class="runs">
{runs}
</ul>
{freq_html}
{gotcha_html}
{platform_section(entry, c) if knobs["platforms"] else ""}
{faq_html}
{related_html}
</div>
</article>
</main>"""
    return page(title=title, description=desc, canonical=url, body=body, active="cron", jsonld=jsonld)


# ─── Hub and homepage ────────────────────────────────────────────────

def grouped_list():
    out = []
    for group, gtitle in GROUP_TITLES.items():
        items = "".join(
            f'<li><a href="/cron/{x.slug}/"><span>{e(x.phrase.capitalize())}</span><code>{e(x.expr)}</code></a></li>'
            for x in CATALOG if x.group == group)
        out.append(f"<h2>{e(gtitle)}</h2>\n<ul class=\"cron-list\">{items}</ul>")
    return "\n".join(out)


def render_hub():
    body = f"""<header class="page-hero">
<div class="hero-bg"><div class="hero-grid"></div><div class="hero-glow"></div></div>
<div class="hero-content">
<h1>Cron expression reference</h1>
<p class="hero-subtitle">{len(CATALOG)} common schedules, each with a field-by-field breakdown,
computed example run times, and the exact syntax for crontab, GitHub Actions, Kubernetes, AWS, Spring and Quartz.</p>
</div>
</header>
<main><section class="section"><div class="container">
<h2>Cron syntax in one line</h2>
<pre class="snippet"><code>┌ minute (0–59)
│ ┌ hour (0–23)
│ │ ┌ day of month (1–31)
│ │ │ ┌ month (1–12 or JAN–DEC)
│ │ │ │ ┌ day of week (0–7 or SUN–SAT, 0 and 7 are Sunday)
* * * * *</code></pre>
{grouped_list()}
</div></section></main>"""
    return page(title="Cron Expression Reference: Common Schedules with Examples",
                description=f"{len(CATALOG)} common cron schedules explained with example run times and "
                            "syntax for crontab, GitHub Actions, Kubernetes, AWS EventBridge, Spring and Quartz.",
                canonical=f"{SITE}/cron/", body=body, active="cron", og_type="website",
                jsonld=[{"@context": "https://schema.org", "@type": "CollectionPage",
                         "name": "Cron expression reference", "url": f"{SITE}/cron/"}])


def render_home():
    popular = ["every-5-minutes", "every-15-minutes", "every-hour", "every-day-at-midnight",
               "every-weekday-at-9am", "every-monday", "every-month", "every-6-hours"]
    cards = "".join(
        f'<li><a href="/cron/{s}/"><span>{e(BY_SLUG[s].phrase.capitalize())}</span>'
        f'<code>{e(BY_SLUG[s].expr)}</code></a></li>' for s in popular)
    body = f"""<header class="hero">
<div class="hero-bg"><div class="hero-grid"></div><div class="hero-glow"></div></div>
<div class="hero-content">
<h1>Cron schedules,<br><span class="gradient-text">explained for every platform.</span></h1>
<p class="hero-subtitle">Find the expression you need, see exactly when it runs, and copy the
right syntax for crontab, GitHub Actions, Kubernetes, AWS, Spring or Quartz.</p>
<div class="hero-cta"><a class="btn btn-primary" href="/cron/">Browse all {len(CATALOG)} schedules</a></div>
</div>
</header>
<main><section class="section"><div class="container">
<h2>Popular schedules</h2>
<ul class="cron-list">{cards}</ul>
</div></section></main>"""
    return page(title="Vipul Codes — Cron Expressions Explained for Every Platform",
                description="Cron expressions explained with computed run times and copy-ready syntax "
                            "for crontab, GitHub Actions, Kubernetes, AWS EventBridge, Spring and Quartz.",
                canonical=f"{SITE}/", body=body, active="home", og_type="website",
                jsonld=[{"@context": "https://schema.org", "@type": "WebSite",
                         "name": "Vipul Codes", "url": f"{SITE}/"}])


# ─── Experiments → knobs ─────────────────────────────────────────────

def load_overrides():
    """slug -> knob overrides from running experiments (treatment pages only)."""
    overrides = {}
    if not EXPERIMENTS_DIR.exists():
        return overrides
    for path in sorted(EXPERIMENTS_DIR.glob("*.json")):
        exp = json.loads(path.read_text())
        if exp.get("status") != "running":
            continue
        unknown = set(exp["changes"]) - set(DEFAULT_KNOBS)
        if unknown:
            raise ValueError(f"{path.name}: unknown knobs {sorted(unknown)}")
        for slug in exp["treatment"]:
            if slug in overrides:
                raise ValueError(f"{slug} is in two running experiments")
            overrides[slug] = exp["changes"]
    return overrides


def site_knobs():
    """DEFAULT_KNOBS plus changes promoted by experiments that ended with "keep"."""
    config = ROOT / "generator" / "site_config.json"
    kept = json.loads(config.read_text()) if config.exists() else {}
    return {**DEFAULT_KNOBS, **kept}


def knobs_for(slug, overrides, base):
    return {**base, **overrides.get(slug, {})}


def build(root=ROOT):
    overrides = load_overrides()
    base = site_knobs()
    written = []

    def write(rel, text):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        written.append(rel)

    for entry in CATALOG:
        write(f"cron/{entry.slug}/index.html", render_cron_page(entry, knobs_for(entry.slug, overrides, base)))
    write("cron/index.html", render_hub())
    write("index.html", render_home())

    urls = ["/", "/cron/", "/about.html", "/contact.html"] + [f"/cron/{x.slug}/" for x in CATALOG]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
          + "".join(f"  <url><loc>{SITE}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    return written


if __name__ == "__main__":
    files = build()
    print(f"wrote {len(files)} files")
