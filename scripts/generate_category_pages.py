#!/usr/bin/env python3
"""Generate programmatic SEO category pages that group jobs by keyword."""

import json
import os
import html
import re
from string import Template

SITE_URL = "https://remotepharmacistjobs.com"

CATEGORIES = [
    {
        "name": "Pharmacy Technician",
        "slug": "remote-pharmacy-technician-jobs",
        "keywords": ["pharmacy technician", "pharmacy tech"],
        "h1": "Remote Pharmacy Technician Jobs",
        "meta_description": "Browse remote pharmacy technician jobs updated daily. Direct listings only \u2014 every link goes straight to the employer's career page. No recruiters.",
        "intro": "Find remote pharmacy technician positions from top employers. Every listing links directly to the company\u2019s career page \u2014 no recruiters, no middlemen.",
    },
    {
        "name": "Clinical Pharmacist",
        "slug": "remote-clinical-pharmacist-jobs",
        "keywords": ["clinical pharmacist"],
        "h1": "Remote Clinical Pharmacist Jobs",
        "meta_description": "Browse remote clinical pharmacist jobs updated daily. Direct employer listings for clinical pharmacy roles. No recruiter middlemen.",
        "intro": "Find remote clinical pharmacist positions including medication therapy management, clinical consulting, and patient care roles. Every listing links directly to the employer.",
    },
    {
        "name": "Ambulatory Care Pharmacist",
        "slug": "remote-ambulatory-care-pharmacist-jobs",
        "keywords": ["ambulatory care pharmacist", "ambulatory pharmacist", "ambulatory clinical pharmacist"],
        "h1": "Remote Ambulatory Care Pharmacist Jobs",
        "meta_description": "Browse remote ambulatory care pharmacist jobs. Direct employer listings for ambulatory pharmacy positions. Updated daily.",
        "intro": "Find remote ambulatory care pharmacist roles focused on outpatient medication management and patient care. Direct links to employer career pages.",
    },
    {
        "name": "Pharmacovigilance",
        "slug": "remote-pharmacovigilance-jobs",
        "keywords": ["pharmacovigilance", "drug safety"],
        "h1": "Remote Pharmacovigilance Jobs",
        "meta_description": "Browse remote pharmacovigilance and drug safety jobs. Direct listings from pharmaceutical and healthcare companies. Updated daily.",
        "intro": "Find remote pharmacovigilance and drug safety positions. Monitor adverse events, ensure regulatory compliance, and protect patient safety \u2014 all from home.",
    },
    {
        "name": "Pharmacy Director",
        "slug": "remote-pharmacy-director-jobs",
        "keywords": ["director"],
        "title_must_also_contain": ["pharmacy", "pharmacist", "pharmaceutical", "pharmacovigilance"],
        "h1": "Remote Pharmacy Director Jobs",
        "meta_description": "Browse remote pharmacy director and senior pharmacy leadership jobs. Direct employer listings updated daily. No recruiter middlemen.",
        "intro": "Find remote pharmacy director and leadership positions including director of pharmacy operations, clinical pharmacy directors, and pharmacy analytics leadership roles.",
    },
    {
        "name": "Prior Authorization Pharmacist",
        "slug": "remote-prior-authorization-pharmacist-jobs",
        "keywords": ["prior authorization"],
        "h1": "Remote Prior Authorization Pharmacist Jobs",
        "meta_description": "Browse remote prior authorization pharmacist and pharmacy technician jobs. Direct employer listings updated daily.",
        "intro": "Find remote prior authorization roles for pharmacists and pharmacy technicians. Review medication requests, apply clinical criteria, and support patient access to care.",
    },
    {
        "name": "Bilingual Pharmacist",
        "slug": "remote-bilingual-pharmacist-jobs",
        "keywords": ["bilingual"],
        "h1": "Remote Bilingual Pharmacist Jobs",
        "meta_description": "Browse remote bilingual pharmacist jobs. Spanish-English and other language pharmacy positions. Direct employer listings.",
        "intro": "Find remote bilingual pharmacist and pharmacy technician positions. Serve diverse patient populations with your language skills. Direct links to employer career pages.",
    },
    {
        "name": "Pharmacy Manager",
        "slug": "remote-pharmacy-manager-jobs",
        "keywords": ["manager", "supervisor", "lead"],
        "title_must_also_contain": ["pharmacy", "pharmacist", "pharmaceutical", "pharmacovigilance"],
        "h1": "Remote Pharmacy Manager Jobs",
        "meta_description": "Browse remote pharmacy manager, supervisor, and lead pharmacist jobs. Direct employer listings updated daily.",
        "intro": "Find remote pharmacy management roles including pharmacy managers, supervisors, team leads, and senior individual contributors. Direct links to employer career pages.",
    },
    # ── "Work from home" synonym pages (high volume, 1K–10K) ──
    {
        "name": "Work From Home Pharmacist",
        "slug": "work-from-home-pharmacist-jobs",
        "match_all": True,
        "match_all_filter": "pharmacist",
        "h1": "Work From Home Pharmacist Jobs",
        "meta_description": "Browse work from home pharmacist jobs updated daily. Direct employer listings only — no recruiters, no staffing agencies. Apply straight to the company.",
        "intro": "Find work from home pharmacist positions from top employers. Every listing links directly to the company's career page — no recruiters, no middlemen.",
    },
    {
        "name": "Work From Home Pharmacy Tech",
        "slug": "work-from-home-pharmacy-tech-jobs",
        "match_all": True,
        "match_all_filter": "tech",
        "h1": "Work From Home Pharmacy Tech Jobs",
        "meta_description": "Browse work from home pharmacy technician jobs updated daily. Direct employer listings only — apply straight to the hiring company.",
        "intro": "Find work from home pharmacy technician positions. Every listing links directly to the employer's career page — no recruiters, no middlemen.",
    },
    {
        "name": "Remote PharmD",
        "slug": "remote-pharmd-jobs",
        "match_all": True,
        "match_all_filter": "pharmacist",
        "h1": "Remote PharmD Jobs",
        "meta_description": "Browse remote PharmD jobs updated daily. Clinical, consulting, and industry positions for Doctor of Pharmacy professionals. Direct employer listings.",
        "intro": "Find remote positions for PharmD professionals including clinical pharmacist, consulting, MTM, pharmacovigilance, and pharmacy leadership roles. Direct links to employer career pages.",
    },
    {
        "name": "Online Pharmacy Tech",
        "slug": "online-pharmacy-tech-jobs",
        "match_all": True,
        "match_all_filter": "tech",
        "h1": "Online Pharmacy Tech Jobs",
        "meta_description": "Browse online pharmacy technician jobs you can do from home. Updated daily with direct employer listings only — no recruiters.",
        "intro": "Find online pharmacy technician jobs from top employers. Work remotely as a pharmacy tech — every listing links directly to the company's career page.",
    },
    {
        "name": "Virtual Pharmacist",
        "slug": "virtual-pharmacist-jobs",
        "match_all": True,
        "h1": "Virtual Pharmacist Jobs",
        "meta_description": "Browse virtual pharmacist jobs updated daily. Telepharmacy, remote clinical, and work from home pharmacy positions. Direct employer listings only.",
        "intro": "Find virtual pharmacist and telepharmacy positions from top employers. Every listing links directly to the company's career page — no recruiters, no middlemen.",
    },
    # ── Niche categories (medium volume, 100–1K) ──
    {
        "name": "MTM Pharmacist",
        "slug": "remote-mtm-pharmacist-jobs",
        "keywords": ["mtm", "medication therapy management", "medication management"],
        "search_description": True,
        "h1": "Remote MTM Pharmacist Jobs",
        "meta_description": "Browse remote MTM pharmacist jobs. Medication therapy management positions updated daily. Direct employer listings only.",
        "intro": "Find remote medication therapy management (MTM) pharmacist positions. Conduct comprehensive medication reviews and optimize patient outcomes — all from home.",
    },
    {
        "name": "Remote Specialty Pharmacy",
        "slug": "remote-specialty-pharmacy-jobs",
        "keywords": ["specialty pharmacy", "specialty pharmacist"],
        "search_description": True,
        "h1": "Remote Specialty Pharmacy Jobs",
        "meta_description": "Browse remote specialty pharmacy jobs updated daily. Specialty pharmacist and technician positions. Direct employer listings.",
        "intro": "Find remote specialty pharmacy positions including specialty pharmacists, technicians, and coordinators. Direct links to employer career pages.",
    },
    {
        "name": "Part-Time Remote Pharmacist",
        "slug": "part-time-remote-pharmacist-jobs",
        "keywords": ["part-time", "part time", "per diem", "prn"],
        "h1": "Part-Time Remote Pharmacist Jobs",
        "meta_description": "Browse part-time remote pharmacist jobs. PRN, per diem, and flexible pharmacy positions updated daily. Direct employer listings.",
        "intro": "Find part-time, PRN, and per diem remote pharmacist positions. Flexible schedules with direct links to employer career pages — no recruiters.",
    },
    {
        "name": "Remote Verification Pharmacist",
        "slug": "remote-verification-pharmacist-jobs",
        "keywords": ["verification", "order entry", "order review"],
        "search_description": True,
        "h1": "Remote Verification Pharmacist Jobs",
        "meta_description": "Browse remote verification pharmacist jobs. Prescription verification and order entry positions updated daily. Direct employer listings.",
        "intro": "Find remote prescription verification and order entry pharmacist positions. Review and verify medication orders from home. Direct links to employer career pages.",
    },
    {
        "name": "Remote Oncology Pharmacist",
        "slug": "remote-oncology-pharmacist-jobs",
        "keywords": ["oncology", "oncologist", "cancer"],
        "search_description": True,
        "h1": "Remote Oncology Pharmacist Jobs",
        "meta_description": "Browse remote oncology pharmacist jobs. Cancer care and oncology pharmacy positions updated daily. Direct employer listings.",
        "intro": "Find remote oncology pharmacist positions in cancer care, clinical oncology, and hematology-oncology pharmacy. Direct links to employer career pages.",
    },
    {
        "name": "Remote Order Entry Pharmacist",
        "slug": "remote-order-entry-pharmacist-jobs",
        "keywords": ["order entry", "data entry", "order processing"],
        "search_description": True,
        "h1": "Remote Order Entry Pharmacist Jobs",
        "meta_description": "Browse remote order entry pharmacist jobs. Prescription processing and order entry positions updated daily. Direct employer listings.",
        "intro": "Find remote order entry and prescription processing pharmacist positions. Process and verify medication orders from home. Direct links to employer career pages.",
    },
]

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


