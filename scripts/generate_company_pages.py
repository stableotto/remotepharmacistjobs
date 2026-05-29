#!/usr/bin/env python3
"""Generate company pages that group jobs by employer."""

import json
import os
import html
import re
from string import Template
from collections import defaultdict

SITE_URL = "https://remotepharmacistjobs.com"

AVATAR_COLORS = [
    '#7c3aed', '#3b82f6', '#06b6d4', '#10b981', '#f59e0b',
    '#ef4444', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316',
    '#6366f1', '#84cc16', '#e11d48', '#0891b2', '#a855f7',
]


def hash_code(s):
    h = 0
    for c in s:
        h = ord(c) + ((h << 5) - h)
    return abs(h)


def get_avatar_color(company):
    return AVATAR_COLORS[hash_code(company) % len(AVATAR_COLORS)]


def build_job_row_html(job):
    company = html.escape(job.get("company", "Unknown"))
    title = html.escape(job.get("title", ""))
    location = html.escape(job.get("location", ""))
    slug = job.get("slug", "")
    detail_url = f"../jobs/{slug}.html" if slug else html.escape(job.get("url", "#"))
    color = get_avatar_color(company)
    initial = company[0].upper() if company else "?"
    logo_url = job.get("logo_url", "")

    salary_parts = []
    if job.get("salary"):
        salary_parts.append(f'<span class="meta-salary">{html.escape(job["salary"]["display"])}</span>')

    meta_parts = [company]
    if salary_parts:
        meta_parts.extend(salary_parts)
    meta_line = '<span class="meta-dot"> \u00b7 </span>'.join(meta_parts)

    if logo_url:
        if logo_url.startswith("logos/"):
            logo_url = f"../{logo_url}"
        logo_html = (
            f'<img class="job-logo" src="{html.escape(logo_url)}" alt="{company}" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<div class="job-logo-fallback" style="background-color:{color};display:none">{html.escape(initial)}</div>'
        )
    else:
        logo_html = f'<div class="job-logo-fallback" style="background-color:{color}">{html.escape(initial)}</div>'

    return f'''<a href="{html.escape(detail_url)}" class="job-row">
      <div class="job-row-left">
        <div class="job-logo-wrap">{logo_html}</div>
        <div class="job-row-info">
          <div class="job-row-title">{title}</div>
          <div class="job-row-meta">{meta_line}</div>
        </div>
      </div>
      <div class="job-row-right">
        <div class="job-row-location">{location}</div>
      </div>
    </a>'''


def build_logo_html(company, logo_url, size="large"):
    color = get_avatar_color(company)
    initial = html.escape(company[0].upper()) if company else "?"

    if size == "large":
        cls_img = "company-hero-logo"
        cls_fb = "company-hero-logo-fallback"
        if logo_url and logo_url.startswith("logos/"):
            logo_url = f"../{logo_url}"
    else:
        cls_img = "job-logo"
        cls_fb = "job-logo-fallback"

    if logo_url:
        return (
            f'<img class="{cls_img}" src="{html.escape(logo_url)}" alt="{html.escape(company)}" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<div class="{cls_fb}" style="background-color:{color};display:none">{initial}</div>'
        )
    return f'<div class="{cls_fb}" style="background-color:{color}">{initial}</div>'


COMPANY_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="/analytics.js"></script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Remote Jobs at ${company} | Remote Pharmacist Jobs</title>
  <meta name="description" content="${meta_description}">
  <meta property="og:title" content="Remote Jobs at ${company} | Remote Pharmacist Jobs">
  <meta property="og:description" content="${meta_description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="${canonical_url}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="Remote Jobs at ${company}">
  <meta name="twitter:description" content="${meta_description}">
  <link rel="canonical" href="${canonical_url}">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link href="https://fonts.cdnfonts.com/css/geist" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
  <script type="application/ld+json">
  ${json_ld}
  </script>
</head>
<body>
  <nav class="site-nav">
    <div class="site-nav-inner">
      <a href="../" class="site-nav-logo">
        <img src="../logo.svg" alt="Remote Pharmacist Jobs" height="32">
      </a>
      <button class="nav-toggle" aria-label="Menu" onclick="this.nextElementSibling.classList.toggle('open')">
        <span></span><span></span><span></span>
      </button>
      <div class="site-nav-links">
        <a href="../">Jobs</a>
        <a href="../categories.html">Categories</a>
        <a href="../about.html">About</a>
        <a href="../post-a-job.html" class="nav-cta">Post a Job</a>
      </div>
    </div>
  </nav>

  <div class="container">
    <nav class="breadcrumb">
      <a href="../">Home</a> &rsaquo; <a href="../companies/">Companies</a> &rsaquo; <span>${company}</span>
    </nav>

    <div class="company-hero">
      ${logo_html}
      <div class="company-hero-text">
        <h1>Remote Jobs at ${company}</h1>
        <p>${intro}</p>
        <span class="category-count">${count} open positions</span>
      </div>
    </div>

    <div class="jobs-list">
      ${job_rows}
    </div>

    <div class="browse-categories">
      <h2>Browse other companies hiring remotely</h2>
      <div class="category-links">
        ${other_companies}
      </div>
    </div>
  </div>

  <footer class="site-footer">
    <div class="site-footer-inner">
      <div class="footer-col">
        <h4>Remote Pharmacist Jobs</h4>
        <p>Direct listings only. No recruiters, no middlemen.</p>
      </div>
      <div class="footer-col">
        <h4>Navigate</h4>
        <a href="../">Jobs</a>
        <a href="../categories.html">Categories</a>
        <a href="../about.html">About</a>
        <a href="../post-a-job.html">Post a Job</a>
      </div>
    </div>
  </footer>
