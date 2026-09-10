#!/usr/bin/env python3
"""Employer entity layer.

Ingested jobs carry an employer name that is really an ATS board token
(`akamerica`, `flcancer`, `wvumedicine`). This module maps those tokens onto
curated employer records so the site can render a real company name.

Curated records live one-per-file in ``data/employers/*.json`` and are the
display source of truth. Ingest never overwrites them. A token with no curated
record resolves to ``None`` and is written to ``data/unmapped-employers.json``
for review — it is never given an invented name.
"""

import json
import os
import re
from collections import defaultdict
from urllib.parse import urlparse

EMPLOYER_DIR = "data/employers"
UNMAPPED_PATH = "data/unmapped-employers.json"

# Employer types. Keys are stored in records; values are display labels.
EMPLOYER_TYPES = {
    "pbm": "PBM",
    "health-plan": "Health plan",
    "telehealth": "Telehealth",
    "specialty-pharmacy": "Specialty pharmacy",
    "pharma": "Pharma / biotech",
    "health-system": "Health system",
    "mtm": "MTM vendor",
    "um-prior-auth": "UM / prior-auth vendor",
    "hit": "Health IT",
    "other": "Other",
}

REMOTE_POSTURES = {
    "fully-remote": "Fully remote",
    "hybrid": "Hybrid",
    "remote-by-state": "Remote, eligible by state",
}

# Workday subdomains that are shared tenants rather than one employer's board.
# Nothing here is treated as an identifying token.
_GENERIC_PATH_TOKENS = {
    "careers", "external", "external_careers", "global", "jobs",
    "job", "recruiting", "en-us", "search",
}


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower().strip()).strip("-")


def ats_tokens_for_url(url):
    """Return candidate ATS tokens for a job URL, most specific first.

    Tokens are namespaced by platform so that a Greenhouse board named `bmc`
    can never collide with a Workday tenant named `bmc`.
    """
    if not url:
        return []
    try:
        parsed = urlparse(url)
    except ValueError:
        return []
    host = (parsed.netloc or "").lower()
    parts = [p for p in (parsed.path or "").split("/") if p]
    tokens = []

    if host.endswith("myworkdayjobs.com"):
        # https://exactcare.wd1.myworkdayjobs.com/anewhealth_career_site/job/...
        # The tenant subdomain is the identity; the first path segment is the
        # career-site name, which is sometimes more specific and sometimes
        # generic ("external", "careers").
        sub = host.split(".")[0]
        if sub:
            tokens.append(f"workday:{sub}")
        if parts and parts[0].lower() not in _GENERIC_PATH_TOKENS:
            tokens.append(f"workday-site:{parts[0].lower()}")
    elif "greenhouse.io" in host:
        if parts:
            tokens.append(f"greenhouse:{parts[0].lower()}")
    elif "lever.co" in host:
        if parts:
            tokens.append(f"lever:{parts[0].lower()}")
    elif "ashbyhq.com" in host:
        if parts:
            tokens.append(f"ashby:{parts[0].lower()}")
    elif "paylocity.com" in host:
        # Paylocity job URLs carry no employer identifier at all, only a
        # numeric posting id. Nothing usable — fall back to the name token.
        pass
    elif host:
        # Employer's own careers page, usually a Greenhouse embed
        # (www.houserx.com/careers?gh_jid=...). Use the registrable label.
        label = host.replace("www.", "").split(".")[0]
        if label:
            tokens.append(f"site:{label}")

    return tokens


def job_tokens(job):
    """All tokens a job could be matched on, including the name fallback."""
    tokens = ats_tokens_for_url(job.get("url") or job.get("absolute_url", ""))
    name_slug = slugify(job.get("company", ""))
    if name_slug:
        tokens.append(f"name:{name_slug}")
    return tokens


def load_employers(directory=EMPLOYER_DIR):
    """Load curated employer records, keyed by slug."""
    employers = {}
    if not os.path.isdir(directory):
        return employers
    for fname in sorted(os.listdir(directory)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(directory, fname)
        with open(path) as f:
            record = json.load(f)
        slug = record.get("slug") or fname[:-5]
        record["slug"] = slug
        if slug in employers:
            raise ValueError(f"Duplicate employer slug {slug!r} in {path}")
        employers[slug] = record
    return employers


def build_token_index(employers):
    """Map every declared ats_token to its employer slug."""
    index = {}
    for slug, record in employers.items():
        for token in record.get("ats_tokens", []):
            token = token.lower()
            if token in index and index[token] != slug:
                raise ValueError(
                    f"Token {token!r} claimed by both {index[token]!r} and {slug!r}"
                )
            index[token] = slug
    return index


def resolve(job, employers, index):
    """Return the curated employer record for a job, or None."""
    for token in job_tokens(job):
        slug = index.get(token.lower())
        if slug:
            return employers[slug]
    return None


def group_jobs(jobs, employers, index):
    """Split jobs into (resolved: slug -> jobs, unresolved: key -> jobs).

    Unresolved jobs are grouped by their most specific token so the review
    queue has one row per real board, not one per job.
    """
    resolved = defaultdict(list)
    unresolved = defaultdict(list)
    for job in jobs:
        record = resolve(job, employers, index)
        if record:
            resolved[record["slug"]].append(job)
        else:
            tokens = job_tokens(job)
            unresolved[tokens[0] if tokens else "name:unknown"].append(job)
    return resolved, unresolved


def write_unmapped(unresolved, path=UNMAPPED_PATH):
    """Write the review queue. One entry per unmapped board token."""
    entries = []
    for token, jobs in sorted(unresolved.items()):
        active = [j for j in jobs if not j.get("expired")]
        entries.append({
            "ats_token": token,
            "ingested_name": jobs[0].get("company", ""),
            "job_count": len(jobs),
            "active_job_count": len(active),
            "sample_titles": sorted({j.get("title", "") for j in jobs})[:5],
            "sample_url": jobs[0].get("url", ""),
            "ats": jobs[0].get("ats", ""),
        })
    entries.sort(key=lambda e: (-e["active_job_count"], e["ats_token"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "_comment": (
            "Employers seen in the feed with no curated record in data/employers/. "
            "They render with a generic template under their ATS token and are NOT "
            "given an invented display name. To fix one: add a record to "
            "data/employers/<slug>.json listing this ats_token."
        ),
        "count": len(entries),
        "employers": entries,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return entries


# ── Derived facts (computed from the feed, never curated) ──

def salary_range(jobs):
    """Annualized salary range across jobs, with n. None if nothing parses.

    Mirrors generate_salary_page.py: hourly x 2080, monthly x 12. Ranges wider
    than 4x are dropped as parse errors, per CLAUDE.md.
    """
    mids, lows, highs = [], [], []
    for job in jobs:
        sal = job.get("salary")
        if not sal or sal.get("min") is None:
            continue
        low = sal["min"]
        high = sal.get("max") or low
        period = sal.get("period", "yearly")
        factor = {"hourly": 2080, "monthly": 12}.get(period, 1)
        low, high = low * factor, high * factor
        if low <= 0 or high <= 0:
            continue
        if high / low > 4:
            continue
        lows.append(low)
        highs.append(high)
        mids.append((low + high) / 2)
    if not mids:
        return None
    return {
        "n": len(mids),
        "min": min(lows),
        "max": max(highs),
        "avg": sum(mids) / len(mids),
    }


def role_types(jobs, limit=8):
    """Distinct job titles observed, most frequent first."""
    counts = defaultdict(int)
    for job in jobs:
        title = (job.get("title") or "").strip()
        if title:
            counts[title] += 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [title for title, _ in ranked[:limit]]
