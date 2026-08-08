#!/usr/bin/env python3
"""
Poll Realtime Trains for the Queens Road Peckham departure board and record
any service calling at Tattenham Corner in data.json, which the GitHub
Pages dashboard reads and displays.

Credentials are read from environment variables so they can be injected as
GitHub Actions secrets:

  RTT_USERNAME  Realtime Trains API username (api.rtt.io)
  RTT_PASSWORD  Realtime Trains API password
"""
import sys
from datetime import date, datetime, timezone

import requests

from data_store import load_data, save_data
from rtt_client import departure_time, fetch_departure_board, matches_target, rtt_auth


def compute_status(history: list) -> dict:
    today = date.today().isoformat()
    todays_times = sorted(h["time"] for h in history if h["date"] == today)
    if todays_times:
        return {
            "spotted_today": True,
            "time": todays_times[0],
            "message": f"\U0001f682 Train spotted at {todays_times[0]}",
        }
    return {
        "spotted_today": False,
        "time": None,
        "message": "No unscheduled train currently spotted",
    }


def main() -> int:
    auth = rtt_auth()
    data = load_data()
    existing_keys = {(h["date"], h["service_uid"]) for h in data["history"]}

    try:
        services = fetch_departure_board(auth)
    except requests.RequestException as exc:
        print(f"Failed to fetch departure board: {exc}", file=sys.stderr)
        return 1

    for service in services:
        service_uid = service.get("serviceUid")
        run_date = service.get("runDate")
        if not service_uid or not run_date or not matches_target(service):
            continue

        key = (run_date, service_uid)
        if key in existing_keys:
            continue

        data["history"].append(
            {
                "date": run_date,
                "time": departure_time(service),
                "service_uid": service_uid,
            }
        )
        existing_keys.add(key)
        print(f"New match: {service_uid} on {run_date}")

    data["history"].sort(key=lambda h: (h["date"], h["time"]), reverse=True)
    data["status"] = compute_status(data["history"])
    data["last_checked"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    save_data(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
