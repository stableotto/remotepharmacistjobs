#!/usr/bin/env python3
"""Generate the licensure navigator: /licensure/ and /licensure/{state}.

High-risk content. Rules from CLAUDE.md that this script enforces:

* Every published state page links to that state's board of pharmacy.
  A record with no board link is a stub: noindex, and kept out of the
  sitemap and the comparison table.
* Every page renders its last_verified date.
* Fees and processing times are labelled approximate and as-of-date. Values
  that could not be sourced render as an em dash, never as an estimate.
* Framed as a starting point for research, never as legal advice.
"""

import html
import json
import os
import sys
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import employers as E

SITE_URL = "https://remotepharmacistjobs.com"
DATA_DIR = "data/licensure"
OUT_DIR = "site/licensure"
NABP_ELTP = "https://nabp.pharmacy/programs/licensure/licensure-transfer/"
NABP_PDF = "https://nabp.pharmacy/wp-content/uploads/Licensure-Transfer-General-Requirements.pdf"
EM_DASH = "&mdash;"

DISCLAIMER = (
    "This page is a starting point for research, not legal advice. Licensure "
    "rules change and boards are the only authority on their own requirements "
    "&mdash; confirm everything with the board before you pay a fee or accept a role."
)


def esc(s):
    return html.escape(s or "")


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
        <a href="../licensure/">Licensure</a>
        <a href="../salary">Salary</a>
        <a href="../about">About</a>
      </div>
    </div>
  </footer>"""

PAGE = Template("""\
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
  <meta property="og:type" content="article">
  <meta property="og:url" content="${canonical}">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="${canonical}">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <link href="https://fonts.cdnfonts.com/css/geist" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
  <script type="application/ld+json">
${json_ld}
  </script>
</head>
<body>
${nav}

  <div class="container content-page">
    <nav class="breadcrumb">
      <a href="../">Home</a> &rsaquo; ${crumb}
    </nav>

    <div class="content-hero">
      <h1>${heading}</h1>
      <p>${lede}</p>
    </div>

${body}

    <div class="content-section">
      <p style="font-size:0.85rem;color:#9ca3af">${disclaimer}${verified}</p>
    </div>
  </div>

