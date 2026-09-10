#!/usr/bin/env python3
"""Generate the employer directory from curated records in data/employers/.

Employer pages are durable reference pages, not job listings. A page must be
worth reading with zero open roles, so curated description, type, licensure
expectation and careers link come first and openings come last.

Two rules this script exists to enforce:

* No employer is ever rendered under a raw ATS board token. A token with no
  curated record gets a generic, noindexed page and a row in
  data/unmapped-employers.json.
* No employer page is ever deleted. Pages persist after the last job expires;
  slug changes emit a 301 into site/_redirects.
"""

import html
import json
import os
import re
import sys
from collections import defaultdict
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import employers as E

SITE_URL = "https://remotepharmacistjobs.com"
REDIRECTS_PATH = "site/_redirects"
# Company pages that existed before the employer directory and were deleted by
# the old "remove pages with no active jobs" sweep. They 301 to the directory
# so previously indexed URLs keep their value instead of serving a 404.
LEGACY_REDIRECTS_PATH = "data/legacy-company-slugs.json"

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


def esc(s):
    return html.escape(s or "")


def money(v):
    return f"${v:,.0f}"


def build_logo_html(name, logo_url, size="large"):
    color = get_avatar_color(name)
    initial = esc(name[0].upper()) if name else "?"
    cls_img, cls_fb = ("company-hero-logo", "company-hero-logo-fallback") if size == "large" \
        else ("job-logo", "job-logo-fallback")
    if logo_url and logo_url.startswith("logos/"):
        logo_url = f"../{logo_url}"
    if logo_url:
        return (
            f'<img class="{cls_img}" src="{esc(logo_url)}" alt="{esc(name)} logo" loading="lazy" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<div class="{cls_fb}" style="background-color:{color};display:none">{initial}</div>'
        )
    return f'<div class="{cls_fb}" style="background-color:{color}">{initial}</div>'


def build_job_row_html(job, employer_name):
    title = esc(job.get("title", ""))
    location = esc(job.get("location", ""))
    slug = job.get("slug", "")
    detail_url = f"../jobs/{slug}" if slug else esc(job.get("url", "#"))
    color = get_avatar_color(employer_name)
    initial = esc(employer_name[0].upper()) if employer_name else "?"
    logo_url = job.get("logo_url", "")

    meta_parts = [esc(employer_name)]
    salary = job.get("salary")
    if salary and salary.get("display"):
        meta_parts.append(f'<span class="meta-salary">{esc(salary["display"])}</span>')
    meta_line = '<span class="meta-dot"> · </span>'.join(meta_parts)

    if logo_url:
        if logo_url.startswith("logos/"):
            logo_url = f"../{logo_url}"
        logo_html = (
            f'<img class="job-logo" src="{esc(logo_url)}" alt="" loading="lazy" '
            f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
            f'<div class="job-logo-fallback" style="background-color:{color};display:none">{initial}</div>'
        )
    else:
        logo_html = f'<div class="job-logo-fallback" style="background-color:{color}">{initial}</div>'

    return f'''<a href="{esc(detail_url)}" class="job-row">
      <div class="job-row-left">
        <div class="job-logo-wrap">{logo_html}</div>
        <div class="job-row-info">
          <div class="job-row-title">{title}</div>
          <div class="job-row-meta">{meta_line}</div>
        </div>
      </div>
      <div class="job-row-right">
        <div class="job-row-location">{location}</div>
      </div>
    </a>'''


NAV = """  <nav class="site-nav">
    <div class="site-nav-inner">
      <a href="../" class="site-nav-logo">
        <img src="../logo.svg" alt="Remote Pharmacist Jobs" height="32">
      </a>
      <button class="nav-toggle" aria-label="Menu" onclick="this.nextElementSibling.classList.toggle('open')">
        <span></span><span></span><span></span>
      </button>
      <div class="site-nav-links">
        <a href="../">Jobs</a>
        <a href="../companies/">Companies</a>
        <a href="../categories">Categories</a>
        <a href="../salary">Salary</a>
        <a href="../about">About</a>
        <a href="../post-a-job" class="nav-cta">Post a Job</a>
      </div>
    </div>
  </nav>"""

