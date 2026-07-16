# Captain's Orders

## Situation
<!-- Background and immediate ship status context -->

Solo maintainer of `harborwatch` (a small marina-management SaaS — berth reservations,
tide data, arrival boards; ~200 marinas, repo at `~/dev/harborwatch`). Day job takes
mornings; ship work happens afternoons and evenings. Current push: stability — two
double-booking incidents in the past month, both on peak weekends.

## Priorities
<!-- What matters most right now. First Mate uses this to order the queue. -->

1. Anything customer-visible broken beats everything else.
2. The stability backlog (double-booking fix, tide-poller backoff) before new features.
3. Keep PRs small — I review on my phone half the time.

## Constraints
<!-- Anything that limits how work can be done. -->

- Python 3.12 / FastAPI, Postgres behind it; no new runtime deps without asking.
- Staging deploys only — production deploys are mine, Fridays never.
- Tests must pass locally (`pytest`) before a PR goes up.

## Standing Orders
<!-- Persistent instructions that apply to all work. -->
- Always run tests before marking a ticket done
- Commit frequently - if you'd be sad to lose it, commit it
- When in doubt, checkpoint and ask
- Never touch `migrations/` without a ticket that explicitly says migration