${footer}
</body>
</html>
""")


def load_states():
    states = []
    for fname in sorted(os.listdir(DATA_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(DATA_DIR, fname)) as f:
                states.append(json.load(f))
    states.sort(key=lambda s: s["name"])
    return states


def value_or_dash(v, suffix=""):
    if v in (None, "", []):
        return f'<span title="Not sourced yet">{EM_DASH}</span>'
    return f"{esc(str(v))}{suffix}"


def build_overview(states, employers_by_state):
    published = [s for s in states if s["status"] == "sourced"]
    stubs = [s for s in states if s["status"] != "sourced"]

    rows = []
    for s in published:
        board = (f'<a href="{esc(s["board_url"])}" rel="noopener" target="_blank">'
                 f'{esc(s["board_name"])}</a>')
        rows.append(
            f'          <tr>'
            f'<td><a href="{s["slug"]}">{esc(s["name"])}</a></td>'
            f'<td>{value_or_dash(s.get("law_exam"))}</td>'
            f'<td>{esc(s.get("transfer_requirement") or "") or EM_DASH}</td>'
            f'<td>{value_or_dash(s.get("application_fee"))}</td>'
            f'<td>{value_or_dash(s.get("processing_time"))}</td>'
            f'<td>{board}</td>'
            f'</tr>'
        )

    stub_links = " · ".join(esc(s["name"]) for s in stubs)

    body = f"""    <div class="content-section">
      <h2>Reciprocity, score transfer and what the difference costs you</h2>
      <p>Pharmacists use &ldquo;reciprocity&rdquo; loosely, but two different mechanisms are
      involved and only one of them is available to you once you are already licensed.</p>
      <p><strong>Score transfer</strong> applies before you are licensed anywhere. You sit the
      NAPLEX once and ask NABP to send that score to additional boards, which is the cheapest
      way to end up licensed in several states &mdash; but you have to decide before you take
      the exam.</p>
      <p><strong>Licensure transfer</strong> &mdash; what NABP runs as the Electronic Licensure
      Transfer Program &mdash; is what you use afterwards. You hold at least one current, active,
      unrestricted licence in good standing, and NABP verifies you into another jurisdiction.
      The board, not NABP, makes the final licensure decision.</p>
      <p>NABP publishes the eLTP application fee as <strong>$300</strong>, plus
      <strong>$100</strong> for each jurisdiction you transfer into. Those are NABP&rsquo;s fees
      only. Each board charges its own application fee on top, and most also require you to sit
      that state&rsquo;s law exam &mdash; usually the MPJE, sometimes a state-specific paper.
      NABP says it reviews a submitted application within three to five business days; how long
      the board then takes is up to the board.</p>
    </div>

    <div class="content-section">
      <h2>Why remote employers ask for several licences</h2>
      <p>A pharmacist practising remotely is generally expected to be licensed where the
      <em>patient</em> is, not where the pharmacist sits. So an employer serving members
      nationally needs its clinical staff licensed across many states, and job postings turn
      that into a hiring requirement. On this site you can see which is which: employers we
      have recorded as expecting multi-state licensure are
      <a href="../companies/">flagged in the directory</a>.</p>
      <p>Two practical consequences. First, a &ldquo;fully remote&rdquo; role is often
      remote-<em>eligible-by-state</em>, and the list of states is the real job requirement.
      Second, employers frequently reimburse additional licences, so the cost is worth raising
      during the offer conversation rather than absorbing quietly.</p>
    </div>

    <div class="content-section">
      <h2>Sequencing additional licences</h2>
      <p>A workable order, given each board sets its own rules:</p>
      <ul class="values-list">
        <li>Keep your original licence active and in good standing. Several boards require the
        licence used as the basis of transfer to be your licence by original examination.</li>
        <li>Check the destination board&rsquo;s own requirements before paying NABP anything
        &mdash; some states impose a minimum time licensed (six months to a year) that no fee
        will shortcut.</li>
        <li>Book the law exam early. In most states passing the MPJE or UMPJE is a
        precondition of the transfer application, not a step that follows it.</li>
        <li>Batch your jurisdictions. NABP charges a single application fee plus a per-state
        fee, and all jurisdictions must be selected when you submit.</li>
      </ul>
    </div>

    <div class="content-section">
      <h2>Requirements by state</h2>
      <p>Transfer requirements below are quoted from NABP&rsquo;s
      <a href="{NABP_PDF}" rel="noopener" target="_blank">General Requirements for Licensure
      Transfer</a>. Fees and processing times are not published here unless we have sourced
      them from the board itself &mdash; an em dash means we have not, not that there is no
      fee. Click a state for its board link and full record.</p>
      <div class="salary-table-wrap">
        <table class="salary-table" id="licensure-table">
          <thead>
            <tr>
              <th>State</th><th>Law exam</th><th>Transfer requirements (NABP)</th>
              <th>Board fee</th><th>Processing</th><th>Board</th>
            </tr>
          </thead>
          <tbody>
{chr(10).join(rows)}
          </tbody>
        </table>
      </div>
      <p style="font-size:0.85rem;color:#9ca3af;margin-top:12px">
      {len(published)} of {len(states)} jurisdictions published. The remaining
      {len(stubs)} are drafted but not yet verified against their board, so we are not
      publishing them: {stub_links}.</p>
    </div>"""
    return body, published, stubs


def build_state(state, employers):
    name = state["name"]
    sourced = state["status"] == "sourced"
    req = state.get("transfer_requirement")

    board_block = ""
    if sourced:
        board_block = (
            f'      <p><strong>Primary source:</strong> '
            f'<a href="{esc(state["board_url"])}" rel="noopener" target="_blank">'
            f'{esc(state["board_name"])}</a>. Everything below should be confirmed there.</p>'
        )
    else:
        board_block = (
            '      <p>We have not yet verified this state against its board of pharmacy, so '
            'this page is deliberately incomplete and is excluded from our sitemap. '
            'The NABP requirement below is accurate as quoted; everything else is unpublished '
            'rather than estimated.</p>'
        )

    if req:
        transfer = (
            f'      <p>NABP lists this requirement for transferring a licence into '
            f'{esc(name)}:</p>\n'
            f'      <blockquote style="margin:0 0 16px;padding-left:16px;'
            f'border-left:2px solid #e5e7eb;color:#374151">{esc(req)}</blockquote>'
        )
    else:
        transfer = (
            f'      <p>NABP&rsquo;s table lists no additional transferring requirements for '
            f'{esc(name)} beyond the general eligibility that applies everywhere. That is an '
            f'absence in their table, not a guarantee &mdash; confirm with the board.</p>'
        )

    rows = [
        ("Law exam", value_or_dash(state.get("law_exam"))),
        ("Board application fee", value_or_dash(state.get("application_fee"))),
        ("Processing time", value_or_dash(state.get("processing_time"))),
        ("CE requirements", value_or_dash(state.get("ce_requirements"))),
    ]
    facts = "\n".join(
        f'        <div class="sidebar-info-row">'
        f'<span class="sidebar-info-label">{label}</span>'
        f'<span class="sidebar-info-value">{value}</span></div>'
        for label, value in rows
    )

    emp_block = ""
    if employers:
        links = "\n".join(
            f'        <a href="../companies/{e["slug"]}" class="category-link">'
            f'{esc(e["name"])}</a>' for e in employers
        )
        emp_block = f"""
    <div class="content-section">
      <h2>Employers that expect multi-state licensure</h2>
      <p>These employers on this site hire remotely and expect licensure in more than one
      state, so an additional {esc(name)} licence may be directly useful to them.</p>
      <div class="category-links">
{links}
      </div>
    </div>"""

    sources = "\n".join(
        f'        <div class="sidebar-info-row"><a href="{esc(s["url"])}" '
        f'rel="noopener" target="_blank">{esc(s.get("what") or "Source")}</a></div>'
        for s in state.get("sources", [])
    )

    body = f"""    <div class="content-section">
      <h2>Transferring a pharmacist licence into {esc(name)}</h2>
{board_block}
{transfer}
      <p>The general route is NABP&rsquo;s
      <a href="{NABP_ELTP}" rel="noopener" target="_blank">Electronic Licensure Transfer
      Program</a>: hold a current, active, unrestricted licence in good standing, apply through
      NABP, and let the board make the decision. NABP&rsquo;s own fees are $300 for the
      application plus $100 per jurisdiction, as of {esc(state["last_verified"])}; the
      {esc(name)} board charges separately.</p>
    </div>

    <div class="content-section">
      <h2>At a glance</h2>
      <div class="sidebar-card">
{facts}
      </div>
      <p style="font-size:0.85rem;color:#9ca3af;margin-top:12px">Fees and processing times are
      approximate and change without notice. An em dash means we have not sourced that value
      from the board, not that it is zero.</p>
    </div>
{emp_block}

    <div class="content-section">
      <h2>Sources</h2>
      <div class="sidebar-card">
{sources}
      </div>
    </div>

    <div class="content-section">
      <h2>Other states</h2>
      <p><a href="./">Back to the licensure guide</a> for the full comparison table and how
      licensure transfer works.</p>
    </div>"""
    return body


def main():
    if not os.path.isdir(DATA_DIR):
        print(f"No {DATA_DIR}; skipping licensure pages")
        return
    states = load_states()
    os.makedirs(OUT_DIR, exist_ok=True)

    store = E.load_employers()
    multi_state = sorted(
        [r for r in store.values()
         if (r.get("multi_state_licensure") or {}).get("expected") is True
         and not r.get("out_of_scope")],
        key=lambda r: r["name"],
    )

    body, published, stubs = build_overview(states, multi_state)
    overview_ld = json.dumps([
        {"@context": "https://schema.org", "@type": "Article",
         "headline": "Multi-State Pharmacist Licensure: A Practical Guide",
         "description": ("How pharmacist licensure transfer works, why remote employers ask "
                         "for multiple state licences, and requirements by state."),
         "url": f"{SITE_URL}/licensure/",
         "dateModified": max(s["last_verified"] for s in states),
         "publisher": {"@type": "Organization", "name": "Remote Pharmacist Jobs",
                       "url": SITE_URL}},
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": [
             {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
             {"@type": "ListItem", "position": 2, "name": "Licensure",
              "item": f"{SITE_URL}/licensure/"}]},
    ], indent=2)

    with open(f"{OUT_DIR}/index.html", "w") as f:
        f.write(PAGE.substitute(
            title="Multi-State Pharmacist Licensure Guide | Remote Pharmacist Jobs",
            meta_description=("How pharmacist licensure transfer works, why remote employers "
                              "ask for multiple state licences, and the transfer requirements "
                              "for each state, sourced to NABP and state boards."),
            robots="", canonical=f"{SITE_URL}/licensure/", json_ld=overview_ld,
            nav=NAV, footer=FOOTER,
            crumb="<span>Licensure</span>",
            heading="Multi-state pharmacist licensure",
            lede=("Remote pharmacy roles increasingly ask for licensure in several states. "
                  "This is how transfer actually works, what it costs, and what each board "
                  "requires."),
            body=body, disclaimer=DISCLAIMER,
            verified=f" Last verified {max(s['last_verified'] for s in states)}."))

    for state in states:
        sourced = state["status"] == "sourced"
        canonical = f"{SITE_URL}/licensure/{state['slug']}"
        name = state["name"]
        ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList",
               "itemListElement": [
                   {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
                   {"@type": "ListItem", "position": 2, "name": "Licensure",
                    "item": f"{SITE_URL}/licensure/"},
                   {"@type": "ListItem", "position": 3, "name": name, "item": canonical}]}]
        if sourced:
            ld.insert(0, {
                "@context": "https://schema.org", "@type": "Article",
                "headline": f"Pharmacist Licensure Transfer in {name}",
                "url": canonical, "dateModified": state["last_verified"],
                "publisher": {"@type": "Organization", "name": "Remote Pharmacist Jobs",
                              "url": SITE_URL}})
        with open(f"{OUT_DIR}/{state['slug']}.html", "w") as f:
            f.write(PAGE.substitute(
                title=f"Pharmacist Licensure Transfer in {name} | Remote Pharmacist Jobs",
                meta_description=(
                    f"How to transfer a pharmacist licence into {name}: NABP transfer "
                    f"requirements, the state law exam, and the board of pharmacy to confirm "
                    f"it with."),
                robots="" if sourced else '\n  <meta name="robots" content="noindex, follow">',
                canonical=canonical,
                json_ld=json.dumps(ld, indent=2),
                nav=NAV, footer=FOOTER,
                crumb=f'<a href="./">Licensure</a> &rsaquo; <span>{esc(name)}</span>',
                heading=f"Pharmacist licensure in {esc(name)}",
                lede=(f"What it takes to add a {esc(name)} pharmacist licence, and where to "
                      f"confirm it."),
                body=build_state(state, multi_state if sourced else []),
                disclaimer=DISCLAIMER,
                verified=f" Last verified {state['last_verified']}."))

    print(f"Generated licensure guide + {len(states)} state pages in {OUT_DIR}/")
    print(f"  published (board-sourced) : {len(published)}")
    print(f"  stubs (noindex, no board) : {len(stubs)}")


if __name__ == "__main__":
    main()
