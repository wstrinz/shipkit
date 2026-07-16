# HW-102: Back off tide polls to dead stations

**Status:** ready
**Source:** ops noise — 40k polls/day against tide stations that have 404'd for weeks
**Branch:** HW-102-tide-poller-backoff
**Goal:** failed station polls retry with exponential backoff and give up after a cap; a permanently-dead station costs ~5 requests, not thousands.

## Acceptance
- [ ] Exponential backoff (1m, 5m, 30m, 2h, 12h), then mark station `suspended`
- [ ] Suspended stations surfaced in the marina dashboard with a "resume" action
- [ ] Existing scheduled polls migrate cleanly (no migration file — use the queue)
- [ ] Specs: backoff schedule, suspension, resume — including resume racing the poller (see HW-101's learning) — and migration of in-flight polls

## Current state
Not started.

## Blocked on
N/A

## Watch history
<!-- Format: - **YYYY-MM-DD-HHMM** - [Log](../../../logs/{project}/{ticket-id}/{filename}.md) - Brief description -->
