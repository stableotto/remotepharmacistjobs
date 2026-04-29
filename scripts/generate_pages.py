#!/usr/bin/env python3
"""Generate individual static HTML pages for each job listing."""

import json
import os
import html
import re
from string import Template
from datetime import datetime, timedelta

SITE_URL = "https://remotepharmacistjobs.com"

PAGE_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
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
        <a href="../categories.html">Categories</a>
        <a href="../about.html">About</a>
        <a href="../post-a-job.html" class="nav-cta">Post a Job</a>
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
        <a href="../categories.html">Categories</a>
        <a href="../about.html">About</a>
        <a href="../post-a-job.html">Post a Job</a>
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
        if sj.get("salary"):
            salary_display = f'<span class="meta-dot"> \u00b7 </span><span class="meta-salary">{html.escape(sj["salary"]["display"])}</span>'

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

        rows.append(f'''<a href="{slug}.html" class="job-row">
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

    description = job.get("description_html", "")
    if not description:
        description = "<p>No description available. Click the Apply button to view the full job posting.</p>"

    meta_desc = f"{title} at {company} - Remote position"
    if salary:
        meta_desc += f" | {salary['display']}"
    meta_desc += f" | {location}"

    # Build meta line items (dot-separated like the reference design)
    skill_map = {"entry": "Entry-level", "mid": "Mid-level", "senior": "Senior"}
    skill_text = skill_map.get(skill_level, "")
    meta_parts = []
    if skill_text:
        meta_parts.append(f'<span>{html.escape(skill_text)}</span>')
    if salary:
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
    if salary:
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


def main():
    jobs_path = "site/jobs.json"
    with open(jobs_path) as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    output_dir = "site/jobs"
    os.makedirs(output_dir, exist_ok=True)

    count = 0
    for job in jobs:
        result = generate_page(job, all_jobs=jobs)
        if not result:
            continue
        slug, page_html = result
        filepath = os.path.join(output_dir, f"{slug}.html")
        with open(filepath, "w") as f:
            f.write(page_html)
        count += 1

    print(f"Generated {count} job detail pages in {output_dir}/")


if __name__ == "__main__":
    main()
