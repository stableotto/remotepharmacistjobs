#!/usr/bin/env python3
"""Scrape job detail pages from ATS systems to enrich jobs with descriptions and salary data."""

import html as html_module
import json
import os
import re
import time
import sys

import requests
from bs4 import BeautifulSoup

SALARY_PATTERN = re.compile(
    r'\$\s?([\d,]+(?:\.\d{2})?)\s*[-–—to]+\s*\$?\s*([\d,]+(?:\.\d{2})?)\s*'
    r'(?:per\s+)?(year|yr|annually|hour|hr|hourly|month|monthly)?',
    re.IGNORECASE,
)

SALARY_SINGLE_PATTERN = re.compile(
    r'\$\s?([\d,]+(?:\.\d{2})?)\s*(?:per\s+)?(year|yr|annually|hour|hr|hourly|month|monthly)',
    re.IGNORECASE,
)


def parse_salary_number(s):
    return float(s.replace(',', ''))


def normalize_period(period_str):
    if not period_str:
        return "yearly"
    p = period_str.lower()
    if p in ("hour", "hr", "hourly"):
        return "hourly"
    if p in ("month", "monthly"):
        return "monthly"
    return "yearly"


def format_salary_display(min_val, max_val, period):
    def fmt(v):
        if v >= 1000:
            return f"${v:,.0f}"
        return f"${v:.2f}"

    suffix = "/yr" if period == "yearly" else "/hr" if period == "hourly" else "/mo"
    if min_val and max_val and min_val != max_val:
        return f"{fmt(min_val)} - {fmt(max_val)}{suffix}"
    val = max_val or min_val
    return f"{fmt(val)}{suffix}"


def build_salary(min_val, max_val, period="yearly", currency="USD"):
    return {
        "min": min_val,
        "max": max_val,
        "currency": currency,
        "period": period,
        "display": format_salary_display(min_val, max_val, period),
    }


def extract_salary_from_text(text):
    """Regex-scan text for salary patterns."""
    m = SALARY_PATTERN.search(text)
    if m:
        min_val = parse_salary_number(m.group(1))
        max_val = parse_salary_number(m.group(2))
        period = normalize_period(m.group(3))
        # Sanity check: if values look like hourly but no period specified, guess
        if not m.group(3) and min_val < 500 and max_val < 500:
            period = "hourly"
        return build_salary(min_val, max_val, period)

    m = SALARY_SINGLE_PATTERN.search(text)
    if m:
        val = parse_salary_number(m.group(1))
        period = normalize_period(m.group(2))
        return build_salary(val, val, period)

    return None


