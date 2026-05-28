#!/usr/bin/env python3
"""Generate a salary insights page aggregating salary data from job listings."""

import json
import html
import math
from collections import defaultdict

SITE_URL = "https://remotepharmacistjobs.com"


def main():
    with open("site/jobs.json") as f:
        data = json.load(f)

    jobs = [j for j in data.get("jobs", []) if not j.get("expired")]

    # Collect salary data, normalizing everything to annual
    salary_entries = []
    for job in jobs:
        sal = job.get("salary")
        if not sal or sal.get("min") is None:
            continue

        min_val = sal["min"]
        max_val = sal.get("max", min_val)
        period = sal.get("period", "yearly")

        if period == "hourly":
            annual_min = min_val * 2080
            annual_max = max_val * 2080
        elif period == "monthly":
            annual_min = min_val * 12
            annual_max = max_val * 12
        else:
            annual_min = min_val
            annual_max = max_val

        salary_entries.append({
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "slug": job.get("slug", ""),
            "display": sal.get("display", ""),
            "annual_min": annual_min,
            "annual_max": annual_max,
            "annual_mid": (annual_min + annual_max) / 2,
        })

    if not salary_entries:
        print("No salary data found, skipping salary page generation")
        return

    # Overall stats
    all_mids = [s["annual_mid"] for s in salary_entries]
    overall_avg = sum(all_mids) / len(all_mids)
    overall_min = min(s["annual_min"] for s in salary_entries)
    overall_max = max(s["annual_max"] for s in salary_entries)
    overall_median = sorted(all_mids)[len(all_mids) // 2]

    # Salary by role type
    role_categories = {
        "Pharmacist": ["pharmacist", "pharmd", "clinical pharmacist"],
        "Pharmacy Technician": ["pharmacy tech", "pharmacy technician"],
        "Pharmacy Manager/Director": ["manager", "director", "supervisor", "lead"],
        "Pharmacovigilance": ["pharmacovigilance", "drug safety"],
    }

    role_stats = {}
    for role_name, keywords in role_categories.items():
        matching = [s for s in salary_entries if any(kw in s["title"].lower() for kw in keywords)]
        if matching:
            mids = [s["annual_mid"] for s in matching]
            role_stats[role_name] = {
                "count": len(matching),
                "avg": sum(mids) / len(mids),
                "min": min(s["annual_min"] for s in matching),
                "max": max(s["annual_max"] for s in matching),
            }

    def fmt(val):
        return f"${val:,.0f}"

    # Build stats cards HTML
    stats_html = f'''
    <div class="salary-stats-grid">
      <div class="salary-stat-card">
        <div class="salary-stat-label">Average Salary</div>
        <div class="salary-stat-value">{fmt(overall_avg)}</div>
        <div class="salary-stat-sub">per year</div>
      </div>
      <div class="salary-stat-card">
        <div class="salary-stat-label">Median Salary</div>
        <div class="salary-stat-value">{fmt(overall_median)}</div>
        <div class="salary-stat-sub">per year</div>
      </div>
      <div class="salary-stat-card">
        <div class="salary-stat-label">Salary Range</div>
        <div class="salary-stat-value">{fmt(overall_min)} - {fmt(overall_max)}</div>
        <div class="salary-stat-sub">per year</div>
      </div>
      <div class="salary-stat-card">
        <div class="salary-stat-label">Jobs with Salary</div>
        <div class="salary-stat-value">{len(salary_entries)}</div>
        <div class="salary-stat-sub">of {len(jobs)} total</div>
      </div>
    </div>'''

    # Build role breakdown table
    role_rows = ""
    for role_name, stats in sorted(role_stats.items(), key=lambda x: -x[1]["avg"]):
        role_rows += f'''
      <tr>
        <td>{html.escape(role_name)}</td>
        <td>{fmt(stats["avg"])}</td>
        <td>{fmt(stats["min"])} - {fmt(stats["max"])}</td>
        <td>{stats["count"]}</td>
      </tr>'''

    role_table_html = f'''
    <div class="salary-table-wrap">
      <table class="salary-table">
        <thead>
          <tr>
            <th>Role</th>
            <th>Average</th>
            <th>Range</th>
            <th>Jobs</th>
          </tr>
        </thead>
        <tbody>{role_rows}
        </tbody>
      </table>
    </div>''' if role_rows else ""

    # Build top-paying jobs list
    top_jobs = sorted(salary_entries, key=lambda x: -x["annual_max"])[:10]
    top_jobs_html = ""
    for job in top_jobs:
        link = f'<a href="jobs/{job["slug"]}.html">' if job["slug"] else ""
        end_link = "</a>" if job["slug"] else ""
        top_jobs_html += f'''
      <div class="salary-job-row">
        <div class="salary-job-info">
          <div class="salary-job-title">{link}{html.escape(job["title"])}{end_link}</div>
          <div class="salary-job-company">{html.escape(job["company"])}</div>
        </div>
        <div class="salary-job-pay">{html.escape(job["display"])}</div>
      </div>'''

    page_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-C0EB4GHJS3"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-C0EB4GHJS3');
  </script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Remote Pharmacist Salary Guide | Remote Pharmacist Jobs</title>
  <meta name="description" content="Remote pharmacist salary data from real job listings. Average salary {fmt(overall_avg)}/year. See salaries by role type and the highest-paying remote pharmacy positions.">
  <meta property="og:title" content="Remote Pharmacist Salary Guide">
  <meta property="og:description" content="Remote pharmacist salary data from real job listings. Average salary {fmt(overall_avg)}/year.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_URL}/salary">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="{SITE_URL}/salary">
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
        <a href="categories.html">Categories</a>
        <a href="about.html">About</a>
        <a href="post-a-job.html" class="nav-cta">Post a Job</a>
      </div>
    </div>
  </nav>

  <div class="container content-page" style="max-width:900px">
    <div class="category-hero">
      <h1>Remote Pharmacist Salary Guide</h1>
      <p>Real salary data from {len(salary_entries)} remote pharmacy job listings. Updated daily as new positions are posted.</p>
    </div>

    <div class="content-section">
      <h2>Salary Overview</h2>
      {stats_html}
    </div>

    <div class="content-section">
      <h2>Salary by Role Type</h2>
      <p>Average annual salaries based on current remote pharmacy job listings.</p>
      {role_table_html}
    </div>

    <div class="content-section">
      <h2>Highest-Paying Remote Pharmacy Jobs</h2>
      <p>The top-paying remote pharmacy positions currently listed.</p>
      <div class="salary-top-jobs">
        {top_jobs_html}
      </div>
    </div>

    <div class="content-section">
      <h2>About This Data</h2>
      <p>Salary figures are based on compensation data from active remote pharmacy job listings on our site. We include only positions that disclose salary information. Data is refreshed daily as jobs are added and removed.</p>
      <p>Salaries shown represent the full range posted by employers. Actual compensation may vary based on experience, location, and other factors.</p>
    </div>

    <div class="post-job-cta-section">
      <p>Looking for remote pharmacy jobs?</p>
      <a href="/" class="apply-button post-job-cta">Browse All Jobs</a>
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
</html>'''

    with open("site/salary.html", "w") as f:
        f.write(page_html)

    print(f"Generated salary page with data from {len(salary_entries)} jobs")


if __name__ == "__main__":
    main()
