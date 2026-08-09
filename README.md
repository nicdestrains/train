# Peckham → Tattenham Corner Watch

Watches the Queens Road Peckham departure board via the
[Realtime Trains API](https://api-portal.rtt.io) for a rare, unscheduled
direct service to Tattenham Corner, and publishes a small dashboard (via
GitHub Pages) showing whether one's been spotted, when the poller last ran,
and the full sighting history.

Runs entirely on GitHub Actions' cron, so nothing needs to stay on locally.

## How it works

1. `notifier.py` asks Realtime Trains for today's services leaving Queens
   Road Peckham (`QRP`) that go on to call at Tattenham Corner (`TAT`).
   The API's `filterTo` parameter does that matching server-side, so a
   quiet day costs one small response rather than a full departure board.
2. New matches are appended to `data.json`, along with the current
   status ("🚂 Train spotted at HH:MM" / "No unscheduled train currently
   spotted") and a `last_checked` timestamp.
3. The GitHub Actions workflow commits the updated `data.json` back
   to the repo after each run, since Actions runners don't persist disk
   between runs.
4. GitHub Pages serves `index.html` (repo root), which fetches `data.json`
   and renders the status, the last-checked time (so you can confirm the
   poller is actually running), and a history table of every sighting.

## Setup

### 1. Realtime Trains API credentials

Sign in at [api-portal.rtt.io](https://api-portal.rtt.io) and request an
API token.

This project uses RTT's **Next Generation** API at `data.rtt.io`. The older
`api.rtt.io` service used an API username and password over HTTP Basic
Auth; it has been retired and now returns `401 Auth Required`, so the
username/password pair is no longer used.

The token you get from the portal is a long-life **refresh** token. It
cannot query data directly — `notifier.py` exchanges it for a short-life
access token (~20 minutes) at the start of every run, via
`GET /api/get_access_token`. That happens automatically; you only ever
need to supply the refresh token.

### 2. GitHub Actions secrets

In the repo settings (`Settings → Secrets and variables → Actions`), add:

| Secret          | Value                            |
|-----------------|----------------------------------|
| `RTT_API_TOKEN` | Your token from api-portal.rtt.io |

No credentials are stored in the code or the repo — only in this secret.
The old `RTT_USERNAME`/`RTT_PASSWORD` secrets are no longer read and can
be deleted.

### 3. GitHub Pages

Go to `Settings → Pages` and set:
- **Source**: Deploy from a branch
- **Branch**: `main`, folder `/ (root)`
- Save

GitHub will publish the dashboard at `https://<your-username>.github.io/<repo-name>/`.
It updates automatically on every push to `main` (including the
automated `data.json` commits from the poller). A `.nojekyll` file sits at
the repo root so GitHub serves `index.html`/`data.json` as-is instead of
running them through Jekyll (which would otherwise auto-render `README.md`
as the site if it ever found no `index.html`).

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

`backfill_history.py` queries each of the last 14 days and seeds
`data.json` with any Tattenham Corner matches it finds. It's deliberately
**not** part of the recurring schedule and never touches
`last_checked`/`status` (those only reflect the live poller).

The API caps a single query at 23h59m and rate limits fairly aggressively,
so each day is fetched as two half-day windows with a short pause between
requests. A 14-day backfill therefore takes a minute or so to run.

Run it once via the Actions tab (**Backfill Historical Data (manual)** →
Run workflow) — it reuses the same `RTT_API_TOKEN` secret. Re-running it
later is safe; already-recorded matches are skipped.

Alternatively, run it locally:

```bash
pip install -r requirements.txt
export RTT_API_TOKEN=...
python backfill_history.py
```

## Local testing

```bash
pip install -r requirements.txt
export RTT_API_TOKEN=...
python notifier.py
```

`data.json` is the single source of truth for the dashboard. Edit or
reset it directly if you want to clear history or force a re-check.
