#!/usr/bin/env python3
"""Inject active job listings into the homepage so crawlers see real HTML.

index.html stays hand-written; this script only replaces marked regions.
"""

import json
import html
from datetime import datetime, timezone

SITE_URL = "https://remotepharmacistjobs.com"
INDEX_PATH = "site/index.html"

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


def parse_dt(date_str):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def time_ago(date_str, now=None):
    dt = parse_dt(date_str)
    if not dt:
        return ""
    now = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    minutes = int(diff.total_seconds() // 60)
    hours = minutes // 60
    days = hours // 24
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    if hours < 24:
        return f"{hours}h ago"
    if days == 1:
        return "1 day ago"
    if days < 30:
        return f"{days} days ago"
    return dt.strftime(f"%b {dt.day}, %Y")


def replace_region(text, start_marker, end_marker, inner):
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start < 0 or end < 0 or end < start:
        raise SystemExit(f"Missing markers {start_marker} / {end_marker} in {INDEX_PATH}")
    return text[: start + len(start_marker)] + inner + text[end:]


def build_job_row_html(job):
    company_raw = job.get("company", "Unknown")
    company = html.escape(company_raw)
    title = html.escape(job.get("title", ""))
    location = html.escape(job.get("location", ""))
    slug = job.get("slug", "")
    detail_url = f"jobs/{slug}.html" if slug else html.escape(job.get("url", "#"))
    color = get_avatar_color(company_raw)
    initial = html.escape(company_raw[0].upper()) if company_raw else "?"
    logo_url = job.get("logo_url", "")

    meta_parts = [company]
    salary = job.get("salary")
    if salary and salary.get("display"):
        meta_parts.append(f'<span class="meta-salary">{html.escape(salary["display"])}</span>')
    meta_line = '<span class="meta-dot"> · </span>'.join(meta_parts)

    if logo_url:
        logo_html = (
            f'<img class="job-logo" src="{html.escape(logo_url)}" alt="{company}" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<div class="job-logo-fallback" style="background-color:{color};display:none">{initial}</div>'
        )
    else:
        logo_html = f'<div class="job-logo-fallback" style="background-color:{color}">{initial}</div>'

    job_date = job.get("posted_at") or job.get("first_seen") or job.get("scraped_at", "")
    date = html.escape(time_ago(job_date))

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
          <div class="job-row-date">{date}</div>
        </div>
      </a>'''


def build_json_ld(jobs):
    item_list = {
        "@type": "ItemList",
        "name": "Remote Pharmacist Jobs",
        "numberOfItems": len(jobs),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "url": f"{SITE_URL}/jobs/{job['slug']}" if job.get("slug") else job.get("url", ""),
                "name": job.get("title", ""),
            }
            for i, job in enumerate(jobs)
            if job.get("slug") or job.get("url")
        ],
    }
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "name": "Remote Pharmacist Jobs",
                "url": SITE_URL,
                "description": "Browse remote pharmacist jobs updated daily from 7,000+ companies. Direct employer listings only.",
                "potentialAction": {
                    "@type": "SearchAction",
                    "target": f"{SITE_URL}/?q={{search_term_string}}",
                    "query-input": "required name=search_term_string",
                },
            },
            item_list,
        ],
    }
    return json.dumps(graph, indent=2)


def main():
    with open("site/jobs.json") as f:
        data = json.load(f)

    jobs = [j for j in data.get("jobs", []) if not j.get("expired")]
    last_updated = data.get("last_updated", "")
    count = data.get("total_jobs") or len(jobs)

    rows = "\n      ".join(build_job_row_html(j) for j in jobs)
    if not rows:
        rows = '<div class="no-results">No remote pharmacy jobs right now. Check back tomorrow.</div>'

    with open(INDEX_PATH) as f:
        html_text = f.read()

    json_ld_block = (
        "\n  <script type=\"application/ld+json\">\n  "
        + build_json_ld(jobs)
        + "\n  </script>\n  "
    )
    html_text = replace_region(
        html_text,
        "<!-- JSON_LD_START -->",
        "<!-- JSON_LD_END -->",
        json_ld_block,
    )
    html_text = replace_region(
        html_text,
        "<!-- JOB_COUNT_START -->",
        "<!-- JOB_COUNT_END -->",
        f"{count} jobs found",
    )
    html_text = replace_region(
        html_text,
        "<!-- UPDATED_START -->",
        "<!-- UPDATED_END -->",
        f"Updated {time_ago(last_updated)}" if last_updated else "",
    )
    html_text = replace_region(
        html_text,
        "<!-- JOBS_START -->",
        "<!-- JOBS_END -->",
        "\n      " + rows + "\n    ",
    )

    with open(INDEX_PATH, "w") as f:
        f.write(html_text)

    print(f"Injected {len(jobs)} jobs into {INDEX_PATH}")


if __name__ == "__main__":
    main()
