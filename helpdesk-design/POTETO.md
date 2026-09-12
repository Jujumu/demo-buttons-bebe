# Poteto mode (helpdesk project)

Standing rule for `Jujumu/demo-buttons-bebe` coding work. Syeed turned this on 2026-09-12.

## Who follows it

- **Forge** and any Cursor cloud agent on this fork: full `/poteto-mode` (pstack plugin 9717366).
- **Probe**: evidence-first QA; prove against the real inbox / review server, not vibes.
- **Big Boss**: routes and judges; does not implement product code.

## Non-negotiables (short)

- One thin PR at a time. Sequence into verifiable units. Tests prove behavior.
- Name the data shape before code. Smallest change that works (laziness).
- Unslopped prose. No invented status. Verify on the real artifact before "done".
- Repo: fork only. Cute Things look-only. Human Send only.

## Playbooks we use most here

| Job | Playbook |
|---|---|
| New filter / search / chrome slice | Feature |
| Bug / CI / wrong alias | Bug fix |
| Drive PR to green + merge | Babysit |
| Land a green stack | Shipping |

## Ops

Forge: open cloud agents with poteto bar in the prompt (one job, verify, thin slice). After Clerk+UX clear, squash-merge. Ping Probe for quiet smoke.

Opt out: Syeed says so in chat.
