#!/usr/bin/env python3
"""
One-off historical backfill: queries the RTT API for each day over the past
14 days at Queens Road Peckham, checks for any service also calling at
Tattenham Corner, and seeds data.json's history with any matches found.

Run manually - this is NOT part of the recurring polling schedule, and it
never touches the "last_checked" / "status" fields (those only reflect the
live poller in notifier.py, not this backfill).

Credentials come from the same environment variable as notifier.py:
  RTT_API_TOKEN
"""
import sys
from datetime import date, timedelta

from data_store import load_data, save_data
from rtt_client import (
    RTTError,
    fetch_matches,
    get_access_token,
    service_date,
    service_id,
    service_time,
)

BACKFILL_DAYS = 14


def main() -> int:
    data = load_data()
    known = {h["service_uid"] for h in data["history"]}

    try:
        token = get_access_token()
    except (RTTError, KeyError) as exc:
        print(f"Failed to authenticate with RTT: {exc}", file=sys.stderr)
        return 1

    today = date.today()
    found = 0
    skipped = []
    for offset in range(BACKFILL_DAYS, -1, -1):
        day = today - timedelta(days=offset)
        try:
            services = fetch_matches(token, day)
        except RTTError as exc:
            # Keep going so one bad day doesn't lose the rest of the range,
            # but remember it - a day we never queried is not a day we know
            # had no train.
            print(f"{day}: SKIPPED - {exc}", flush=True)
            skipped.append(day)
            continue

        new_today = 0
        for service in services:
            uid = service_id(service)
            run_date = service_date(service) or day.isoformat()
            if not uid or uid in known:
                continue

            data["history"].append(
                {
                    "date": run_date,
                    "time": service_time(service),
                    "service_uid": uid,
                }
            )
            known.add(uid)
            found += 1
            new_today += 1

        print(f"{day}: {len(services)} match(es), {new_today} new", flush=True)

    # Save whatever was gathered even on a partial run - the days that did
    # succeed are still worth keeping.
    data["history"].sort(key=lambda h: (h["date"], h["time"]), reverse=True)
    save_data(data)

    print(f"\n{found} new match(es) added to history.")
    if skipped:
        # Exiting non-zero matters: a partial backfill reported as success
        # looks exactly like "there were no trains", which is the specific
        # wrong conclusion this project keeps running into.
        print(
            f"INCOMPLETE: {len(skipped)} day(s) could not be queried: "
            f"{', '.join(d.isoformat() for d in skipped)}\n"
            "Re-run this workflow to retry them (already-recorded matches "
            "are skipped, so it is safe).",
            file=sys.stderr,
        )
        return 1

    print(f"Backfill complete. All {BACKFILL_DAYS + 1} days queried.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
