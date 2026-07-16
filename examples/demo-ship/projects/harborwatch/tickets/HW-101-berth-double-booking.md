# HW-101: Stop double-booked berths

**Status:** awaiting-captain
**Source:** June 21 + July 2 incidents (two marinas double-booked the same slip during peak weekends — two front-desk sessions booking seconds apart)
**Branch:** HW-101-berth-double-booking
**Goal:** two overlapping reservations for the same berth can never both commit; the losing request gets a clean 409 pointing at the winner, not a corrupted calendar.

## Acceptance
- [x] DB-enforced: exclusion constraint on (berth, stay range) — this ticket explicitly includes the migration
- [x] Losing request gets 409 + the conflicting reservation id; adjacent stays (checkout == next check-in) do NOT conflict
- [x] Turnaround buffer configurable per-marina (default 0h, premium 2h) without a deploy
- [x] Specs cover: overlap, adjacency, two berths isolated, and the actual race (two concurrent writers)

## Current state
Done and PR'd. Exclusion constraint (migration 0042, half-open stay ranges) with a 409
mapping in the reservations API, advisory-lock approach rejected — see watch 1 log for
why — buffers read from `config/turnaround.yml`, 12 new specs, full suite green locally.
Draft PR [harborwatch#41](https://github.com/example-org/harborwatch/pull/41)
up with test plan; non-maker review passed (2 findings addressed, see mate log 2026-07-09).
Awaiting Captain: read + mark ready.

## Blocked on
N/A

## Watch history
<!-- Format: - **YYYY-MM-DD-HHMM** - [Log](../../../logs/{project}/{ticket-id}/{filename}.md) - Brief description -->
- **2026-07-08-1410** - [Log](../../../logs/harborwatch/HW-101-berth-double-booking/2026-07-08-1410.md) - Research + constraint core; ran out of runway mid-specs (confidence 3)
- **2026-07-09-0930** - [Log](../../../logs/harborwatch/HW-101-berth-double-booking/2026-07-09-0930.md) - Fresh session finished specs + buffer config from watch 1's handoff (confidence 5)
