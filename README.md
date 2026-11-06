# DeskBot Stats API

DeskBot is a small Wi-Fi desk clock that shows your business numbers next to the time and weather:
MRR, users, customers and the day's wins. It reads them from **one endpoint on your server**. This
guide explains what that endpoint receives and what it should reply.

- [Quick start](#quick-start)
- [The request](#the-request)
- [The reply](#the-reply)
- [Money](#money)
- [Using your own JSON](#using-your-own-json)
- [HTTPS](#https)
- [Errors DeskBot shows](#errors-deskbot-shows)
- [Check your endpoint](#check-your-endpoint)
- [Example server](#example-server)

## Quick start

1. Add a `GET` endpoint to your server that returns the [JSON below](#the-reply), and protect it
   with a key of your choice (`Authorization: Bearer <key>`). [server.mjs](server.mjs) is a working
   example.
2. Open DeskBot's settings page. Scan the **Settings QR** screen on the clock with your phone's
   camera, or go to `http://deskbot.local`.
3. Under **Business stats**, enter your endpoint's address, add the key and tap **Test connection**.
   DeskBot says how many fields it found.

Is your JSON shaped differently? You don't have to change it: [map the fields](#using-your-own-json)
on the settings page instead.

## The request

Every minute (or the interval set on the clock, never more often), DeskBot sends:

```http
GET /api/v1/stats HTTP/1.0
Host: api.example.com
Authorization: Bearer <your key>
Accept: application/json
User-Agent: DeskBot/0.3.0
```

- **The address.** If the address on the settings page has no path (`https://api.example.com`),
  DeskBot asks for `/api/v1/stats`. If it has a path (`https://example.com/hooks/deskbot`), it's
  used exactly as entered.
- **HTTP/1.0.** Reply with a `Content-Length`, or close the connection when you're done. Nearly
  every framework does one of these by itself.
- **Reply within 8 seconds** with status `200` and a JSON body. Anything else counts as a failed
  check, and the clock tries again at the next interval.
- **Redirects aren't followed.** Enter the final URL.
- The key is stored on the clock and is never shown again. It's only ever sent to the saved address,
  and changing the address on the settings page removes it. Use a key that can do nothing but read
  these numbers.

Each clock asks once a minute. If your numbers are expensive to work out, cache them for a minute
on your side.

## The reply

The standard format (also in [sample-response.json](sample-response.json)):

```json
{
  "people": {
    "total": 1284,
    "new": { "1d": 12, "7d": 57, "30d": 203 },
    "active": { "1d": 148, "7d": 512, "30d": 903 }
  },
  "organisations": { "trial": 18, "paying": 42, "trialEnded": 25, "suspended": 3 },
  "revenue": {
    "mrr": [{ "currency": "USD", "amount": 120000 }],
    "arr": [{ "currency": "USD", "amount": 1440000 }],
    "change": {
      "7d": [{ "currency": "USD", "amount": 1000, "percent": 0.8 }],
      "30d": [{ "currency": "USD", "amount": 3500, "percent": 3.0 }]
    }
  },
  "positives": {
    "signUps": { "1d": 9 },
    "conversions": { "1d": 3 },
    "meetings": { "1d": 4 },
    "newPayingThisMonth": 2,
    "trialsConverted30d": 7
  },
  "negatives": { "churnedThisMonth": 1, "pastDue": 2, "trialsExpired30d": 3 },
  "regions": { "missing": [] }
}
```

**Every field is optional.** A missing one keeps its last value, or 0 until it's been seen.
Leave out what you don't have, and turn off the screens you don't need on the settings page. Extra
fields are ignored. `1d`, `7d` and `30d` are rolling windows: the last 24 hours, 7 days and 30 days.

| Field | Standard path | On the clock |
|---|---|---|
| Total users | `people.total` | Users screen, big number |
| New users | `people.new.1d` / `7d` / `30d` | Users screen: today, week and month chips |
| Active users | `people.active.1d` / `7d` / `30d` | Users screen: bars as a share of the total |
| Organisations | `organisations.trial`, `paying`, `trialEnded`, `suspended` | Organisations screen: ring and legend |
| Trials converted / expired, 30 days | `positives.trialsConverted30d`, `negatives.trialsExpired30d` | Organisations screen: trial → paid rate |
| MRR | `revenue.mrr` | Revenue screen, big number. Optionally the clock screen's bottom strip |
| ARR | `revenue.arr` | Revenue screen. Optional: when it's missing, DeskBot shows 12 × MRR |
| MRR change | `revenue.change.7d` / `30d` | Revenue screen: ▲/▼ chips |
| Sign-ups, conversions, meetings today | `positives.signUps.1d`, `conversions.1d`, `meetings.1d` | Pulse screen, wins |
| New paying this month | `positives.newPayingThisMonth` | Pulse screen. **A rise is celebrated** on the clock |
| Churned this month | `negatives.churnedThisMonth` | Pulse screen. **A rise shows an alert** |
| Payments past due | `negatives.pastDue` | Pulse screen. **A rise shows an alert** |
| Trials expired, 30 days | `negatives.trialsExpired30d` | Pulse screen, losses |
| Sources that didn't answer | `regions.missing` | An amber badge naming them ("EU didn't answer"). A list of names, or one name |

Counts are whole numbers. The revenue screen's sparkline is drawn by the clock itself, which
records MRR every hour.

Celebrations and alerts compare each reply with the one before, so make the counters monotonic
within their window: `newPayingThisMonth` should only go up during a month. Each one can be turned
off on the settings page.

## Money

A money value can be any of these:

```json
"mrr": 120000
"mrr": { "currency": "USD", "amount": 120000 }
"mrr": [{ "currency": "USD", "amount": 120000 }, { "currency": "EUR", "amount": 31000 }]
```

- **Units.** The standard is **minor units**: cents, pence. `120000` is $1,200.00. If your amounts are
  in whole units, set **Money amounts in → whole units** on the settings page.
- **Currencies are never converted.** With a list, DeskBot shows the currency set under **Currency
  to show**, or the first one in the list when none is set. ARR and the changes use the same
  currency. A plain number has no currency: set one on the settings page to show its symbol.
  £, € and $ show as symbols, other currencies by their code ("AUD 12.3K").
- **Changes** (`revenue.change.7d`, `30d`) can carry a `percent`: the change against the start of
  the window, as a percentage (`0.8` means +0.8 %). Use `null` when there was no revenue at the
  start, and the clock shows "new". A plain number there is taken as the percentage.
- **On screen** amounts are shortened to three digits: 950, 1.2K, 12.3K, 123K, 1.2M.

## Using your own JSON

If your endpoint already returns these numbers in another shape, point DeskBot at them instead of
changing your server. On the settings page, open **API format → Match the fields to your JSON** and
give the path of each value:

| Your JSON | Path |
|---|---|
| `{"data": {"users": {"count": 1284}}}` | `data.users.count` |
| `{"metrics": [{"mrr": 1200}]}` | `metrics.0.mrr` |
| `{"billing": {"mrr_usd": 1200}}` | `billing.mrr_usd`, with **whole units** and currency `USD` |

- A path is keys separated by dots. A number picks an item from a list: `0` is the first.
- Empty boxes keep the standard path.
- The example reply on the settings page follows your paths as you type.
- After **Test connection**, fields that weren't in your reply are marked.

What stays fixed: the screens and the numbers on them. A path can only say where to find each value,
not add new ones.

## HTTPS

DeskBot is a small microcontroller, so it has some limits:

- **TLS 1.2.** A server that only accepts TLS 1.3 won't work. Almost every host accepts both.
- **Public certificates.** Your certificate must chain to one of about 50 well-known roots:
  Let's Encrypt, Google Trust Services, DigiCert, Sectigo/ZeroSSL, Amazon, GlobalSign,
  GoDaddy/Starfield, Microsoft, SSL.com, Entrust, IdenTrust and a few more. The full list is in
  [deskbot-roots.pem](deskbot-roots.pem). That covers Vercel, Netlify, Cloudflare, AWS, Google
  Cloud, Azure, Heroku, Fly.io, Supabase, Firebase and most other hosts. Self-signed and private CA
  certificates aren't supported.
- **Plain `http://`** works too, for a server on the same network. The key then crosses the network
  unencrypted, so don't use it over the internet.

DeskBot updates itself, and the list of roots can grow with an update.

## Errors DeskBot shows

**Test connection** on the settings page shows the same message as the stats screens.

| Message | What to do |
|---|---|
| Can't reach the API host | Check the address. The host must be reachable from the clock's Wi-Fi |
| Certificate not trusted by DeskBot | Your certificate doesn't chain to a [supported root](#https) |
| Certificate is for another host | The certificate doesn't cover the host name you entered |
| Certificate expired or not valid yet | Renew the certificate |
| Secure connection failed (TLS n) | The server and DeskBot share no TLS 1.2 cipher. See [HTTPS](#https) |
| API key refused (HTTP 401) | Add or replace the key on the settings page |
| No stats at this address (HTTP 404) | Check the path. Without one, DeskBot asks for `/api/v1/stats` |
| Redirected (HTTP 301): use the final URL | Enter the address the redirect points to |
| API took longer than 8 s | Make the endpoint faster, or cache the reply |
| Reply isn't valid JSON | The body must be JSON |
| No known fields in the reply | None of the paths matched. Check the format on the settings page |

A typed address that isn't saved yet can be tested too. DeskBot then only checks that it can reach
the server, and doesn't send the key.

## Check your endpoint

[check_api.py](check_api.py) makes the same request DeskBot makes, using the same root
certificates, and reports what the clock would show. It needs Python 3.8 or later and nothing else.

```bash
python3 check_api.py https://api.example.com
```

It reads the key from `DESKBOT_KEY`, or asks for it without echoing. To check against field paths
saved on a clock, save that clock's format first:

```bash
curl http://deskbot.local/api/format > format.json
python3 check_api.py https://api.example.com --format format.json
```

## Example server

[server.mjs](server.mjs) serves the standard format with Node.js 18 or later, no dependencies:

```bash
DESKBOT_KEY=choose-a-long-random-key node server.mjs
```

It listens on port 8787. Replace `getStats()` with queries against your own database or billing
system. To use it over the internet, run it behind HTTPS on any host, or a reverse proxy with a
certificate from Let's Encrypt.

---

The code in this repository (`server.mjs`, `check_api.py`) is MIT licensed: see [LICENSE](LICENSE).
DeskBot is developed by [dulandias.com](https://dulandias.com).
