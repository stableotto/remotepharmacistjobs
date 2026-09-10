# CLAUDE.md

Operating guide for this repo. Keep it short. If something here is wrong, fix this file in the same PR.

## What this is

`remotepharmacistjobs.com` — a static site on **Cloudflare Pages**. **This is a live production site.**
A scheduled GitHub Action ingests a pre-aggregated job feed, filters for remote pharmacy roles, and
regenerates the site. Every listing links directly to the employer's ATS. We never proxy or gate applications.

We are extending it from a job board into a **career resource for pharmacists** with four surfaces over one dataset:

1. **Jobs** (exists) — the daily feed.
2. **Employer directory** (new) — durable, hand-curated pages per company. Does not go stale weekly.
3. **Licensure navigator** (new) — state-by-state reference for multi-state licensure.
4. **Salary** (partly exists) — currently derived from listings; adding user-contributed comp.

`Employer` is the spine. Jobs, salary records, and licensure requirements all hang off it.

## Stack — verified, do not guess

- **No Node, no `package.json`, no bundler, no template engine.** Python 3.12 + `string.Template`.
- **Runtime deps:** `requests`, `beautifulsoup4`. Everything else is stdlib.
- **No `wrangler.toml`.** Cloudflare Pages config lives in the dashboard; deploy is a `wrangler pages deploy`
  step inside `.github/workflows/update-jobs.yml`.
- **Templates are duplicated inline** in each generate script, not shared partials. Changing the nav or
  footer means editing every template that carries it (see Template Locations).

## Commands

```bash
# install
pip install requests beautifulsoup4

# build — full pipeline, in this exact order (see Build Pipeline Order)
python scripts/filter_jobs.py          # network: GitHub releases API
python scripts/scrape_details.py       # network: employer ATS pages (slow)
python scripts/generate_pages.py
python scripts/generate_category_pages.py
python scripts/generate_company_pages.py
python scripts/generate_salary_page.py
python scripts/generate_licensure_pages.py
python scripts/generate_homepage.py
python scripts/generate_sitemap.py

# regenerate only (no network) — safe locally, reads site/jobs.json
for s in generate_pages generate_category_pages generate_company_pages \
         generate_salary_page generate_licensure_pages generate_homepage \
         generate_sitemap; do
  python scripts/$s.py || break
done

# dev server
python -m http.server 8000 --directory site    # note: serves .html WITH extension; prod is extensionless

# typecheck / lint / test
# none configured. There is no test suite, no linter, no type checker.
# Verification is: regenerate, then `git diff` and read it.
```

**Regeneration is deterministic** apart from relative timestamps ("16h ago", sitemap `lastmod`). A clean
regenerate should produce a diff containing *only* those. Anything else is your change — read it.

## Architecture

- **Ingest** (`filter_jobs.py`) — downloads `all_jobs.json` from the latest
  `Feashliaa/job-board-aggregator` GitHub release. **There are no per-ATS adapters here.** The aggregator
  has already normalized Greenhouse/Workday/Lever; each job carries an `ats` field. We filter by title
  keyword + remote keyword, then merge against the previous `site/jobs.json` to preserve `first_seen` and
  scraped enrichment.
- **Enrich** (`scrape_details.py`) — fetches descriptions, salary, logos.
- **Generate** — static HTML written directly into `site/`, the publish directory. Generated output is
  committed to git.
- **Deploy** — Cloudflare Pages, from the daily workflow (6 AM UTC) or `workflow_dispatch`.

Dynamic behaviour runs in **Pages Functions** under `site/functions/`. Today that is exactly one file,
`_middleware.js`, which 301s `www.` to the apex. **There is no D1 or KV binding.** There is no server.
Anything that needs to persist user input needs D1 or KV, and needs to be justified before adding.

## Hard rules

**Design.** A design system already exists in `site/styles.css`. It uses **literal hex values, not CSS
custom properties** — there is no `:root` block and no token layer. Reuse existing classes. Do not
introduce new colors, fonts, spacing scales, CSS frameworks or utility libraries. Do not restyle existing
pages. New pages are assembled from existing primitives. If a genuinely new primitive is needed, ask first.

**Extensionless URLs (most important).** Cloudflare Pages 308-redirects `/about.html` → `/about`.
- Files are stored as `.html` on disk.
- **All canonical tags, `og:url`, sitemap entries and JSON-LD URLs MUST be extensionless.** Adding `.html`
  to metadata URLs breaks Google indexing (commit `1b7e48b` fixed this once already).
- Internal `<a href>` links currently use `.html` and eat a redirect on every hop. Emit extensionless
  hrefs; keep the on-disk `.html` filenames.

