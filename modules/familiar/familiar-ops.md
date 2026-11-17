# Familiar operating notes

The runbook that goes with the contract ([familiar.md](familiar.md)). The contract says what
the seat may do; this says how a session runs well. Your own recurring chores (weekly checks,
house conventions) belong in `docs/familiar/ops.local.md`, which the Familiar can edit and
which this module never overwrites.

## Starting a seat

```
modules/familiar/scripts/launch-familiar.sh --check     # is one already standing?
modules/familiar/scripts/launch-familiar.sh --ensure    # background seat, only if none is
claude --agent ship-familiar                            # or an interactive one
```

`--ensure` refuses to start a second seat and names the live one instead; two Familiars send
conflicting commands to one Mate. It also refuses when it cannot tell (the `claude agents`
scan failed): a scan that did not run is not a scan that found nothing. `--force` is the
deliberate override. The guard can only see background seats; it cannot see an interactive one
in another terminal.

## Wake, in this order (the `familiar-wake` skill)

0. **`python3 modules/familiar/scripts/familiar_orient.py --open-log`.** One screen: Mate lock
   holder and heartbeat age, `status.json` age and current activity, Bosun heartbeat, unread mail
   with subjects, your commands the Mate has not yet processed, today's Mate log watch count,
   and the last `## Note to tomorrow`. It starts today's `logs/familiar/` file if needed.
1. **Read every note in `inbox/familiar/`.** This is step 1, not an afterthought: the Mate's
   results, its pushback and the Navigator's proposals all land here, and the one
   time-sensitive fact of the day is usually in a note nobody has read. Archive each processed
   note: `familiar_drop.py archive <name>`.
2. **Settle the lifecycle question** (contract §6) for anything orient could not answer. The
   check orient is worst at is *identity*: which session holds the lock, and is that session
   the one that is live?
3. **Check the budget before planning the session.** Rotations and wakes are the expensive
   moves; know the weekly position before ordering either.
4. **Write the seat-open line** in today's log, then ask the Captain what they need.

## Close, in this order (the `familiar-close` skill)

The wake reads what the close writes, so the close is where continuity is made or lost.

1. **Mate wind-down by command, not only by message,** if the day is ending: housekeeping, the
   compound pass, the end-of-day standup, then a rotation to the night posture. Its handoff must
   carry tomorrow's plan in order, the open Captain one-liners, and anything unpushed (branch
   and SHA).
2. **Verify the successor's model from its transcript.** The session name and the agents list
   only repeat the launch flag.
3. **Archive processed mail.** Leave undecided proposals unread, on purpose, and name them in the
   note below.
4. **Write `## Note to tomorrow`** in today's `logs/familiar/` file: what to re-measure first,
   open Captain decisions, commands in flight and what will prove they landed.
5. **Leave the commit to the Mate.** Your log and state files ride in the Mate's next Ship
   commit; say so in the wind-down command if they matter tonight.

## Writing a good command

- **One command per decision batch,** not per Captain message (contract §10).
- **Bounds carry the bright lines every time.** "Prepare, do not fire" for every Captain-owned
  click, restated in each drop, not assumed as ambient. Over a busy day the restated bound is
  the one that holds.
- **Ask for contradiction in the Report section.** The Mate reframing a command, catching a
  stale premise, or reporting a check it broke is the contract working.
- **Success conditions name durable evidence:** a file, a PR state, a log line. "Done" is not
  evidence.

## Judgment notes

- **Verify the primitive before commanding on it.** If the authoritative source is one command
  away, run the command. Direct verification is usually right *and* shrinks the work.
- **Answer from state when you can.** A file read costs nothing; a Mate wake re-reads a context.
- **The Captain reads top-down.** Put the one decision you need first, in plain words, then the
  supporting detail. Name work by what it does, not by ticket number.
