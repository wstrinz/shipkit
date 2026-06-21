---
name: ship-watch-start
description: >
  The clean entrypoint for STARTING or RESUMING the Ship First Mate Loop Mode
  heartbeat. Invoke once — at a fresh launch (`/ship-watch-start`) or when
  resuming after an auto-compaction. It detects mode (fresh launch vs
  post-compaction resume), re-anchors on role+docs+state, verifies the wake
  machinery, runs the appropriate preflight, then hands off to the per-tick loop
  `/loop /ship-tick`. Runs ONCE then yields to the per-tick loop. Not for use
  outside an active Mate Loop Mode session.
---

# /ship-watch-start — start or resume the heartbeat

You are the First Mate. This skill runs **once** to bring Loop Mode to a clean
starting line, then it launches `/loop /ship-tick` (the per-tick body) and stops.
It does NOT run a tick itself — `ship-tick` owns the tick.

**Config seam:** read `loop.config.json` first — `ship_root` (all ship paths
resolve from here), `repos`, `chat_surface`, `headroom_signal_path`,
`validator_cmd`. Optional fields that are null degrade gracefully.

The *meaning* of every step lives in `mate.md` — read it there, do not re-derive.
Core carries the functional summary; depth lives in plain (non-`@`) modules you
backstop-force when a step needs them:
- **Post-compaction continuation** — `mate.md` → "Heartbeat Mode"
- **The Loop / Heartbeat Mode** — `mate.md` → "Heartbeat Mode"
- **Preflight (GO/NO-GO)** — `mate.md` → "Heartbeat Mode" (minimum gate inline);
  full 8-gate card in `modules/loop-mode.md` (backstop-force on FRESH launch)

## 1. Detect mode

- **RESUME** (post-compaction) — you arrived via a SessionStart re-anchor
  directive, or a recent pre-compaction handoff snapshot exists in `state/`. A
  stale snapshot from a prior session is NOT a resume signal.
- **FRESH** — no recent handoff snapshot; the Captain launched
  `/ship-watch-start` by hand after the opening ceremony.

State which mode you detected before proceeding.

## 2. Re-anchor (both modes)

Read role + docs + state — the FILES, not any summary:
- `mate.md` (role)
- **every `@`-prefixed reference in `mate.md`** — these are force-load-up-front by
  convention (`mate.md` header → "Reference convention"). In practice that's
  `mate.local.md` (your behavioral-prefs overlay: thresholds, model roster, report
  format, loop skill, etc.). Read it now; its values resolve core's "your
  configured X" seams.
- the pre-compaction handoff snapshot (RESUME only — last tick #, wake_reason,
  in-flight crew, next_wake, last_actions, queue summary)
- `queue.md`, `captain.md`
- today's `logs/mate/<date>.md` (the prior watch / prior ticks)
- `state/status.json`

Plain (non-`@`) references in `mate.md` — `modules/loop-mode.md`,
`modules/subagent-roster.md`, `modules/pull-requests.md`, and the other module docs
— are **read-on-demand**, NOT loaded here. The per-tick loop backstop-forces them
when a tick actually needs the detail (see `ship-tick`).

In RESUME mode, carry the last tick number forward — **tick numbering continues
unbroken** (compaction is a context event, not a watch boundary). Do NOT open a
new watch section.

## 3. Verify / arm the wake machinery

Background tasks may or may not survive a compaction. Check what's alive:
- **Wake-monitor** — the loop's wake signals are (a) the `chat_surface` from
  `loop.config.json` (if set), (b) changes to `inbox/` and `captain.md`, and (c)
  crew completions (harness-native). If a file-watch monitor backs (a)/(b) and it
  is gone, **re-arm it**. The monitor classifies each net-new item via
  `scripts/classify_input.py` and wakes the Mate only on **wake**-class; it
  records **batch**-class in its seen-set (no wake) for the tick to drain.
- **/loop wakeup** — launching `/loop /ship-tick` at step 5 re-establishes the
  wakeup; no separate re-schedule is needed here.

## 4. Preflight (mode-dependent)

- **RESUME** — run the *lighter* "did it survive the rotation" check: reconcile
  verdict still CLEAN (if a `validator_cmd` is configured), `state/status.json`
  current, the wake-monitor armed (step 3), no orphaned crew vs the handoff
  snapshot. Don't block the loop on headroom — a resumed session is mid-watch.
- **FRESH** — run the **full Preflight card**. Core `mate.md` → "Heartbeat Mode"
  carries the minimum gate inline; the **full 8-gate GO/NO-GO card** lives in
  `modules/loop-mode.md` → "Preflight" — **backstop-force-read that module now**
  (it's a plain, read-on-demand reference, and this is the moment it's needed).
  Print the card. **Refuse to launch on any NO-GO** (Captain waiver only, recorded
  next to the launch line). Do NOT duplicate the card text here — the module is the
  single source of truth.

> **Anti-double-preflight:** `ship-tick` auto-runs the full preflight on its FIRST
> tick (no telemetry line yet this session). To avoid a double preflight, treat
> the preflight here as authoritative and **write the preflight RESULT as the
> session's first telemetry line in today's mate log before launching** — that
> line is exactly what `ship-tick` checks to decide "is this the first tick?".
> With the line present, `ship-tick`'s first invocation skips its auto-preflight
> and runs a normal tick. (If you do NOT write a telemetry line, ship-tick simply
> re-runs the full preflight — safe, just redundant.)

## 5. Launch the loop, then stop

Launch `/loop /ship-tick` (the per-tick loop) and **stop**. ship-watch-start runs
once; from here every wake is a `ship-tick`, not a `ship-watch-start`.

In RESUME mode the first `ship-tick` is just the next tick in the unbroken
sequence — continue as if the compaction hadn't happened.

## Bounds
- Run **once** per launch/resume. Never loop ship-watch-start itself.
- Never run a tick body here — that's `ship-tick`'s job.
- FRESH mode launches only on an all-GO preflight (or a recorded Captain waiver).
- Tier bright lines and all `mate.md` ceremony semantics hold unchanged.
