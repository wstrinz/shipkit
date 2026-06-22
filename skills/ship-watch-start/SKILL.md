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

**Bootstrap: locate ship_root first, before reading any ship-root file.**

`loop.config.json` lives in the ship root, not next to this skill. Resolve the
ship root in this order — stop at the first hit:

1. Read `~/.claude/ship-root.txt` (one-line absolute path written by
   `scripts/shipkit_init.py` during onboarding). This is the fast path.
2. If not present, look for `loop.config.json` in the current working directory
   or in any parent that contains `queue.md` (the ship root's fingerprint).
3. If still not found, ask the Captain: "Where is your ship directory?" Record
   the answer and remind them to re-run `/shipkit-init` to write the pointer.

Once `ship_root` is resolved, read `loop.config.json` from `<ship_root>/loop.config.json`.
Extract: `ship_root` (authoritative — use this going forward), `repos`,
`chat_surface`, `headroom_signal_path`, `validator_cmd`. Optional fields that are
null degrade gracefully. See `loop.config.example.json` in the ship root for the
full field contract.

All subsequent file references (`mate.md`, `modules/loop-mode.md`, `queue.md`,
`captain.md`, `state/status.json`, `logs/mate/`) are **relative to `ship_root`**,
not to this skill's directory.

The *meaning* of every step lives in the docs — read it there, do not re-derive.
**Base role** is in `<ship_root>/mate.md` (request/response First Mate). **The
autonomous-loop doctrine** — everything specific to running the heartbeat — lives
in `<ship_root>/modules/loop-mode.md`; read it on entry, it is the source of truth
for Loop Mode:
- **Post-compaction continuation** — `modules/loop-mode.md` → "Post-compaction continuation"
- **The Loop / Heartbeat Mode** — `modules/loop-mode.md` → "The Loop" / "Heartbeat Mode"
- **Preflight (GO/NO-GO)** — `mate.md` → "Loop / Heartbeat Mode" carries the brief
  pointer; the full 8-gate card lives in `modules/loop-mode.md` → "Preflight"
  (backstop-force on FRESH launch)

## 1. Detect mode

- **RESUME** (post-compaction) — you arrived via a SessionStart re-anchor
  directive, or a recent pre-compaction handoff snapshot exists in `state/`. A
  stale snapshot from a prior session is NOT a resume signal.
- **FRESH** — no recent handoff snapshot; the Captain launched
  `/ship-watch-start` by hand after the opening ceremony.

State which mode you detected before proceeding.

## 2. Re-anchor (both modes)

Read role + docs + state — the FILES, not any summary. All paths below are
relative to the `ship_root` resolved in the Bootstrap step above.
- `mate.md` (base role — request/response First Mate)
- **`modules/loop-mode.md`** (the autonomous-loop doctrine) — Loop Mode lives here,
  not in `mate.md`. Read it on entry; it is load-bearing for running the heartbeat.
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

The other module docs — `modules/subagent-roster.md`, `modules/pull-requests.md`,
etc. — are **read-on-demand**, NOT loaded here. The per-tick loop backstop-forces
them when a tick actually needs the detail (see `ship-tick`).

In RESUME mode, carry the last tick number forward — **tick numbering continues
unbroken** (compaction is a context event, not a watch boundary). Do NOT open a
new watch section.

## 3. Verify / arm the wake machinery

Background tasks may or may not survive a compaction. Check what's alive, and on
a FRESH launch **arm the monitor + offer the UI** (don't leave them to the
operator — that was the Watch-1 hand-assembly this folds back):

- **Wake-monitor — ARM IT.** The loop's wake signals are (a) the `chat_surface`
  from `loop.config.json` (if set), (b) changes to `inbox/` and `captain.md`,
  and (c) crew completions (harness-native). shipkit ships the reference
  monitor at **`scripts/wake_monitor.py`** (the zero-dep, cross-platform poll
  version — see `modules/wake-monitor.md`). Run it under the harness **Monitor**
  tool from `<ship_root>` so every `WAKE <reason>` stdout line wakes the loop:
  `python3 scripts/wake_monitor.py` (env `SHIP_ROOT=<ship_root>`,
  `WAKE_POLL_SECS` to tune the ~8s default). It baselines silently on first run
  and persists its seen-set, so arming it here (FRESH) and **re-arming it on
  RESUME if the background task did not survive** is safe — it won't re-fire
  pre-existing items. It classifies each net-new item via
  `scripts/classify_input.py` and wakes only on **wake**-class; **batch**-class
  is recorded in the seen-set (no wake) for the tick to drain. (A local opt-in
  fast path — `scripts/wake_monitor_native.py`, watchdog-based — exists for
  lower latency; do NOT use it unless the operator installed `watchdog`.)
- **Status UI — OFFER TO START IT.** If `loop.config.json` →
  `hosts_ports.status_surface` is set, the reference UI
  (`examples/status-surface/`) should be serving it. Check whether it is up
  (e.g. a quick GET on the URL, or `netstat`/`findstr` for the port). If it is
  NOT up, offer a one-line prompt: *"Status surface configured at <url> but
  nothing is serving it — start it? [y]"* and on yes, start
  `python3 examples/status-surface/server.py` (honor `PORT`/`SHIP_ROOT` per its
  README) as a background task. **Clean (re)start on Windows:** a stale server
  can keep holding the port (`SO_REUSEADDR` lets a second start also bind it →
  stale code served round-robin). Before starting, kill any holder by PID
  (`netstat -ano | findstr :<port>` → `taskkill /F /PID <pid>`), confirm the
  port is FREE, then start exactly one. If `status_surface` is unset, skip this
  silently.
- **/loop wakeup** — launching `/loop /ship-tick` at step 5 re-establishes the
  wakeup; no separate re-schedule is needed here.

## 4. Preflight (mode-dependent)

- **RESUME** — run the *lighter* "did it survive the rotation" check: reconcile
  verdict still CLEAN (if a `validator_cmd` is configured), `state/status.json`
  current, the wake-monitor armed (step 3), no orphaned crew vs the handoff
  snapshot. Don't block the loop on headroom — a resumed session is mid-watch.
- **FRESH** — run the **full Preflight card**. The **full 8-gate GO/NO-GO card**
  lives in `modules/loop-mode.md` → "Preflight" (read at step 2). Print the card.
  **Refuse to launch on any NO-GO** (Captain waiver only, recorded
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

## 4.5 First-tick guided framing (FRESH only)

**FRESH launch only — skip entirely in RESUME mode** (a resumed session is
mid-watch; the Captain has already been oriented). On a FRESH launch, the
*first* `ship-tick` after this skill hands off must emit a consistent "welcome
aboard" orientation report instead of improvising one each time. Set this up so
the first tick surfaces it: stash the four points below as the framing to emit on
tick 1, or — equivalently — emit it yourself as the launch report immediately
before launching the loop. Either way the Captain sees the SAME orientation every
fresh launch. Surface all four, in this order:

1. **Context gauge / wind-down.** Read whether `headroom_signal_path` is set in
   `loop.config.json`.
   - **Not configured (the common fresh case):** state `gauge=stale` and what it
     means — *self-estimates never wind the loop down*, so the heartbeat runs
     until the Captain calls it or a compaction / context-low system warning
     fires (the wind-down triple-signal rule, `modules/loop-mode.md`). Tell the
     Captain how to wire a real signal: point `headroom_signal_path` at a file
     whose contents are a current headroom reading, and the loop will wind down
     at the configured threshold instead of running to compaction.
   - **Configured:** name the path and reference the wind-down threshold the loop
     will honor.
2. **Wake sources.** What can wake the loop between ticks: a direct
   Captain message / `chat_surface` steer (immediate), a crew completion
   (event-driven, harness-native), and the fallback timer (≈1200–1800s) as the
   floor. State whether a **wake-monitor is armed** (step 3 now arms
   `scripts/wake_monitor.py` by default on FRESH launch) — confirm it is up so
   an inbox/drops steer wakes within ~8s. If for some reason none is armed,
   say so plainly: an inbox edit won't wake the loop instantly, it'll be caught
   on the next fallback tick or sooner if crew completes, and standing up that
   monitor is itself a good first affordance.
3. **Empty queue is not a stop signal.** Explain the heartbeat keeps ticking the
   fallback even with an empty queue and no crew — a *feeling* of doneness is not
   a stop signal; only low headroom, a context-low warning, or a Captain order
   ends the loop. So a quiet first tick is healthy, not idle-to-exit.
4. **What I need from you.** The two natural inputs that make the watch
   productive (either is fine, both welcome):
   - **Projects** — name the project(s). For each: a repo path (added to
     `loop.config.json` → `repos`) and a one-line goal. The Mate files tickets
     and dispatches crew.
   - **Affordances** — the ship UI / status surface, a wake-monitor on the inbox,
     dispatch bands, sensors. Each is an opt-in module under `modules/`. Note
     which are already up vs. not yet serving.

Keep it tight — this is orientation, not a status dump. The autonomy tiers and
bright lines (`mate.md`) still gate everything that follows.

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
