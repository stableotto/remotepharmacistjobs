#!/usr/bin/env python3
"""Aggregate moderated salary contributions into data/salary-contributions.json.

The site is static, so pages cannot query D1 at request time. Rendering
contributed pay client-side would also make it invisible to search engines,
which defeats the point of collecting it. So the build exports aggregates and
the generators read a plain JSON file.

This runs only when a D1 export is available; with no input it exits quietly
and the generators render no contributed section at all.

Usage in CI, before the generate steps:

    wrangler d1 execute remotepharmacistjobs --json --command \\
      "SELECT employer_slug, role_type, base_comp, comp_period, bonus, \\
              years_experience, remote_posture, state \\
         FROM salary_contributions WHERE status = 'approved'" \\
      > /tmp/contributions.json
    python scripts/export_contributions.py /tmp/contributions.json

Two rules are enforced here rather than in the templates, so they cannot be
forgotten at a call site:

  * a bucket is published only at n >= MIN_BUCKET
  * hourly and yearly are never mixed; hourly is annualised at 2080 h first
"""

import json
import os
import sys
from collections import defaultdict

OUT_PATH = "data/salary-contributions.json"
MIN_BUCKET = 5
HOURS_PER_YEAR = 2080


def annualise(row):
    comp = row["base_comp"]
    if row["comp_period"] == "hourly":
        comp *= HOURS_PER_YEAR
    return comp + (row.get("bonus") or 0)


def summarise(rows):
    values = sorted(annualise(r) for r in rows)
    n = len(values)
    if n < MIN_BUCKET:
        return None
    return {
        "n": n,
        "min": values[0],
        "max": values[-1],
        "median": values[n // 2],
        "average": round(sum(values) / n),
    }


def main():
    if len(sys.argv) < 2:
        print("No D1 export given; leaving contributed salary data untouched.")
        return
    with open(sys.argv[1]) as f:
        payload = json.load(f)

    # wrangler --json wraps results as [{"results": [...]}]
    if isinstance(payload, list) and payload and isinstance(payload[0], dict) \
            and "results" in payload[0]:
        rows = payload[0]["results"]
    elif isinstance(payload, dict) and "results" in payload:
        rows = payload["results"]
    else:
        rows = payload

    # Bucket by (employer, role), never by employer alone. A pharmacy
    # technician and a clinical pharmacist at the same employer are not the
    # same labour market, and averaging them produces a number that is wrong
    # in a way readers cannot see.
    by_employer = defaultdict(list)
    by_role = defaultdict(list)
    for row in rows:
        by_employer[(row["employer_slug"], row["role_type"])].append(row)
        by_role[row["role_type"]].append(row)

    out = {
        "_comment": (
            "Aggregated from moderated, user-contributed salary reports. Buckets "
            f"with fewer than {MIN_BUCKET} reports are omitted entirely. Generated "
            "by scripts/export_contributions.py — do not edit by hand."
        ),
        "min_bucket": MIN_BUCKET,
        "total_reports": len(rows),
        "by_employer": {},
        "by_role": {},
    }
    for (slug, role), group in by_employer.items():
        summary = summarise(group)
        if summary:
            summary["role_type"] = role
            out["by_employer"].setdefault(slug, []).append(summary)
    for slug in out["by_employer"]:
        out["by_employer"][slug].sort(key=lambda b: -b["n"])
    for role, group in by_role.items():
        summary = summarise(group)
        if summary:
            out["by_role"][role] = summary

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(f"Exported {len(rows)} approved reports "
          f"({sum(len(v) for v in out['by_employer'].values())} employer/role buckets, "
          f"{len(out['by_role'])} role buckets) to {OUT_PATH}")


if __name__ == "__main__":
    main()
