#!/usr/bin/env python3
"""Shared UI fragments for the contributed-salary form and email capture.

Both depend on a D1 binding and Turnstile that are not provisioned yet, so both
are behind flags in data/features.json. With a flag off these functions return
an empty string — the page renders no form, no heading and no placeholder.

Assembled from existing classes in site/styles.css. No new primitives: form
controls are inputs wrapped in .search-wrapper, with <datalist> for constrained
fields, because there is no styled <select> in the design system. The Function
validates against closed vocabularies regardless, so the datalist is a
convenience and never the control.
"""

import html
import json
import os

FEATURES_PATH = "data/features.json"

ROLE_TYPES = [
    ("clinical-pharmacist", "Clinical pharmacist"),
    ("staff-pharmacist", "Staff pharmacist"),
    ("managed-care-pharmacist", "Managed care pharmacist"),
    ("specialty-pharmacist", "Specialty pharmacist"),
    ("prior-authorization-pharmacist", "Prior authorization pharmacist"),
    ("mtm-pharmacist", "MTM pharmacist"),
    ("informatics-pharmacist", "Informatics pharmacist"),
    ("pharmacy-manager", "Pharmacy manager"),
    ("pharmacy-technician", "Pharmacy technician"),
    ("prior-authorization-technician", "Prior authorization technician"),
    ("other", "Other"),
]

POSTURES = [
    ("fully-remote", "Fully remote"),
    ("hybrid", "Hybrid"),
    ("remote-by-state", "Remote, eligible by state"),
]

STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
]

LABEL = 'style="display:block;font-size:0.85rem;color:#374151;margin-bottom:6px"'
HINT = 'style="font-size:0.8rem;color:#9ca3af;margin-top:12px"'


def esc(s):
    return html.escape(str(s or ""))


def load_features(path=FEATURES_PATH):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def turnstile_script(features):
    """Only loaded when a flag that needs it is on."""
    if not features.get("turnstile_site_key"):
        return ""
    return ('  <script src="https://challenges.cloudflare.com/turnstile/v0/api.js"'
            ' async defer></script>\n')


def _field(label, control, hint=""):
    hint_html = f'<p {HINT}>{hint}</p>' if hint else ""
    return (f'        <div class="search-wrapper">\n'
            f'          <label {LABEL}>{label}</label>\n'
            f'          {control}\n{hint_html}'
            f'        </div>')


def _datalist(list_id, options):
    opts = "".join(
        f'<option value="{esc(v)}">{esc(l)}</option>' if l else f'<option value="{esc(v)}">'
        for v, l in options
    )
    return f'<datalist id="{list_id}">{opts}</datalist>'


def email_capture(prefix, source, features):
    """One capture block. Never rendered on a job page — see CLAUDE.md."""
    if not features.get("email_capture"):
        return ""
    key = esc(features.get("turnstile_site_key", ""))
    return f"""
    <div class="content-section">
      <div class="sidebar-card">
        <div class="sidebar-card-title">New remote pharmacy roles, weekly</div>
        <p style="font-size:0.9rem;color:#374151;margin-bottom:12px">One email a week
        with new direct-employer listings. No recruiters, and nothing here is ever
        gated behind it &mdash; every job on this site stays readable without an
        address.</p>
        <form class="email-capture" data-source="{esc(source)}" novalidate>
          <div class="search-wrapper">
            <label {LABEL} for="ec-email-{esc(source)}">Email address</label>
            <input type="email" id="ec-email-{esc(source)}" name="email" required
                   autocomplete="email" placeholder="you@example.com">
          </div>
          <div class="cf-turnstile" data-sitekey="{key}" data-size="flexible"></div>
          <button type="submit" class="apply-button" style="margin-top:12px">Subscribe</button>
          <p class="form-status" role="status" {HINT}></p>
        </form>
      </div>
    </div>
"""


