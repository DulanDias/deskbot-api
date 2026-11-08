// A DeskBot stats endpoint in the standard format. Node.js 18 or later, no dependencies.
//
//   DESKBOT_KEY=choose-a-long-random-key node server.mjs
//
// Serves GET http://localhost:8787/api/v1/stats to anyone with the key. Replace getStats() with your
// own queries; README.md describes every field. Over the internet, run it behind HTTPS.
import { createServer } from "node:http";
import { timingSafeEqual } from "node:crypto";

const PORT = Number(process.env.PORT || 8787);
const KEY = process.env.DESKBOT_KEY || "";
const CACHE_MS = 30_000; // each clock asks every minute; work the numbers out at most this often

if (KEY.length < 16) {
  console.error("Set DESKBOT_KEY to a key of 16 or more characters. You'll enter the same key on DeskBot.");
  process.exit(1);
}

// Every field is optional. Money is in minor units (cents, pence): 120000 is 1,200.00.
async function getStats() {
  return {
    people: {
      total: 1284,
      new: { "1d": 12, "7d": 57, "30d": 203 },
      active: { "1d": 148, "7d": 512, "30d": 903 },
    },
    // The breakdown screen's groups, in the order they're named on DeskBot's settings page.
    breakdown: [42, 18, 25, 3],
    revenue: {
      mrr: [{ currency: "USD", amount: 120000 }],
      arr: [{ currency: "USD", amount: 1440000 }],
      change: {
        "7d": [{ currency: "USD", amount: 1000, percent: 0.8 }],
        "30d": [{ currency: "USD", amount: 3500, percent: 3.0 }],
      },
    },
    positives: {
      signUps: { "1d": 9 },
      conversions: { "1d": 3 },
      meetings: { "1d": 4 },
      newPayingThisMonth: 2,
      trialsConverted30d: 7,
    },
    negatives: { churnedThisMonth: 1, pastDue: 2, trialsExpired30d: 3 },
    regions: { missing: [] },
  };
}

function keyMatches(header = "") {
  const given = Buffer.from(header.replace(/^Bearer\s+/i, ""));
  const want = Buffer.from(KEY);
  return given.length === want.length && timingSafeEqual(given, want);
}

function send(res, status, body) {
  const json = typeof body === "string" ? body : JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(json), // DeskBot speaks HTTP/1.0: no chunked replies
    "Cache-Control": "no-store",
  });
  res.end(json);
}

let cache = { at: 0, json: "" };

createServer(async (req, res) => {
  const { pathname } = new URL(req.url, "http://localhost");
  if (req.method !== "GET" || pathname !== "/api/v1/stats") return send(res, 404, { error: "not found" });
  if (!keyMatches(req.headers.authorization)) return send(res, 401, { error: "wrong or missing key" });
  try {
    if (Date.now() - cache.at > CACHE_MS) cache = { at: Date.now(), json: JSON.stringify(await getStats()) };
    send(res, 200, cache.json);
  } catch (err) {
    console.error(err);
    send(res, 500, { error: "couldn't work out the stats" });
  }
}).listen(PORT, () => console.log(`DeskBot stats on http://localhost:${PORT}/api/v1/stats`));
