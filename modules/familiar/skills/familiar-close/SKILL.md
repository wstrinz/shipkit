---
name: familiar-close
description: Close a Familiar seat so the next one can start cold. Wind the Mate down by command if the day is ending, archive processed mail, and write the Note to tomorrow that familiar_orient.py prints at the next wake. Run at the end of every Familiar session.
---

# Familiar close

The next wake reads what this close writes. A close that skips the note leaves the next seat
re-deriving the day. Runbook: `modules/familiar/familiar-ops.md`, "Close".

1. **Is the day ending?** If yes, send the Mate one wind-down command (draft under
   `state/familiar/drafts/`, then `familiar_drop.py send`): housekeeping, the compound pass,
   the end-of-day standup, then a rotation to the night posture. Bounds: its handoff carries
   tomorrow's plan in order, the open Captain one-liners, and anything unpushed (branch and
   SHA). If no, skip this step; a mid-day close needs no Mate wake.

2. **Verify, don't assume.** If a rotation ran, read the successor's model from its
   transcript; the session name only repeats the launch flag.

3. **Archive processed mail** with `familiar_drop.py archive <name>`. Leave undecided proposals
   unread, deliberately, and list them in the note.

4. **Write `## Note to tomorrow`** at the end of today's `logs/familiar/` file. Plain sentences:
   - what to re-measure first, and why;
   - commands in flight, and the durable evidence that will show they landed;
   - open Captain decisions, the ask stated first;
   - unread-on-purpose mail and what it is waiting for.

5. **Hand off the commit.** You do not commit. If tonight's log or state matter before the Mate's
   next Ship commit, say so in the wind-down command.
