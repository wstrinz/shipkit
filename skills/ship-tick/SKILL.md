---
name: ship-tick
description: >
  One heartbeat tick of the Ship First Mate loop. Invoke via `/loop /ship-tick`
  (dynamic, self-paced) when running Ship in Loop Mode. Each invocation handles
  whatever woke the session (crew completion, timer, a Captain directive),
  reconciles ship state, dispatches Autonomous-tier work if there's capacity,
  logs one telemetry line, then either schedules its own next wake or winds
  down. Not for use outside an active Mate Loop Mode session.
---

# /ship-tick — one heartbeat tick

You are the First Mate running in Loop Mode. This is **one tick**, not the whole
loop. Run the steps below once, then pace-or-wind-down (step 7) and stop.

This skill is **operative procedure only**. The *meaning* of every step lives in
`mate.md` — read it there, do not re-derive it here:
- **The Loop / Heartbeat Mode** — `mate.md` → "Heartbeat Mode"
- **Autonomy tiers** (the dispatch gate) — `mate.md` → "Heartbeat Mode" / "Autonomy & Bright Lines"
- **Reviewing Completed Watches** (reap procedure) — `mate.md` → "Reviewing Completed Watches"
- **Wind-down triple-signal rule** — `mate.md` → "Heartbeat Mode"

**Reference convention + backstops.** `mate.md`'s `@`-refs (i.e. `mate.local.md`)
were force-loaded at launch by `ship-watch-start`. Its plain (non-`@`) module
references are **read-on-demand** — and this skill **backstop-forces** the relevant
one at the moment a step needs the detail. The backstops, by step:
- **Auto-preflight** (loop entry) → full 8-gate card in `modules/loop-mode.md`.
- **Reap** (step 2) → PR mergeability/stacked-PR mechanics in
  `modules/pull-requests.md` when a PR watch lands; the lookout/reviewer roster in
  `modules/subagent-roster.md` when verifying a "done" claim or running a review
  gate. (The ticket/queue update procedure itself is inline in `mate.md` →
  "Reviewing Completed Watches".)
- **Dispatch** (step 5) → the dispatch patterns + watch-orders template in
  `modules/subagent-roster.md` when dispatching a pilot/reviewer/team.
Read the inline summary in `mate.md` first; pull the module only when you actually
need the depth.

**Config seam:** read machine/org specifics from `loop.config.json` — `ship_root`,
`repos`, `chat_surface`, `headroom_signal_path`, `validator_cmd`,
`max_concurrent_crew`. All ship paths below resolve from `ship_root`. Optional
fields that are null degrade gracefully (no validator => reconcile is a no-op; no
headroom signal => keep ticking, note `gauge=stale`).

**Auto-preflight (loop entry only):** if this is the FIRST tick of a `/loop
/ship-tick` session (no telemetry line yet this session), run the full preflight
card before anything else and print it — backstop-force-read the full 8-gate card
from `modules/loop-mode.md` → "Preflight" (core `mate.md` carries the minimum gate
inline). **On any NO-GO,
refuse to start the loop** — report the failing line and stop (no next-wake
scheduled). Only an explicit Captain waiver in-session overrides; record it next
to the launch line. This gate is structural, not remembered — it also catches a
stale wakeup echo from a previous session's loop. **Wake provenance must be
NAMED, never assumed to be the Captain.**

**Date-ground every stamp — PROGRAMMATICALLY:** stamps in status.json or any
script-written file must be computed by the writing script itself
(`status_writer.py` calls `datetime.now()`), NEVER typed as literals — running a
clock command first and then typing the value still drifts. For hand-written log
lines, paste the clock output from the SAME command block, not from memory.

## The tick

1. **Orient on wake reason.** Why were you re-invoked? A crew completion (handle
   the reap first), the fallback timer, or a Captain directive in-session? Name
   it — it drives the rest of the tick and goes in the telemetry line.
   **Then immediately write `now` into `state/status.json`** (before doing the
   work): `python3 scripts/status_writer.py now "<one plain sentence on what
   you're addressing>" --wake "<reason>"`. This is the at-a-glance "Mate now"
   the moment the tick starts. Update it mid-tick when switching to a distinctly
   different action.

2. **Reap completed crew.** For each finished watch: read its log; **verify any
   load-bearing "done" claim** (tests green, PR exists and is mergeable, file
   landed) before acting on it — a `ship-lookout` is a cheap way to do this. Then
   run the full `mate.md` → "Reviewing Completed Watches" procedure: update the
   ticket's Current State + Watch History, set its status, update `queue.md`.

3. **Reconcile.** If `validator_cmd` is set in `loop.config.json`, run it and heal
   any drift it reports (the canonical source — ticket frontmatter — wins). Parse
   the result into a CLEAN / MISMATCH / STALE verdict and carry it to step 7 (the
   wind-down must print it). If no validator is configured, this step is a no-op
   and the verdict is `NONE`.

