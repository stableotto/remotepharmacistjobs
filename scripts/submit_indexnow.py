#!/usr/bin/env python3
"""Tell IndexNow (Bing, ChatGPT search, Yandex, ...) which pages changed in the last commit.

Runs in the daily workflow after the Cloudflare Pages deploy, using the commit it just made.
Sitemap URLs are extensionless, so the submitted URLs are too.
"""

import json
import re
import subprocess
import urllib.request

SITE_URL = "https://remotepharmacistjobs.com"
HOST = "remotepharmacistjobs.com"
INDEXNOW_KEY = "dcf0a6672bb88e3996e80af72d267cd3"


def sitemap_urls(rev):
    out = subprocess.run(
        ["git", "show", f"{rev}:site/sitemap.xml"],
        capture_output=True, text=True,
    ).stdout
    return set(re.findall(r"<loc>([^<]+)</loc>", out))


def changed_urls():
    # Most pages change daily (relative dates, similar jobs), so only report URLs that
    # entered or left the sitemap (new and expired jobs), plus the homepage.
    before, after = sitemap_urls("HEAD~1"), sitemap_urls("HEAD")
    return sorted((before ^ after) | {SITE_URL})


def main():
    urls = changed_urls()
    if not urls:
        print("No changed pages to submit")
        return
    body = json.dumps({
        "host": HOST,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": urls[:10000],
    }).encode()
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f"Submitted {len(urls)} URLs to IndexNow: HTTP {resp.status}")


if __name__ == "__main__":
    main()
