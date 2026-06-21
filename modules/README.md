# Modules

Optional, generally-useful capabilities **and depth docs** that layer on top of the
general-core `mate.md`. Core stays readable on its own; each module is referenced by
one line from core and is self-contained here. Turn on capability modules you want
(via `/shipkit-init` or by hand) and ignore the rest — a core-only operator needs
none of them.

**Three kinds of module.** One module is the **whole opt-in autonomous layer**:
[loop-mode.md](loop-mode.md) holds the *complete* Loop Mode doctrine — it is NOT
summarized inline in `mate.md` (base core is request/response only; it carries just a
brief pointer). Some modules add a *capability* you opt into (wake-monitor,
review-cycle, dispatch-bands, sensors). Others are *depth docs* — the fuller detail
pared out of a core section that stays functional inline (subagent-roster,
pull-requests). Capability + depth modules are referenced from core as a **plain
(non-`@`) pointer** (read-on-demand); core's inline summary is always enough to
operate. The Loop-Mode skills **force-read** `loop-mode.md` on launch (it's
load-bearing for the loop) and **backstop-force** the depth docs at the moment a tick
needs them (PR mechanics when reaping a PR watch, etc.).

| Module | Kind | For | What it adds |
|---|---|---|---|
| [loop-mode.md](loop-mode.md) | opt-in layer | Loop / Heartbeat Mode | The **complete** autonomous-heartbeat doctrine: the Loop, self-pacing, the wind-down triple-signal rule, post-compaction continuation, the full preflight GO/NO-GO card (8 gates), and how the lifecycle modules compose. Base `mate.md` carries only a brief pointer; this is the source of truth. |
| [subagent-roster.md](subagent-roster.md) | depth | Dispatch | The full 4-type roster, dispatch code patterns, per-type security model, watch-orders template, agent teams. Core carries crew + lookout + the act of dispatching. |
| [pull-requests.md](pull-requests.md) | depth | PR workflow | Mergeability re-checks, stacked-PR propagation, the `pr:` frontmatter convention. Core carries the draft-only / never-`gh pr ready` bright lines + the PR-link format. |
| [wake-monitor.md](wake-monitor.md) | capability | Heartbeat Mode | A watcher that wakes the loop on directives between ticks. Contract + the incident-scar pitfalls (enumerate-don't-glob, dedup-by-filename, classify-before-wake). |
| [loop-exit-guard.md](loop-exit-guard.md) | capability | Heartbeat Mode | `/loop`-primary keep-alive, why not to layer `/goal`, and the loop-aware Stop-hook exit-guard. |
| [dispatch-bands.md](dispatch-bands.md) | capability | Heartbeat Mode / any | Rate/cost-aware modulation of the crew cap + dispatch appetite, with fixed bright-line guardrails. |
| [review-cycle.md](review-cycle.md) | capability | Any | The maker≠checker *enforcement* mechanism: a non-maker `ship-reviewer` gate, the standards doc, and the policy knobs (core ships only the principle). |
| [sensors.md](sensors.md) | capability | Heartbeat Mode | Watching external signals (PR comments, CI, resolved-out-of-band) via a cheap sub-agent sweep rather than an in-session cron. |

Each module's tunable values live in `mate.local.md` (behavioral prefs) and/or
`loop.config.json` (machine config), not in the module doc itself.
