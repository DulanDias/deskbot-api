#!/usr/bin/env python3
"""Check a DeskBot stats endpoint the way the clock checks it.

    python3 check_api.py https://api.example.com
    python3 check_api.py https://api.example.com --format format.json

Makes DeskBot's request (HTTP/1.0, TLS 1.2, the root certificates in deskbot-roots.pem, an 8 second
limit), then shows each field as the clock would read it. The key comes from the DESKBOT_KEY
environment variable, or is asked for without echoing. --format takes field paths saved on a clock
(curl http://deskbot.local/api/format). Python 3.8 or later, nothing else needed.
"""
import argparse
import getpass
import http.client
import json
import math
import os
import ssl
import sys
import time
import urllib.parse

ROOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deskbot-roots.pem")
TIMEOUT = 8

# (key, standard path, kind, label): the same fields, in the same order, as the clock.
FIELDS = [
    ("usersTotal", "people.total", "count", "Total users"),
    ("usersNewDay", "people.new.1d", "count", "New users today"),
    ("usersNewWeek", "people.new.7d", "count", "New users, 7 days"),
    ("usersNewMonth", "people.new.30d", "count", "New users, 30 days"),
    ("activeDay", "people.active.1d", "count", "Active users today"),
    ("activeWeek", "people.active.7d", "count", "Active users, 7 days"),
    ("activeMonth", "people.active.30d", "count", "Active users, 30 days"),
    ("orgsTrial", "organisations.trial", "count", "Organisations on trial"),
    ("orgsPaying", "organisations.paying", "count", "Paying organisations"),
    ("orgsTrialEnded", "organisations.trialEnded", "count", "Trial ended"),
    ("orgsSuspended", "organisations.suspended", "count", "Suspended"),
    ("mrr", "revenue.mrr", "money", "MRR"),
    ("arr", "revenue.arr", "money", "ARR"),
    ("mrrChange7d", "revenue.change.7d", "change", "MRR change, 7 days"),
    ("mrrChange30d", "revenue.change.30d", "change", "MRR change, 30 days"),
    ("signUpsToday", "positives.signUps.1d", "count", "Sign-ups today"),
    ("conversionsToday", "positives.conversions.1d", "count", "Trials converted today"),
    ("meetingsToday", "positives.meetings.1d", "count", "Meetings today"),
    ("newPayingMonth", "positives.newPayingThisMonth", "count", "New paying this month"),
    ("trialsConverted30d", "positives.trialsConverted30d", "count", "Trials converted, 30 days"),
    ("churnedMonth", "negatives.churnedThisMonth", "count", "Churned this month"),
    ("pastDue", "negatives.pastDue", "count", "Payments past due"),
    ("trialsExpired30d", "negatives.trialsExpired30d", "count", "Trials expired, 30 days"),
    ("sourcesDown", "regions.missing", "names", "Sources that didn't answer"),
]
MISSING = object()


def stats_url(address):
    """As on the clock: no path means /api/v1/stats, a path is used as it is, no scheme means https."""
    url = address.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urllib.parse.urlsplit(url)
    if parts.path in ("", "/"):
        parts = parts._replace(path="/api/v1/stats")
    return urllib.parse.urlunsplit(parts)


def at(root, path):
    value = root
    for key in path.split("."):
        if isinstance(value, list) and key.isdigit():
            value = value[int(key)] if int(key) < len(value) else MISSING
        elif isinstance(value, dict):
            value = value.get(key, MISSING)
        else:
            return MISSING
        if value is MISSING or value is None:
            return MISSING
    return value


def money_entry(value, want):
    if not isinstance(value, list):
        return value
    for entry in value:
        if want and isinstance(entry, dict) and str(entry.get("currency", "")).upper() == want:
            return entry
    return value[0] if value else None


def amount_of(entry, minor):
    amount = entry.get("amount") if isinstance(entry, dict) else entry
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None
    return amount / 100 if minor else amount


def shown(amount, currency):
    """The clock's money(): £ € $ as symbols, other codes in front, never more than three digits."""
    unit = {"GBP": "£", "EUR": "€", "USD": "$"}.get(currency, f"{currency} " if currency else "")
    sign, v, i = "-" if amount < 0 else "", abs(amount), 0
    while v >= 999.5 and i < 3:
        v, i = v / 1000, i + 1
    num = f"{v:.1f}" if i and v < 99.95 else f"{v:.0f}"
    if num.endswith(".0"):
        num = num[:-2]
    return f"{sign}{unit}{num}{['', 'K', 'M', 'B'][i]}"


def request(url, key):
    parts = urllib.parse.urlsplit(url)
    notes = []
    if parts.scheme == "https":
        ctx = ssl.create_default_context(cafile=ROOTS)
        try:
            ctx.maximum_version = ssl.TLSVersion.TLSv1_2  # DeskBot speaks TLS 1.2
        except (AttributeError, ValueError):
            notes.append("This Python can't limit itself to TLS 1.2, so a TLS 1.3-only server would pass here.")
        conn = http.client.HTTPSConnection(parts.hostname, parts.port or 443, timeout=TIMEOUT, context=ctx)
    elif parts.scheme == "http":
        notes.append("Plain http: the key crosses the network unencrypted. Fine on your own network only.")
        conn = http.client.HTTPConnection(parts.hostname, parts.port or 80, timeout=TIMEOUT)
    else:
        sys.exit("The address must start with https:// or http://")
    conn._http_vsn, conn._http_vsn_str = 10, "HTTP/1.0"  # as the clock sends it
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": "DeskBot-check/1"}
    start = time.monotonic()
    conn.request("GET", path, headers=headers)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp, body, time.monotonic() - start, notes