FOOTER = """  <footer class="site-footer">
    <div class="site-footer-inner">
      <div class="footer-col">
        <h4>Remote Pharmacist Jobs</h4>
        <p>Direct listings only. No recruiters, no middlemen.</p>
      </div>
      <div class="footer-col">
        <h4>Navigate</h4>
        <a href="../">Jobs</a>
        <a href="../companies/">Companies</a>
        <a href="../categories">Categories</a>
        <a href="../salary">Salary</a>
        <a href="../about">About</a>
        <a href="../post-a-job">Post a Job</a>
      </div>
    </div>
  </footer>"""

COMPANY_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="/analytics.js"></script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title}</title>
  <meta name="description" content="${meta_description}">${robots}
  <meta property="og:title" content="${title}">
  <meta property="og:description" content="${meta_description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="${canonical_url}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="${title}">
  <meta name="twitter:description" content="${meta_description}">
  <link rel="canonical" href="${canonical_url}">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link href="https://fonts.cdnfonts.com/css/geist" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
  <script type="application/ld+json">
${json_ld}
  </script>
</head>
<body>
${nav}

  <div class="container detail-page">
    <nav class="breadcrumb">
      <a href="../">Home</a> &rsaquo; <a href="../companies/">Companies</a> &rsaquo; <span>${name}</span>
    </nav>

    <div class="company-hero">
      ${logo_html}
      <div class="company-hero-text">
        <h1>${heading}</h1>
        <p>${tagline}</p>
      </div>
    </div>

    <div class="detail-pills">${pills}</div>

    <div class="detail-page-layout">
      <div class="detail-main">
${body}
      </div>
      <aside class="detail-sidebar">
${sidebar}
      </aside>
    </div>

    <div class="browse-categories">
      <h2>${related_heading}</h2>
      <div class="category-links">
${related}
      </div>
    </div>
  </div>

${footer}
</body>
</html>
""")

INDEX_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="/analytics.js"></script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Companies Hiring Remote Pharmacists | Remote Pharmacist Jobs</title>
  <meta name="description" content="A directory of ${count} employers that hire remote pharmacists and pharmacy technicians — PBMs, health plans, telehealth, specialty pharmacy and health systems. Direct listings only.">
  <meta property="og:title" content="Companies Hiring Remote Pharmacists">
  <meta property="og:description" content="A directory of ${count} employers that hire remote pharmacists and pharmacy technicians. Direct employer listings only.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="${site}/companies">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="${site}/companies">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link href="https://fonts.cdnfonts.com/css/geist" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
  <script type="application/ld+json">
${json_ld}
  </script>
</head>
<body>
${nav}

  <div class="container">
    <div class="category-hero">
      <h1>Companies Hiring Remote Pharmacists</h1>
      <p>${count} employers that hire pharmacists and pharmacy technicians into remote roles — who they are, what they hire for, and whether they expect licensure in more than one state. Every listing links directly to the employer. ${open_note}</p>
    </div>

    <div class="search-wrapper">
      <input type="search" id="employer-search" placeholder="Search employers by name or role type"
             aria-label="Search employers" autocomplete="off">
    </div>

    <div class="detail-pills" id="employer-filters">
      <button type="button" class="pill" data-filter="all" aria-pressed="true">All (${count})</button>
      <button type="button" class="pill" data-filter="open" aria-pressed="false">Hiring now (${open_count})</button>
${type_filters}
    </div>

    <div class="category-grid" id="employer-grid">
${cards}
    </div>

    <p class="no-results" id="employer-empty" hidden>No employers match that filter.</p>

    <div class="browse-categories">
      <h2>Browse by role instead</h2>
      <div class="category-links">
${category_links}
      </div>
    </div>
  </div>

${footer}
  <script>
  // Progressive enhancement only: the full, unfiltered directory above is
  // already in the HTML. This narrows what is shown; it never fetches.
  (function () {
    var grid = document.getElementById('employer-grid');
    if (!grid) return;
    var cards = Array.prototype.slice.call(grid.querySelectorAll('.category-card'));
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll('#employer-filters .pill'));
    var search = document.getElementById('employer-search');
    var empty = document.getElementById('employer-empty');
    var active = 'all';

    function apply() {
      var q = (search.value || '').trim().toLowerCase();
      var shown = 0;
      cards.forEach(function (card) {
        var okFilter =
          active === 'all' ||
          (active === 'open' && card.dataset.open === 'true') ||
          card.dataset.type === active;
        var okSearch = !q || (card.dataset.search || '').indexOf(q) !== -1;
        var show = okFilter && okSearch;
        card.hidden = !show;
        if (show) shown++;
      });
      empty.hidden = shown !== 0;
    }

    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        active = btn.dataset.filter;
        buttons.forEach(function (b) {
          b.setAttribute('aria-pressed', String(b === btn));
          b.style.borderColor = b === btn ? '#7c3aed' : '';
        });
        apply();
      });
    });
    search.addEventListener('input', apply);
  })();
  </script>
</body>
</html>
""")


