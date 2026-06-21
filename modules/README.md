# Modules

Optional, generally-useful capabilities that layer on top of the general-core
`mate.md`. Core stays mode-free and readable on its own; each module is referenced
by one line from core and is self-contained here. Turn on what you want (via
`/shipkit-init` or by hand) and ignore the rest — a core-only operator needs none of
them.

| Module | For | What it adds |
|---|---|---|
| [wake-monitor.md](wake-monitor.md) | Heartbeat Mode | A watcher that wakes the loop on directives between ticks. Contract + the incident-scar pitfalls (enumerate-don't-glob, dedup-by-filename, classify-before-wake). |
| [loop-exit-guard.md](loop-exit-guard.md) | Heartbeat Mode | `/loop`-primary keep-alive, why not to layer `/goal`, and the loop-aware Stop-hook exit-guard. |
| [dispatch-bands.md](dispatch-bands.md) | Heartbeat Mode / any | Rate/cost-aware modulation of the crew cap + dispatch appetite, with fixed bright-line guardrails. |
| [review-cycle.md](review-cycle.md) | Any | The maker≠checker *enforcement* mechanism: a non-maker `ship-reviewer` gate, the standards doc, and the policy knobs (core ships only the principle). |
| [sensors.md](sensors.md) | Heartbeat Mode | Watching external signals (PR comments, CI, resolved-out-of-band) via a cheap sub-agent sweep rather than an in-session cron. |

Each module's tunable values live in `mate.local.md` (behavioral prefs) and/or
`loop.config.json` (machine config), not in the module doc itself.