**URLs are permanent.** Never change or drop an existing job, company or category URL. Removing a page
requires a 410 or a redirect to a sensible parent, not a silent delete.
Employer and category pages are never deleted for lack of open jobs; they render a zero-state
instead. `site/_redirects` is generated by `generate_company_pages.py` and 301s every prior
company URL, including the 125 recorded in `data/legacy-company-slugs.json` that earlier runs
deleted outright. A page is removed from disk only once a redirect covers its URL — Cloudflare
Pages serves a static file in preference to a `_redirects` rule, so a leftover file would keep
the stale URL live. The generator refuses to leave a page uncovered.

**Direct listings only.** No recruiter or staffing-agency postings. No application gating, no email wall on
jobs, no "unlock this listing". This is the site's stated promise on `/about`.
> Note: jobs carry an `is_recruiter` boolean from the aggregator. Nothing reads it. 10 of 82 active jobs are
> flagged `true` (all Shields Health Solutions, a real specialty pharmacy — likely a false positive). Do not
> wire this into the filter without checking the flag's accuracy first.

**Google Analytics.** gtag.js `G-C0EB4GHJS3` loads via `<script async src="/analytics.js">` immediately
after `<head>` in every template. Keep it there when adding pages.

**Structured data.** Job pages must keep valid `JobPosting` JSON-LD (built in `generate_pages.py`, includes
`directApply: true`). Verify before and after any template change. Company pages currently emit `ItemList`;
employer pages should emit `Organization`.

**No client-side framework.** Static HTML. Progressive enhancement only — vanilla JS, no hydration, no SPA router.

**Never fabricate data.** Company metadata, licensure rules and comp figures are either sourced or absent.
An empty field is fine; an invented one is not. Every curated fact carries a source URL and a `last_verified` date.

## Build Pipeline Order

Scripts must run in this sequence; each consumes the previous one's output.

1. `filter_jobs.py` — aggregator → `site/jobs.json`
2. `scrape_details.py` — enrich with descriptions, salary, logos
3. `generate_pages.py` — `site/jobs/*.html`
4. `generate_category_pages.py` — `site/category/*.html` + `site/categories.html`
5. `generate_company_pages.py` — `site/companies/*.html`
6. `generate_salary_page.py` — `site/salary.html`
7. `generate_licensure_pages.py` — `site/licensure/` (reads `data/licensure/` + `data/employers/`)
8. `generate_homepage.py` — injects job list into `site/index.html` between markers
9. `generate_sitemap.py` — `site/sitemap.xml`

`scripts/employers.py` is a shared module, not a pipeline step. Steps 3–7 import it
to resolve an ingested job onto a curated employer record.

## Template Locations

All pages must stay consistent; nav and footer are copy-pasted across these.

- `site/index.html` — homepage shell (hand-written; job list injected between `<!-- JOBS_START -->` / `<!-- JOBS_END -->`)
- `site/about.html`, `site/post-a-job.html` — hand-written
- `scripts/generate_pages.py` — `PAGE_TEMPLATE`
- `scripts/generate_category_pages.py` — `CATEGORY_TEMPLATE` + `INDEX_TEMPLATE`
- `scripts/generate_company_pages.py` — `COMPANY_TEMPLATE` + `INDEX_TEMPLATE` + shared `NAV`/`FOOTER`
- `scripts/generate_licensure_pages.py` — `PAGE` + shared `NAV`/`FOOTER`
- `scripts/generate_salary_page.py` — inline f-string template

Nav and footer are still duplicated across the older templates. If you change them,
change all of them — a mismatch is easy to miss and every page carries one.

**After modifying any template, re-run that script.** Generated files under `site/jobs/`, `site/category/`,
`site/companies/` are committed.

## Data conventions

### `site/jobs.json`

```json
{ "last_updated": "ISO8601", "total_jobs": 82,
  "jobs": [{ "company", "company_slug", "title", "slug", "url", "absolute_url", "location", "ats",
             "expired", "salary", "description_html", "logo_url", "first_seen", "last_seen", ... }] }
```

`total_jobs` counts **active** jobs only; `jobs[]` also carries expired ones (159 records / 82 active today).
`expired: true` after 7 days missing from the aggregator; dropped entirely at 30 days. Expired job pages get
`<meta name="robots" content="noindex">` and are excluded from the sitemap.

### Slugs

```python
slug = re.sub(r'[^a-z0-9]+', '-', f"{company} {title}".lower()).strip('-')
slug = f"{slug}-{hashlib.md5(url.encode()).hexdigest()[:6]}"
```

**Never change job slug logic** — it would orphan every existing URL and break the Google index.
Employer slugs are stable and derived from the **canonical employer**, not the ATS token. Changing an
employer slug requires a redirect.

### Employer identity

