# Captain's Orders

## Situation
<!-- Background and immediate ship status context -->

Solo maintainer of `harborwatch` (a small uptime-monitoring SaaS, ~200 paying users,
repo at `~/dev/harborwatch`). Day job takes mornings; ship work happens afternoons and
evenings. Current push: stability — the upload endpoint fell over twice last month under
burst traffic.

## Priorities
<!-- What matters most right now. First Mate uses this to order the queue. -->

1. Anything customer-visible broken beats everything else.
2. The stability backlog (rate limiting, webhook retries) before new features.
3. Keep PRs small — I review on my phone half the time.

## Constraints
<!-- Anything that limits how work can be done. -->

- Ruby 3.3 / Rails 7.1; no new runtime deps without asking.
- Staging deploys only — production deploys are mine, Fridays never.
- Tests must pass locally (`bundle exec rspec`) before a PR goes up.

## Standing Orders
<!-- Persistent instructions that apply to all work. -->
- Always run tests before marking a ticket done
- Commit frequently - if you'd be sad to lose it, commit it
- When in doubt, checkpoint and ask
- Never touch `db/migrate/` without a ticket that explicitly says migration
