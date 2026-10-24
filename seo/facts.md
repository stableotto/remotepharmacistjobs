# Remote Pharmacist Jobs: facts

The source of truth for anything the site states about itself. Confirmed by the owner on 2026-10-24 unless marked `(unconfirmed)`. Skills must not use unconfirmed facts.

## What it is

- A free job board for **remote** pharmacist and pharmacy technician jobs at https://remotepharmacistjobs.com.
- Every listing links straight to the employer's own career page. The "Apply" button never goes to a recruiter, staffing agency or lead form.
- Recruiter and staffing-agency postings are not accepted.
- Free for job seekers: no sign-up, no premium tier, no "unlock this job".
- Contact: hello@remotepharmacistjobs.com.

## How listings are collected

- Every day, job listings are pulled from 7,000+ company career pages via their ATS (Greenhouse, Workday, Lever).
- Pharmacy roles that are remote are filtered in: pharmacist, pharmacy technician, clinical pharmacist, pharmacovigilance, MTM and related roles.
- Refreshed daily (06:00 UTC). New listings from an indexed company typically appear within 24 hours.
- A job missing from the source for 7 days is marked expired (shown with a notice, noindexed, removed from the sitemap) and deleted after 30 days.
- Salary is shown only when the employer publishes it. It is extracted from the posting and normalized to yearly for the salary guide.

## Numbers (change daily; quote only with an "as of" date and re-check `site/jobs.json` first)

- As of 2026-10-23: 108 active jobs from 60 companies; 52 of them list a salary.
- As of 2026-10-23: average published salary on /salary is $136,296/year.

## For employers

- Jobs on an employer's career page are picked up automatically at no cost.
- Employers can submit their company and career page URL through the form at /post-a-job to be added to the index.
- Featured placements: "reach out to discuss options". No public pricing.

## Primary conversion

1. Job seeker clicks **Apply** through to the employer's career page.
2. Employer submits the form on **/post-a-job**.

## Never say

- Any number of applicants, visitors, users, page views or traffic.
- "Guaranteed" (jobs, interviews, placement, responses) or "verified remote".
- Any price for featured placements or job posts.
- That the site offers, accepts or partners with recruiters or staffing agencies (don't mention them as an offering at all; describing the "no recruiters" policy is fine).
- Anything implying the site employs, screens or places candidates.
- Technical rule: never write a `.html` URL in a canonical tag, og:url, sitemap entry or JSON-LD. URLs there are extensionless.
