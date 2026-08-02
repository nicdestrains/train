# Peckham → Tattenham Corner Notifier

Watches the Queens Road Peckham departure board via the
[Realtime Trains API](https://api.rtt.io) and sends a WhatsApp/SMS alert
(via Twilio) the first time it spots a service that calls at or terminates
at Tattenham Corner — a rare, unscheduled direct working on this line.

Runs entirely on GitHub Actions' cron, so nothing needs to stay on locally.

## How it works

1. `notifier.py` fetches today's departure board for Queens Road Peckham
   (`QRP`).
2. For each service not already checked, it fetches the full calling
   pattern and checks whether Tattenham Corner (`TAT`) appears in it.
3. Matches trigger a Twilio message. Service IDs (keyed by service UID +
   run date) are recorded in `state.json` so the same service never
   triggers a second alert, and so already-checked non-matching services
   aren't re-fetched on every run.
4. The GitHub Actions workflow commits the updated `state.json` back to
   the repo after each run, since Actions runners don't persist disk
   between runs.
5. A second workflow sends a weekly heartbeat message (`weekly_status.py`)
   so you get a periodic confirmation that the notifier is still running,
   independent of whether a matching train has actually shown up. It does
   a live RTT fetch and reports how many matches were spotted in the last
   7 days, so a broken RTT/Twilio connection shows up even in a quiet week.

## Setup

### 1. Realtime Trains API credentials

Register for a free account at [api.rtt.io](https://api.rtt.io) and note
your API username and password (the API uses HTTP Basic Auth).

### 2. Twilio credentials

Set up a Twilio account with a number capable of sending SMS or WhatsApp
messages (for WhatsApp, this can be the Twilio Sandbox for WhatsApp while
testing). You'll need:

- Account SID
- Auth Token
- A "from" number (e.g. `whatsapp:+14155238886` for WhatsApp, or `+1415...`
  for plain SMS)
- Your "to" number, in the same format (e.g. `whatsapp:+44...`)

### 3. GitHub Actions secrets

In the repo settings (`Settings → Secrets and variables → Actions`), add:

| Secret               | Example                     |
|----------------------|------------------------------|
| `RTT_USERNAME`       | `rttapi_yourname`            |
| `RTT_PASSWORD`       | `your-rtt-password`          |
| `TWILIO_ACCOUNT_SID` | `ACxxxxxxxxxxxxxxxxxxxxxxxx` |
| `TWILIO_AUTH_TOKEN`  | `your-twilio-auth-token`     |
| `TWILIO_FROM_NUMBER` | `whatsapp:+14155238886`      |
| `TWILIO_TO_NUMBER`   | `whatsapp:+447xxxxxxxxx`     |

No credentials are stored in the code or the repo — only in these secrets.

### 4. Schedule

The workflow (`.github/workflows/notify.yml`) polls every 15 minutes by
default:

```yaml
schedule:
  - cron: "*/15 * * * *"
```

Adjust the cron expression to taste (it runs in UTC). You can also trigger
a run manually from the Actions tab via `workflow_dispatch`.

The weekly heartbeat (`.github/workflows/weekly-status.yml`) runs Sundays
at 08:00 UTC:

```yaml
schedule:
  - cron: "0 8 * * 0"
```

GitHub Actions cron only fires on its schedule going forward — it won't
retroactively run for "today" just because the workflow was just added.
To get today's confirmation immediately, open the **Actions** tab →
**Weekly Notifier Status Check** → **Run workflow** to trigger it manually
via `workflow_dispatch`; after that it'll run weekly on its own.

## Local testing

```bash
pip install -r requirements.txt

export RTT_USERNAME=...
export RTT_PASSWORD=...
export TWILIO_ACCOUNT_SID=...
export TWILIO_AUTH_TOKEN=...
export TWILIO_FROM_NUMBER=...
export TWILIO_TO_NUMBER=...

python notifier.py
```

Delete/reset `state.json` (or remove specific keys from it) if you want to
force a re-alert on a service you've already been notified about.
