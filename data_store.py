"""Read/write helpers for data.json, the file the GitHub Pages
dashboard fetches and displays."""
import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data.json"

_EMPTY = {
    "last_checked": None,
    "status": {
        "spotted_today": False,
        "message": "No unscheduled train currently spotted",
        "time": None,
    },
    "history": [],
}


def load_data() -> dict:
    if not DATA_FILE.exists():
        return json.loads(json.dumps(_EMPTY))
    with DATA_FILE.open() as f:
        data = json.load(f)
    data.setdefault("last_checked", None)
    data.setdefault("status", dict(_EMPTY["status"]))
    data.setdefault("history", [])
    return data


def save_data(data: dict) -> None:
    with DATA_FILE.open("w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
