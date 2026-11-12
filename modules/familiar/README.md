# The familiar module: do you need it?

**Probably not.** Most ships need two roles: a **Captain** (you) and a **Mate** (one Claude
Code session that owns the queue and dispatches workers). Crew, the reviewer and the lookout
are workers the Mate starts; they are not seats you manage. The full cast is six layers
(Captain, Familiar, Navigator, Mate, Bosun, Crew), and every layer you add is another context to
pay for and another place for authority to blur. Add one only when you can name the problem it
solves.

| You want | Run |
|---|---|
| Work that survives session ends, a queue, bounded workers, hard limits | core (Captain + Mate) |
| The Mate to keep working while you are away, woken by events | `autonomous` (adds the Bosun heartbeat) |
| Someone to argue strategy and shape tickets without touching the queue | `navigator` |
| A standing seat that commands the Mate *for* you across days, rotations and failures | `familiar` |

## Who the Familiar is for

You are a candidate if all of these are true:

- you run the **autonomous** tier and the Mate rotates or restarts often enough that continuity
  between Mates has become your job;
- you talk to the ship from several places or sessions, and you want one seat to turn that
  into ordered, bounded commands with a record of *whose* authority each one carries;
- you want lifecycle supervision ("is a healthy Mate holding the deck?") done by something
  other than you or the Mate itself.

If you mostly sit in the Mate's session and talk to it directly, you do not need a Familiar:
you *are* the command layer, and adding one costs a Mate wake per relayed message.

## What you get

- `familiar.md`: the contract. Authority stack, no split command, the command schema with
  provenance (`authority: standing | relayed-explicit`), the trust bootstrap, the mailbox
  return channel, lifecycle and failure posture, cost rules.
- `familiar-ops.md`: the runbook for a session, wake to close.
- `agents/ship-familiar.md` with two hooks. Both are **positive allow-lists**: the Familiar can
  write its own log, state, docs and drafts and run read-only and lifecycle commands, and
  nothing else. `queue.md` and tickets are refused by mechanism, not by asking nicely.
- `scripts/familiar_drop.py`, the Familiar's only door into `inbox/drops/`: validates, stamps the name
  from the UTC clock, archives read mail. `scripts/familiar_orient.py`, the one-screen wake.
  `scripts/launch-familiar.sh`, with a double-boot guard.
- Skills `familiar-wake` and `familiar-close`, and `templates/persona.example.md` for your own
  voice and preferences.
- Seams: `lib/classify_input.py` won't wake the Mate on a `source: familiar` drop unless this
  module is enabled and the drop validates. That is a wake decision, not a filter: the file
  stays in `inbox/drops/`, and a ship with no install record is not gated, so the Mate runs
  `familiar_drop.py validate` itself before obeying (contract §12). The Navigator reports to
  `inbox/familiar/` instead of the Mate when this module is enabled.

## Install

```
python3 shipkit_init.py --modules familiar --ship-root .
cp modules/familiar/templates/persona.example.md docs/familiar/persona.md   # optional
```

Then the trust bootstrap (contract §4): tell the running Mate yourself, on a surface it
already trusts, that the Familiar is now a command layer, or start a fresh Mate. A drop saying
so is not enough, by design.

## Before you rely on it

This module was extracted from one operator's ship. It has not yet run on a second one.
Expect rough edges, and report them.
