/**
 * POST /api/salary-contributions — accept one anonymous salary contribution.
 *
 * NOT YET LIVE. Requires a D1 binding named DB plus Turnstile and salt secrets.
 * Without them this returns 503, and the form is not rendered on /salary at all,
 * so the endpoint is inert until it is deliberately provisioned.
 *
 * Nothing submitted here is ever published directly. Rows land as 'pending' and
 * reach the site only after moderation, and only inside buckets of five or more.
 */

const ROLE_TYPES = new Set([
  "clinical-pharmacist", "staff-pharmacist", "managed-care-pharmacist",
  "specialty-pharmacist", "prior-authorization-pharmacist", "mtm-pharmacist",
  "informatics-pharmacist", "pharmacy-manager", "pharmacy-technician",
  "prior-authorization-technician", "other",
]);
const POSTURES = new Set(["fully-remote", "hybrid", "remote-by-state"]);
const PERIODS = new Set(["yearly", "hourly"]);
const RATE_LIMIT_PER_DAY = 3;

const json = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

async function hashIp(ip, salt) {
  const data = new TextEncoder().encode(salt + ":" + ip);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function verifyTurnstile(token, secret, ip) {
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token || "");
  if (ip) form.append("remoteip", ip);
  const res = await fetch(
    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    { method: "POST", body: form },
  );
  const out = await res.json();
  return out.success === true;
}

export async function onRequestPost(context) {
  const { request, env } = context;
  if (!env.DB || !env.TURNSTILE_SECRET_KEY || !env.IP_HASH_SALT) {
    return json(503, { error: "Contributions are not enabled yet." });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json(400, { error: "Expected JSON." });
  }

  const ip = request.headers.get("CF-Connecting-IP") || "";
  if (!(await verifyTurnstile(body.turnstileToken, env.TURNSTILE_SECRET_KEY, ip))) {
    return json(403, { error: "Verification failed. Reload the page and try again." });
  }

  // Validate against closed vocabularies. Anything unrecognised is rejected
  // rather than coerced, so the dataset cannot drift into free text.
  const employer = String(body.employerSlug || "").trim();
  const role = String(body.roleType || "").trim();
  const period = String(body.compPeriod || "").trim();
  const posture = String(body.remotePosture || "").trim();
  const state = String(body.state || "").trim().toUpperCase();
  const comp = Number(body.baseComp);
  const bonus = body.bonus === "" || body.bonus == null ? null : Number(body.bonus);
  const years = Number(body.yearsExperience);

  if (!/^[a-z0-9-]{2,80}$/.test(employer)) return json(400, { error: "Unknown employer." });
  if (!ROLE_TYPES.has(role)) return json(400, { error: "Unknown role type." });
  if (!PERIODS.has(period)) return json(400, { error: "Unknown pay period." });
  if (!POSTURES.has(posture)) return json(400, { error: "Unknown remote posture." });
  if (!/^[A-Z]{2}$/.test(state)) return json(400, { error: "Expected a two-letter state." });
  if (!Number.isFinite(years) || years < 0 || years > 60) {
    return json(400, { error: "Years of experience looks wrong." });
  }
  if (!Number.isFinite(comp)) return json(400, { error: "Enter your base pay." });

  // Sanity bounds, so one typo cannot poison an average.
  const bounds = period === "hourly" ? [10, 400] : [20000, 700000];
  if (comp < bounds[0] || comp > bounds[1]) {
    return json(400, { error: "That pay figure is outside the range we accept." });
  }
  if (bonus != null && (!Number.isFinite(bonus) || bonus < 0 || bonus > 500000)) {
    return json(400, { error: "That bonus figure is outside the range we accept." });
  }

  // The employer must already exist in the curated store, mirrored into D1 by
  // the build. This is what keeps contributions joinable to employer pages.
  const known = await env.DB.prepare("SELECT 1 FROM employers WHERE slug = ?1")
    .bind(employer).first().catch(() => null);
  if (!known) return json(400, { error: "Pick an employer from the list." });

  const ipHash = ip ? await hashIp(ip, env.IP_HASH_SALT) : null;
  if (ipHash) {
    const row = await env.DB.prepare(
      "SELECT COUNT(*) AS count FROM salary_contributions" +
      " WHERE ip_hash = ?1 AND created_at > datetime('now', '-1 day')",
    ).bind(ipHash).first();
    if (row && row.count >= RATE_LIMIT_PER_DAY) {
      return json(429, { error: "You have submitted a few already today. Thanks!" });
    }
  }

  await env.DB.prepare(
    "INSERT INTO salary_contributions" +
    " (employer_slug, role_type, base_comp, comp_period, bonus," +
    "  years_experience, remote_posture, state, ip_hash)" +
    " VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
  ).bind(
    employer, role, Math.round(comp), period,
    bonus == null ? null : Math.round(bonus),
    Math.round(years), posture, state, ipHash,
  ).run();

  return json(201, {
    ok: true,
    message: "Thanks. This goes into a moderation queue and is only ever published "
           + "as part of an aggregate, once we have at least five for that bucket.",
  });
}
