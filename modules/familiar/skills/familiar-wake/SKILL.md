---
name: familiar-wake
description: Open a Familiar seat. Orient from durable state in one screen, read and archive the mailbox, settle whether a healthy Mate holds the deck, then write the seat-open line and wait for the Captain. Run at the start of every Familiar session (launch-familiar.sh starts a background seat with it).
---

# Familiar wake

The wake spends what the last close saved. Do the steps in order and keep them cheap: read
state, not the Mate. Doctrine: `modules/familiar/familiar.md`; runbook:
`modules/familiar/familiar-ops.md`.

1. **Load the contract.** Read `modules/familiar/familiar.md` and `familiar-ops.md`, plus
   `docs/familiar/persona.md` and `docs/familiar/ops.local.md` if they exist.

2. **Orient.** From the ship root:

   ```
   python3 modules/familiar/scripts/familiar_orient.py --open-log
   ```

   Note anything it reports as absent or unreadable; an absent signal is not a quiet one.

3. **Read the mail, all of it.** Every file in `inbox/familiar/` that orient listed. For each:
   - triage it against live state before acting (much of an old pile is already satisfied);
   - act or plan;
   - archive it once processed:
     `python3 modules/familiar/scripts/familiar_drop.py archive <name>`.
   Leave an undecided proposal unread on purpose, and say so in your log.

4. **Check your own commands.** Orient lists `familiar-*` drops the Mate has not processed. One
   older than the Mate's normal wake latency means the Mate is not waking or not reading:
   that is a lifecycle question, not a reason to resend.

5. **Settle the lifecycle question** (contract §6) for whatever orient could not: lock holder
   versus a live `ship-mate` session (`claude agents --json`), status age, Bosun
   (`modules/autonomous/scripts/launch-bosun.sh --check`). Never conclude from one signal.

6. **Write the seat-open line** in today's `logs/familiar/` file: what you found, the one thing
   that matters most, and what you will do first.

7. **Ask the Captain what they need,** leading with the single decision that is waiting on them,
   if there is one. Then wait.
