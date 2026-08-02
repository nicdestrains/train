#!/usr/bin/env python3
"""
Poll Realtime Trains for the Queens Road Peckham departure board and send a
WhatsApp/SMS alert (via Twilio) the first time a service calling at or
terminating at Tattenham Corner shows up.

Credentials are read from environment variables so they can be injected as
GitHub Actions secrets:

  RTT_USERNAME        Realtime Trains API username (api.rtt.io)
  RTT_PASSWORD        Realtime Trains API password
  TWILIO_ACCOUNT_SID  Twilio account SID
  TWILIO_AUTH_TOKEN   Twilio auth token
  TWILIO_FROM_NUMBER  Sending number, e.g. "whatsapp:+14155238886" or "+44..."
  TWILIO_TO_NUMBER    Your number, in the same format as TWILIO_FROM_NUMBER
"""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from twilio.rest import Client

RTT_BASE = "https://api.rtt.io/api/v1/json"
ORIGIN_CRS = "QRP"  # Queens Road Peckham
TARGET_CRS = "TAT"  # Tattenham Corner
STATE_FILE = Path(__file__).parent / "state.json"
STATE_RETENTION_DAYS = 3


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"checked": [], "alerted": []}
    with STATE_FILE.open() as f:
        data = json.load(f)
    data.setdefault("checked", [])
    data.setdefault("alerted", [])
    return data


def save_state(state: dict) -> None:
    cutoff = (date.today() - timedelta(days=STATE_RETENTION_DAYS)).isoformat()
    for key in ("checked", "alerted"):
        state[key] = [entry for entry in state[key] if run_date_of(entry) >= cutoff]
    with STATE_FILE.open("w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")


def run_date_of(service_key: str) -> str:
    # service_key is "<serviceUid>_<runDate>"; runDate is an ISO date so
    # string comparison against another ISO date works for the cutoff check.
    return service_key.rsplit("_", 1)[-1]


def rtt_auth() -> tuple:
    return (os.environ["RTT_USERNAME"], os.environ["RTT_PASSWORD"])


def fetch_departure_board(auth: tuple) -> list:
    resp = requests.get(f"{RTT_BASE}/search/{ORIGIN_CRS}", auth=auth, timeout=20)
    resp.raise_for_status()
    return resp.json().get("services") or []


def fetch_service_detail(auth: tuple, service_uid: str, run_date: str) -> dict:
    year, month, day = run_date.split("-")
    url = f"{RTT_BASE}/service/{service_uid}/{year}/{month}/{day}"
    resp = requests.get(url, auth=auth, timeout=20)
    resp.raise_for_status()
    return resp.json()


def calls_at_target(detail: dict) -> bool:
    return any(loc.get("crs") == TARGET_CRS for loc in detail.get("locations", []))


def send_alert(service_uid: str, detail: dict) -> None:
    origin = detail.get("locations", [{}])[0].get("description", "Queens Road Peckham")
    departure = detail.get("locations", [{}])[0].get("gbttBookedDeparture", "?")
    body = (
        f"Train alert: a service to Tattenham Corner is running from "
        f"{origin} today, departing {departure[:2]}:{departure[2:]}. "
        f"(Service {service_uid})"
    )

    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    client.messages.create(
        body=body,
        from_=os.environ["TWILIO_FROM_NUMBER"],
        to=os.environ["TWILIO_TO_NUMBER"],
    )
    print(f"Alert sent for {service_uid}: {body}")


def main() -> int:
    auth = rtt_auth()
    state = load_state()
    checked = set(state["checked"])
    alerted = set(state["alerted"])

    try:
        services = fetch_departure_board(auth)
    except requests.RequestException as exc:
        print(f"Failed to fetch departure board: {exc}", file=sys.stderr)
        return 1

    for service in services:
        service_uid = service.get("serviceUid")
        run_date = service.get("runDate")
        if not service_uid or not run_date:
            continue

        key = f"{service_uid}_{run_date}"
        if key in checked:
            continue

        try:
            detail = fetch_service_detail(auth, service_uid, run_date)
        except requests.RequestException as exc:
            print(f"Failed to fetch detail for {key}: {exc}", file=sys.stderr)
            continue

        checked.add(key)

        if calls_at_target(detail) and key not in alerted:
            try:
                send_alert(service_uid, detail)
                alerted.add(key)
            except Exception as exc:
                print(f"Failed to send alert for {key}: {exc}", file=sys.stderr)

    state["checked"] = sorted(checked)
    state["alerted"] = sorted(alerted)
    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
