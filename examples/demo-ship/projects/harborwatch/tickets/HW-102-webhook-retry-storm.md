# HW-102: Back off webhook retries to dead endpoints

**Status:** ready
**Source:** ops noise — 40k retries/day to endpoints that have 404'd for weeks
**Branch:** HW-102-webhook-retry-storm
**Goal:** failed webhook deliveries retry with exponential backoff and give up after a cap; a permanently-dead endpoint costs ~5 requests, not thousands.

## Acceptance
- [ ] Exponential backoff (1m, 5m, 30m, 2h, 12h), then mark endpoint `suspended`
- [ ] Suspended endpoints surfaced in the customer dashboard with a "resume" action
- [ ] Existing pending retries migrate cleanly (no migration file — use the queue)
- [ ] Specs: backoff schedule, suspension, resume, migration of in-flight retries

## Current state
Not started.

## Blocked on
N/A

## Watch history
<!-- Format: - **YYYY-MM-DD-HHMM** - [Log](../../../logs/{project}/{ticket-id}/{filename}.md) - Brief description -->