def matches_category(job, cat):
    title = job.get("title", "").lower()

    # "match_all" pages show all jobs (or filtered subset) — synonym pages like WFH, virtual
    if cat.get("match_all"):
        filt = cat.get("match_all_filter", "")
        if filt:
            return filt in title
        return True

    keywords = cat.get("keywords", [])
    matched = any(kw in title for kw in keywords)

    # Optionally also search the job description for keyword matches
    if not matched and cat.get("search_description"):
        desc = job.get("description_html", "").lower()
        matched = any(kw in desc for kw in keywords)

    if not matched:
        return False
    # If category requires secondary keyword, check that too
    must_also = cat.get("title_must_also_contain")
    if must_also:
        return any(kw in title for kw in must_also)
    return True


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
        # Fix relative path for category pages (they're in site/category/)
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


CATEGORY_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} | Remote Pharmacist Jobs</title>
  <meta name="description" content="${meta_description}">
  <meta property="og:title" content="${title} | Remote Pharmacist Jobs">
  <meta property="og:description" content="${meta_description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="${canonical_url}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="${title}">
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
        <a href="../categories.html" class="active">Categories</a>
        <a href="../about.html">About</a>
        <a href="../post-a-job.html" class="nav-cta">Post a Job</a>
      </div>
    </div>
  </nav>

  <div class="container">
    <nav class="breadcrumb">
      <a href="../">Home</a> &rsaquo; <a href="../categories.html">Categories</a> &rsaquo; <span>${name}</span>
    </nav>

    <div class="category-hero">
      <h1>${h1}</h1>
      <p>${intro}</p>
      <span class="category-count">${count} jobs</span>
    </div>

    <div class="jobs-list">
      ${job_rows}
    </div>

    <div class="browse-categories">
      <h2>Browse other categories</h2>
      <div class="category-links">
        ${other_categories}
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
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Browse Remote Pharmacist Job Categories | Remote Pharmacist Jobs</title>
  <meta name="description" content="Browse remote pharmacist jobs by category. Clinical pharmacist, pharmacy technician, pharmacovigilance, and more. Direct employer listings only.">
  <meta property="og:title" content="Browse Remote Pharmacist Job Categories">
  <meta property="og:description" content="Browse remote pharmacist jobs by category. Direct employer listings only.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://remotepharmacistjobs.com/categories.html">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="https://remotepharmacistjobs.com/categories.html">
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link href="https://fonts.cdnfonts.com/css/geist" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <nav class="site-nav">
    <div class="site-nav-inner">
      <a href="/" class="site-nav-logo">
        <img src="logo.svg" alt="Remote Pharmacist Jobs" height="32">
      </a>
      <button class="nav-toggle" aria-label="Menu" onclick="this.nextElementSibling.classList.toggle('open')">
        <span></span><span></span><span></span>
      </button>
      <div class="site-nav-links">
        <a href="/">Jobs</a>
        <a href="categories.html" class="active">Categories</a>
        <a href="about.html">About</a>
        <a href="post-a-job.html" class="nav-cta">Post a Job</a>
      </div>
    </div>
  </nav>

  <div class="container">
    <div class="category-hero">
      <h1>Browse by Category</h1>
      <p>Find remote pharmacist jobs organized by specialty and role type.</p>
    </div>

    <div class="category-grid">
      ${category_cards}
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
        <a href="/">Jobs</a>
        <a href="categories.html">Categories</a>
        <a href="about.html">About</a>
        <a href="post-a-job.html">Post a Job</a>
      </div>
    </div>
  </footer>