def build_sidebar(record, jobs, salary, generic):
    """Facts panel. Curated facts carry their source and last_verified date."""
    rows = []
    if not generic:
        etype = E.EMPLOYER_TYPES.get(record.get("employer_type", ""), "")
        if etype:
            rows.append(("Type", esc(etype)))
        posture = E.REMOTE_POSTURES.get(record.get("remote_posture", ""), "")
        if posture:
            rows.append(("Remote", esc(posture)))
        ms = (record.get("multi_state_licensure") or {}).get("expected")
        if ms is True:
            rows.append(("Licensure", 'Expects multiple states'))
        elif ms is False:
            rows.append(("Licensure", 'Usually single state'))
    active = [j for j in jobs if not j.get("expired")]
    rows.append(("Open roles", str(len(active)) if active else "None right now"))

    cards = []
    if rows:
        info = "\n".join(
            f'          <div class="sidebar-info-row">'
            f'<span class="sidebar-info-label">{label}</span>'
            f'<span class="sidebar-info-value">{value}</span></div>'
            for label, value in rows
        )
        cards.append(
            '        <div class="sidebar-card">\n'
            '          <div class="sidebar-card-title">At a glance</div>\n'
            f'{info}\n'
            '        </div>'
        )

    if salary:
        n = salary["n"]
        cards.append(
            '        <div class="sidebar-card">\n'
            '          <div class="sidebar-card-title">Pay seen on this site</div>\n'
            f'          <div class="sidebar-info-row"><span class="sidebar-info-label">Range</span>'
            f'<span class="sidebar-info-value">{money(salary["min"])} &ndash; {money(salary["max"])}</span></div>\n'
            f'          <div class="sidebar-info-row"><span class="sidebar-info-label">Average</span>'
            f'<span class="sidebar-info-value">{money(salary["avg"])}</span></div>\n'
            f'          <div class="sidebar-info-row"><span class="sidebar-info-label">Based on</span>'
            f'<span class="sidebar-info-value">{n} listing{"s" if n != 1 else ""}</span></div>\n'
            '          <p style="font-size:0.8rem;color:#9ca3af;margin-top:12px">'
            'Annualised from pay ranges published in this employer&rsquo;s own listings. '
            'A small sample is not a salary benchmark.</p>\n'
            '        </div>'
        )

    careers = record.get("careers_url")
    if careers and not generic:
        cards.append(
            '        <div class="sidebar-card">\n'
            '          <div class="sidebar-card-title">Apply direct</div>\n'
            f'          <a class="apply-button" href="{esc(careers)}" rel="noopener nofollow" '
            f'target="_blank">{esc(record["name"])} careers &rarr;</a>\n'
            '        </div>'
        )

    sources = record.get("sources") or []
    if sources and not generic:
        items = "\n".join(
            f'          <div class="sidebar-info-row"><a href="{esc(s["url"])}" '
            f'rel="noopener nofollow" target="_blank">{esc(s.get("what") or "Source")}</a></div>'
            for s in sources
        )
        cards.append(
            '        <div class="sidebar-card">\n'
            '          <div class="sidebar-card-title">Sources</div>\n'
            f'{items}\n'
            f'          <p style="font-size:0.8rem;color:#9ca3af;margin-top:12px">'
            f'Last verified {esc(record.get("last_verified", ""))}.</p>\n'
            '        </div>'
        )
    return "\n".join(cards)