def contribution_form(employers, features):
    """Salary submission form for /salary."""
    if not features.get("salary_contributions"):
        return ""
    key = esc(features.get("turnstile_site_key", ""))
    employer_opts = sorted(
        ((r["slug"], r["name"]) for r in employers.values() if not r.get("out_of_scope")),
        key=lambda t: t[1].lower(),
    )
    # Value is the display name; the slug rides along in a data attribute map so
    # the payload sends the slug the Function expects.
    emp_list = "".join(
        f'<option value="{esc(name)}" data-slug="{esc(slug)}">'
        for slug, name in employer_opts
    )
    slug_map = json.dumps({name: slug for slug, name in employer_opts})

    return f"""
    <div class="content-section">
      <h2>Add your own compensation</h2>
      <p>Listing data only shows what employers choose to publish, which skews high and
      misses bonus entirely. If you work a remote pharmacy role, adding yours makes this
      page better for the next person.</p>
      <p {HINT}>Anonymous. We ask for no name, no email and no free text, and nothing you
      enter is published on its own &mdash; contributions appear only inside an aggregate,
      and only once a bucket has at least five reports. Everything is reviewed before it
      is published.</p>
      <form id="salary-contribution-form" novalidate>
{_field("Employer", '<input type="text" name="employer" list="employer-list" required autocomplete="off" placeholder="Start typing a company name">', "Pick from the list. We can only attach a contribution to an employer already in our directory.")}
        <datalist id="employer-list">{emp_list}</datalist>
{_field("Role type", '<input type="text" name="roleType" list="role-list" required autocomplete="off" placeholder="Clinical pharmacist">')}
        {_datalist("role-list", ROLE_TYPES)}
{_field("Base pay", '<input type="number" name="baseComp" required min="0" step="any" inputmode="decimal" placeholder="130000">', "Base only &mdash; bonus goes below. Enter an hourly rate if you are paid hourly.")}
{_field("Paid", '<input type="text" name="compPeriod" list="period-list" required autocomplete="off" value="yearly">')}
        {_datalist("period-list", [("yearly", "Per year"), ("hourly", "Per hour")])}
{_field("Annual bonus", '<input type="number" name="bonus" min="0" step="any" inputmode="decimal" placeholder="Optional">')}
{_field("Years of experience", '<input type="number" name="yearsExperience" required min="0" max="60" inputmode="numeric" placeholder="6">')}
{_field("Remote posture", '<input type="text" name="remotePosture" list="posture-list" required autocomplete="off" placeholder="Fully remote">')}
        {_datalist("posture-list", POSTURES)}
{_field("Your state", '<input type="text" name="state" list="state-list" required autocomplete="off" maxlength="2" placeholder="OH" style="text-transform:uppercase">')}
        {_datalist("state-list", [(s, "") for s in STATES])}
        <div class="cf-turnstile" data-sitekey="{key}" data-size="flexible"></div>
        <button type="submit" class="apply-button" style="margin-top:16px">Submit anonymously</button>
        <p class="form-status" role="status" {HINT}></p>
      </form>
    </div>

    <script>
    // Progressive enhancement. Without JS the form simply does not submit;
    // nothing on this page is hidden behind it.
    (function () {{
      var form = document.getElementById('salary-contribution-form');
      if (!form) return;
      var SLUGS = {slug_map};
      var LABELS = {json.dumps({l: v for v, l in ROLE_TYPES})};
      var POSTURE = {json.dumps({l: v for v, l in POSTURES})};
      var status = form.querySelector('.form-status');

      form.addEventListener('submit', function (e) {{
        e.preventDefault();
        var f = new FormData(form);
        var token = (form.querySelector('[name="cf-turnstile-response"]') || {{}}).value;
        var payload = {{
          employerSlug: SLUGS[f.get('employer')] || '',
          roleType: LABELS[f.get('roleType')] || f.get('roleType'),
          baseComp: f.get('baseComp'),
          compPeriod: (f.get('compPeriod') || '').toLowerCase().indexOf('hour') !== -1
            ? 'hourly' : 'yearly',
          bonus: f.get('bonus'),
          yearsExperience: f.get('yearsExperience'),
          remotePosture: POSTURE[f.get('remotePosture')] || f.get('remotePosture'),
          state: (f.get('state') || '').toUpperCase(),
          turnstileToken: token
        }};
        if (!payload.employerSlug) {{
          status.textContent = 'Pick an employer from the list.';
          return;
        }}
        status.textContent = 'Sending...';
        fetch('/api/salary-contributions', {{
          method: 'POST',
          headers: {{ 'content-type': 'application/json' }},
          body: JSON.stringify(payload)
        }}).then(function (r) {{ return r.json().then(function (b) {{
          status.textContent = b.message || b.error || 'Something went wrong.';
          if (r.ok) form.reset();
        }}); }}).catch(function () {{
          status.textContent = 'Could not reach the server. Try again later.';
        }});
      }});
    }})();
    </script>
"""


EMAIL_CAPTURE_JS = """
  <script>
  // Progressive enhancement for the weekly-digest form.
  (function () {
    Array.prototype.forEach.call(
      document.querySelectorAll('form.email-capture'), function (form) {
      var status = form.querySelector('.form-status');
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var email = (form.querySelector('[name="email"]') || {}).value || '';
        var token = (form.querySelector('[name="cf-turnstile-response"]') || {}).value;
        status.textContent = 'Sending...';
        fetch('/api/subscribe', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            email: email, source: form.dataset.source, turnstileToken: token
          })
        }).then(function (r) { return r.json().then(function (b) {
          status.textContent = b.message || b.error || 'Something went wrong.';
          if (r.ok) form.reset();
        }); }).catch(function () {
          status.textContent = 'Could not reach the server. Try again later.';
        });
      });
    });
  })();
  </script>
"""


def email_capture_js(features):
    return EMAIL_CAPTURE_JS if features.get("email_capture") else ""