</body>
</html>
""")


def main():
    with open("site/jobs.json") as f:
        data = json.load(f)
    # Only show active (non-expired) jobs on category pages
    jobs = [j for j in data.get("jobs", []) if not j.get("expired")]

    os.makedirs("site/category", exist_ok=True)

    # Build category data
    cat_data = []
    for cat in CATEGORIES:
        matching = [j for j in jobs if matches_category(j, cat)]
        cat_data.append({**cat, "jobs": matching, "count": len(matching)})

    # Generate each category page
    for cat in cat_data:
        if cat["count"] == 0:
            continue

        job_rows = "\n".join(build_job_row_html(j) for j in cat["jobs"])

        other_cats = [c for c in cat_data if c["slug"] != cat["slug"] and c["count"] > 0]
        other_html = "\n".join(
            f'<a href="{c["slug"]}.html" class="category-link">{html.escape(c["name"])} <span>({c["count"]})</span></a>'
            for c in other_cats
        )

        json_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": cat["h1"],
            "description": cat["meta_description"],
            "numberOfItems": cat["count"],
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "url": f"{SITE_URL}/jobs/{j['slug']}.html" if j.get("slug") else j.get("url", ""),
                    "name": j.get("title", ""),
                }
                for i, j in enumerate(cat["jobs"])
            ],
        }, indent=2)

        page_html = CATEGORY_TEMPLATE.substitute(
            title=html.escape(cat["h1"]),
            name=html.escape(cat["name"]),
            meta_description=html.escape(cat["meta_description"]),
            canonical_url=f"{SITE_URL}/category/{cat['slug']}.html",
            h1=html.escape(cat["h1"]),
            intro=html.escape(cat["intro"]),
            count=cat["count"],
            job_rows=job_rows,
            other_categories=other_html,
            json_ld=json_ld,
        )

        with open(f"site/category/{cat['slug']}.html", "w") as f:
            f.write(page_html)

    # Generate categories index
    cards_html = "\n".join(
        f'<a href="category/{c["slug"]}.html" class="category-card">'
        f'<h3>{html.escape(c["name"])}</h3>'
        f'<p>{html.escape(c["intro"][:120])}...</p>'
        f'<span class="category-count">{c["count"]} jobs</span>'
        f'</a>'
        for c in cat_data if c["count"] > 0
    )

    index_html = INDEX_TEMPLATE.substitute(category_cards=cards_html)
    with open("site/categories.html", "w") as f:
        f.write(index_html)

    total_pages = sum(1 for c in cat_data if c["count"] > 0)
    print(f"Generated {total_pages} category pages + index in site/category/")
    for c in cat_data:
        if c["count"] > 0:
            print(f"  {c['name']}: {c['count']} jobs")


if __name__ == "__main__":
    main()
