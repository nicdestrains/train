#!/usr/bin/env python3
"""
Poll Realtime Trains for services leaving Queens Road Peckham today that go
on to call at Tattenham Corner, and record them in data.json, which the
GitHub Pages dashboard reads and displays.

Credentials come from an environment variable so it can be injected as a
GitHub Actions secret:

  RTT_API_TOKEN  Realtime Trains API refresh token (from api-portal.rtt.io)
"""
import sys
from datetime import date, datetime, timezone

from data_store import load_data, save_data
from rtt_client import (
    RTTError,
    fetch_matches,
    get_access_token,
    service_date,
    service_id,
    service_time,
)


def compute_status(history: list) -> dict:
    today = date.today().isoformat()
    todays = sorted(h["time"] for h in history if h["date"] == today)
    if todays:
        return {
            "spotted_today": True,
            "time": todays[0],
            "message": f"\U0001f682 Train spotted at {todays[0]}",
        }
    return {
        "spotted_today": False,
        "time": None,
        "message": "No unscheduled train currently spotted",
    }


def main() -> int:
    data = load_data()
    known = {h["service_uid"] for h in data["history"]}

    try:
        token = get_access_token()
        services = fetch_matches(token, date.today())
    except (RTTError, KeyError) as exc:
        print(f"Failed to query RTT: {exc}", file=sys.stderr)
        return 1

    for service in services:
        uid = service_id(service)
        run_date = service_date(service)
        if not uid or not run_date or uid in known:
            continue

        data["history"].append(
            {
                "date": run_date,
                "time": service_time(service),
                "service_uid": uid,
            }
        )
        known.add(uid)
        print(f"New match: {uid}")

    data["history"].sort(key=lambda h: (h["date"], h["time"]), reverse=True)
    data["status"] = compute_status(data["history"])
    data["last_checked"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    save_data(data)
    print(f"Checked OK. {len(services)} match(es) today, {len(data['history'])} total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
