# Queue

> **Owned by First Mate.** Crew: read only.

<!-- CANONICAL SECTIONS — this is the queue state machine; docs and seeds must match:
  Ready | Active | In Review | Awaiting Captain | Blocked | Backlog | Done (recent) -->

## Ready
<!-- Tickets ready for dispatch, in priority order. Mate pops from top. -->

1. [HW-102-tide-poller-backoff](projects/harborwatch/tickets/HW-102-tide-poller-backoff.md) - poller hammers dead tide stations; needs backoff + cap | last: 2026-07-09

## Active
<!-- Currently being worked. One crew per ticket. -->

<!-- empty -->

## In Review
<!-- Has PR(s) waiting on CI, review, or merge -->

<!-- empty -->

## Awaiting Captain
<!-- Ship work done; a Captain action is needed. STATE THE ACTION. -->

1. [HW-101-berth-double-booking](projects/harborwatch/tickets/HW-101-berth-double-booking.md) - **read draft [harborwatch#41](https://github.com/example-org/harborwatch/pull/41) + mark ready if good** (reviewed, tests green) | last: 2026-07-09

## Blocked
<!-- Waiting on external input / a decision. Name the blocker. -->

<!-- empty -->

## Backlog
<!-- Not actively being worked. Tags: [impl-ready] [needs-captain] [someday] -->

1. HW-arrivals-digest [someday] - daily arrivals/departures digest for harbormasters instead of per-vessel pings; resurrect if churn mentions notification fatigue | last: 2026-07-05

## Done (recent)
<!-- Recently completed. CAP ~10. -->

1. HW-100 - monthly statement export timeout fixed (streaming), shipped | 2026-07-07
