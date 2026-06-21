# Module: Loop Mode (the autonomous heartbeat)

**This is the complete doctrine for running Ship as a self-paced, continuously
running heartbeat — the opt-in "next level of autonomy" upgrade on top of the base
First Mate.** Core `mate.md` runs **request/response**: the Captain drives you turn
by turn, and `mate.md` alone is a complete operating doctrine for that. This module
is everything that's *different* when you instead run a loop — the doctrine core
deliberately leaves out so the base doc stays a plain-terminal First Mate.

Base and Loop currently **diverge** (base = a human-driven session; Loop = a
self-paced watch with its own clock, preflight, and post-compaction continuation).
The Stage-1→5 autonomy classification may eventually unify the two — that's the
Captain's call, not assumed here. For now, read base in `mate.md`, read the
autonomous layer here.

**You enter Loop Mode through the skills**, not by reading this doc — start or resume
with **`/ship-watch-start`** (preflight → launch `/loop /ship-tick`), and each tick is
**`/ship-tick`**. Those skills are *operative procedure*; this module is the *meaning*
behind their steps. They backstop-force the relevant parts of this doc at the moment a
step needs them (the full preflight card on the first tick, etc.).

**What stays the same.** Loop Mode changes nothing about base request/response, the
autonomy tiers, the bright lines, dispatch, ticket/queue lifecycle, reviewing
completed watches, or PR handling — all of that lives in `mate.md` and holds
unchanged. The heartbeat **widens throughput, not authority.**

---

## The Loop

Running the heartbeat, you cycle this continuously — not once per Captain turn (as in
base mode) but on your own clock, every tick:

```
┌─────────────────────────────────────────┐
│  1. CHECK INBOX                          │
│     - Process inbox/captain.md           │
│     - Check inbox/drops/                 │
│     - Triage: ticket, quick task, or     │
│       question to discuss                │
│     - Clear processed items              │
│                 ↓                        │
│  2. CHECK ACTIVE WORK                    │
│     - Review completed crew watches      │
│     - Update ticket/queue status         │
│     - Note anything for the Captain      │
│                 ↓                        │
│  3. DISPATCH IF CAPACITY                 │
│     - Pop top Ready ticket               │
│     - Prepare watch orders               │
│     - Launch crew (background)           │
│                 ↓                        │
│  4. STAY PRESENT / PACE                  │
│     - Available for Captain steering     │
│     - Housekeeping if queue clear        │
│     - Schedule next wake, or wind down   │
└─────────────────────────────────────────┘
```

**Key principle:** inbox checking is continuous, not one-time. The Captain can add
items anytime and they get processed on the next tick.

## Heartbeat Mode — the functional description

By default (base `mate.md`) you run **request/response** — you act when the Captain
invokes you. **Heartbeat mode** is opt-in and additive: instead of waiting, you run a
**self-pacing loop** that keeps its own time, waking on directives, on crew
completions, and on a fallback timer, reconciling ship state every tick. Nothing in
request/response changes; the heartbeat is inert until the loop is started.

**Enter:** start the loop with `/ship-watch-start` — it runs the preflight, then
hands off to `/loop /ship-tick`, which self-paces. The loop runs **headless** — a
status surface, gauges, dispatch bands, and sensors are optional modules layered on
top, not requirements.

**The self-paced "watch."** In Loop Mode the unit of work is a **watch**: a single
self-paced heartbeat run that opens at `/ship-watch-start` and closes only on a real
wind-down signal — *not* per Captain turn, and *not* "when the queue empties." A watch
can span many ticks and survive a mid-watch compaction unbroken. The day is still the
unit of human reporting (handoff notes per watch, a standup rollup per day) — same as
base, but here a "watch" is the self-paced run, not a human-driven session.

**Tier gate.** The heartbeat dispatches/acts **only in the Autonomous tier**
(`mate.md` → "Autonomy & Bright Lines"); Confirm-first / Never items go to Awaiting
Captain with the action stated, never acted on. **Bright lines hold with zero
exceptions.**

## Self-pacing, in full

Each tick schedules its own next wake. **An empty queue is not a stop signal** — a
quiet tick logs its telemetry line and schedules the next fallback. The loop runs
until a real wind-down signal fires, not until "there's nothing to do."

**Pacing.** Steady-state wake is a fallback timer; shorten it only when shepherding a
known-fast external thing (a CI run). **Crew completions are event-driven** — a
backgrounded crew re-invokes the session when it finishes, so **never poll for crew**.
The timer is only for what the harness can't track (inbox appends, drops, external/CI
state, hung crew). Pick the fallback interval to avoid the worst case for your
prompt-cache TTL; your configured value lives in `mate.local.md` (`pacing_fallback`).

## The wind-down triple-signal rule (full)

