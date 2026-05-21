# Remote Pharmacist Jobs - Project Guide

## What This Is
A static job board for remote pharmacy jobs. Deployed to **Cloudflare Pages** at `remotepharmacistjobs.com`. Updated daily via GitHub Actions. **This is a live production site.**

## Architecture
- **Static HTML site** in `site/` — no framework, no build tool, just HTML/CSS/JS
- **Python scripts** in `scripts/` generate pages from `site/jobs.json`
- **Cloudflare Pages** serves `site/` directory as the live site
- **GitHub Actions** (`.github/workflows/update-jobs.yml`) runs daily at 6 AM UTC

## Critical Rules - DO NOT BREAK PRODUCTION

### Extensionless URLs (Most Important)
Cloudflare Pages auto-redirects `.html` to extensionless URLs (308 redirect).
- Files are stored as `.html` on disk
- **All canonical tags, og:url, sitemap entries, and JSON-LD URLs MUST be extensionless** (no `.html`)
- Internal `<a href>` links CAN use `.html` (resolved before redirect)
- If you add `.html` to metadata URLs, Google indexing breaks (commit 1b7e48b fixed this)

### Google Analytics
- gtag.js with ID `G-C0EB4GHJS3` is in every page template
- Placed immediately after `<head>` in: `index.html`, all 4 generate scripts (7 templates total)

### Build Pipeline Order (scripts must run in this sequence)
1. `filter_jobs.py` — downloads from job-board-aggregator, filters pharmacy jobs → `site/jobs.json`
2. `scrape_details.py` — enriches with descriptions, salary, logos
3. `generate_pages.py` — individual job pages → `site/jobs/*.html`
4. `generate_category_pages.py` — category pages → `site/category/*.html` + `site/categories.html`
5. `generate_company_pages.py` — company pages → `site/companies/*.html`
6. `generate_salary_page.py` — salary guide → `site/salary.html`
7. `generate_sitemap.py` — SEO sitemap → `site/sitemap.xml`

### Template Locations (all pages must stay consistent)
- `site/index.html` — homepage (hand-written, not generated)
- `site/about.html` — about page (hand-written)
- `site/post-a-job.html` — job posting info (hand-written)
- `scripts/generate_pages.py` — `PAGE_TEMPLATE` (job detail pages)
- `scripts/generate_category_pages.py` — `CATEGORY_TEMPLATE` + `INDEX_TEMPLATE`
- `scripts/generate_company_pages.py` — `COMPANY_TEMPLATE` + `INDEX_TEMPLATE`
- `scripts/generate_salary_page.py` — inline f-string template

### jobs.json Structure
```json
{
  "last_updated": "ISO timestamp",
  "total_jobs": 104,
  "jobs": [{ "company", "title", "slug", "url", "expired", "salary", "description_html", ... }]
}
```
- `slug` = `{company}-{title}-{md5(url)[:6]}` — deterministic, used for filenames and URLs
- `expired: true` after 7 days missing from aggregator; retained 30 days total
- Expired jobs get `<meta name="robots" content="noindex">`

### Slug Generation
```python
slug = re.sub(r'[^a-z0-9]+', '-', f"{company} {title}".lower()).strip('-')
slug = f"{slug}-{hashlib.md5(url.encode()).hexdigest()[:6]}"
```
**Never change slug logic** — it would orphan all existing URLs and break Google index.

## Key Patterns
- Company names: hardcoded 252-line mapping in `filter_jobs.py` (slug → display name)
- Logos: hardcoded domain map in `scrape_details.py`, saved to `site/logos/`
- Categories: 18 keyword-based definitions in `generate_category_pages.py` (lines 12-178)
- Salary extraction: regex-based from description text, normalized to yearly
- Similar jobs: scored by shared title keywords + company match bonus, top 4 shown
- Avatar fallback: hash-based color from 15-color palette when no logo

## Deployment
- Push to `main` triggers nothing automatically (deploy is via GitHub Actions workflow)
- Manual deploy: `wrangler pages deploy site/ --project-name=remotepharmacistjobs`
- Secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`

## After Modifying Templates
If you change any generate script template, **you must re-run those scripts** to update the generated HTML files. The generated files in `site/jobs/`, `site/category/`, `site/companies/` are committed to git.