4. **Check inbox + batch-reconcile.** Read `inbox/captain.md` and `inbox/drops/`.
   Triage per the inbox rules. Clear processed items, then **re-read the file and
   confirm the cleared lines are actually gone** (a silent no-op clear is a known
   failure mode); note `inbox-verified` in telemetry.
   **Batch-reconcile bookkeeping drops (the input model).** Drops are classified
   by `scripts/classify_input.py` into **wake** (directives — a chat message, a
   `steer` / `comment` / `status-request`) vs **batch** (bookkeeping —
   `status-applied` / `close-applied`, self-authored items, sensor re-drops). The
   wake-monitor only *wakes* you on wake-class; batch-class accumulate silently.
   So each tick, **drain the accumulated batch-class drops in ONE pass**, not
   per-drop: apply all queued status/queue moves + a single priority-heal, clear
   sensor noise. The live ticket frontmatter already serves the Captain's views,
   so this reconcile is cosmetic and correctly non-real-time — which is exactly
   why it batches instead of waking. **One exception to surface, not silently
   batch:** a status change that hits an **active ticket with running crew** —
   flag it this tick (it may need the crew stopped or redirected).

5. **Dispatch if capacity.** Pop the top Ready ticket **only if the work sits in
   the Autonomous tier** (`mate.md` → "Loop Mode" / "Autonomy as the dispatch gate"). Cap at
   `max_concurrent_crew` (from `loop.config.json`; default 2). Confirm-first /
   Never-tier items → move to **Awaiting Captain with the specific action
   stated**; never act on them. A *denied* (non-allowlisted) tool call →
   escalate to Awaiting Captain and move on; never retry it verbatim.
   (Rate/cost-aware dispatch *bands* — varying the cap by headroom — are an
   optional module, not core.)

6. **Telemetry line.** Append ONE line to today's mate log:
   `HH:MM tick — wake=<reason> · did=<actions or "no-op"> · crew=<in-flight>`
   **Quiet on no-op:** an empty tick logs its line and surfaces nothing to the
   Captain. This telemetry line is the durable, grep-able per-tick record — NOT
   a `ticks[]` array in status.json (that's a UI-module render cache).

6.5 **Write `state/status.json`** via the writer — never hand-edit:
   `python3 scripts/status_writer.py tick <n> "<wake>" --delay-seconds <secs>
   --wake-label <reason> --validator "<RESULT>" --last-actions "<a>" "<b>"`.
   The writer computes `next_wake` as a local-time clock stamp from
   `now()+delay` (a clock stamp, NOT a duration; never a typed literal) and
   advances the monotonic `tick`. Rich fields (hot list, ready-for-you, crew[])
   are written by a status-surface module if one is installed; a headless loop
   writes only the core fields. **If a UI module owns server/template files this
   tick, the status.json write still happens** — it's Mate-owned and
   conflict-free by design.

7. **Pace or wind down.** **A heartbeat tick may only wind down on one of three
   signals: (a) a context-headroom reading at/above the wind-down threshold
   (read from `headroom_signal_path` if configured), (b) a compaction /
   context-low system warning, (c) a Captain order. Self-estimates NEVER
   qualify** — a *feeling* of doneness is not a signal (it runs ahead of actual
   context; documented proxy-estimation failures put full wind-downs at ~37%
   actual usage). If the headroom signal is stale or missing and no other signal
   fires: **keep ticking**, and note `gauge=stale` in telemetry. Any wind-down
   justification must QUOTE the headroom value if it has one.
   - **Headroom fine (or no signal, no other trigger):** schedule the next wake
     re-passing `/ship-tick`. Delay = a sensible fallback (≈1200–1800s); shorter
     only when shepherding a known-fast external thing (e.g. a CI run). Crew in
     flight will wake you sooner on their own — never poll for them. Then stop.
   - **Headroom low, or Captain called it:** run the full wind-down ceremony
     (handoff notes → today's mate log, queue + inbox housekeeping, commit) and
     **do NOT reschedule** — the loop ends here. The wind-down must **print** the
     reconcile verdict and a one-line handoff-written confirmation.
     **Self-modification is Confirm-first, always:** propose changes to mate.md /
     this skill / hooks in the handoff notes — never apply them mid-loop.

## Bounds (do not exceed)
- **No fixed tick cap** — the session runs until headroom or the Captain winds it
  down.
- Max concurrent crew = `max_concurrent_crew` from `loop.config.json`. No
  crew-spawning-crew.
- An empty queue is **not** a stop signal — keep ticking the fallback. A *feeling*
  of doneness is **not** a stop signal. Only low headroom / a context-low warning
  / a Captain order ends the loop.
- Tier bright lines hold with zero exceptions (no external comments, merges, or
  prod writes without Captain authorization). The heartbeat widens throughput,
  not authority.
