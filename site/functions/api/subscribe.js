/**
 * POST /api/subscribe — email capture for the jobs digest.
 *
 * NOT YET LIVE; inert without a D1 binding. Deliberately separate from the
 * salary table and never joined to it: someone who shares their pay has not
 * agreed to be emailed, and vice versa.
 *
 * Per the site's promise on /about this must never gate content, and must
 * never appear on a job page.
 */

const ALLOWED_SOURCES = new Set(["employer", "salary", "licensure"]);

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
    return json(503, { error: "Sign-up is not enabled yet." });
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

  const email = String(body.email || "").trim().toLowerCase();
  const source = String(body.source || "").trim();
  if (email.length > 254 || !/^[^@\s]+@[^@\s.]+\.[^@\s]+$/.test(email)) {
    return json(400, { error: "That does not look like an email address." });
  }
  if (!ALLOWED_SOURCES.has(source)) return json(400, { error: "Unknown source." });

  const token = crypto.randomUUID();
  const ipHash = ip ? await hashIp(ip, env.IP_HASH_SALT) : null;

  // Idempotent: re-subscribing clears an earlier unsubscribe but never resets
  // a confirmation that already happened.
  await env.DB.prepare(
    "INSERT INTO subscribers (email, source, confirm_token, ip_hash)" +
    " VALUES (?1, ?2, ?3, ?4)" +
    " ON CONFLICT(email) DO UPDATE SET unsubscribed = 0",
  ).bind(email, source, token, ipHash).run();

  return json(201, { ok: true, message: "Check your inbox to confirm." });
}
