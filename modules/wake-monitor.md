# Module: Wake-Monitor

**Optional. For Heartbeat Mode.** Core `mate.md` says only "arm a wake-monitor (see
module)." This is the module: what a wake-monitor is, the contract it must satisfy,
and the hard-won pitfalls of building one.

## What it is

A self-pacing heartbeat loop wakes on three things: crew completions
(harness-native), a fallback timer, and **directives that arrive between ticks**. A
wake-monitor is the mechanism for that third one — a lightweight background watcher
on your **directive surface(s)** (a chat endpoint, the Captain's inbox file, a
drops directory) that re-invokes the loop when a directive shows up, so a Captain
message doesn't sit unseen until the next fallback timer fires.

Without it, a loop with a long fallback interval can leave a Captain steer
unattended for many minutes. With it, directives wake promptly while routine
bookkeeping does **not** (that asymmetry is the whole point — see the input model).

## The contract

A wake-monitor must:

1. **Watch every directive surface** you accept directives on — typically the chat
   surface, `inbox/captain.md`, and `inbox/drops/`. A surface you don't watch can
   only be picked up on the fallback timer.
2. **Wake on `wake`-class inputs only.** Classify each net-new item (directive →
   wake; bookkeeping/self-authored/unchanged-state → batch; explicitly-declared
   noise → silent). Wake the loop on `wake`; record `batch`/`silent` in the seen-set
   so they don't re-fire, and let the tick drain `batch` at its reconcile step.
   **Default to wake when ambiguous** — a missed steer costs more than an extra tick.
3. **Stay in sync with the loop's own writes.** The loop edits the same surfaces it
   watches (it `mv`s a drop to processed, appends its own status line to the chat).
   The monitor must not fire on the loop's *own* actions.
4. **Survive rotation / compaction or be re-armed.** Background tasks may not carry
   across a compaction. The post-compaction continuation step checks the monitor
   survived and re-arms it if not.

## Pitfalls (incident scars — read these before building one)

These are real failures from a production loop. They generalize to anyone building
a file-watch wake-monitor.

### 1. Enumerate, don't glob

When detecting net-new files in a drops directory, **enumerate with `find`, not a
shell glob.** Example: `find inbox/drops -maxdepth 1 \( -name '*.md' -o -name
'*.json' \)` — NOT `ls *.md *.json`.

A shell glob that matches nothing is a footgun: under some shells (zsh with the
default `nomatch` behavior) a glob with no matches **aborts the command**. If the
monitor enumerates drops with `ls *.md *.json` and there happen to be no `.json`
files, the whole `ls` aborts and drops-detection silently breaks — while unrelated
checks (a chat grep, a `stat`) keep working, so the loop *looks* healthy (chat
wakes fire) but ticket-comment/drop cards never wake. A silent partial failure is
the worst kind. (Companion footgun: a `bash -c` monitor on older bash has no
associative arrays — use sorted files / `comm` for the seen-set, not `declare -A`.)

### 2. Dedup by net-new filename, not by count

Track drops by a **seen-set of basenames** and wake only on *growth* (a net-new
filename), NOT by a count-delta.

A count-delta monitor breaks two ways: (a) it fires on the loop's **own** `mv`-to-
processed (count goes 1→0, which looks like a change), producing a spurious self-
wake the loop just no-ops; and (b) it lags under rapid steers (reports 2→1 when the
true count is already 0). A filename-set keyed on growth stays in sync with the
loop's own edits — the loop adds a basename to the seen-set when it processes a
drop, so the monitor never re-fires on it.

### 3. Classify before you wake

Run each net-new drop through a classifier before deciding to wake. **Wake** on
directives (a Captain steer, a substantive comment, a status-*request*). **Batch**
(record in the seen-set silently, drain at the next tick's reconcile) on
bookkeeping: status-applied / close-applied confirmations, sensor re-drops of
unchanged state, the loop's own self-authored cards. **Default to wake** when a drop
doesn't clearly classify.

Skipping classification produces a **wake storm**: every bookkeeping drop wakes the
loop, each wake may cascade (renumbering, re-reconciling), and a burst of routine
status updates turns into a flurry of no-op ticks. Classification is what keeps the
loop quiet under routine churn and responsive under real directives.

### 4. A chat surface needs a sender filter

If your chat surface is one the loop *also writes to* (the loop appends its own
status replies), the monitor must wake only on **Captain-authored** entries, not on
the Mate's own appends. Count/match by author role, not raw message count, or the
loop self-wakes on its own status posts.

## The reference implementation (shipped)

shipkit ships a working wake-monitor: **`scripts/wake_monitor.py`** — the
companion this module used to describe only in the abstract. It is the version
`ship-watch-start` arms on launch (step 3, "verify / arm the wake machinery").

- **Zero-dependency, cross-platform, stdlib-only POLL loop** (default 8s,
  `WAKE_POLL_SECS`). This is shipkit's default by design — it matches the
  toolkit's "stdlib only, cross-platform" posture and needs no `pip install`.
- Reuses `scripts/classify_input.py` so a declared `wake_class` is honored
  verbatim (no second, drifting copy of the wake/batch/silent ladder).
- Solves the four pitfalls above by construction: enumerates drops with Python
  globbing (no shell-nomatch footgun, #1); dedups drops by a seen-set of
  basenames (#2); classifies before waking (#3); keys `inbox/captain.md` by
  added content-line hashes so a clear can only shrink the set and thus cannot
  self-wake (#4).
- Baselines silently on first run and persists its seen-set
  (`state/.wake_monitor_state.json`) so a restart / post-compaction re-arm
  resumes without re-firing.
- Run it under the harness Monitor tool: every `WAKE <reason>` stdout line is a
  loop wake; `batch`/`silent` items are absorbed into the seen-set and drained
  at the next tick's reconcile.

Tests: `tests/test_wake_monitor.py` covers the Watch-1 five behaviors
(wake-steer fires, batch silent, dedup holds across a processed-move,
captain-add fires, captain-clear no-self-wake) plus the silent-baseline +
state-persistence guarantees.

### Optional native fast path (local opt-in — NOT the default)

If the ~8s poll latency on steers proves annoying on a local box, there is an
**opt-in** native filesystem-watch variant: **`scripts/wake_monitor_native.py`**.
It is behaviorally identical (same surfaces, dedup, classify-before-wake, silent
baseline, persisted seen-set, `WAKE <reason>` contract — it literally reuses
`wake_monitor.poll()`), but triggers a re-check on a real fs event via the
third-party **`watchdog`** package instead of on a fixed timer, with a slow
safety poll underneath so a coalesced event can't strand a steer.

This is the **only** piece of the wake machinery that takes a runtime
dependency, which is exactly why it is opt-in and not shipped on the default
path. Install `watchdog` (`pip install watchdog`) to use it; without it the
script prints a clear note and exits non-zero (it never silently falls back, so
you never *think* you have the fast path when you're running nothing). **Prefer
the poll version unless you have a measured reason to switch.**

## Wiring it (sketch)

The concrete mechanism depends on your harness. A common shape: a background
process (or a `ScheduleWakeup`-driven check) that, each interval, enumerates the
watched surfaces, diffs against a persisted seen-set of basenames + last-seen chat
timestamp, classifies net-new items, and re-invokes the loop iff any are `wake`-
class. Persist the seen-set so it survives a monitor restart, and re-arm the
monitor as part of post-compaction continuation.
