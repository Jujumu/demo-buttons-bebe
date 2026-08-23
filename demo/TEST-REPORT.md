# Cute Things Demo — Adversarial Test Report

Date: 2026-08-23

## Outcome

The real webhook, queue, processor, Hermes runner, review-console API, learning
capture, and notification paths completed an isolated end-to-end campaign using
only synthetic Cute Things data and localhost simulators. The release-equivalent
offline gate and all added adversarial suites pass.

This report does **not** claim that the current VPS deployment or live Buttons
Bebe integrations were tested. Nothing was pushed or deployed.

## Isolation boundary

- Shopify target: `yznyc1-ez.myshopify.com` (Cute Things demo store).
- Gorgias REST: `127.0.0.1:8190`, captured locally with `delivered=false`.
- KB, Redo, and Gorgias MCPs: `127.0.0.1:8177-8179`.
- WhatsApp: `127.0.0.1:8185`, captured locally with `delivered=false`.
- Webhook/console API: `127.0.0.1:8100`; demo console: `127.0.0.1:8101`.
- Queue database and learning files: ignored demo-only paths under
  `webhook/data/` and `demo/data/` (the first campaign used `/tmp`).
- Hermes profile: explicit `cutethingsdemo`; the default profile was not edited.
- Demo-mode settings ignore the shared root `.env`, and the safe launcher clears
  inherited client-integration variables before importing application code.
- Hermes runs with `--ignore-rules` plus only the three demo MCP toolsets; its
  demo profile `.env` contains no client-integration credential.
- Demo configuration declares zero Shopify mutations and rejects non-local
  Gorgias, result, and WhatsApp endpoints.

## Real-stack campaign

The campaign used the real application code and real Hermes executable with the
three fake, read-only MCPs:

1. A normal delayed-tracking ticket was signed and submitted to the real webhook.
2. The real queue and processor claimed it once, Hermes produced a normal draft,
   and the dashboard stored it as `normal/drafted`.
3. Re-delivery of the same message returned `duplicate` and created no second job.
4. A cancellation/refund ticket was classified `critical/sensitive_draft`, kept
   its sensitive-review warning, and created one simulated WhatsApp owner alert.
5. The console successfully loaded both tickets and showed one normal and one
   critical result with zero failures.
6. An unconfirmed public send was rejected with HTTP 409. A confirmed public
   send and an internal note were captured by the local Gorgias sink only.
7. A rewrite used the explicit demo Hermes profile and the `todo`-only rewrite
   tool allowance. It created a learning entry without adding a Gorgias action.

Final captured state:

- Jobs: 2 done, 0 failed.
- Results: 1 normal draft, 1 critical sensitive draft.
- WhatsApp alerts: 1 simulated, 0 delivered externally.
- Gorgias actions: 2 simulated (`note`, `send`), both `delivered=false`.
- Learning actions: 3, stored only in the throwaway demo KB path.

## Faults found and fixed

- Multiple concurrent workers could all report that they claimed one job.
- Concurrent duplicate webhooks could enqueue duplicate jobs.
- Stale-job recovery read a column it had not selected.
- Invalid, missing, future, and timezone-less event timestamps were accepted.
- Non-object JSON shapes, malformed nested fields, huge IDs, invalid sender roles,
  and payloads larger than 1 MiB could bypass validation or produce server errors.
- Result and console-action APIs accepted malformed field types and unsafe limits.
- Public send relied only on browser confirmation; it now requires
  `confirmed=true` at the server boundary as well.
- Send, note, and rewrite accepted ticket IDs absent from the review console.
- The processor result URL and Gorgias REST base URL were not demo-configurable.
- The current local Hermes CLI required explicit profile and direct MCP names;
  demo execution now supplies both without changing production defaults.
- `HERMES_HOME` collided with Hermes' own profile resolver; the OS home override
  is now `HERMES_OS_HOME`.
- Rewrite had no explicit tool allowance; it is now restricted to `todo` by
  default and is asserted by a regression test.
- The real Gorgias adapter had an undefined fallback variable and its demo test
  depended on test execution order. Both were fixed.
- A final Luna isolation audit found shared-root `.env` fallback, unbounded
  callback destinations, inherited legacy Shopify variables, a copied Hermes
  profile environment, and direct fake-server host overrides. Demo mode now
  rejects all five paths at runtime, and `run_real_stack.sh` is the supported
  one-command launcher.
- The follow-up audit found substring-only path validation; database and learning
  storage are now confined to exact approved demo directories, arbitrary launcher
  env-file selection was removed, and deceptive `client-data/demo-*` paths have
  regression coverage.
- The standalone `cutethingsdemo` wrapper now whitelists only locked interactive,
  help/version, or exactly one one-shot prompt; appended profile/toolset overrides
  are rejected before Hermes starts.

## Verification

Targeted adversarial suites:

```bash
processor/.venv/bin/python -m unittest \
  demo.adversarial.test_demo_isolation \
  demo.adversarial.test_processor_adversarial \
  demo.adversarial.test_processor_security \
  demo.adversarial.test_queue_resilience -v

WEBHOOK_SECRET=demo-console-adversarial-secret PYTHONPATH=webhook/src \
  webhook/.venv/bin/python -m unittest \
  demo.adversarial.test_webhook_adversarial \
  demo.adversarial.test_console_api \
  demo.test_real_gorgias_client \
  webhook.test_notifications webhook.test_notification_api -v

python3 -m unittest discover -s demo -p 'test_fake_*.py' -v
python3 demo/verify_config.py demo/.env.example
```

Result: 122 targeted tests passed (64 isolation/processor/queue, 34 webhook/console/client,
24 simulator tests), and the demo configuration validator passed.

Repository release-equivalent gate:

```bash
PROCESSOR_PYTHON=processor/.venv/bin/python bash tools/verify_release.sh
```

Result: passed, including 338 processor tests, classifier self-tests, KB/index
safety tests, deployment guardrails, tool contracts, WhatsApp auth, KB admin,
75-file Python syntax validation, 31 shell-script checks, manifests, and the
no-Twilio check.

## Remaining limits

- Model authenticity checks are not semantic data-loss prevention. A valid
  model draft may still contain undesirable text, so human review remains a
  required safety boundary.
- Browser automation reached the real JavaScript confirmation dialog but its
  controller timed out while the modal was open. The dialog was visibly present,
  and the server-side confirmation requirement was independently verified.
- Before any production deployment, verify the three live Hermes MCP names on
  the VPS. Local Hermes uses direct names while production defaults retain the
  currently documented `mcp-buttonsbebe_*` names.
- Live Gorgias, Redo, WhatsApp, and VPS behavior were deliberately excluded to
  protect client data. Confidence is high for the isolated application path,
  not a claim of live-integration certification.
