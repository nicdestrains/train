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

import requests

LEGACY_BASE = "https://api.rtt.io/api/v1/json"
NEW_BASE = "https://data.rtt.io"

ORIGIN_CODE = "QRP"  # Queens Road Peckham
TARGET_CODE = "TAT"  # Tattenham Corner

# How much of a JSON body to show. Enough to see the schema, short enough
# to stay readable in an Actions log.
PREVIEW_CHARS = 4000


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
    if isinstance(body, dict):
        print(f"Top-level keys: {list(body.keys())}")
        for key in ("services", "locations"):
            if isinstance(body.get(key), list):
                print(f"len({key}) = {len(body[key])}")
    print(f"Body (first {PREVIEW_CHARS} chars):")
    print(json.dumps(body, indent=2)[:PREVIEW_CHARS])


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


def probe_new() -> None:
    token = os.environ.get("RTT_API_TOKEN")
    print(f"\n=== NEW data.rtt.io (token set: {bool(token)}) ===")
    if not token:
        print("Skipped - RTT_API_TOKEN not set.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # Plain board first: confirms auth works and shows the response schema.
    # Then the same query with filterTo, which should make RTT do the
    # "subsequently calls at Tattenham Corner" matching server-side.
    probes = [
        ("new: board only", {"code": ORIGIN_CODE}),
        ("new: board + filterTo", {"code": ORIGIN_CODE, "filterTo": TARGET_CODE}),
        (
            "new: board + filterTo + detailed",
            {"code": ORIGIN_CODE, "filterTo": TARGET_CODE, "detailed": "true"},
        ),
    ]
    for label, params in probes:
        for path in ("/gb-nr/location", "/rtt/location"):
            try:
                resp = requests.get(
                    f"{NEW_BASE}{path}", headers=headers, params=params, timeout=20
                )
            except requests.RequestException as exc:
                print(f"\n--- {label} [{path}] ---\nRequest failed: {exc}")
                continue
            show(f"{label} [{path}]", resp)
            # If the namespaced path works, no need to try the generic one.
            if resp.status_code == 200:
                break


def main() -> int:
    probe_legacy()
    probe_new()
    print("\nDone. No credential values are printed above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