def sanitize_html(html):
    """Strip dangerous tags and attributes from HTML."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "iframe", "object", "embed", "form"]):
        tag.decompose()
    for tag in soup.find_all(True):
        attrs_to_remove = [a for a in tag.attrs if a.lower().startswith("on")]
        for a in attrs_to_remove:
            del tag[a]
    return str(soup)


def scrape_greenhouse(job):
    """Scrape Greenhouse job via their JSON API."""
    board = job.get("company_slug", "").split("/")[0] if "/" in job.get("company_slug", "") else job.get("company_slug", "")
    job_id = job.get("id")
    if not board or not job_id:
        return None, None, None

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    resp = requests.get(api_url, timeout=15)
    if resp.status_code != 200:
        return None, None, None

    data = resp.json()
    # Greenhouse API returns HTML-entity-escaped content — unescape first
    raw_content = html_module.unescape(data.get("content", ""))
    description_html = sanitize_html(raw_content)
    salary = None
    logo_url = None

    # Extract real posted date from Greenhouse (first_published is the original posting date)
    gh_posted = data.get("first_published") or data.get("updated_at", "")
    if gh_posted:
        job["posted_at"] = gh_posted

    # Check pay_input_ranges
    pay_ranges = data.get("pay_input_ranges", [])
    if pay_ranges:
        pr = pay_ranges[0]
        min_val = pr.get("min_cents", 0) / 100 if pr.get("min_cents") else None
        max_val = pr.get("max_cents", 0) / 100 if pr.get("max_cents") else None
        if min_val or max_val:
            salary = build_salary(min_val or max_val, max_val or min_val)

    # Fallback: regex scan the description
    if not salary and description_html:
        text = BeautifulSoup(description_html, "html.parser").get_text()
        salary = extract_salary_from_text(text)

    return description_html, salary, logo_url


def scrape_workday(job):
    """Scrape Workday job via their CXS API."""
    slug_parts = job.get("company_slug", "").split("|")
    if len(slug_parts) != 3:
        return None, None, None

    sub, wd, tenant = slug_parts
    url = job.get("url", "")

    # Extract the path slug from the URL
    # URL format: https://{sub}.{wd}.myworkdayjobs.com/{tenant}/job/{path-slug}
    match = re.search(r'/job/(.+?)(?:\?|$)', url)
    if not match:
        return None, None, None
    path_slug = match.group(1)

    api_url = f"https://{sub}.{wd}.myworkdayjobs.com/wday/cxs/{sub}/{tenant}/job/{path_slug}"
    headers = {"Accept": "application/json"}
    resp = requests.get(api_url, headers=headers, timeout=15)
    if resp.status_code != 200:
        return None, None, None

    data = resp.json()
    posting_info = data.get("jobPostingInfo", {})
    description_html = sanitize_html(posting_info.get("jobDescription", ""))
    salary = None
    logo_url = None

    # Extract real posted date from Workday (startDate is the ISO date)
    wd_posted = posting_info.get("startDate", "")
    if wd_posted:
        job["posted_at"] = wd_posted

    # Check for logo in Workday response
    logo = posting_info.get("companyLogoUrl") or data.get("brandBanner", {}).get("logoUrl")
    if logo:
        logo_url = logo

    # Check for salary fields in posting info
    min_sal = posting_info.get("minSalary") or posting_info.get("payRangeMin")
    max_sal = posting_info.get("maxSalary") or posting_info.get("payRangeMax")
    if min_sal or max_sal:
        min_val = float(min_sal) if min_sal else None
        max_val = float(max_sal) if max_sal else None
        salary = build_salary(min_val or max_val, max_val or min_val)

    # Check startingPay / endingPay
    if not salary:
        start_pay = posting_info.get("startingPay")
        end_pay = posting_info.get("endingPay")
        if start_pay or end_pay:
            salary = build_salary(
                float(start_pay) if start_pay else float(end_pay),
                float(end_pay) if end_pay else float(start_pay),
            )

    # Check additionalInformation or payRangeStatement
    if not salary:
        for field in ("additionalInformation", "payRangeStatement", "externalUrl"):
            text = posting_info.get(field, "")
            if text:
                salary = extract_salary_from_text(text)
                if salary:
                    break

    # Fallback: regex scan description
    if not salary and description_html:
        text = BeautifulSoup(description_html, "html.parser").get_text()
        salary = extract_salary_from_text(text)

    return description_html, salary, logo_url


def scrape_lever(job):
    """Scrape Lever job via HTML page."""
    url = job.get("url", "")
    if not url:
        return None, None, None

    # Try Lever API for posted date
    # URL format: https://jobs.lever.co/{company}/{uuid}
    lever_match = re.search(r'jobs\.lever\.co/([^/]+)/([a-f0-9-]+)', url)
    if lever_match:
        company_slug, posting_id = lever_match.groups()
        try:
            api_resp = requests.get(
                f"https://api.lever.co/v0/postings/{company_slug}/{posting_id}",
                timeout=10
            )
            if api_resp.status_code == 200:
                api_data = api_resp.json()
                created_ms = api_data.get("createdAt")
                if created_ms:
                    from datetime import datetime, timezone
                    dt = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
                    job["posted_at"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass

    resp = requests.get(url, timeout=15)
    if resp.status_code != 200:
        return None, None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    logo_url = None

    # Extract company logo from Lever page
    logo_img = soup.select_one(".main-header-logo img, .main-header img[src*='lever-client-logos']")
    if logo_img and logo_img.get("src"):
        logo_url = logo_img["src"]

    # Lever structure: multiple .section-wrapper divs
    # [0] = main header, [1] = posting header, [2+] = description sections
    # Inside the last description wrapper, skip .last-section-apply
    content_parts = []
    section_wrappers = soup.select(".section-wrapper")
    if len(section_wrappers) > 2:
        # The description content is in section_wrappers[2] onward
        for wrapper in section_wrappers[2:]:
            for section in wrapper.select(".section.page-centered"):
                # Skip the apply button section
                if "last-section-apply" in section.get("class", []):
                    continue
                content_parts.append(str(section))

    # Fallback: try older Lever layout selectors
    if not content_parts:
        for section in soup.select(".posting-page .content, .content-wrapper .section"):
            content_parts.append(str(section))

    description_html = sanitize_html("\n".join(content_parts))
    salary = None

    # Scan full page text for salary
    page_text = soup.get_text()
    salary = extract_salary_from_text(page_text)

    return description_html, salary, logo_url


SCRAPERS = {
    "Greenhouse": scrape_greenhouse,
    "Workday": scrape_workday,
    "Lever": scrape_lever,
}

# Map company slugs to website domains for logo fetching
COMPANY_DOMAINS = {
    "cvshealth": "cvshealth.com",
    "unitedhealthgroup": "unitedhealthgroup.com",
    "walgreens": "walgreens.com",
    "cigna": "cigna.com",
    "humana": "humana.com",
    "optum": "optum.com",
    "amazon": "amazon.com",
    "walmart": "walmart.com",
    "kroger": "kroger.com",
    "centene": "centene.com",
    "molinahealthcare": "molinahealthcare.com",
    "cardinalhealth": "cardinalhealth.com",
    "mckesson": "mckesson.com",
    "expressscripts": "express-scripts.com",
    "carelon": "carelon.com",
    "elevancehealth": "elevancehealth.com",
    "thermofisher": "thermofisher.com",
    "bighealth": "bighealth.com",
    "capitalrx": "capitalrx.com",
    "exactcare": "exactcare.com",
    "smithrx": "smithrx.com",
    "rvohealth": "rvohealth.com",
    "realchemistry": "realchemistry.com",
    "bmc": "bmc.org",
    "progyny": "progyny.com",
    "devoted": "devoted.com",
    "gravie": "gravie.com",
    "transcarent": "transcarent.com",
    "welocalize": "welocalize.com",
    "midihealth": "midihealth.com",
    "arine": "arine.io",
    "erasca": "erasca.com",
    "terrascend": "terrascend.com",
    "evergreennephrology": "evergreennephrology.com",
    "rightwayhealthcare": "rightwayhealthcare.com",
    "shieldshealthsolutions": "shieldshealthsolutions.com",
    "azuritypharmaceuticals": "azurity.com",
    "dianthustherapeutics": "dianthustx.com",
    "maplighttherapeutics": "maplighttherapeutics.com",
    "praxisprecisionmedicines": "praxismedicines.com",
    "springboardmentors": "springboardmentors.com",
    "edgewoodpartnersinsurancecenter": "epicbrokers.com",
    "foundationriskpartners": "foundationrp.com",
    "thequalitygroupgmbh1": "thequalitygroup.de",
    "thequalitygroupgmbh2": "thequalitygroup.de",
    "jointqg": "thequalitygroup.de",
}

LOGOS_DIR = "site/logos"

# Cache: domain -> local filename (or None if failed)
_logo_cache = {}


def fetch_company_logo(company_slug):
    """Fetch a company logo from their website and save it locally.

    Tries: apple-touch-icon link tag, apple-touch-icon.png well-known path,
    og:image meta tag. Downloads the image to site/logos/{slug}.png.
    Returns the relative path (logos/{slug}.png) or None.
    """
    base_slug = company_slug.split("|")[0] if "|" in company_slug else company_slug
    domain = COMPANY_DOMAINS.get(base_slug)
    if not domain:
        return None

    # Check cache
    if base_slug in _logo_cache:
        return _logo_cache[base_slug]

    os.makedirs(LOGOS_DIR, exist_ok=True)
    out_filename = f"{base_slug}.png"
    out_path = os.path.join(LOGOS_DIR, out_filename)

    # If already downloaded in a previous run, reuse
    if os.path.exists(out_path) and os.path.getsize(out_path) > 100:
        _logo_cache[base_slug] = f"logos/{out_filename}"
        return _logo_cache[base_slug]

    headers = {"User-Agent": "Mozilla/5.0 (compatible; RemotePharmacistJobs/1.0)"}
    logo_url = None

    try:
        # Strategy 1: Fetch homepage and look for apple-touch-icon or og:image
        resp = requests.get(f"https://{domain}", timeout=8, headers=headers)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")

            # apple-touch-icon (usually 180x180)
            ati = soup.find("link", rel=lambda r: r and "apple-touch-icon" in r)
            if ati and ati.get("href"):
                logo_url = ati["href"]

            # og:image fallback
            if not logo_url:
                og = soup.find("meta", property="og:image")
                if og and og.get("content"):
                    logo_url = og["content"]
    except Exception:
        pass

    # Strategy 2: well-known apple-touch-icon.png path
    if not logo_url:
        try:
            resp = requests.head(
                f"https://{domain}/apple-touch-icon.png",
                timeout=5, headers=headers, allow_redirects=True
            )
            if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
                logo_url = f"https://{domain}/apple-touch-icon.png"
        except Exception:
            pass

    if not logo_url:
        _logo_cache[base_slug] = None
        return None

    # Make absolute URL
    if logo_url.startswith("//"):
        logo_url = "https:" + logo_url
    elif logo_url.startswith("/"):
        logo_url = f"https://{domain}{logo_url}"

    # Download the image
    try:
        resp = requests.get(logo_url, timeout=10, headers=headers)
        if resp.status_code == 200 and len(resp.content) > 100:
            with open(out_path, "wb") as f:
                f.write(resp.content)
            _logo_cache[base_slug] = f"logos/{out_filename}"
            return _logo_cache[base_slug]
    except Exception:
        pass

    _logo_cache[base_slug] = None
    return None


def main():
    jobs_path = "site/jobs.json"
    with open(jobs_path) as f:
        data = json.load(f)

    jobs = data.get("jobs", [])
    total = len(jobs)
    success = 0
    salary_count = 0
    logo_count = 0
    errors = 0

    print(f"Scraping details for {total} jobs...")

    for i, job in enumerate(jobs):
        ats = job.get("ats", "")
        scraper = SCRAPERS.get(ats)
        if not scraper:
            print(f"  [{i+1}/{total}] SKIP {ats}: {job.get('title', '')[:50]}")
            continue

        try:
            desc, salary, logo_url = scraper(job)
            if desc:
                job["description_html"] = desc
            if salary:
                job["salary"] = salary
                salary_count += 1

            # Set logo: prefer ATS-provided (download locally), fallback to company website
            # Clear any old remote favicon URLs
            old_logo = job.get("logo_url", "")
            if "google.com/s2/favicons" in old_logo:
                job.pop("logo_url", None)

            base_slug = job.get("company_slug", "").split("|")[0]

            if logo_url:
                # Download ATS logo (e.g. Lever S3) locally
                local_path = os.path.join(LOGOS_DIR, f"{base_slug}.png")
                if not os.path.exists(local_path) or os.path.getsize(local_path) < 100:
                    try:
                        os.makedirs(LOGOS_DIR, exist_ok=True)
                        lr = requests.get(logo_url, timeout=10)
                        if lr.status_code == 200 and len(lr.content) > 100:
                            with open(local_path, "wb") as lf:
                                lf.write(lr.content)
                            job["logo_url"] = f"logos/{base_slug}.png"
                    except Exception:
                        pass
                else:
                    job["logo_url"] = f"logos/{base_slug}.png"

            if not job.get("logo_url") or "google.com" in job.get("logo_url", ""):
                local_logo = fetch_company_logo(job.get("company_slug", ""))
                if local_logo:
                    job["logo_url"] = local_logo

            if job.get("logo_url"):
                logo_count += 1

            success += 1
            status = "OK" + (" +salary" if salary else "") + (" +logo" if job.get("logo_url") else "")
            print(f"  [{i+1}/{total}] {status}: {job.get('title', '')[:50]}")
        except Exception as e:
            errors += 1
            print(f"  [{i+1}/{total}] ERROR: {job.get('title', '')[:50]} - {e}")

        time.sleep(1.0)

    # Remove newly-discovered jobs with old ATS posting dates.
    # If we just found a job today (first_seen within last 24h) but the ATS says
    # it was posted more than 2 days ago, drop it — we only want fresh listings.
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    max_post_age_days = 7
    before_count = len(jobs)
    kept_jobs = []
    dropped = 0
    for job in jobs:
        first_seen = job.get("first_seen", "")
        posted_at = job.get("posted_at", "")

        # Only filter newly-discovered jobs (first_seen within last 24h)
        if first_seen:
            try:
                fs_dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
                if fs_dt.tzinfo is None:
                    fs_dt = fs_dt.replace(tzinfo=timezone.utc)
                is_new = (now - fs_dt).total_seconds() < 86400
            except (ValueError, AttributeError):
                is_new = False
        else:
            is_new = False

        if posted_at:
            try:
                pa_dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                if pa_dt.tzinfo is None:
                    pa_dt = pa_dt.replace(tzinfo=timezone.utc)
                age_days = (now - pa_dt).days

                # Drop any job posted more than 30 days ago
                if age_days > 30:
                    dropped += 1
                    print(f"  DROPPED (posted {age_days}d ago): {job.get('title', '')[:50]}")
                    continue

                # Drop newly discovered jobs posted more than 7 days ago
                if is_new and age_days > max_post_age_days:
                    dropped += 1
                    print(f"  DROPPED (posted {age_days}d ago, new): {job.get('title', '')[:50]}")
                    continue
            except (ValueError, AttributeError):
                pass

        kept_jobs.append(job)

    data["jobs"] = kept_jobs
    data["total_jobs"] = len([j for j in kept_jobs if not j.get("expired")])

    with open(jobs_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nDone: {success} scraped, {salary_count} with salary, {logo_count} with logo, {errors} errors out of {total} jobs")
    if dropped:
        print(f"Dropped {dropped} stale jobs (posted >{max_post_age_days}d ago, first seen today)")


if __name__ == "__main__":
    main()
