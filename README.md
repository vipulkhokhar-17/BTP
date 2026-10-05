# vip-ul.codes: an SEO experiment agent

The goal: an agent that changes a website, measures what that does to Google
rankings, and keeps the changes that help. The test site is
[vip-ul.codes](https://vip-ul.codes), a cron expression reference.

## Why cron expressions

- **Real search demand with real competitors.** Searches like "cron every 5 minutes"
  or "github actions cron every monday" have steady volume, and established
  sites (crontab.guru, Cronitor, Stack Overflow) compete for them.
- **Long tail.** Platform-specific searches have little competition, so a new
  domain can realistically get impressions within weeks.
- **Pages are uniform.** Every page has the same layout, so pages can be split
  into control and treatment groups for experiments.
- **Content is computed, not invented.** Field meanings, example run times,
  gotchas and platform syntax are generated from the expression by
  `generator/cron.py`. The tests check its run times against `croniter`.

## Layout

| Path | What |
|---|---|
| `generator/catalog.py` | The schedules the site publishes (one page each) |
| `generator/cron.py` | Cron parser, run-time calculator, platform translations, gotcha detection |
| `generator/build.py` | Builds `cron/*/index.html`, `index.html`, `sitemap.xml`, `robots.txt`; defines the **knobs** experiments can change |
| `seo_agent/audit.py` | On-page audit: titles, meta, canonical, h1, JSON-LD, internal links, orphans, sitemap |
| `seo_agent/gsc.py` | Google Search Console export (clicks, impressions, CTR, position per page per day) |
| `seo_agent/experiment.py` | Matched control/treatment split, start/stop, keep/revert |
| `seo_agent/analyze.py` | Difference-in-differences effect + permutation-test p-value |
| `experiments/` | One JSON file per experiment (the agent's log) |
| `reports/` | Generated experiment reports |

`about.html`, `contact.html`, `css/` and `js/` are hand-written. Everything under
`cron/`, plus `index.html`, `sitemap.xml` and `robots.txt`, is generated. Don't
edit those by hand.

## Experiment loop

```bash
pip install -r requirements.txt
python -m generator.build          # build the site
python -m seo_agent audit          # baseline: 0 issues expected
python -m pytest -q                # engine + analysis tests

# 1. Collect a baseline (≥ 4 weeks of Search Console data)
python -m seo_agent fetch --start 2026-10-10

# 2. Create an experiment: half the pages get the change
python -m seo_agent new faq-01 \
  --hypothesis "A visible FAQ with FAQPage markup increases clicks" \
  --change faq=true
python -m seo_agent start faq-01
python -m generator.build && git commit -am "Start faq-01" && git push

# 3. After ~5 weeks (1 week of recrawl + 4 weeks of measurement)
python -m seo_agent fetch --start 2026-10-10
python -m seo_agent analyze faq-01     # writes reports/faq-01.md

# 4. Keep (applies to every page) or revert
python -m seo_agent stop faq-01 keep
python -m generator.build && git commit -am "End faq-01: keep" && git push
```

### Knobs (the agent's action space)

| Knob | Values | Hypothesis it tests |
|---|---|---|
| `title_style` | `phrase_first`, `expr_first`, `question` | Title wording changes CTR |
| `meta_style` | `summary`, `runs` | Snippet text changes CTR |
| `related_links` | 0–N | Internal links affect crawling and ranking (0 = deliberate degradation test) |
| `faq` | true/false | FAQ content and markup affect clicks |
| `breadcrumbs` | true/false | Breadcrumb markup changes the result snippet |
| `platforms` | true/false | Platform-specific sections earn long-tail impressions (false = degradation test) |

Every knob only changes how true, computed information is presented. No knob
adds fake dates, fake stats, hidden text, or content shown only to crawlers.

### Reading results

- Clicks and impressions are per page per day. For position, lower is better.
- **DiD effect** = (treatment after − before) − (control after − before). Site-wide
  movement such as Google updates or the domain ageing cancels out.
- **p-value** comes from a permutation test: the share of 5,000 random page splits
  that produce an effect as large as the real one.
- "Degraded" is a valid result. Revert the change and write up why it hurt.

## Search Console setup

See the docstring at the top of `seo_agent/gsc.py`. You need to verify the domain
and give a service account read access.