def explain_tls(err):
    text = str(err)
    if "wrong version number" in text or "record layer" in text:
        return "That address doesn't answer HTTPS. For a plain-http server, start it with http://"
    if "hostname" in text or "match" in text:
        return "Certificate is for another host"
    if "expired" in text or "not yet valid" in text:
        return "Certificate expired or not valid yet"
    if "verify failed" in text:
        return "Certificate not trusted by DeskBot: it doesn't chain to a root in deskbot-roots.pem"
    if "version" in text or "protocol" in text:
        return "No TLS 1.2: DeskBot can't talk to a TLS 1.3-only server"
    return f"Secure connection failed ({text})"


def main():
    ap = argparse.ArgumentParser(description="Check a DeskBot stats endpoint the way the clock does.")
    ap.add_argument("address", help="as you'd enter it on DeskBot's settings page")
    ap.add_argument("--format", help="field paths saved on a clock: curl http://deskbot.local/api/format")
    args = ap.parse_args()

    fmt = {"currency": "", "minorUnits": True, "paths": {}}
    if args.format:
        with open(args.format) as f:
            fmt.update(json.load(f))
    currency, minor = (fmt.get("currency") or "").upper(), fmt.get("minorUnits", True)
    key = os.environ.get("DESKBOT_KEY") or getpass.getpass("API key (not shown): ")

    url = stats_url(args.address)
    print(f"GET {url}")
    try:
        resp, body, took, notes = request(url, key)
    except ssl.SSLError as err:
        sys.exit(f"✗ {explain_tls(err)}")
    except (OSError, http.client.HTTPException) as err:
        sys.exit(f"✗ Can't reach the API host ({err})")
    for note in notes:
        print(f"! {note}")

    print(f"{'✓' if resp.status == 200 else '✗'} HTTP {resp.status} in {took:.1f} s, {len(body):,} bytes, "
          f"{resp.getheader('Content-Type', 'no content type')}")
    if took > TIMEOUT:
        print(f"✗ DeskBot gives up after {TIMEOUT} s")
    if resp.status in (301, 302, 307, 308):
        sys.exit(f"✗ Redirected to {resp.getheader('Location')}: DeskBot doesn't follow redirects, so enter that address")
    if resp.status in (401, 403):
        sys.exit("✗ API key refused")
    if resp.status != 200:
        sys.exit("✗ DeskBot needs HTTP 200")
    if resp.getheader("Transfer-Encoding", "").lower() == "chunked":
        print("! Chunked reply to an HTTP/1.0 request: DeskBot can't read it. Send a Content-Length instead.")
    try:
        root = json.loads(body)
    except ValueError:
        sys.exit("✗ Reply isn't valid JSON")

    found, warnings = 0, []
    mrr_currency = currency
    print()
    for name, standard, kind, label in FIELDS:
        path = fmt["paths"].get(name) or standard
        value = at(root, path)
        if value is MISSING:
            print(f"  –  {label:28} {path}: not in the reply")
            continue
        found += 1
        if kind == "count":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                warnings.append(f"{path} should be a number, not {json.dumps(value)[:40]}")
            text = str(value)
        elif kind == "money":
            entry = money_entry(value, mrr_currency)
            amount = amount_of(entry, minor) if entry is not None else None
            cur = (entry.get("currency", "") if isinstance(entry, dict) else "") or currency
            if name == "mrr":
                mrr_currency = cur.upper()
            if amount is None:
                text = "no revenue yet" if value == [] else f"? {json.dumps(value)[:40]}"
                if value != []:
                    warnings.append(f"{path}: expected a number, {{currency, amount}} or a list of those")
            else:
                if minor and isinstance(entry, dict) and isinstance(entry.get("amount"), float) and \
                        not float(entry["amount"]).is_integer():
                    warnings.append(f"{path}: {entry['amount']} has decimals; minor units are whole cents")
                text = f"{shown(amount, cur.upper())} on screen"
        elif kind == "change":
            entry = money_entry(value, mrr_currency)
            if isinstance(entry, (int, float)) and not isinstance(entry, bool):
                pct = entry
            elif isinstance(entry, dict) and isinstance(entry.get("percent"), (int, float)):
                pct = entry["percent"]
            else:
                moved = amount_of(entry, minor) if entry is not None else None
                pct = math.nan if moved and moved > 0 else 0
            text = "new" if isinstance(pct, float) and math.isnan(pct) else f"{pct:+.1f} %"
        else:
            names = [value] if isinstance(value, str) else value if isinstance(value, list) else None
            if names is None:
                warnings.append(f"{path} should be a list of names, or one name")
            text = ", ".join(str(n).upper() for n in names) if names else "all answered"
        print(f"  ✓  {label:28} {path}: {text}")

    print(f"\n{found} of {len(FIELDS)} fields found")
    for w in warnings:
        print(f"! {w}")
    if not found:
        sys.exit("✗ No known fields in the reply: check the paths")
    print("✓ DeskBot can read this endpoint")


if __name__ == "__main__":
    main()