</body>
</html>
""")

INDEX_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="/analytics.js"></script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Companies Hiring Remote Pharmacists | Remote Pharmacist Jobs</title>
  <meta name="description" content="Browse companies hiring remote pharmacists. See all open remote pharmacy positions by employer. Direct listings only — no recruiters.">
  <meta property="og:title" content="Companies Hiring Remote Pharmacists">
  <meta property="og:description" content="Browse companies hiring remote pharmacists. Direct employer listings only.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://remotepharmacistjobs.com/companies">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="https://remotepharmacistjobs.com/companies">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link href="https://fonts.cdnfonts.com/css/geist" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  <nav class="site-nav">
    <div class="site-nav-inner">
      <a href="../" class="site-nav-logo">
        <img src="../logo.svg" alt="Remote Pharmacist Jobs" height="32">
      </a>
      <button class="nav-toggle" aria-label="Menu" onclick="this.nextElementSibling.classList.toggle('open')">
        <span></span><span></span><span></span>
      </button>
      <div class="site-nav-links">
        <a href="../">Jobs</a>
        <a href="../categories.html">Categories</a>
        <a href="../about.html">About</a>
        <a href="../post-a-job.html" class="nav-cta">Post a Job</a>
      </div>
    </div>
  </nav>

  <div class="container">
    <div class="category-hero">
      <h1>Companies Hiring Remote Pharmacists</h1>
      <p>Browse all employers with open remote pharmacy positions. Every listing links directly to the company's career page.</p>
    </div>

    <div class="category-grid">
      ${company_cards}
    </div>
  </div>

  <footer class="site-footer">
    <div class="site-footer-inner">
      <div class="footer-col">
        <h4>Remote Pharmacist Jobs</h4>
        <p>Direct listings only. No recruiters, no middlemen.</p>
      </div>
      <div class="footer-col">
        <h4>Navigate</h4>
        <a href="../">Jobs</a>
        <a href="../categories.html">Categories</a>
        <a href="../about.html">About</a>
        <a href="../post-a-job.html">Post a Job</a>
      </div>
    </div>
  </footer>
</body>
</html>
""")


def slugify(name):
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    return s.strip('-')


def main():
    with open("site/jobs.json") as f:
        data = json.load(f)

    # Only show active (non-expired) jobs
    jobs = [j for j in data.get("jobs", []) if not j.get("expired")]

    # Group by company
    by_company = defaultdict(list)
    for job in jobs:
        company = job.get("company", "Unknown")
        by_company[company].append(job)

    os.makedirs("site/companies", exist_ok=True)

    # Build company data sorted by job count (most first)
    company_data = []
    for company, company_jobs in sorted(by_company.items(), key=lambda x: (-len(x[1]), x[0])):
        # Always use slugified company name for clean URLs
        slug = slugify(company)
        logo_url = company_jobs[0].get("logo_url", "") if company_jobs else ""
        company_data.append({
            "name": company,
            "slug": slug,
            "jobs": company_jobs,
            "count": len(company_jobs),
            "logo_url": logo_url,
        })

    # Generate each company page
    for comp in company_data:
        job_rows = "\n".join(build_job_row_html(j) for j in comp["jobs"])

        other_companies = [c for c in company_data if c["slug"] != comp["slug"]][:12]
        other_html = "\n".join(
            f'<a href="{c["slug"]}.html" class="category-link">{html.escape(c["name"])} <span>({c["count"]})</span></a>'
            for c in other_companies
        )

        meta_desc = f"Browse {comp['count']} remote pharmacy job{'s' if comp['count'] != 1 else ''} at {comp['name']}. Apply directly — no recruiters, no middlemen."
        intro = f"View all open remote pharmacy positions at {comp['name']}. Every listing links directly to {comp['name']}'s career page."

        json_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": f"Remote Jobs at {comp['name']}",
            "description": meta_desc,
            "numberOfItems": comp["count"],
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "url": f"{SITE_URL}/jobs/{j['slug']}" if j.get("slug") else j.get("url", ""),
                    "name": j.get("title", ""),
                }
                for i, j in enumerate(comp["jobs"])
            ],
        }, indent=2)

        logo_html = build_logo_html(comp["name"], comp["logo_url"], "large")

        page_html = COMPANY_TEMPLATE.substitute(
            company=html.escape(comp["name"]),
            meta_description=html.escape(meta_desc),
            canonical_url=f"{SITE_URL}/companies/{comp['slug']}",
            logo_html=logo_html,
            intro=html.escape(intro),
            count=comp["count"],
            job_rows=job_rows,
            other_companies=other_html,
            json_ld=json_ld,
        )

        with open(f"site/companies/{comp['slug']}.html", "w") as f:
            f.write(page_html)

    # Generate company index page
    cards_html = "\n".join(
        f'<a href="{c["slug"]}.html" class="category-card">'
        f'<h3>{html.escape(c["name"])}</h3>'
        f'<p>View remote pharmacy positions at {html.escape(c["name"])}.</p>'
        f'<span class="category-count">{c["count"]} open positions</span>'
        f'</a>'
        for c in company_data
    )

    index_html = INDEX_TEMPLATE.substitute(company_cards=cards_html)
    with open("site/companies/index.html", "w") as f:
        f.write(index_html)

    print(f"Generated {len(company_data)} company pages + index in site/companies/")
    for c in company_data:
        print(f"  {c['name']}: {c['count']} jobs")


if __name__ == "__main__":
    main()
