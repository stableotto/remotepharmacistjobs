-- D1 schema for contributed salary data and email capture.
--
-- NOT YET PROVISIONED. Applying this requires creating the D1 database and
-- adding the binding, which needs sign-off — see docs/phase-3-proposal.md.
--
-- Apply with:
--   wrangler d1 create remotepharmacistjobs
--   wrangler d1 execute remotepharmacistjobs --file=migrations/0001_salary_and_subscribers.sql
--
-- Design notes:
--  * Nothing here identifies a person. No name, no email, no free text on the
--    salary table. Employer is a foreign key onto our own curated slugs, not a
--    typed string, so a contributor cannot write prose into the dataset.
--  * status defaults to 'pending'. Nothing is published without moderation.
--  * ip_hash is a salted hash used only for rate limiting, and is dropped by a
--    retention job after 30 days. The raw IP is never stored.

CREATE TABLE IF NOT EXISTS salary_contributions (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  employer_slug     TEXT    NOT NULL,
  role_type         TEXT    NOT NULL,
  base_comp         INTEGER NOT NULL,
  comp_period       TEXT    NOT NULL CHECK (comp_period IN ('yearly','hourly')),
  bonus             INTEGER,
  years_experience  INTEGER NOT NULL CHECK (years_experience BETWEEN 0 AND 60),
  remote_posture    TEXT    NOT NULL CHECK (remote_posture IN ('fully-remote','hybrid','remote-by-state')),
  state             TEXT    NOT NULL,
  status            TEXT    NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','approved','rejected')),
  moderated_at      TEXT,
  moderator_note    TEXT,
  ip_hash           TEXT,
  created_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_salary_status    ON salary_contributions (status);
CREATE INDEX IF NOT EXISTS idx_salary_employer  ON salary_contributions (employer_slug, status);
CREATE INDEX IF NOT EXISTS idx_salary_role      ON salary_contributions (role_type, status);
CREATE INDEX IF NOT EXISTS idx_salary_ip        ON salary_contributions (ip_hash, created_at);

-- Email capture. Separate table, separate consent, never joined to salary rows.
CREATE TABLE IF NOT EXISTS subscribers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email         TEXT    NOT NULL UNIQUE,
  source        TEXT    NOT NULL,          -- which surface captured it
  confirmed     INTEGER NOT NULL DEFAULT 0,
  confirm_token TEXT,
  unsubscribed  INTEGER NOT NULL DEFAULT 0,
  ip_hash       TEXT,
  created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_subscribers_confirmed ON subscribers (confirmed, unsubscribed);
