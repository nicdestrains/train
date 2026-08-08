# Peckham → Tattenham Corner Watch

Watches the Queens Road Peckham departure board via the
[Realtime Trains API](https://api.rtt.io) for a rare, unscheduled direct
service to Tattenham Corner, and publishes a small dashboard (via GitHub
Pages) showing whether one's been spotted, when the poller last ran, and
the full sighting history.

Runs entirely on GitHub Actions' cron, so nothing needs to stay on locally.

## How it works

1. `notifier.py` fetches today's departure board for Queens Road Peckham
   (`QRP`) and checks each service's destination for Tattenham Corner
   (TIPLOC `TATNHMC`). Tattenham Corner is a branch terminus, so any
   service reaching it terminates there — checking the destination is
   enough, no extra per-service lookup needed.
2. New matches are appended to `docs/data.json`, along with the current
   status ("🚂 Train spotted at HH:MM" / "No unscheduled train currently
   spotted") and a `last_checked` timestamp.
3. The GitHub Actions workflow commits the updated `docs/data.json` back
   to the repo after each run, since Actions runners don't persist disk
   between runs.
4. GitHub Pages serves `docs/index.html`, which fetches `data.json` and
   renders the status, the last-checked time (so you can confirm the
   poller is actually running), and a history table of every sighting.

## Setup

### 1. Realtime Trains API credentials

Register for a free account at [api.rtt.io](https://api.rtt.io) and note
your API username and password (the API uses HTTP Basic Auth).

### 2. GitHub Actions secrets

In the repo settings (`Settings → Secrets and variables → Actions`), add:

| Secret         | Example            |
|----------------|---------------------|
| `RTT_USERNAME` | `rttapi_yourname`   |
| `RTT_PASSWORD` | `your-rtt-password` |

No credentials are stored in the code or the repo — only in these secrets.

### 3. GitHub Pages

Go to `Settings → Pages` and set:
- **Source**: Deploy from a branch
- **Branch**: `main`, folder `/docs`
- Save

GitHub will publish the dashboard at `https://<your-username>.github.io/<repo-name>/`.
It updates automatically on every push to `main` (including the
automated `docs/data.json` commits from the poller).

### 4. Schedule

The polling workflow (`.github/workflows/notify.yml`) runs every 15
minutes by default:

```yaml
schedule:
  - cron: "*/15 * * * *"
```

Adjust the cron expression to taste (it runs in UTC). You can also trigger
a run manually from the Actions tab via `workflow_dispatch`.

### 5. One-off historical backfill

`backfill_history.py` queries RTT's dated search endpoint for each day
over the last ~6 months and seeds `docs/data.json` with any Tattenham
Corner matches it finds. It's deliberately **not** part of the recurring
schedule and never touches `last_checked`/`status` (those only reflect the
live poller).

Run it once via the Actions tab (**Backfill Historical Data (manual)** →
Run workflow) — it reuses the same `RTT_USERNAME`/`RTT_PASSWORD` secrets.
Re-running it later is safe; already-recorded matches are skipped.

Alternatively, run it locally:

```bash
pip install -r requirements.txt
export RTT_USERNAME=...
export RTT_PASSWORD=...
python backfill_history.py
```

## Local testing

```bash
pip install -r requirements.txt
export RTT_USERNAME=...
export RTT_PASSWORD=...
python notifier.py
```

`docs/data.json` is the single source of truth for the dashboard. Edit or
reset it directly if you want to clear history or force a re-check.
