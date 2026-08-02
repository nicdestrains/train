#!/usr/bin/env python3
"""
Weekly heartbeat: sends a WhatsApp/SMS message confirming the notifier is
still running, and reports whether any Tattenham Corner service has been
spotted from Queens Road Peckham in the past 7 days.

This does its own live fetch of today's departure board (rather than just
reading state.json) so the message also confirms the RTT connection is
still working, not just that the workflow executed.
"""
import sys
from datetime import date, timedelta

import requests

from notifier import load_state, run_date_of
from rtt_client import fetch_departure_board, rtt_auth, send_message

LOOKBACK_DAYS = 7


def recent_alert_count(state: dict) -> int:
    cutoff = (date.today() - timedelta(days=LOOKBACK_DAYS)).isoformat()
    return sum(1 for key in state["alerted"] if run_date_of(key) >= cutoff)


def main() -> int:
    auth = rtt_auth()
    state = load_state()
    matches = recent_alert_count(state)

    try:
        fetch_departure_board(auth)
        rtt_ok = True
    except requests.RequestException as exc:
        print(f"Live RTT check failed: {exc}", file=sys.stderr)
        rtt_ok = False

    if matches == 0:
        match_summary = f"No Tattenham Corner service spotted in the last {LOOKBACK_DAYS} days."
    elif matches == 1:
        match_summary = f"1 Tattenham Corner service was spotted in the last {LOOKBACK_DAYS} days."
    else:
        match_summary = f"{matches} Tattenham Corner services were spotted in the last {LOOKBACK_DAYS} days."

    status = "running normally" if rtt_ok else "running, but the live RTT check just failed"
    body = f"Weekly check-in: Peckham → Tattenham Corner notifier is {status}. {match_summary}"

    send_message(body)
    print(f"Weekly status sent: {body}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
