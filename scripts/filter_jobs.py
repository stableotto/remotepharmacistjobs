#!/usr/bin/env python3
"""Download all_jobs.json from job-board-aggregator releases and filter to remote pharmacist jobs."""

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


def main():
    print("Fetching latest release info...")
    resp = requests.get(RELEASE_API, timeout=30)
    resp.raise_for_status()
    release = resp.json()

    asset_url = None
    for asset in release.get("assets", []):
        if asset["name"] == "all_jobs.json":
            asset_url = asset["browser_download_url"]
            break

    if not asset_url:
        print("ERROR: all_jobs.json not found in latest release assets")
        sys.exit(1)

    print(f"Downloading all_jobs.json from {asset_url}...")
    resp = requests.get(asset_url, timeout=300)
    resp.raise_for_status()
    all_jobs = resp.json()
    print(f"Downloaded {len(all_jobs):,} total jobs")

    # Filter
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

        job["company"] = clean_company_name(job.get("company", ""))

        # Generate deterministic URL slug
        slug = re.sub(r'[^a-z0-9]+', '-', f"{job['company']} {title}".lower()).strip('-')
        slug = f"{slug}-{hashlib.md5(url.encode()).hexdigest()[:6]}"
        job["slug"] = slug

        filtered.append(job)

    # Sort by scraped_at descending
    filtered.sort(key=lambda j: j.get("scraped_at", ""), reverse=True)

    output = {
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_jobs": len(filtered),
        "jobs": filtered,
    }

    out_path = "site/jobs.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(filtered)} jobs to {out_path}")


if __name__ == "__main__":
    main()
