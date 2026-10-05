# Baseline results (5 Oct 2026, before any ranking data)

## 1. Site: before vs after

Measured with `seo_agent/audit.py` and a duplicate-text check on the content pages.

| Measure | Before (Antigravity output) | After (cron reference) |
|---|---|---|
| Content pages | 3 | 46 (+ hub and homepage) |
| Technical issues found by audit | 9 (6 missing from sitemap, 3 orphan pages) | 0 |
| Text blocks repeated within the same page | 26% | 0% |
| Words unique to each page (topic keyword masked) | 10% | 58% (lowest page 50%) |
| Facts checked against a reference | none | run times, counts and gaps match `croniter` on every page (69 tests) |
| Made-up claims ("25K readers", "50+ articles", fake contact form) | yes | removed |

The old guides scored "88.8%, grade A" on Antigravity's own scorer while
repeating about a quarter of their paragraphs word for word. The scorer
measured surface features (length, headings, keyword density), and the
generator optimised for those features instead of for usefulness.

## 2. How sensitive the experiments are (power analysis)

Simulated with `python -m seo_agent power`. Setup: 46 pages split 23/23,
traffic varying across pages like real search traffic (log-normal), daily
counts Poisson, a site-wide trend, 28 days before, 7-day burn-in.

**Probability that a real effect is detected (p < 0.05):**

| Median clicks per page per day | +10% | +20% | +30% | +50% |
|---|---|---|---|---|
| 0.5, 28 days after | 15% | 35% | 63% | 93% |
| 0.5, 56 days after | 15% | 58% | 72% | 100% |
| 2, 28 days after | 27% | 77% | 98% | 100% |
| 2, 56 days after | 30% | 87% | 98% | 100% |
| 10, 28 days after | 75% | 100% | 100% | 100% |

When there was no real effect, the test wrongly reported one 5–7% of the time,
which is what a 5% significance level should give.

**Finding: the first version of the analysis was wrong.** It compared
absolute changes in clicks per page. Running the simulation showed that
detection got *worse* with longer experiments. With traffic spread unevenly
across pages, the natural drift of the few biggest pages swamped the signal.
Comparing each page's *relative* change (log ratio) fixed this: detection now
improves with more traffic and longer runs, as it should.

**What this means for the plan**
- While the site is new and clicks are rare, use **impressions** as the
  primary metric. Each page has many more impressions than clicks, which puts
  the test in the higher-power rows of the table.
- Only expect to detect effects of roughly +30% or more until traffic grows.
  Run experiments for 8 weeks rather than 4 while traffic is low.

## 3. Next

1. Merge [vipulkhokhar-17/BTP#1](https://github.com/vipulkhokhar-17/BTP/pull/1), verify the domain in Search Console, submit the sitemap.
2. Collect 4 weeks of baseline data (`python -m seo_agent fetch`).
3. First experiments (impressions as primary metric):
   - `faq-01`: visible FAQ + FAQPage markup on half the pages.
   - `links-00` (degradation test): remove related links on half the pages.
4. Add the LLM step that proposes the next experiment from audit and Search Console data.
