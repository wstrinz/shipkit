# Module: Loop Mode (heartbeat depth)

**Depth doc for the opt-in heartbeat.** Core `mate.md` → "Heartbeat Mode" carries
the *functional* description — self-pacing, the wind-down triple-signal rule, the
tier gate, that a preflight gate exists. That inline summary is enough to run a
loop. This module holds the *depth*: the full preflight GO/NO-GO card, pacing
nuance, and how the loop's lifecycle machinery (wake-monitor, exit-guard, bands,
sensors) compose. It's a **plain (non-`@`) reference** — read on demand, and the
tick skills backstop-force the relevant parts (the preflight card on first tick).

## Self-pacing, in full

Each tick schedules its own next wake. **An empty queue is not a stop signal** — a
quiet tick logs its telemetry line and schedules the next fallback. The loop runs
until a real wind-down signal fires, not until "there's nothing to do."

**Pacing.** Steady-state wake is a fallback timer; shorten it only when shepherding
a known-fast external thing (a CI run). **Crew completions are event-driven** — a
backgrounded crew re-invokes the session when it finishes, so **never poll for
crew**. The timer is only for what the harness can't track (inbox appends, drops,
external/CI state, hung crew). Pick the fallback interval to avoid the worst case
for your prompt-cache TTL; your configured value lives in `mate.local.md`
(`pacing_fallback`).

## The wind-down triple-signal rule (full)

To end the loop, run the full wind-down ceremony (commit, log, handoff), then
simply *omit* the next scheduled wakeup. An empty queue or a *feeling* of doneness
is **not** a stop signal — keep ticking the fallback. Wind down only on one of:

- **Low headroom** — a context-headroom reading at/above your configured wind-down
  threshold (read from the headroom signal if you have one).
- **A compaction / context-low system warning.**
- **A Captain order.**

A self-estimate of remaining context does **not** qualify (self-estimates run ahead
of the truth — documented proxy-estimation failures put full wind-downs at ~37%
actual usage). If you have no headroom signal, keep ticking and note the gauge is
stale. Any wind-down justification must quote the headroom value if it has one.

## Bounds

There need be no fixed tick cap — the session runs until headroom winds it down or
the Captain calls it. Concurrent crew is capped (a flat default,
`max_concurrent_crew`, in `loop.config.json`); reading a capacity gauge to vary that
cap with rate/cost headroom is the optional [dispatch-bands](dispatch-bands.md)
module.

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
- **Sensors.** Watching external signals (PR comments, CI, resolved-out-of-band) via
  a cheap sub-agent sweep rather than an in-session cron — see [sensors.md](sensors.md).
