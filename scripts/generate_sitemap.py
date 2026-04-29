#!/usr/bin/env python3
"""Generate sitemap.xml for SEO."""

import json
import os
from datetime import datetime, timezone

SITE_URL = "https://remotepharmacistjobs.com"


def main():
    with open("site/jobs.json") as f:
        data = json.load(f)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = []

    # Static pages (extensionless to match Cloudflare Pages serving)
    urls.append(("", "1.0", "daily", today))
    urls.append(("about", "0.5", "monthly", today))
    urls.append(("post-a-job", "0.5", "monthly", today))
    urls.append(("categories", "0.8", "daily", today))
    urls.append(("salary", "0.7", "daily", today))

    # Category pages
    cat_dir = "site/category"
    if os.path.isdir(cat_dir):
        for fname in sorted(os.listdir(cat_dir)):
            if fname.endswith(".html"):
                name = fname[:-5]  # strip .html
                urls.append((f"category/{name}", "0.8", "daily", today))

    # Company pages
    company_dir = "site/companies"
    if os.path.isdir(company_dir):
        for fname in sorted(os.listdir(company_dir)):
            if fname.endswith(".html"):
                name = fname[:-5]  # strip .html
                urls.append((f"companies/{name}", "0.7", "daily", today))

    # Job detail pages
    for job in data.get("jobs", []):
        slug = job.get("slug")
        if slug:
            date = job.get("scraped_at", job.get("updated_at", today))
            if "T" in date:
                date = date.split("T")[0]
            urls.append((f"jobs/{slug}", "0.6", "weekly", date))

    # Build XML
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for path, priority, changefreq, lastmod in urls:
        url = f"{SITE_URL}/{path}" if path else f"{SITE_URL}/"
        xml_parts.append(f"""  <url>
    <loc>{url}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>""")

    xml_parts.append("</urlset>")

    sitemap = "\n".join(xml_parts) + "\n"
    with open("site/sitemap.xml", "w") as f:
        f.write(sitemap)

    print(f"Generated sitemap.xml with {len(urls)} URLs")


if __name__ == "__main__":
    main()
