---
name: shipkit-tutorial
description: >
  The guided, hands-on walkthrough of one full Ship Loop-Mode cycle, for a new
  operator who chose "guided" at onboarding (or runs `/shipkit-tutorial` later to
  replay it). It teaches the loop BY DOING one cycle end to end: file a first
  ticket, dispatch a toy crew watch, start the status UI, arm the wake-monitor,
  send a steer from the browser, and watch the steer wake the loop. Replayable
  and idempotent — every step is reversible and uses a throwaway "tutorial"
  ticket. Not a per-tick loop skill; it runs ONCE and yields.
---

# /shipkit-tutorial — learn the loop by running one full cycle

You are walking a NEW operator (the Captain) through their first complete Ship
Loop-Mode cycle, hands-on. This is the **guided** branch of onboarding: where
`/shipkit-init` wires the machine, this skill teaches the *rhythm* by doing one
real (but disposable) cycle together. The operator chose this over
self-directed; your job is to be a patient, concrete guide — show, don't lecture.

**This skill is conversational + replayable.** Run it once at first onboarding
(invoked by `/shipkit-init` when the Captain picks "guided"), or any time later
with `/shipkit-tutorial` to refresh. It is **idempotent**: it works on a single
throwaway `TUTORIAL` ticket and cleans up after itself (or leaves a clearly
labelled artifact the operator can delete). It assumes `/shipkit-init` has
already run (config + skills + agents installed); if it hasn't, say so and point
to `/shipkit-init` first.

**Pacing.** One step at a time. After each step, confirm the operator sees what
you described before moving on — the *point* is that they watch each mechanism
fire. Don't batch the steps into one dump.

## Before you start (preflight the tutorial)

- Resolve `ship_root` the same way `ship-watch-start` does (read
  `~/.claude/ship-root.txt`, else find `loop.config.json` near a `queue.md`).
  All paths below are relative to `ship_root`.
- Confirm `state/status.json` exists (seeded by init) and the
  `ship-watch-start` / `ship-tick` skills are installed. If not, stop and send
  them to `/shipkit-init`.
- Tell the operator what the next ~10 minutes look like: "We'll file one toy
  ticket, dispatch a quick crew on it, bring up the browser surface, arm the
  wake-monitor, then steer from the browser and watch the loop wake. Everything
  we make is disposable — I'll clean it up at the end."

## The cycle (do these in order, confirming each)

### 1. File a first ticket
Create a throwaway ticket from `templates/ticket.md` at
`projects/tutorial/tickets/TUTORIAL.md` (create `projects/tutorial/tickets/` and
`logs/tutorial/` if absent). Give it a trivially safe, self-contained goal that
needs no repo and no external state — e.g. *"Read README.md and report the
one-sentence pitch for Ship in your log."* Show the operator the filed ticket and
add it to `queue.md` under Ready (the Mate owns `queue.md` — narrate that this is
the dispatch surface). Explain: tickets are the unit of work; the queue is what
the Mate dispatches from.

### 2. Dispatch a toy crew watch
Dispatch ONE `ship-crew` subagent against the TUTORIAL ticket with tight watch
orders: read the ticket, do the trivial task, write a log to
`logs/tutorial/TUTORIAL/<YYYY-MM-DD-HHMM>.md`, update the ticket's Current state,
say "Watch complete." Narrate what's happening: crew are autonomous bounded
sessions; they can't touch `queue.md` or commit (enforced by the hook baked into
`ship-crew`); the log is the handoff. When it finishes, reap it together: read
the log, show how the ticket/queue update reflects the result. (If `ship-crew`
isn't dispatchable because the agents only registered after the init session, use
a built-in agent for the demo and note that the real `ship-crew` is live next
launch — see FOLD-AFFORDANCES.)

### 3. Start the status UI
If `loop.config.json` → `hosts_ports.status_surface` is set (or just for the
tutorial), start the reference surface:
`python3 examples/status-surface/server.py` (honor `PORT`/`SHIP_ROOT` per its
README) as a background task, and open the URL. Show the operator the **Status**,
**Queue**, and **Tickets** tabs — point out their TUTORIAL ticket showing up.
**Clean restart note (Windows):** if a server is already holding the port, kill
it by PID first (`netstat -ano | findstr :<port>` → `taskkill /F /PID <pid>`),
confirm the port is free, then start one — a stale holder serves old code
round-robin.

### 4. Arm the wake-monitor
Start the shipped poll monitor under the harness **Monitor** tool from
`ship_root`: `python3 scripts/wake_monitor.py` (it baselines silently, so
nothing fires yet). Explain the asymmetry that's about to matter: it watches the
directive surfaces (`inbox/captain.md`, `inbox/drops/`), classifies each net-new
item via `scripts/classify_input.py`, and emits a `WAKE` line ONLY for
`wake`-class items — bookkeeping stays quiet. (Mention the optional native fast
path `scripts/wake_monitor_native.py` exists but the poll version is the default.)

### 5. Send a steer from the browser
Have the operator type a steer into the UI's steer box and press Send — e.g.
*"tutorial steer: acknowledge me."* Show that this writes a declared-envelope
drop into `inbox/drops/` (`shipkit_input: v1`, `kind: steer`, `wake_class: wake`).

### 6. Watch it wake the loop
Point at the wake-monitor: within ~8s it should emit a `WAKE drop …` line — that
line wakes the loop. If a `/loop /ship-tick` (or `ship-watch-start`) session is
running, watch the tick fire and respond to the steer. THIS is the payoff: a
browser steer → a drop → a classified wake → a tick. Contrast it explicitly:
have the operator make a pure *bookkeeping* edit (flip a status field) and show
the monitor stays silent — that asymmetry IS the input model.

### 7. Wrap up + clean up
Recap the cycle in one breath: *ticket → dispatch → reap → UI → wake-monitor →
steer → wake.* Then clean up the disposable artifacts (offer, don't force):
remove the TUTORIAL ticket + its queue line + the tutorial drop(s) you created,
or leave them clearly labelled for the operator to delete. Stop the tutorial UI /
monitor background tasks if you started them just for this (leave any the
operator wants running). Point them at the real next step: `/ship-watch-start`
for an actual watch, and `modules/loop-mode.md` for the doctrine.

## Bounds
- Run **once** per invocation; this is not a per-tick loop skill.
- Use ONLY the throwaway `TUTORIAL` ticket + tutorial drops — never dispatch real
  work or touch real tickets/queue items here.
- Keep crew watches trivial and self-contained (no repo writes, no external
  calls) — the demo crew exists to show the mechanism, not to do work.
- Leave `loop.config.json` / `mate.local.md` untouched — the tutorial reads
  config, it does not rewrite it (`/shipkit-init` owns those).
- Idempotent + reversible: a second run starts from a clean TUTORIAL ticket.
