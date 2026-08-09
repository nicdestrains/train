"""Client for the Realtime Trains "Next Generation" API (data.rtt.io).

Replaces the retired api.rtt.io Basic Auth service, which now returns 401
for this account. Auth is a long-life *refresh* token (RTT_API_TOKEN) that
must be exchanged for a short-life access token before querying data.

Behaviours below are all confirmed against the live API rather than docs:
  - the access token lasts ~20 minutes, so exchange once per run
  - queries cap at "maximum query duration is 23h59m", and a local day can
    exceed that across a DST fall-back, so days are fetched in two halves
  - filterTo does the "subsequently calls at" matching server-side
  - the "services" key is omitted entirely when there are no matches
  - the API rate limits aggressively; callers must pace themselves
"""
import os
import time as time_module
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

BASE = "https://data.rtt.io"
LOCATION_PATH = "/gb-nr/location"

ORIGIN_CODE = "QRP"  # Queens Road Peckham (long code PCKHMQD)
TARGET_CODE = "TAT"  # Tattenham Corner (long code TATNHMC)

# Train times are published in UK local time; querying in UTC would slice
# the day at the wrong point during BST.
UK = ZoneInfo("Europe/London")

RATE_LIMIT_PAUSE = 2.0  # seconds between requests
MAX_RETRIES = 4


class RTTError(RuntimeError):
    pass


def get_access_token() -> str:
    """Exchange the long-life refresh token for a short-life access token."""
    refresh = os.environ["RTT_API_TOKEN"]
    resp = requests.get(
        f"{BASE}/api/get_access_token",
        headers={"Authorization": f"Bearer {refresh}"},
        timeout=20,
    )
    if resp.status_code != 200:
        raise RTTError(f"Token exchange failed ({resp.status_code}): {resp.text[:200]}")
    token = resp.json().get("token")
    if not token:
        raise RTTError("Token exchange returned no token")
    return token


def _get(token: str, params: dict) -> dict:
    """GET with backoff, since the API 429s readily."""
    delay = RATE_LIMIT_PAUSE
    for attempt in range(MAX_RETRIES):
        resp = requests.get(
            f"{BASE}{LOCATION_PATH}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        if resp.status_code == 429:
            if attempt == MAX_RETRIES - 1:
                break
            time_module.sleep(delay)
            delay *= 2
            continue
        if resp.status_code != 200:
            raise RTTError(f"Query failed ({resp.status_code}): {resp.text[:200]}")
        return resp.json()
    raise RTTError("Rate limited by RTT after repeated retries")


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day_halves(day: date) -> list:
    """Split a local day into two windows.

    A single whole-day query would sit right on the API's 23h59m ceiling,
    and exceed it outright on the October day that gains an hour, so the
    day is always fetched as two halves.
    """
    start = datetime.combine(day, time(0, 0), tzinfo=UK)
    middle = datetime.combine(day, time(12, 0), tzinfo=UK)
    end = datetime.combine(day, time(23, 59, 59), tzinfo=UK)
    return [(start, middle), (middle, end)]


def fetch_matches(token: str, day: date) -> list:
    """All services from Queens Road Peckham on `day` that go on to call at
    Tattenham Corner. Returns [] when there are none."""
    matches = []
    for window_start, window_end in _day_halves(day):
        body = _get(
            token,
            {
                "code": ORIGIN_CODE,
                "filterTo": TARGET_CODE,
                "timeFrom": _utc(window_start),
                "timeTo": _utc(window_end),
            },
        )
        # Absent rather than empty when nothing matches.
        matches.extend(body.get("services") or [])
        time_module.sleep(RATE_LIMIT_PAUSE)
    return matches


def service_id(service: dict) -> str:
    """Stable per-run identity, e.g. "gb-nr:C18730:2026-08-09"."""
    return service.get("scheduleMetadata", {}).get("uniqueIdentity", "")


def service_date(service: dict) -> str:
    return service.get("scheduleMetadata", {}).get("departureDate", "")


def service_time(service: dict) -> str:
    """Advertised departure from Queens Road Peckham, as HH:MM local."""
    dep = service.get("temporalData", {}).get("departure", {})
    stamp = dep.get("scheduleAdvertised") or dep.get("scheduleInternal")
    if not stamp:
        return "?"
    try:
        return datetime.fromisoformat(stamp).strftime("%H:%M")
    except ValueError:
        return "?"
