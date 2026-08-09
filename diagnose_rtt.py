#!/usr/bin/env python3
"""
Diagnostic probe - run manually to work out which RTT API this account can
actually use, and what the response actually looks like.

This exists because the legacy api.rtt.io Basic Auth endpoint started
returning 401 for every request. RTT has since launched a token-based
"Next Generation" API at data.rtt.io, so this script probes both and dumps
enough of the real response to write the matching logic against.

It prints NO credential values - only whether each env var is set, and the
HTTP status / response shape. GitHub Actions additionally masks secrets.

Env vars (all optional - each probe is skipped if its creds are missing):
  RTT_USERNAME, RTT_PASSWORD   legacy api.rtt.io Basic Auth
  RTT_API_TOKEN                new data.rtt.io Bearer token
"""
import json
import os
import sys
from datetime import date, timedelta

import requests

LEGACY_BASE = "https://api.rtt.io/api/v1/json"
NEW_BASE = "https://data.rtt.io"

ORIGIN_CODE = "QRP"  # Queens Road Peckham
TARGET_CODE = "TAT"  # Tattenham Corner

# How much of a JSON body to show. Enough to see the schema, short enough
# to stay readable in an Actions log.
PREVIEW_CHARS = 4000


def day_params(day: date, filter_to: str = None) -> dict:
    """Whole-day window. The API defaults to only 60 minutes, so any
    "what ran on this date" question has to say so explicitly."""
    params = {
        "code": ORIGIN_CODE,
        "timeFrom": f"{day.isoformat()}T00:00:00Z",
        "timeTo": f"{day.isoformat()}T23:59:59Z",
    }
    if filter_to:
        params["filterTo"] = filter_to
    return params


def summarise_services(services: list) -> None:
    """One line per service. Full-day windows return far too much JSON to
    read raw, and the fields that matter for matching are few."""
    print(f"len(services) = {len(services)}")
    for svc in services[:40]:
        meta = svc.get("scheduleMetadata", {})
        dep = svc.get("temporalData", {}).get("departure", {})
        when = dep.get("scheduleAdvertised") or dep.get("scheduleInternal") or "?"
        dests = []
        for d in svc.get("destination", []):
            loc = d.get("location", {})
            codes = ",".join(loc.get("longCodes", []))
            dests.append(f"{loc.get('description')} [{codes}]")
        print(
            f"  {when}  {meta.get('uniqueIdentity')}  "
            f"{meta.get('operator', {}).get('code')}  -> {'; '.join(dests)}"
        )
    if len(services) > 40:
        print(f"  ... {len(services) - 40} more")


def show(label: str, resp: requests.Response) -> None:
    print(f"\n--- {label} ---")
    print(f"URL:    {resp.url}")
    print(f"Status: {resp.status_code}")
    ctype = resp.headers.get("content-type", "")
    print(f"Type:   {ctype}")

    if "json" not in ctype:
        print(f"Body (first {PREVIEW_CHARS} chars):")
        print(resp.text[:PREVIEW_CHARS])
        return

    body = resp.json()
    if not isinstance(body, dict):
        print(json.dumps(body, indent=2)[:PREVIEW_CHARS])
        return

    print(f"Top-level keys: {list(body.keys())}")
    # A "services" key that is absent entirely means zero matches - the API
    # omits it rather than returning an empty list.
    if "services" in body:
        summarise_services(body["services"])
    else:
        print("NO services key -> zero results for this query.")
        print(f"query echo: {json.dumps(body.get('query'))[:800]}")


def probe_legacy() -> None:
    user, password = os.environ.get("RTT_USERNAME"), os.environ.get("RTT_PASSWORD")
    print(f"\n=== LEGACY api.rtt.io (set: {bool(user)}/{bool(password)}) ===")
    if not user or not password:
        print("Skipped - RTT_USERNAME/RTT_PASSWORD not set.")
        return
    try:
        resp = requests.get(
            f"{LEGACY_BASE}/search/{ORIGIN_CODE}", auth=(user, password), timeout=20
        )
        show("legacy search", resp)
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")


def exchange_for_access_token(refresh_token: str) -> str:
    """RTT issues long-life *refresh* tokens that must be swapped for a
    short-life access token before querying data endpoints. Using a refresh
    token directly as the bearer returns "Invalid or expired token", so try
    the exchange and fall back to using the token as-is."""
    print("\n--- token exchange: GET /api/get_access_token ---")
    try:
        resp = requests.get(
            f"{NEW_BASE}/api/get_access_token",
            headers={"Authorization": f"Bearer {refresh_token}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"Request failed: {exc}")
        return refresh_token

    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Body: {resp.text[:500]}")
        print("-> Exchange failed; will retry queries with the raw token.")
        return refresh_token

    body = resp.json()
    access = body.get("token")
    # Never print the token itself - only proof we got one, and its metadata.
    print(f"Got access token: {bool(access)} (len {len(access) if access else 0})")
    print(f"validUntil:   {body.get('validUntil')}")
    print(f"entitlements: {json.dumps(body.get('entitlements'))[:1500]}")
    return access or refresh_token


def probe_new() -> None:
    token = os.environ.get("RTT_API_TOKEN")
    print(f"\n=== NEW data.rtt.io (token set: {bool(token)}) ===")
    if not token:
        print("Skipped - RTT_API_TOKEN not set.")
        return

    token = exchange_for_access_token(token)
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()
    past = today - timedelta(days=7)

    # The first run proved auth works but told us little else: filterTo=TAT
    # returned no services, which is indistinguishable from filterTo being
    # broken. So probe two things that actually discriminate:
    #
    #  1. CONTROL - filterTo against Battersea Park, a destination the
    #     unfiltered board definitely serves. Services here means filterTo
    #     works and an empty TAT result is a real "no train", not a bug.
    #  2. HISTORY - a past date, since the access token reported no
    #     entitlements and the backfill depends on historical queries.
    probes = [
        ("today, full day, unfiltered", day_params(today)),
        ("today, full day, filterTo=BATRSPK (CONTROL)", day_params(today, "BATRSPK")),
        ("today, full day, filterTo=TAT", day_params(today, TARGET_CODE)),
        (f"past {past}, full day, unfiltered", day_params(past)),
        (f"past {past}, full day, filterTo=TAT", day_params(past, TARGET_CODE)),
    ]
    for label, params in probes:
        try:
            resp = requests.get(
                f"{NEW_BASE}/gb-nr/location", headers=headers, params=params, timeout=30
            )
        except requests.RequestException as exc:
            print(f"\n--- {label} ---\nRequest failed: {exc}")
            continue
        show(label, resp)


def main() -> int:
    probe_legacy()
    probe_new()
    print("\nDone. No credential values are printed above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
