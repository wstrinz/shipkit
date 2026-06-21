# Module: Loop Exit-Guard (`/loop` vs `/goal`, the Stop-hook)

**Optional. For Heartbeat Mode.** Core `mate.md` carries the short version in
Heartbeat Mode ("`/loop` is the primary keep-alive; don't layer `/goal` over it;
a stop-hook exit-guard is a separate mechanism"). This module is the detail — kept
in a module because it's dense and version-sensitive (it tracks the harness's
session-keeper primitives, which evolve).

## `/loop` is the primary mechanism

**Use `/loop` to keep a heartbeat alive.** `/loop` re-invokes the session on a
schedule and lets each tick decide whether to reschedule its own next wake — which
is exactly the shape of a self-pacing loop. The tick body runs, schedules the next
fallback (or, at wind-down, *omits* it), and yields. This is the natural and
correct fit for the heartbeat. **Lead with `/loop`.**

## Do NOT layer `/goal` over `/loop`

`/goal` is **incompatible** with a self-pacing heartbeat loop, for two reasons:

1. **Setting a goal starts a turn immediately**, with the goal condition itself as
   the directive. A wind-down-shaped condition therefore makes the Mate wind down
   *now*, not when the condition is actually met.
2. **The goal evaluator fires after every turn** and, if the condition isn't met,
   "starts another turn instead of returning control" — which **vetoes the loop's
   scheduled-wakeup sleeps**, turning the paced heartbeat into a hot loop.

The harness frames `/goal` and `/loop` as **alternative** session-keepers, not
layers. Don't stack them. (`/goal` *is* the right primitive for a detached
run-to-completion session — `claude -p "/goal ..."` — where there's no sleep to
fight; that's a different use case from the paced heartbeat.)

## The exit-guard done right (the Stop-hook)

The thing `/goal` wraps is a **session-scoped Stop hook**: a prompt-based check
that decides whether the session is allowed to stop. For a loop, you want
**loop-aware** stop logic:

- **Allow stop** when a scheduled wakeup is pending (the loop intends to continue —
  stopping is just the gap between ticks) **OR** when wind-down evidence was printed
  (the loop deliberately ended: full ceremony + commit, and it omitted the next
  wakeup).
- **Block stop** otherwise — the session is trying to die mid-loop without either a
  pending wake or a recorded wind-down.

This makes the loop durable without the hot-loop pathology of `/goal`: the timer
keeps it alive, the stop-hook catches accidental deaths, and a real wind-down
(evidence printed, no wakeup scheduled) is allowed through cleanly.

## Wind-down evidence

Whatever exit-guard you run, the wind-down ceremony should **print evidence** — at
minimum a validator/reconcile RESULT line and a handoff-notes-written confirmation —
so the audit record shows the loop ended deliberately, not by accident. The
exit-guard reads that evidence; the log preserves it.
