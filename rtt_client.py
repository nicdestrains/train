"""Shared helpers for talking to the Realtime Trains API."""
import os
from datetime import date

import requests

RTT_BASE = "https://api.rtt.io/api/v1/json"
ORIGIN_CRS = "QRP"  # Queens Road Peckham

# The search/departure-board response's destination entries only carry a
# tiploc (not a crs code), so matching happens on tiploc.
TARGET_TIPLOC = "TATNHMC"  # Tattenham Corner


def rtt_auth() -> tuple:
    return (os.environ["RTT_USERNAME"], os.environ["RTT_PASSWORD"])


def fetch_departure_board(auth: tuple, on_date: date = None) -> list:
    """Fetch the QRP departure board.

    With `on_date` set, queries that specific day (RTT's dated search
    endpoint); otherwise RTT returns the rolling board around now.
    """
    url = f"{RTT_BASE}/search/{ORIGIN_CRS}"
    if on_date is not None:
        url += f"/{on_date:%Y/%m/%d}"
    resp = requests.get(url, auth=auth, timeout=20)
    resp.raise_for_status()
    return resp.json().get("services") or []


def matches_target(service: dict) -> bool:
    # Tattenham Corner is a branch terminus, so any service that reaches it
    # terminates there - checking the board's destination is equivalent to
    # checking the full calling pattern, without an extra API call per service.
    destinations = service.get("locationDetail", {}).get("destination", [])
    return any(d.get("tiploc") == TARGET_TIPLOC for d in destinations)


def departure_time(service: dict) -> str:
    """Booked public departure time from Queens Road Peckham, as HH:MM."""
    t = service.get("locationDetail", {}).get("gbttBookedDeparture")
    if not t or len(t) != 4:
        return "?"
    return f"{t[:2]}:{t[2:]}"
