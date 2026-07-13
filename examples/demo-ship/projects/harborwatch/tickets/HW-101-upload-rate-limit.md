# HW-101: Rate-limit the metrics upload endpoint

**Status:** awaiting-captain
**Source:** July 2 + July 19 incidents (burst uploads from one misconfigured client took the endpoint down)
**Branch:** HW-101-upload-rate-limit
**Goal:** `POST /api/v1/metrics` sheds burst traffic per-client with 429s instead of falling over; existing well-behaved clients unaffected.
**PR:** [harborwatch#41](https://github.com/example-org/harborwatch/pull/41) (draft)

## Acceptance
- [x] Per-API-key sliding-window limit (default 120 req/min), returns 429 + `Retry-After`
- [x] Limit configurable per-plan (free 120, pro 600) without a deploy
- [x] Request specs cover: under limit, at limit, burst, two keys isolated
- [x] No latency regression on the happy path (< 1ms added, measured in spec)

## Current state
Done and PR'd. `RateLimiter` middleware (Redis sliding window, `rack-attack`-free — see
watch 2 log for why), plan limits read from `plans.yml`, 12 new request specs, full suite
green locally. Draft PR [harborwatch#41](https://github.com/example-org/harborwatch/pull/41)
up with test plan; non-maker review passed (2 findings addressed, see mate log 2026-07-09).
Awaiting Captain: read + mark ready.

## Blocked on
N/A

## Watch history
<!-- Format: - **YYYY-MM-DD-HHMM** - [Log](../../../logs/{project}/{ticket-id}/{filename}.md) - Brief description -->
- **2026-07-08-1410** - [Log](../../../logs/harborwatch/HW-101-upload-rate-limit/2026-07-08-1410.md) - Research + limiter core; ran out of runway mid-specs (confidence 3)
- **2026-07-09-0930** - [Log](../../../logs/harborwatch/HW-101-upload-rate-limit/2026-07-09-0930.md) - Fresh session finished specs + plan config from watch 1's handoff (confidence 5)
