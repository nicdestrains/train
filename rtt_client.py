"""Shared helpers for talking to the Realtime Trains API and Twilio."""
import os

import requests
from twilio.rest import Client

RTT_BASE = "https://api.rtt.io/api/v1/json"
ORIGIN_CRS = "QRP"  # Queens Road Peckham
TARGET_CRS = "TAT"  # Tattenham Corner


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


def send_message(body: str) -> None:
    client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    client.messages.create(
        body=body,
        from_=os.environ["TWILIO_FROM_NUMBER"],
        to=os.environ["TWILIO_TO_NUMBER"],
    )