**Wind-down = stop rescheduling.** To end the loop, run the full wind-down ceremony
(commit, log, handoff), then simply *omit* the next scheduled wakeup. An empty queue
or a *feeling* of doneness is **not** a stop signal — keep ticking the fallback. Wind
down only on one of:

- **Low headroom** — a context-headroom reading at/above your configured wind-down
  threshold (read from the headroom signal if you have one).
- **A compaction / context-low system warning.**
- **A Captain order.**

A self-estimate of remaining context does **not** qualify (self-estimates run ahead
of the truth — documented proxy-estimation failures put full wind-downs at ~37%
actual usage). If you have no headroom signal, keep ticking and note the gauge is
stale. Any wind-down justification must quote the headroom value if it has one.

This is what makes the loop different from base: in base mode you don't watch a gauge
or self-pace at all — the Captain ends the session. In Loop Mode the headroom signal
*is* the primary end-of-watch driver.

## Bounds

There need be no fixed tick cap — the session runs until headroom winds it down or
the Captain calls it. Concurrent crew is capped (a flat default,
`max_concurrent_crew`, in `loop.config.json`); reading a capacity gauge to vary that
cap with rate/cost headroom is the optional [dispatch-bands](dispatch-bands.md)
module.

## Post-compaction continuation

A long watch can survive an auto-compaction mid-watch — you wake into a summarized
context, NOT a fresh launch. This is unique to Loop Mode (a base session is just
ended by the Captain or by context pressure; it doesn't try to continue across a
compaction). Resume via `/ship-watch-start` in RESUME mode. Do NOT re-run the full
preflight, do NOT open a "new watch":

1. **Re-anchor on the ship FILES, not the summary** — the compaction summary is
   background; the truth is `queue.md`, `captain.md`, today's `logs/mate/` file,
   `state/status.json`. Read them.
2. **Verify background machinery survived** — background tasks may or may not carry
   across a compaction. Check the wake-monitor and any pending wakeup survived;
   re-arm/re-schedule if not (see [wake-monitor.md](wake-monitor.md) and
   [loop-exit-guard.md](loop-exit-guard.md)). This is the same "did it survive
   rotation" check done at session start.
3. **Continue the watch** — compaction is a context event, not a watch boundary; the
   watch (and the tick numbering) continues unbroken.
4. Keep ship state committed often so the *next* compaction is equally clean.

## Preflight — the full GO / NO-GO card

The heartbeat launches only from a clean starting line. The principle is
**structural, not remembered**: the loop skill (`ship-watch-start`, or `ship-tick`
on its first tick) auto-runs this on entry and **refuses to start on any NO-GO**
(Captain waiver only, recorded next to the launch line in the log). This is what
makes a stale wakeup echo or a forgotten-running loop safe — and the preflight
result is the loop's first telemetry entry.

Generic gates (some optional; the *specifics* — a particular validator path, a UI
port, an extended allowlist — come from `loop.config.json`, they don't change the
shape of the card):

1. **State writable + seeded** — your persistent state file exists and `state/` is
   writable.
2. **Ship git clean** — commit anything dirty first.
3. **Drops empty** — triage `inbox/drops/` before looping, not during tick 1.
4. **No orphaned crew** — nothing left running from a prior session this loop
   doesn't know about.
5. **Headroom** — enough context free that a loop has room to run.
6. **Wake-monitor armed** — your directive surface(s) are being watched (or you've
   accepted inbox-edit + crew-completion as the only wake sources). See
   [wake-monitor.md](wake-monitor.md).
7. **(Optional) Status surface up** — if you run a UI module, it's reachable.
8. **(Optional) Validator clean** — if a validator is configured, it runs clean
   (or the drift is named and accepted).

## Lifecycle machinery (the loop's companion modules)

- **Wake-monitor.** A loop that only the fallback timer can wake will miss
  directives between ticks. Arm a wake-monitor on your directive surface(s) so a
  Captain message / inbox steer wakes the loop promptly while bookkeeping does not.
  The contract and hard-won pitfalls live in [wake-monitor.md](wake-monitor.md).
- **Exit-guard.** `/loop` is the primary keep-alive: it re-invokes the session on a
  schedule and lets each tick decide whether to reschedule (the natural fit for a
  self-pacing heartbeat). Do **not** layer `/goal` over `/loop` — a goal condition
  starts a turn immediately and its post-turn evaluator vetoes the loop's sleeps,
  producing a hot loop. A stop-hook exit-guard (block stop unless a wake is pending
  or wind-down evidence was printed) is a separate mechanism. See
  [loop-exit-guard.md](loop-exit-guard.md).
- **Dispatch bands.** Rate/cost-aware modulation of the crew cap + dispatch
  appetite, with fixed bright-line guardrails — see [dispatch-bands.md](dispatch-bands.md).
- **Sensors.** Watching external signals (PR comments, CI, resolved-out-of-band) via
  a cheap sub-agent sweep rather than an in-session cron — see [sensors.md](sensors.md).
