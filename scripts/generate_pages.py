#!/usr/bin/env python3
"""Generate individual static HTML pages for each job listing."""

import json
import os
import sys
import html
import re
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import employers as E
from datetime import datetime, timedelta
from urllib.parse import urljoin

SITE_URL = "https://remotepharmacistjobs.com"

PAGE_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="/analytics.js"></script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} at ${company} | Remote Pharmacist Jobs</title>
  <meta name="description" content="${meta_description}">
  <meta property="og:title" content="${title} at ${company} | Remote Pharmacist Jobs">
  <meta property="og:description" content="${meta_description}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="${canonical_url}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="${title} at ${company}">
  <meta name="twitter:description" content="${meta_description}">
  ${noindex}<link rel="canonical" href="${canonical_url}">
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
        <a href="../companies/">Companies</a>
        <a href="../categories">Categories</a>
        <a href="../licensure/">Licensure</a>
        <a href="../salary">Salary</a>
        <a href="../about">About</a>
        <a href="../post-a-job" class="nav-cta">Post a Job</a>
      </div>
    </div>
  </nav>

  <div class="container detail-page">
    <nav class="breadcrumb">
      <a href="../">Home</a> &rsaquo; <a href="../">Jobs</a> &rsaquo; <span>${title_short}</span>
    </nav>

    ${expired_banner}
    <div class="detail-page-layout">
      <div class="detail-main">
        <div class="detail-company-row">
          ${logo_html}
          <span class="detail-company-name">${company}</span>
        </div>

        <h1 class="detail-title">${title}</h1>

        <div class="detail-meta-line">
          ${meta_items}
        </div>

        ${pills_html}

        <div class="job-description">
          ${description}
        </div>
      </div>

      <aside class="detail-sidebar">
        <a href="${apply_url}" target="_blank" rel="noopener noreferrer" class="apply-button">
          Apply for this job
        </a>

        <div class="sidebar-card">
          <div class="sidebar-card-title">About ${company}</div>
          ${sidebar_rows}
        </div>
      </aside>
    </div>

    <div class="detail-bottom-apply">
      <a href="${apply_url}" target="_blank" rel="noopener noreferrer" class="apply-button">
        Apply for this job
      </a>
    </div>

    ${similar_jobs_html}
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
        <a href="../companies/">Companies</a>
        <a href="../categories">Categories</a>
        <a href="../licensure/">Licensure</a>
        <a href="../salary">Salary</a>
        <a href="../about">About</a>
        <a href="../post-a-job">Post a Job</a>
      </div>
    </div>
  </footer>
