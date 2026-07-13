# Demo ship — one finished cycle, readable

A fictional ship, frozen mid-operation, so you can **read what good looks like** before
running your own first watch. Everything here is fake (the `harborwatch` repo, the org,
the PR numbers) but every file has the real shape: this is exactly what your ship's state
should look like after a week of use.

**The one thing to actually read: a complete dispatch → log → handoff → reconcile cycle.**
Follow it in order:

1. **The ticket** — [projects/harborwatch/tickets/HW-101-upload-rate-limit.md](projects/harborwatch/tickets/HW-101-upload-rate-limit.md).
   Note the shape: Status (the Mate's field), Goal, acceptance criteria, Current state,
   and a Watch history linking every log.
2. **Watch 1** — [logs/harborwatch/HW-101-upload-rate-limit/2026-07-08-1410.md](logs/harborwatch/HW-101-upload-rate-limit/2026-07-08-1410.md).
   A crew session that ran out of runway *honestly*: it says exactly where it stopped,
   what's uncommitted, and what to do next — **handoff confidence 3**, and why.
3. **Watch 2** — [logs/harborwatch/HW-101-upload-rate-limit/2026-07-09-0930.md](logs/harborwatch/HW-101-upload-rate-limit/2026-07-09-0930.md).
   A *fresh* session picking up from watch 1's "Next steps" alone — no shared memory,
   no transcript — and finishing the work. This is the whole system in one file: **logs
   are the handoff.**
4. **The Mate's day** — [logs/mate/2026-07-09.md](logs/mate/2026-07-09.md). Two session
   sections in one daily log: dispatch, the reap of watch 2, the review gate, the queue
   reconcile, handoff notes, and the end-of-day standup rollup.
5. **The queue** — [queue.md](queue.md). Where everything above landed: HW-101 sits in
   **Awaiting Captain** with the concrete action stated (the Mate never marks a PR ready
   — that's the Captain's click), HW-102 waits in **Ready**.

Also here, for shape reference: a filled-in [captain.md](captain.md) (standing orders the
Mate actually uses) and an [inbox](inbox/captain.md) with one unprocessed item (the Mate
clears lines as it processes them — a non-empty inbox means pending work).

**Don't copy these files onto your ship** — your live skeleton is already installed; this
directory is a museum, not a template. (Only tickets HW-101/HW-102 have files here; the
queue's Done line references a pruned ticket, which is itself the retention rule working.)
