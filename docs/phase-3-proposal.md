# Phase 3 — contributed salary data and email capture

**Status: proposed, not provisioned. Nothing in this document is live.**

The code and the UI are both written and inert, behind flags in
`data/features.json`. With the flags off the generators emit byte-identical
pages — no form, no heading, no placeholder, and the Turnstile script is not
even loaded. Both Pages Functions additionally return `503` without a D1
binding, so there are two independent locks. Provisioning needs your approval — it is
the only phase that adds infrastructure and the only one that stores anything a
person typed.

## What needs your decision

1. Create the D1 database and bind it. This is the actual commitment — once it
   exists, the site stores user-submitted data and inherits the obligations that
   come with that.
2. Turnstile site key and secret.
3. A moderation route. Nothing publishes automatically, so someone has to review
   the queue. Without a named owner this collects rows nobody reads.

## Provisioning

```bash
wrangler d1 create remotepharmacistjobs
wrangler d1 execute remotepharmacistjobs \
  --file=migrations/0001_salary_and_subscribers.sql
```

Then in the Pages project: bind the database as `DB`, and set
`TURNSTILE_SECRET_KEY` and `IP_HASH_SALT` (a long random string) as secrets.
There is no `wrangler.toml` in this repo — bindings live in the dashboard.

Finally, turn the surfaces on in `data/features.json` and re-run the generators:

```json
{ "salary_contributions": true, "email_capture": true,
  "turnstile_site_key": "<your Turnstile site key>" }
```

Flip them independently — email capture does not depend on the salary work.
Do not enable either before the D1 binding exists, or visitors get a form whose
endpoint answers 503.

## Schema

`migrations/0001_salary_and_subscribers.sql`. Two tables, deliberately never
joined.

`salary_contributions` — employer slug, role type, base comp, period, bonus,
years of experience, remote posture, state, status, moderation fields, salted
IP hash, timestamp.

`subscribers` — email, source surface, confirmation state, unsubscribe flag,
salted IP hash, timestamp.

Privacy decisions worth challenging if you disagree:

- **No free text anywhere on the salary table.** Every field is a number or a
  member of a closed vocabulary validated in the Function. Free text is how
  someone accidentally identifies themselves, and how a dataset becomes
  unusable.
- **Employer is a foreign key onto our own slugs**, not a typed string, so
  contributions stay joinable to employer pages and cannot invent employers.
- **The raw IP is never stored** — only a salted SHA-256 hash, used for rate
  limiting, dropped after 30 days by a retention job that still needs writing.
- **Email and salary are never joined.** Sharing your pay is not consent to be
  emailed.

## How data reaches the site

The site is static, so pages cannot query D1 at request time. Rendering
contributed pay client-side would also hide it from search engines, which
defeats the point of collecting it. So the build exports aggregates:

```
wrangler d1 execute remotepharmacistjobs --json --command \
  "SELECT ... FROM salary_contributions WHERE status = 'approved'" \
  > /tmp/contributions.json
python scripts/export_contributions.py /tmp/contributions.json
```

That writes `data/salary-contributions.json`, which the generators read. With no
such file the generators render nothing at all — not an empty heading.

Two rules are enforced in the exporter rather than the templates, so a call site
cannot forget them:

- **A bucket publishes only at n >= 5.**
- **Buckets are keyed by employer *and* role type.** An early version keyed on
  employer alone; testing it produced an AnewHealth range of
  "$50,960 – $150,000" by averaging a pharmacy technician's hourly rate with
  clinical pharmacist salaries. That number was wrong in a way a reader could
  not see, which is worse than showing nothing.

Hourly is annualised at 2080 hours before aggregation, and units are never mixed.

## What is built

- The submission form on `/salary`, with employer autocomplete against the
  curated store, closed-vocabulary datalists, and Turnstile.
- Email capture on employer pages, `/salary` and `/licensure/` — one component,
  never on a job page and never gating content.
- The contributed-pay section on `/salary` (by role) and on employer pages (by
  employer and role), rendered separately from listing-derived figures.

Form controls reuse `.search-wrapper` inputs with `<datalist>` rather than
`<select>`, because the design system has no styled select and adding one would
need your sign-off. The Function validates against closed vocabularies
regardless, so the datalist is a convenience, never the control.

## What is still missing

- The email confirmation send. `subscribe.js` writes a `confirm_token` but
  nothing mails it, so no address can currently confirm. Needs an email provider
  decision.
- The `/api/subscribe/confirm` endpoint and unsubscribe handling.
- A moderation interface. Today moderation means running SQL by hand.
- The 30-day `ip_hash` retention job.
- The `employers` mirror table in D1 that `salary-contributions.js` validates
  against, populated from `data/employers/` at build time.
Per the site's promise on `/about`, email capture must never gate content and
must never appear on a job page.