</body>
</html>
""")

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


def get_ats_name(job):
    ats = job.get("ats", "")
    if ats:
        return ats
    url = job.get("url", "")
    if "greenhouse" in url:
        return "Greenhouse"
    if "workday" in url or "myworkdayjobs" in url:
        return "Workday"
    if "lever.co" in url:
        return "Lever"
    return "Company Site"


def format_date(date_str):
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except (ValueError, AttributeError):
        return ""


def truncate(s, length=60):
    if len(s) <= length:
        return s
    return s[:length-3] + "..."


def absolutize_links(desc_html, job_url):
    """Resolve relative href/src in scraped descriptions against the employer.

    Scraped copy sometimes carries the employer's own root-relative links
    (/us/en/home.html). Left alone they resolve against this site, so Google
    crawls 404s that were never ours. Cloudflare email-protection stubs are
    unwrapped to nothing useful off-site, so their href is dropped.
    """
    if not desc_html or not job_url:
        return desc_html

    def fix(m):
        attr, url = m.group(1), m.group(2)
        if url.startswith(("http://", "https://", "//", "mailto:", "tel:", "#", "data:")):
            return m.group(0)
        if "/cdn-cgi/l/email-protection" in url:
            return f'{attr}="#"'
        return f'{attr}="{urljoin(job_url, url)}"'

    return re.sub(r'(href|src)="([^"]*)"', fix, desc_html)


def strip_html_tags(text):
    """Strip HTML tags to get plain text for JSON-LD."""
    clean = re.sub(r'<[^>]+>', ' ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:5000]  # Cap at 5000 chars for JSON-LD


def build_json_ld(job):
    """Build JSON-LD JobPosting schema."""
    desc_html = job.get("description_html", "")
    desc_text = strip_html_tags(desc_html) if desc_html else job.get("title", "")

    date_posted = job.get("posted_at") or job.get("first_seen") or job.get("scraped_at", "")
    valid_through = ""
    if date_posted:
        try:
            dt = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
            valid_through = (dt + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, AttributeError):
            pass

    # Google for Jobs prefers HTML description when available
    description_for_ld = desc_html if desc_html else desc_text

    ld = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": job.get("title", ""),
        "description": description_for_ld,
        "datePosted": date_posted,
        "employmentType": "FULL_TIME",
        "jobLocationType": "TELECOMMUTE",
        "hiringOrganization": {
            "@type": "Organization",
            "name": job.get("company", ""),
        },
        "jobLocation": {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "US",
            }
        },
        "applicantLocationRequirements": [{
            "@type": "Country",
            "name": "US",
        }],
        "directApply": True,
    }
    if valid_through:
        ld["validThrough"] = valid_through

    salary = job.get("salary")
    if salary:
        unit_text = "YEAR"
        if salary.get("period") == "hourly":
            unit_text = "HOUR"
        elif salary.get("period") == "monthly":
            unit_text = "MONTH"
        ld["baseSalary"] = {
            "@type": "MonetaryAmount",
            "currency": salary.get("currency", "USD"),
            "value": {
                "@type": "QuantitativeValue",
                "minValue": salary.get("min"),
                "maxValue": salary.get("max"),
                "unitText": unit_text,
            }
        }

    url = job.get("absolute_url") or job.get("url", "")
    if url:
        ld["url"] = url

    logo_url = job.get("logo_url", "")
    if logo_url:
        if logo_url.startswith("logos/"):
            logo_url = f"{SITE_URL}/{logo_url}"
        ld["hiringOrganization"]["logo"] = logo_url

    return json.dumps(ld, indent=2)


def build_logo_html(job, size="detail"):
    """Build logo HTML with fallback to avatar initial."""
    company = job.get("company", "Unknown")
    color = get_avatar_color(company)
    initial = html.escape(company[0].upper()) if company else "?"
    logo_url = job.get("logo_url", "")

    if size == "detail":
        cls_img = "detail-logo"
        cls_fb = "detail-logo-fallback"
        # Detail pages are in site/jobs/, so logos are at ../logos/
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


def build_similar_jobs_html(job, all_jobs, max_count=4):
    """Find similar jobs based on title keywords and company."""
    current_slug = job.get("slug", "")
    current_title = job.get("title", "").lower()
    current_company = job.get("company", "")

    # Score each job for similarity
    title_words = set(re.sub(r'[^a-z\s]', '', current_title).split())
    # Remove common stop words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'of', 'at', 'in', 'for', 'to', 'is', 'remote'}
    title_words -= stop_words

    scored = []
    for other in all_jobs:
        other_slug = other.get("slug", "")
        if other_slug == current_slug or not other_slug:
            continue
        if other.get("expired"):
            continue

        other_title = other.get("title", "").lower()
        other_words = set(re.sub(r'[^a-z\s]', '', other_title).split()) - stop_words

        # Score: shared title words + company match bonus
        shared = len(title_words & other_words)
        score = shared
        if other.get("company") == current_company:
            score += 2  # Same company bonus

        if score > 0:
            scored.append((score, other))

    scored.sort(key=lambda x: -x[0])
    similar = [j for _, j in scored[:max_count]]

    if not similar:
        return ""

    rows = []
    for sj in similar:
        company = html.escape(sj.get("company", "Unknown"))
        title = html.escape(sj.get("title", ""))
        slug = sj.get("slug", "")
        color = get_avatar_color(company)
        initial = company[0].upper() if company else "?"
        logo_url = sj.get("logo_url", "")

        salary_display = ""
        sj_salary = sj.get("salary")
        if sj_salary and sj_salary.get("display"):
            salary_display = f'<span class="meta-dot"> \u00b7 </span><span class="meta-salary">{html.escape(sj_salary["display"])}</span>'

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

        rows.append(f'''<a href="{slug}" class="job-row">
      <div class="job-row-left">
        <div class="job-logo-wrap">{logo_html}</div>
        <div class="job-row-info">
          <div class="job-row-title">{title}</div>
          <div class="job-row-meta">{company}{salary_display}</div>
        </div>
      </div>
    </a>''')

    return f'''<div class="similar-jobs">
      <h2>Similar Jobs</h2>
      <div class="jobs-list">
        {"".join(rows)}
      </div>
    </div>'''


def generate_page(job, all_jobs=None):
    slug = job.get("slug", "")
    if not slug:
        return None

    company = job.get("company", "Unknown")
    title = job.get("title", "")
    location = job.get("location", "Remote")
    salary = job.get("salary")
    ats = get_ats_name(job)
    apply_url = job.get("absolute_url") or job.get("url", "#")
    # Use posted_at (from ATS) > first_seen (when we found it) > scraped_at (fallback)
    date_str = job.get("posted_at") or job.get("first_seen") or job.get("scraped_at", "")
    skill_level = job.get("skill_level", "")
    is_expired = job.get("expired", False)

    description = absolutize_links(job.get("description_html", ""),
                                   job.get("url") or job.get("absolute_url", ""))
    if not description:
        description = "<p>No description available. Click the Apply button to view the full job posting.</p>"

    meta_desc = f"{title} at {company} - Remote position"
    if salary and salary.get("display"):
        meta_desc += f" | {salary['display']}"
    meta_desc += f" | {location}"

    # Build meta line items (dot-separated like the reference design)
    skill_map = {"entry": "Entry-level", "mid": "Mid-level", "senior": "Senior"}
    skill_text = skill_map.get(skill_level, "")
    meta_parts = []
    if skill_text:
        meta_parts.append(f'<span>{html.escape(skill_text)}</span>')
    if salary and salary.get("display"):
        meta_parts.append(f'<span class="detail-meta-salary">{html.escape(salary["display"])}</span>')
    meta_parts.append(f'<span class="detail-meta-location">{html.escape(location)}</span>')
    meta_items = '<span class="meta-dot"> · </span>'.join(meta_parts)

    # Build pills
    pills = []
    pills.append(f'<span class="pill">Remote</span>')
    if skill_text:
        pills.append(f'<span class="pill">{html.escape(skill_text)}</span>')
    if date_str:
        pills.append(f'<span class="pill">Posted {html.escape(format_date(date_str))}</span>')
    pills.append(f'<span class="pill">{html.escape(ats)}</span>')
    pills_html = f'<div class="detail-pills">{"".join(pills)}</div>' if pills else ''

    # Build sidebar info rows
    sidebar_parts = []
    sidebar_parts.append(
        f'<div class="sidebar-info-row"><span class="sidebar-info-label">Source</span>'
        f'<span class="sidebar-info-value">{html.escape(ats)}</span></div>'
    )
    sidebar_parts.append(
        f'<div class="sidebar-info-row"><span class="sidebar-info-label">Location</span>'
        f'<span class="sidebar-info-value">{html.escape(location)}</span></div>'
    )
    if salary and salary.get("display"):
        sidebar_parts.append(
            f'<div class="sidebar-info-row"><span class="sidebar-info-label">Salary</span>'
            f'<span class="sidebar-info-value">{html.escape(salary["display"])}</span></div>'
        )
    if skill_text:
        sidebar_parts.append(
            f'<div class="sidebar-info-row"><span class="sidebar-info-label">Level</span>'
            f'<span class="sidebar-info-value">{html.escape(skill_text)}</span></div>'
        )
    if date_str:
        sidebar_parts.append(
            f'<div class="sidebar-info-row"><span class="sidebar-info-label">Posted</span>'
            f'<span class="sidebar-info-value">{html.escape(format_date(date_str))}</span></div>'
        )
    sidebar_rows = "\n          ".join(sidebar_parts)

    logo_html = build_logo_html(job, "detail")

    # Expired job handling
    noindex = '<meta name="robots" content="noindex">\n  ' if is_expired else ''
    expired_banner = ''
    if is_expired:
        expired_banner = (
            '<div class="expired-banner">'
            '<strong>This job may no longer be available.</strong> '
            'It was last seen on our sources ' + html.escape(format_date(job.get("last_seen", ""))) + '. '
            '<a href="../">Browse active jobs</a>'
            '</div>'
        )

    # Build similar jobs section
    similar_jobs_html = ""
    if all_jobs:
        similar_jobs_html = build_similar_jobs_html(job, all_jobs)

    page_html = PAGE_TEMPLATE.substitute(
        title=html.escape(title),
        company=html.escape(company),
        meta_description=html.escape(meta_desc),
        canonical_url=f"{SITE_URL}/jobs/{slug}",
        title_short=html.escape(truncate(title)),
        logo_html=logo_html,
        location=html.escape(location),
        meta_items=meta_items,
        pills_html=pills_html,
        apply_url=html.escape(apply_url),
        ats_name=html.escape(ats),
        description=description,
        json_ld=build_json_ld(job),
        sidebar_rows=sidebar_rows,
        noindex=noindex,
        expired_banner=expired_banner,
        similar_jobs_html=similar_jobs_html,
    )

    return slug, page_html


JOBS_INDEX_NAV = """  <nav class="site-nav">
    <div class="site-nav-inner">
      <a href="../" class="site-nav-logo">
        <img src="../logo.svg" alt="Remote Pharmacist Jobs" height="32">
      </a>
      <button class="nav-toggle" aria-label="Menu" onclick="this.nextElementSibling.classList.toggle('open')">
        <span></span><span></span><span></span>
      </button>
      <div class="site-nav-links">
        <a href="../" class="active">Jobs</a>
        <a href="../companies/">Companies</a>
        <a href="../categories">Categories</a>
        <a href="../licensure/">Licensure</a>
        <a href="../salary">Salary</a>
        <a href="../about">About</a>
        <a href="../post-a-job" class="nav-cta">Post a Job</a>
      </div>
    </div>
  </nav>"""

JOBS_INDEX_FOOTER = """  <footer class="site-footer">
    <div class="site-footer-inner">
      <div class="footer-col">
        <h4>Remote Pharmacist Jobs</h4>
        <p>Direct listings only. No recruiters, no middlemen.</p>
      </div>
      <div class="footer-col">
        <h4>Navigate</h4>
        <a href="../">Jobs</a>
        <a href="../companies/">Companies</a>
        <a href="../categories">Categories</a>
        <a href="../licensure/">Licensure</a>
        <a href="../salary">Salary</a>
        <a href="../about">About</a>
        <a href="../post-a-job">Post a Job</a>
      </div>
    </div>
  </footer>"""


def build_jobs_index(jobs, employers):
    """The complete listing at /jobs — every open role on one page.

    Job detail pages already live under site/jobs/, so the index belongs here
    too; it is added to the keep set in main() or the prune step would delete
    it on the next run.
    """
    active = [j for j in jobs if not j.get("expired")]
    active.sort(key=lambda j: j.get("posted_at") or j.get("first_seen") or "", reverse=True)

    type_of = {}
    for record in employers.values():
        for _ in (0,):
            type_of[record["slug"]] = record.get("employer_type", "other")

    rows = []
    for job in active:
        slug = job.get("slug", "")
        company = job.get("company", "")
        title = job.get("title", "")
        location = job.get("location", "")
        salary = (job.get("salary") or {}).get("display", "")
        etype = type_of.get(job.get("employer_slug", ""), "other")
        color = get_avatar_color(company)
        initial = html.escape(company[:1].upper() or "?")
        logo = job.get("logo_url", "")
        if logo:
            badge = (
                f'<img class="job-logo" src="../{html.escape(logo)}" alt="" loading="lazy" '
                f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
                f'<div class="job-logo-fallback" style="background-color:{color};display:none">{initial}</div>'
            )
        else:
            badge = f'<div class="job-logo-fallback" style="background-color:{color}">{initial}</div>'

        meta = [html.escape(company)]
        if salary:
            meta.append(f'<span class="meta-salary">{html.escape(salary)}</span>')
        blob = " ".join([company, title, location]).lower()
        meta_line = '<span class="meta-dot"> &middot; </span>'.join(meta)
        esc_slug, esc_type = html.escape(slug), html.escape(etype)
        esc_title, esc_loc = html.escape(title), html.escape(location)
        esc_blob = html.escape(blob)
        paid_attr = "true" if salary else "false"
        rows.append(
            f'      <a href="{esc_slug}" class="job-row" data-type="{esc_type}" '
            f'data-paid="{paid_attr}" data-search="{esc_blob}">'
            f'<div class="job-row-left">'
            f'<div class="job-logo-wrap">{badge}</div>'
            f'<div class="job-row-info">'
            f'<div class="job-row-title">{esc_title}</div>'
            f'<div class="job-row-meta">{meta_line}</div>'
            f'</div></div>'
            f'<div class="job-row-right">'
            f'<div class="job-row-location">{esc_loc}</div>'
            f'</div></a>'
        )

    counts = {}
    for job in active:
        etype = type_of.get(job.get("employer_slug", ""), "other")
        counts[etype] = counts.get(etype, 0) + 1
    paid = len([j for j in active if (j.get("salary") or {}).get("display")])

    filters = [f'      <button type="button" class="pill" data-filter="all" aria-pressed="true">'
               f'All ({len(active)})</button>',
               f'      <button type="button" class="pill" data-filter="paid" aria-pressed="false">'
               f'Salary shown ({paid})</button>']
    for key, label in E.EMPLOYER_TYPES.items():
        if counts.get(key):
            filters.append(
                f'      <button type="button" class="pill" data-filter="{key}" aria-pressed="false">'
                f'{html.escape(label)} ({counts[key]})</button>')

    cats = []
    for slug_, label in [("clinical-pharmacist", "Clinical pharmacist"),
                         ("pharmacy-technician", "Pharmacy technician"),
                         ("managed-care-pharmacist", "Managed care"),
                         ("specialty-pharmacy", "Specialty pharmacy"),
                         ("prior-authorization", "Prior authorization"),
                         ("medication-therapy-management", "MTM")]:
        if os.path.exists(f"site/category/{slug_}.html"):
            cats.append(f'        <a href="../category/{slug_}" class="category-link">'
                        f'{html.escape(label)}</a>')

    ld = json.dumps([
        {"@context": "https://schema.org", "@type": "ItemList",
         "name": "All remote pharmacy jobs",
         "numberOfItems": len(active),
         "itemListElement": [
             {"@type": "ListItem", "position": i + 1,
              "url": f"{SITE_URL}/jobs/{j['slug']}", "name": j.get("title", "")}
             for i, j in enumerate(active) if j.get("slug")]},
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [
             {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
             {"@type": "ListItem", "position": 2, "name": "Jobs", "item": f"{SITE_URL}/jobs"}]},
    ], indent=2)

    desc = (f"All {len(active)} open remote pharmacy jobs, updated daily. Filter by employer "
            f"type and pay. Every listing links directly to the employer — no recruiters.")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="/analytics.js"></script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>All Remote Pharmacy Jobs ({len(active)} Open) | Remote Pharmacist Jobs</title>
  <meta name="description" content="{html.escape(desc)}">
  <meta property="og:title" content="All Remote Pharmacy Jobs">
  <meta property="og:description" content="{html.escape(desc)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_URL}/jobs">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="{SITE_URL}/jobs">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link href="https://fonts.cdnfonts.com/css/geist" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
  <script type="application/ld+json">
{ld}
  </script>
</head>
<body>
{JOBS_INDEX_NAV}

  <div class="container">
    <nav class="breadcrumb">
      <a href="../">Home</a> &rsaquo; <span>Jobs</span>
    </nav>

    <div class="category-hero">
      <h1>All remote pharmacy jobs</h1>
      <p>Every open remote pharmacist and pharmacy technician role we track, newest first.
      {paid} of {len(active)} publish a pay range. Each one links straight to the employer&rsquo;s
      own listing &mdash; no recruiters, no middlemen.</p>
    </div>

    <div class="search-wrapper">
      <input type="search" id="job-search" placeholder="Search by title, company or location"
             aria-label="Search jobs" autocomplete="off">
    </div>

    <div class="detail-pills" id="job-filters">
{chr(10).join(filters)}
    </div>

    <div class="jobs-list" id="job-list">
{chr(10).join(rows)}
    </div>

    <p class="no-results" id="job-empty" hidden>No roles match that filter.</p>

    <div class="browse-categories">
      <h2>Browse by role</h2>
      <div class="category-links">
{chr(10).join(cats)}
      </div>
    </div>
  </div>

{JOBS_INDEX_FOOTER}
  <script>
  // Progressive enhancement: the full list above is already in the HTML.
  (function () {{
    var list = document.getElementById('job-list');
    if (!list) return;
    var rows = Array.prototype.slice.call(list.querySelectorAll('.job-row'));
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll('#job-filters .pill'));
    var search = document.getElementById('job-search');
    var empty = document.getElementById('job-empty');
    var active = 'all';

    function apply() {{
      var q = (search.value || '').trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (row) {{
        var okFilter = active === 'all'
          || (active === 'paid' && row.dataset.paid === 'true')
          || row.dataset.type === active;
        var okSearch = !q || (row.dataset.search || '').indexOf(q) !== -1;
        var show = okFilter && okSearch;
        row.hidden = !show;
        if (show) shown++;
      }});
      empty.hidden = shown !== 0;
    }}

    buttons.forEach(function (btn) {{
      btn.addEventListener('click', function () {{
        active = btn.dataset.filter;
        buttons.forEach(function (b) {{
          b.setAttribute('aria-pressed', String(b === btn));
          b.style.borderColor = b === btn ? '#7c3aed' : '';
        }});
        apply();
      }});
    }});
    search.addEventListener('input', apply);
  }})();
  </script>
</body>
</html>
"""

def main():
    jobs_path = "site/jobs.json"
    with open(jobs_path) as f:
        data = json.load(f)

    jobs = E.decorate(data.get("jobs", []))
    output_dir = "site/jobs"
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    keep = set()
    for job in jobs:
        result = generate_page(job, all_jobs=jobs)
        if not result:
            continue
        slug, page_html = result
        filename = f"{slug}.html"
        keep.add(filename)
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            f.write(page_html)
        count += 1

    # The complete listing at /jobs. Written here because job pages live in
    # this directory and the prune below would otherwise delete it.
    keep.add("index.html")
    with open(os.path.join(output_dir, "index.html"), "w") as f:
        f.write(build_jobs_index(jobs, E.load_employers()))

    removed = 0
    for fname in os.listdir(output_dir):
        if fname.endswith(".html") and fname not in keep:
            os.remove(os.path.join(output_dir, fname))
            removed += 1

    print(f"Generated {count} job detail pages + /jobs index in {output_dir}/ (removed {removed} stale pages)")


if __name__ == "__main__":
    main()
