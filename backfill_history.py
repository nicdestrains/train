#!/usr/bin/env python3
"""
One-off historical backfill: queries the RTT API for each day over the past
~6 months at Queens Road Peckham, checks for any service also calling at
Tattenham Corner, and seeds data.json's history with any matches found.

Run manually - this is NOT part of the recurring polling schedule, and it
never touches the "last_checked" / "status" fields (those only reflect the
live poller in notifier.py, not this backfill).

Credentials are read from the same environment variables as notifier.py:
  RTT_USERNAME, RTT_PASSWORD
"""
import sys
from datetime import date, timedelta

import requests

from data_store import load_data, save_data
from rtt_client import departure_time, fetch_departure_board, matches_target, rtt_auth

BACKFILL_DAYS = 183  # roughly 6 months


def main() -> int:
    auth = rtt_auth()
    data = load_data()
    existing_keys = {(h["date"], h["service_uid"]) for h in data["history"]}

    today = date.today()
    found = 0
    for offset in range(BACKFILL_DAYS, -1, -1):
        day = today - timedelta(days=offset)
        try:
            services = fetch_departure_board(auth, on_date=day)
        except requests.RequestException as exc:
            print(f"Failed to fetch board for {day}: {exc}", file=sys.stderr)
            continue

        day_matches = 0
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
            found += 1
            day_matches += 1

        print(f"{day}: {len(services)} services checked, {day_matches} match(es)")

    data["history"].sort(key=lambda h: (h["date"], h["time"]), reverse=True)
    save_data(data)
    print(f"Backfill complete. {found} new match(es) added to history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
