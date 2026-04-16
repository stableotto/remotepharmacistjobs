#!/usr/bin/env python3
"""Download all_jobs.json from job-board-aggregator releases and filter to remote pharmacist jobs."""

import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone

import requests

RELEASE_API = "https://api.github.com/repos/Feashliaa/job-board-aggregator/releases/latest"

TITLE_KEYWORDS = [
    "pharmacist",
    "pharmacy",
    "telepharmacy",
    "medication review",
    "drug utilization review",
    "medication therapy management",
    "pharmacovigilance",
    "pharmaceutical",
]
TITLE_WHOLE_WORDS = ["dur", "mtm"]

REMOTE_KEYWORDS = ["remote", "work from home", "wfh", "telecommute", "anywhere"]

COMPANY_NAME_MAP = {
    "cvshealth": "CVS Health",
    "cvs-health": "CVS Health",
    "unitedhealthgroup": "UnitedHealth Group",
    "unitedhealth-group": "UnitedHealth Group",
    "walgreens": "Walgreens",
    "riteaid": "Rite Aid",
    "cigna": "Cigna",
    "humana": "Humana",
    "optum": "Optum",
    "amazon": "Amazon",
    "walmart": "Walmart",
    "kroger": "Kroger",
    "anthem": "Anthem",
    "centene": "Centene",
    "molinahealthcare": "Molina Healthcare",
    "omnicare": "Omnicare",
    "cardinalhealth": "Cardinal Health",
    "mckesson": "McKesson",
    "amerisourcebergen": "AmerisourceBergen",
    "expressscripts": "Express Scripts",
    "carelon": "Carelon",
    "elevancehealth": "Elevance Health",
    "thermofisher": "Thermo Fisher",
    "bighealth": "Big Health",
    "capitalrx": "Capital Rx",
    "exactcare": "ExactCare",
    "smithrx": "SmithRx",
    "rvohealth": "RVO Health",
    "realchemistry": "Real Chemistry",
    "bmc": "BMC",
    "progyny": "Progyny",
    "devoted": "Devoted Health",
    "gravie": "Gravie",
    "transcarent": "Transcarent",
    "welocalize": "Welocalize",
    "midihealth": "Midi Health",
    "arine": "Arine",
    "erasca": "Erasca",
    "terrascend": "TerrAscend",
    "evergreennephrology": "Evergreen Nephrology",
    "rightwayhealthcare": "Rightway Healthcare",
    "shieldshealthsolutions": "Shields Health Solutions",
    "azuritypharmaceuticals": "Azurity Pharmaceuticals",
    "dianthustherapeutics": "Dianthus Therapeutics",
    "maplighttherapeutics": "Maplelight Therapeutics",
    "praxisprecisionmedicines": "Praxis Precision Medicines",
    "springboardmentors": "Springboard Mentors",
    "edgewoodpartnersinsurancecenter": "Edgewood Partners Insurance Center",
    "foundationriskpartners": "Foundation Risk Partners",
    "thequalitygroupgmbh1": "The Quality Group",
    "thequalitygroupgmbh2": "The Quality Group",
    "jointqg": "Joint QG",
}


def clean_company_name(name: str) -> str:
    """Clean up company name to human-readable form."""
    lower = name.lower().strip()
    if lower in COMPANY_NAME_MAP:
        return COMPANY_NAME_MAP[lower]
    # Replace hyphens/underscores with spaces and title-case
    cleaned = name.replace("-", " ").replace("_", " ")
    # If it's a single concatenated word, try splitting on camelCase boundaries
    if " " not in cleaned.strip():
        cleaned = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', cleaned)
    return cleaned.title()


def matches_title(title: str) -> bool:
    """Check if job title matches pharmacy keywords."""
    lower = title.lower()
    for kw in TITLE_KEYWORDS:
        if kw in lower:
            return True
    for word in TITLE_WHOLE_WORDS:
        if re.search(rf"\b{word}\b", lower):
            return True
    return False


def is_remote(location: str) -> bool:
    """Check if location indicates remote work."""
    if not location:
        return False
    lower = location.lower()
    return any(kw in lower for kw in REMOTE_KEYWORDS)