def build_body(record, jobs, generic):
    """Main column. Reads top to bottom even when there are no open roles."""
    name = record["name"]
    active = [j for j in jobs if not j.get("expired")]
    parts = []

    if generic:
        parts.append(
            '        <div class="content-section">\n'
            f'          <p>We have seen remote pharmacy roles posted from this employer&rsquo;s '
            f'applicant tracking system, but we have not yet confirmed who the employer is. '
            f'Rather than publish a company name derived from a job-board URL, we leave it blank '
            f'until someone verifies it. The roles below link straight to the original posting.</p>\n'
            '        </div>'
        )
    else:
        parts.append(
            '        <div class="content-section">\n'
            f'          <h2>About {esc(name)}</h2>\n'
            f'          <p>{esc(record["description"])}</p>\n'
            '        </div>'
        )
        aka = [a for a in record.get("aka", []) if a]
        if aka:
            parts.append(
                '        <div class="content-section">\n'
                '          <h2>Also known as</h2>\n'
                f'          <p>{esc(", ".join(aka))}. '
                'Job listings may appear under any of these names.</p>\n'
                '        </div>'
            )
        note = (record.get("multi_state_licensure") or {}).get("note")
        if note:
            ms = record["multi_state_licensure"].get("expected")
            heading = "Licensure expectation"
            body = esc(note)
            if ms:
                body += (
                    ' If you are weighing which licences to add, our '
                    '<a href="../licensure/">state licensure guide</a> covers reciprocity and '
                    'what each board asks for.'
                )
            parts.append(
                '        <div class="content-section">\n'
                f'          <h2>{heading}</h2>\n'
                f'          <p>{body}</p>\n'
                '        </div>'
            )

    roles = E.role_types(jobs)
    if roles:
        items = "".join(f'<li>{esc(r)}</li>' for r in roles)
        parts.append(
            '        <div class="content-section">\n'
            '          <h2>Pharmacy roles they hire for</h2>\n'
            '          <p>Remote roles we have seen posted here:</p>\n'
            f'          <ul class="values-list">{items}</ul>\n'
            '        </div>'
        )

    if active:
        rows = "\n".join(build_job_row_html(j, name) for j in active)
        parts.append(
            '        <div class="content-section">\n'
            f'          <h2>Open remote roles ({len(active)})</h2>\n'
            f'          <div class="jobs-list">\n{rows}\n          </div>\n'
            '        </div>'
        )
    else:
        parts.append(
            '        <div class="content-section">\n'
            '          <h2>Open remote roles</h2>\n'
            '          <p class="no-results">No open remote pharmacy roles here right now. '
            'This page stays up so you can check back &mdash; and the '
            '<a href="../">jobs feed</a> updates daily.</p>\n'
            '        </div>'
        )
    return "\n".join(parts)


def build_json_ld(record, jobs, canonical, generic):
    graph = [{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Companies", "item": f"{SITE_URL}/companies"},
            {"@type": "ListItem", "position": 3, "name": record["name"], "item": canonical},
        ],
    }]
    if not generic:
        org = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": record["name"],
            "description": record["description"],
            "url": record.get("homepage") or canonical,
        }
        aka = [a for a in record.get("aka", []) if a]
        if aka:
            org["alternateName"] = aka
        if record.get("logo"):
            org["logo"] = f"{SITE_URL}/{record['logo']}"
        same_as = [s["url"] for s in record.get("sources", []) if s.get("url")]
        if record.get("homepage"):
            same_as = [record["homepage"]] + [u for u in same_as if u != record["homepage"]]
        if same_as:
            org["sameAs"] = same_as
        graph.insert(0, org)
    return json.dumps(graph, indent=2, ensure_ascii=False)