`data/employers/*.json` is the curated store, one record per employer, hand-edited and
version-controlled. Ingest never overwrites it. `scripts/employers.py` resolves a job onto a
record through namespaced `ats_tokens`:

| ATS | Token | Where it comes from |
| --- | --- | --- |
| Workday | `workday:<tenant>` | host subdomain, e.g. `exactcare.wd1.myworkdayjobs.com` |
| Workday | `workday-site:<site>` | first path segment, skipped when generic (`external`, `careers`) |
| Greenhouse / Lever / Ashby | `greenhouse:<board>` etc | first path segment |
| Employer's own domain | `site:<label>` | e.g. `www.houserx.com` |
| Paylocity | `paylocity:<guid>` | the feed's `company_slug`; the URL has no employer id |
| any | `name:<slug>` | fallback on the ingested name |

Namespacing matters: a Greenhouse board named `bmc` and a Workday tenant named `bmc` are
different companies. Several employers legitimately hold multiple tokens (`precisionaq` and
`precisionmedicinegroup`; `exactcare` and `anewhealth_career_site`).

Generators call `E.decorate(jobs)` to swap the ingested name for the curated one at render
time. It mutates the in-memory dicts only — `site/jobs.json` and job slugs never move.

A token with no record resolves to nothing: the page renders generically, is noindexed, is
excluded from the directory and sitemap, and is written to `data/unmapped-employers.json`.
It is never given an invented name. Employers that are not pharmacist or pharmacy technician
roles carry `out_of_scope` with a reason, keeping their URL alive while staying out of the
directory.

### The original problem, for context

`clean_company_name()` in `filter_jobs.py` holds a hardcoded token → display-name map (~55 entries).
Anything unmapped is title-cased, so `/companies/` today lists **Akamerica, Flcancer, Wvumedicine,
Arkbluecross, Precisionaq, Bcbst, Houserx** and a company literally named **"Career Opportunities"**.
32 of 41 active employers render under a raw board token.

- Maintain an explicit alias map from board token → canonical employer.
- Curated employer records are the display source of truth; ingest never overwrites them.
- Multiple tokens may map to one employer (`precisionaq` and `precisionmedicinegroup` are the same org).
- A token with no mapping renders with a generic template and lands on a review queue. It does not get a
  fabricated name.

### Salary

Parses both hourly and annual, normalized to yearly (`hourly × 2080`, `monthly × 12`) in
`generate_salary_page.py`. Never mix units in an aggregate. Exclude ranges wider than ~4x as parse errors.
Show `n` alongside every average — a $207k "average" from 4 listings is noise, and presenting it as fact is
a defect.

### Other hardcoded maps

- Logos: domain map in `scrape_details.py` → `site/logos/`
- Categories: 18 keyword definitions in `generate_category_pages.py`
- Similar jobs: shared title keywords + company-match bonus, top 4
- Avatar fallback: hash-based pick from a 15-color palette when no logo

### Licensure data

`data/licensure/<state>.json`, one per US jurisdiction (50 + DC). `status: "sourced"` means
the board of pharmacy link is verified and the page is published; `status: "stub"` means it is
not, so the page renders noindex and is kept out of the sitemap and the comparison table.
Transfer requirements are quoted verbatim from NABP rather than paraphrased. Unsourced fees,
processing times and CE values are `null` and render as an em dash with a note that this means
unsourced, not zero.

## Licensure content — treat as high risk

People make real licensing and money decisions on this. Errors are worse than absence.

- Every state record links to that state's board of pharmacy as primary source.
- Every state record carries `last_verified`, rendered on the page.
- Fees and processing times are labeled as approximate and as-of-date.
- Framed as a starting point for research, never as legal advice.
- If a fact cannot be sourced to a board or NABP, omit it.

## Verification

Before claiming done:

- Every generate script runs clean; `git diff` shows only your intended change plus relative timestamps.
- Existing URLs still resolve — spot-check a job, a company, a category, `/salary`.
- New pages render correctly at mobile width using existing styles only.
- JSON-LD validates on a job page and an employer page.
- Sitemap includes new routes and excludes nothing that was there before.
- `git diff` contains no stray color, font or spacing changes in `site/styles.css`.

## Deployment

- Push to `main` does **not** deploy. Deploy happens in `.github/workflows/update-jobs.yml` (daily cron +
  `workflow_dispatch`), which commits regenerated output and then runs `wrangler pages deploy`.
- Manual: `wrangler pages deploy site/ --project-name=remotepharmacistjobs`
- Secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`
- **New generate scripts must be added to the workflow**, including their output paths in the `git add` line,
  or their output will never ship.

## Repo etiquette

- Small, reviewable commits. One concern each.
- Do not commit scraped payloads or `.env`.
- Do not add a dependency without saying why in the commit message.
- Do not reformat files you did not otherwise change.