RETENTION_DAYS = 30  # Keep jobs for 30 days after they disappear from aggregator


def main():
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load existing jobs.json to preserve first_seen and enrichment data
    out_path = "site/jobs.json"
    existing_jobs = {}
    try:
        with open(out_path) as f:
            old_data = json.load(f)
        for job in old_data.get("jobs", []):
            url = job.get("url") or job.get("absolute_url", "")
            if url:
                existing_jobs[url] = job
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    print(f"Loaded {len(existing_jobs)} existing jobs from {out_path}")

    print("Fetching latest release info...")
    resp = requests.get(RELEASE_API, timeout=30)
    resp.raise_for_status()
    release = resp.json()

    asset_url = None
    compressed = False
    for asset in release.get("assets", []):
        if asset["name"] == "all_jobs.json":
            asset_url = asset["browser_download_url"]
            break
        if asset["name"] == "all_jobs.json.gz":
            asset_url = asset["browser_download_url"]
            compressed = True
            break

    if not asset_url:
        print("ERROR: all_jobs.json not found in latest release assets")
        sys.exit(1)

    print(f"Downloading {('all_jobs.json.gz' if compressed else 'all_jobs.json')} from {asset_url}...")
    resp = requests.get(asset_url, timeout=300)
    resp.raise_for_status()
    if compressed:
        all_jobs = json.loads(gzip.decompress(resp.content))
    else:
        all_jobs = resp.json()
    print(f"Downloaded {len(all_jobs):,} total jobs")

    # Filter new jobs from aggregator
    fresh_urls = set()
    filtered = []
    seen_urls = set()
    for job in all_jobs:
        title = job.get("title", "")
        location = job.get("location", "")
        url = job.get("url") or job.get("absolute_url", "")

        if not matches_title(title):
            continue
        if not is_remote(location):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        fresh_urls.add(url)

        job["company"] = clean_company_name(job.get("company", ""))

        # Generate deterministic URL slug
        slug = re.sub(r'[^a-z0-9]+', '-', f"{job['company']} {title}".lower()).strip('-')
        slug = f"{slug}-{hashlib.md5(url.encode()).hexdigest()[:6]}"
        job["slug"] = slug

        # Merge with existing data: preserve first_seen, enrichment (description, salary, logo)
        if url in existing_jobs:
            old = existing_jobs[url]
            # Use the oldest known date as first_seen: existing first_seen > posted_at > now
            job["first_seen"] = old.get("first_seen") or old.get("posted_at") or now_str
            # Preserve enrichment data from scrape_details.py
            for key in ("description_html", "salary", "logo_url", "posted_at"):
                if key in old and key not in job:
                    job[key] = old[key]
        else:
            job["first_seen"] = now_str

        job["last_seen"] = now_str
        job["expired"] = False

        filtered.append(job)

    # Retain old jobs not in today's aggregator (within retention window)
    retained = 0
    expired = 0
    for url, old_job in existing_jobs.items():
        if url in fresh_urls:
            continue  # Already in filtered

        last_seen = old_job.get("last_seen", old_job.get("scraped_at", ""))
        if not last_seen:
            continue

        try:
            last_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            days_gone = (now - last_dt).days
        except (ValueError, AttributeError):
            continue

        if days_gone <= RETENTION_DAYS:
            old_job["expired"] = days_gone >= 7  # Mark as expired after 7 days missing
            filtered.append(old_job)
            retained += 1
            if old_job["expired"]:
                expired += 1

    # Sort: active jobs first by posted_at (most recent first), expired jobs last
    active = [j for j in filtered if not j.get("expired")]
    expired_jobs = [j for j in filtered if j.get("expired")]
    active.sort(key=lambda j: j.get("posted_at") or j.get("first_seen") or "1970-01-01", reverse=True)
    expired_jobs.sort(key=lambda j: j.get("last_seen", ""), reverse=True)
    filtered = active + expired_jobs

    output = {
        "last_updated": now_str,
        "total_jobs": len(active),
        "jobs": filtered,
    }

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(filtered)} jobs to {out_path} ({len(active)} active, {retained} retained, {expired} expired)")


if __name__ == "__main__":
    main()
