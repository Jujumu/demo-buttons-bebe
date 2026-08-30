# Heartbeat alert — install guide

**What it does in one sentence:** every 5 minutes a tiny script checks that the
ticket processor is still running and still doing something; if it isn't, you
get one WhatsApp message, and one more when it comes back.

Without this, if the processor dies at 2am nobody finds out until tickets pile
up in the morning.

## What gets installed

| File | Where it goes on the VPS | What it is |
|---|---|---|
| `processor/heartbeat.sh` | `/opt/buttonsbebe/processor/heartbeat.sh` | The check itself |
| `deploy/systemd/buttonsbebe-heartbeat.service` | `/etc/systemd/system/` | How to run the check |
| `deploy/systemd/buttonsbebe-heartbeat.timer` | `/etc/systemd/system/` | How often to run it (every 5 min) |

## Install

```bash
cd "/opt/buttonsbebe"
install -m 755 processor/heartbeat.sh "/opt/buttonsbebe/processor/heartbeat.sh"
cp deploy/systemd/buttonsbebe-heartbeat.service /etc/systemd/system/
cp deploy/systemd/buttonsbebe-heartbeat.timer   /etc/systemd/system/

# The heartbeat needs the same two WhatsApp values the processor already uses.
mkdir -p /etc/systemd/system/buttonsbebe-heartbeat.service.d
cp /etc/systemd/system/buttonsbebe-processor.service.d/whatsapp.conf \
   /etc/systemd/system/buttonsbebe-heartbeat.service.d/whatsapp.conf

systemctl daemon-reload
systemctl enable --now buttonsbebe-heartbeat.timer
```

## Check it worked

```bash
systemctl list-timers | grep buttonsbebe-heartbeat   # should show a next-run time
systemctl start buttonsbebe-heartbeat.service        # run one check right now
journalctl -u buttonsbebe-heartbeat -n 20            # should say "processor healthy"
```

## Prove the alert actually fires

Do this once, in a quiet hour:

```bash
systemctl stop buttonsbebe-processor
# wait up to 5 minutes → one WhatsApp message should arrive
systemctl start buttonsbebe-processor
# wait up to 5 more minutes → one "back up" message should arrive
```

You should get **exactly two** messages, not a stream of them. If you get
repeats while it is down, the state file is not persisting — check that
`StateDirectory=buttonsbebe` is still in the service unit and that nothing
added `PrivateTmp=true`.

If you get **no** message at all, check `journalctl -u buttonsbebe-heartbeat`.
An alert is only marked as sent once WhatsApp actually accepted it, so a failed
delivery logs `staying unlatched` and retries on the next firing rather than
going quiet.

## Settings you can change

All of these are read from the environment, so they go in the `.env` or in the
service drop-in:

| Variable | Default | Meaning |
|---|---|---|
| `PROCESSOR_UNIT` | `buttonsbebe-processor` | Which service to watch |
| `HEARTBEAT_STALE_MINUTES` | `10` | No completed work in this long counts as "hung" |
| `HEARTBEAT_STATE_FILE` | `/var/lib/buttonsbebe/heartbeat.state` | Where the "already alerted" marker lives |
| `PROCESSOR_HEARTBEAT_SECONDS` | `120` | How often the processor logs "still alive" while idle |

`PROCESSOR_HEARTBEAT_SECONDS` must stay comfortably below
`HEARTBEAT_STALE_MINUTES × 60`, otherwise a quiet queue looks like a hang.

Note these are deliberately **two different settings**. `PROCESSOR_STALE_MINUTES`
belongs to the queue — it decides when a job stuck in `processing` gets retried.
Reusing it here meant that tuning the queue silently widened or narrowed the
dead-man's switch. Keep both out of the shared `.env`: systemd merges
`EnvironmentFile=` **after** `Environment=`, so anything in the `.env` would
override the unit.

## Safety

The script can only read systemd state and POST one message. Every failure
path exits 0, so it can never take a service down. Its WhatsApp credentials
travel in an `Authorization: Bearer` header — the same contract
`processor/whatsapp_notifier.py` uses — never in the URL.
