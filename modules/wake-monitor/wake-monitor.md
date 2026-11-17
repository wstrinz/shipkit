# Module: Wake-Monitor

**For the event-driven Mate.** Core `ship-watch-start` says only "arm the wake-monitor
(see module)." This is the module: what a wake-monitor is, the contract it must satisfy,
and the pitfalls of building one.

## What it is

An **event-driven Mate** ([mate-event-driven.md](../autonomous/mate-event-driven.md))
idles between events. Crew completions wake it natively. A wake-monitor covers the rest:
it watches the Mate's **directive surfaces** (`inbox/captain.md` and `inbox/drops/`, where
the **Bosun** also writes its delta-drops) and wakes the idle Mate when a directive shows
up, while routine bookkeeping does **not** wake it. That asymmetry is the point.

## Native substrate (what Claude Code gives you, and what it doesn't)

The harness `Monitor` tool is the **transport**: it runs the watcher and turns each stdout
line into a wake. It is **not persistent**. Every watch has a deadline of at most 30 minutes
(5 by default), after which Claude gets one notice and the watch ends
([tools-reference, Monitor tool](https://code.claude.com/docs/en/tools-reference#monitor-tool),
read 2026-11-12). So:

- **On the expiry notice, re-arm** (kill any prior instance first; single-instance).
- **Then cover the gap.** Because the seen-set persists, the re-armed watcher reports
  anything that landed while it was down on its first poll. If the state file is missing it
  baselines silently and swallows those, so when re-arming from scratch (or when unsure)
  sweep `inbox/drops/` and `inbox/captain.md` by hand. Drops really do land in the gap; a
  missed re-arm leaves them unseen until something else wakes the Mate.
- **Plugin monitors** run for the whole session with no per-watch deadline, but don't start
  under `-p` ([plugins/components](https://code.claude.com/docs/en/plugins/components.md)).
  Whether they run in a `claude --bg --agent` session is unproven; probe before relying on it.
- **Channels** can push webhook-style events into an open session (research preview,
  allow-listed plugins only; [channels](https://code.claude.com/docs/en/channels.md)). They
  don't watch a directory.

Nothing native classifies a drop, keeps a seen-set, or avoids self-waking on the Mate's own
writes. That policy is what this module supplies.

## The contract

A wake-monitor must:

1. **Watch every directive surface** you accept directives on. A surface you don't watch
   is only picked up on the next sweep.
2. **Wake on `wake`-class inputs only.** Classify each net-new item (directive → wake;
   bookkeeping/self-authored/unchanged-state → batch; declared noise → silent). Record
   `batch`/`silent` in the seen-set so they don't re-fire. **Default to wake when
   ambiguous**: a missed steer costs more than an extra wake.
3. **Stay in sync with the Mate's own writes.** The Mate `mv`s drops to processed and
   clears inbox lines; the monitor must not fire on those.
4. **Be re-armed** on every Monitor expiry, compaction and rotation (see above). The
   post-compaction continuation step checks it is running.

## Pitfalls

All four are real failures (`DECISIONS.md`).

1. **Enumerate, don't glob.** Under zsh's default `nomatch`, a shell glob that matches
   nothing aborts the command, so `ls *.md *.json` with no `.json` files silently kills
   drop detection while other checks keep working. Enumerate in Python (returns empty
   cleanly). Older bash has no associative arrays either: use sorted files / `comm`.
2. **Dedup by net-new filename, not by count.** A count-delta fires on the Mate's own
   `mv`-to-processed and lags under rapid steers. A seen-set of basenames, waking only on
   growth, stays in sync with the Mate's edits.
3. **Classify before you wake.** Without a classifier, every status-applied confirmation,
   unchanged sensor re-drop and self-authored card wakes the Mate, and a burst of routine
   updates becomes a wake storm.
4. **A content surface needs a clear-safe key.** Key a file the Mate also clears by
   **added content-line hashes**, not line count. A clear can only shrink that set, so it
   can't self-wake.

## The reference implementation

**`modules/wake-monitor/wake_monitor.py`**, armed by `ship-watch-start` step 4:

- Stdlib-only, cross-platform **poll loop** (default 8s, `WAKE_POLL_SECS`).
- Classifies through `lib/classify_input.py`, so a declared `wake_class` (the Bosun's
  `wake_class: wake` drops) is honoured verbatim.
- Solves the four pitfalls by construction: Python globbing, a basename seen-set,
  classify-before-wake, and `inbox/captain.md` keyed by added content-line hashes.
- Baselines silently on first run and persists its seen-set
  (`state/.wake_monitor_state.json`), so a re-arm resumes without re-firing.
- Each `WAKE <reason>` stdout line is a Mate wake.

Tests: `modules/wake-monitor/tests/test_wake_monitor.py`.