def write_redirects(entries, existing_slugs):
    """301 old company URLs at their new employer page. Never 404 a live URL."""
    lines = [
        "# Generated by scripts/generate_company_pages.py — do not edit by hand.",
        "# Employer slugs are derived from the canonical company name, so a company",
        "# previously published under its raw ATS board token needs a redirect.",
    ]
    seen = set()
    for old, new in sorted(entries):
        if old == new or old in seen:
            continue
        seen.add(old)
        lines.append(f"/companies/{old} /companies/{new} 301")
        lines.append(f"/companies/{old}.html /companies/{new} 301")

    legacy = []
    if os.path.exists(LEGACY_REDIRECTS_PATH):
        with open(LEGACY_REDIRECTS_PATH) as f:
            legacy = json.load(f).get("slugs", [])
    lines.append("")
    lines.append("# Company pages published before the employer directory and later removed")
    lines.append("# by the old 'delete pages with no active jobs' sweep. Sent to the directory")
    lines.append("# rather than left as 404s.")
    for slug in sorted(set(legacy)):
        if slug in seen or slug in existing_slugs:
            continue
        seen.add(slug)
        lines.append(f"/companies/{slug} /companies/ 301")
        lines.append(f"/companies/{slug}.html /companies/ 301")

    with open(REDIRECTS_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    return len([ln for ln in lines if ln.startswith("/companies/")])


def main():
    with open("site/jobs.json") as f:
        data = json.load(f)
    all_jobs = data.get("jobs", [])

    store = E.load_employers()
    index = E.build_token_index(store)
    resolved, unresolved = E.group_jobs(all_jobs, store, index)
    unmapped_rows = E.write_unmapped(unresolved)

    os.makedirs("site/companies", exist_ok=True)

    # Every curated employer gets a page, including those with no jobs at all —
    # that durability is the point of the directory.
    pages = []
    for slug, record in store.items():
        jobs = resolved.get(slug, [])
        pages.append((slug, record, jobs, False))

    # Unmapped boards keep their existing URL but render generically and noindex.
    for token, jobs in unresolved.items():
        slug = E.slugify(jobs[0].get("company", "")) or E.slugify(token)
        record = {
            "slug": slug,
            "name": "Employer not yet verified",
            "aka": [],
            "homepage": "",
            "careers_url": "",
            "logo": "",
            "description": "",
            "sources": [],
        }
        pages.append((slug, record, jobs, True))

    existing_slugs = {slug for slug, _, _, _ in pages}

    # Sort for the index: hiring now first, then by open count, then name.
    def sort_key(item):
        _, record, jobs, generic = item
        active = len([j for j in jobs if not j.get("expired")])
        return (0 if active else 1, -active, record["name"].lower())

    listed = sorted(
        [p for p in pages if not p[3] and not p[1].get("out_of_scope")],
        key=sort_key,
    )

    redirect_pairs = []
    written = 0
    for slug, record, jobs, generic in pages:
        active = [j for j in jobs if not j.get("expired")]
        salary = E.salary_range(jobs)
        canonical = f"{SITE_URL}/companies/{slug}"
        name = record["name"]
        out_of_scope = record.get("out_of_scope")

        # Old URLs this employer used to live at, from the ingested names.
        for job in jobs:
            old = E.slugify(job.get("company", ""))
            if old and old != slug:
                redirect_pairs.append((old, slug))

        if generic:
            title = "Employer pending verification | Remote Pharmacist Jobs"
            heading = "Employer pending verification"
            meta_desc = ("A remote pharmacy role posted from an employer we have not yet "
                         "verified. The listing links to the original posting.")
            tagline = "We publish a company name only once we can source it."
        else:
            noun = "remote pharmacy jobs"
            title = f"{name} Remote Pharmacy Jobs & Company Profile | Remote Pharmacist Jobs"
            heading = f"{name}"
            if active:
                meta_desc = (f"{len(active)} open remote pharmacy role"
                             f"{'s' if len(active) != 1 else ''} at {name}. "
                             f"What they do, what they hire for and licensure expectations. "
                             f"Apply directly — no recruiters.")
                tagline = (f"{len(active)} open remote role"
                           f"{'s' if len(active) != 1 else ''} right now.")
            else:
                meta_desc = (f"{name} and {noun}: what they do, the pharmacy roles they hire "
                             f"remotely, and whether they expect multi-state licensure.")
                tagline = "No open remote roles here right now."

        robots = ""
        if generic or out_of_scope:
            robots = '\n  <meta name="robots" content="noindex, follow">'

        pills = []
        if not generic:
            etype = E.EMPLOYER_TYPES.get(record.get("employer_type", ""))
            if etype:
                pills.append(f'<span class="pill">{esc(etype)}</span>')
            posture = E.REMOTE_POSTURES.get(record.get("remote_posture", ""))
            if posture:
                pills.append(f'<span class="pill">{esc(posture)}</span>')
        if active:
            pills.append(f'<span class="pill">{len(active)} open role'
                         f'{"s" if len(active) != 1 else ""}</span>')
        if out_of_scope:
            pills.append('<span class="pill">Not a pharmacy practice role</span>')

        # Related employers: same type first — real internal linking, not a dump.
        same_type = [
            p for p in listed
            if p[0] != slug and p[1].get("employer_type") == record.get("employer_type")
        ]
        related_pool = (same_type + [p for p in listed if p[0] != slug and p not in same_type])[:12]
        related_heading = "Similar employers hiring remote pharmacists"
        if same_type and not generic:
            label = E.EMPLOYER_TYPES.get(record.get("employer_type", ""), "")
            if label:
                related_heading = f"Other {label.lower()} employers hiring remote pharmacists"
        related = "\n".join(
            f'        <a href="{p[0]}" class="category-link">{esc(p[1]["name"])}'
            f'<span>({len([j for j in p[2] if not j.get("expired")])})</span></a>'
            for p in related_pool
        )

        page = COMPANY_TEMPLATE.substitute(
            title=esc(title),
            meta_description=esc(meta_desc),
            canonical_url=canonical,
            robots=robots,
            json_ld=build_json_ld(record, jobs, canonical, generic),
            nav=NAV,
            footer=FOOTER,
            name=esc(name),
            heading=esc(heading),
            tagline=esc(tagline),
            logo_html=build_logo_html(name, record.get("logo", ""), "large"),
            pills="".join(pills),
            body=build_body(record, jobs, generic),
            sidebar=build_sidebar(record, jobs, salary, generic),
            related_heading=esc(related_heading),
            related=related,
        )
        with open(f"site/companies/{slug}.html", "w") as f:
            f.write(page)
        written += 1

    # ── Index ──
    type_counts = defaultdict(int)
    for _, record, jobs, _ in listed:
        type_counts[record.get("employer_type", "other")] += 1
    type_filters = "\n".join(
        f'      <button type="button" class="pill" data-filter="{key}" aria-pressed="false">'
        f'{esc(E.EMPLOYER_TYPES[key])} ({type_counts[key]})</button>'
        for key in E.EMPLOYER_TYPES if type_counts.get(key)
    )

    cards = []
    for slug, record, jobs, _ in listed:
        active = len([j for j in jobs if not j.get("expired")])
        etype = E.EMPLOYER_TYPES.get(record.get("employer_type", ""), "")
        roles = E.role_types(jobs, limit=3)
        search_blob = " ".join(
            [record["name"]] + record.get("aka", []) + [etype] + roles
        ).lower()
        blurb = record["description"].split(". ")[0]
        if len(blurb) > 150:
            blurb = blurb[:147].rsplit(" ", 1)[0] + "…"
        elif not blurb.endswith("."):
            blurb += "."
        count_label = (f"{active} open role{'s' if active != 1 else ''}"
                       if active else "No open roles right now")
        cards.append(
            f'      <a href="{slug}" class="category-card" '
            f'data-type="{esc(record.get("employer_type", "other"))}" '
            f'data-open="{"true" if active else "false"}" '
            f'data-search="{esc(search_blob)}">'
            f'<h3>{esc(record["name"])}</h3>'
            f'<p>{esc(blurb)}</p>'
            f'<span class="category-count">{esc(etype)} · {count_label}</span>'
            f'</a>'
        )

    open_count = len([p for p in listed if any(not j.get("expired") for j in p[2])])
    category_links = "\n".join(
        f'        <a href="../category/{s}" class="category-link">{esc(lbl)}</a>'
        for s, lbl in [
            ("clinical-pharmacist", "Clinical Pharmacist"),
            ("pharmacy-technician", "Pharmacy Technician"),
            ("managed-care-pharmacist", "Managed Care"),
            ("specialty-pharmacy", "Specialty Pharmacy"),
            ("prior-authorization", "Prior Authorization"),
            ("medication-therapy-management", "MTM"),
        ] if os.path.exists(f"site/category/{s}.html")
    )

    index_ld = json.dumps([
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "Companies Hiring Remote Pharmacists",
            "url": f"{SITE_URL}/companies",
            "description": (f"A directory of {len(listed)} employers that hire remote "
                            f"pharmacists and pharmacy technicians."),
        },
        {
            "@context": "https://schema.org",
            "@type": "ItemList",
            "numberOfItems": len(listed),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "url": f"{SITE_URL}/companies/{slug}", "name": record["name"]}
                for i, (slug, record, _, _) in enumerate(listed)
            ],
        },
    ], indent=2, ensure_ascii=False)

    index_html = INDEX_TEMPLATE.substitute(
        site=SITE_URL,
        count=len(listed),
        open_count=open_count,
        open_note=(f"{open_count} are hiring right now; the rest stay listed so you can "
                   f"check back." if open_count < len(listed) else ""),
        type_filters=type_filters,
        cards="\n".join(cards),
        category_links=category_links,
        json_ld=index_ld,
        nav=NAV,
        footer=FOOTER,
    )
    with open("site/companies/index.html", "w") as f:
        f.write(index_html)

    n_redirects = write_redirects(redirect_pairs, existing_slugs)

    # Remove pages superseded by a redirect. Cloudflare Pages serves a static
    # file in preference to a _redirects rule, so leaving the old page on disk
    # would keep the stale URL live and duplicate the new one. A page is only
    # ever removed when a redirect covers its URL — never silently.
    covered = set()
    with open(REDIRECTS_PATH) as f:
        for line in f:
            m = re.match(r"^/companies/([^/\s.]+)\s", line)
            if m:
                covered.add(m.group(1))
    keep = existing_slugs | {"index"}
    removed = []
    orphaned = []
    for fname in sorted(os.listdir("site/companies")):
        if not fname.endswith(".html"):
            continue
        slug = fname[:-5]
        if slug in keep:
            continue
        if slug in covered:
            os.remove(os.path.join("site/companies", fname))
            removed.append(slug)
        else:
            orphaned.append(slug)
    if orphaned:
        raise SystemExit(
            "Refusing to leave company pages without a redirect: "
            + ", ".join(orphaned)
        )

    print(f"Generated {written} employer pages + index in site/companies/")
    print(f"  superseded pages  : {len(removed)} removed, each 301'd to its new URL")
    print(f"  curated employers : {len(store)}")
    print(f"  with open roles   : {open_count}")
    print(f"  unmapped boards   : {len(unmapped_rows)} (see {E.UNMAPPED_PATH})")
    print(f"  redirect lines    : {n_redirects} (see {REDIRECTS_PATH})")


if __name__ == "__main__":
    main()
