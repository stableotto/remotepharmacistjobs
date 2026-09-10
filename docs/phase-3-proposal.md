# Phase 3 — contributed salary data and email capture

**Status: proposed, not provisioned. Nothing in this document is live.**

The code is written and inert. Both Pages Functions return `503` unless a D1
binding and two secrets exist, and no form is rendered on the site, so merging
this changes nothing a visitor can see. Provisioning needs your approval — it is
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

## What is still missing

- The email confirmation send. `subscribe.js` writes a `confirm_token` but
  nothing mails it, so no address can currently confirm. Needs an email provider
  decision.
- The `/api/subscribe/confirm` endpoint and unsubscribe handling.
- A moderation interface. Today moderation means running SQL by hand.
- The 30-day `ip_hash` retention job.
- The `employers` mirror table in D1 that `salary-contributions.js` validates
  against, populated from `data/employers/` at build time.
- The submission form and email capture UI. Deliberately not built yet: the
  form should not exist before the endpoint behind it does.

Per the site's promise on `/about`, email capture must never gate content and
must never appear on a job page.
