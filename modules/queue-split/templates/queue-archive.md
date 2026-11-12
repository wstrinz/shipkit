# Queue Archive

> **Owned by First Mate.** Crew: read only. **Not read at boot.** Parked Ready, Backlog, Shelved and
> older Done live here, split out of the live queue by `queue_split.py` (modules/queue-split/).
> Ticket status is unchanged: Ready (parked) = `ready`, Backlog = `backlog`, Shelved = `shelved`, Done = `done`.

## Ready (parked)
<!-- Ready, but deliberately not next. Back to the live queue: queue_move.py --from "Ready (parked)" --to Ready -->

## Backlog
<!-- Not actively being worked. Format: 1. [ticket-id](path) [tag] - summary + resurrect trigger | last: YYYY-MM-DD -->

## Shelved
<!-- Answered, deliberately not built. Entry needs ALL THREE (modules/queue-split/queue-split.md):
     the answer is complete, a named resurrection trigger, and a findable knowledge doc.
     Format: 1. [ticket-id](path) - the answer in a line; trigger: <what must become true>; doc: <path> | shelved: YYYY-MM-DD -->

## Done
<!-- Newest first. queue_split.py moves live Done entries older than the done-days threshold here. -->
