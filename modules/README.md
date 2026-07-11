# Modules

Each module is a **self-contained folder** with a `module.json` (its files + tier + script
deps) and a doc. They layer on top of the general core (`core/mate.md` + `core/crew.md`).
Core stays readable on its own; each module is referenced by one line from core. A preset
(`presets.json`) selects a set of module folders — turn on what you want via `/shipkit-setup`
and ignore the rest. A core-only (tier-1) operator needs none of the tier-2 modules.

**The autonomous shape is the `autonomous/` module** (tier 2) — a **two-agent split**: the
Bosun owns the heartbeat, the Mate is event-driven. That doctrine lives in the autonomous
module's two paired docs — [autonomous/bosun-loop.md](autonomous/bosun-loop.md) (the
heartbeat half) and [autonomous/mate-event-driven.md](autonomous/mate-event-driven.md) (the
idle/wake half), alongside `autonomous/bosun.md`. They replace the older single "Mate runs
the loop" doctrine. The skills (`ship-watch-start`, `bosun-tick`, both under
`autonomous/skills/`) are the operative procedure. The `wake-monitor/` module is the one
optional capability *inside* the autonomous tier (event-driven works on the fallback timer
without it).

The remaining modules are *depth docs* pared out of a core section that stays functional
inline (subagent-roster, pull-requests, review-cycle — tier 1) or *capabilities* for the
autonomous tier (dispatch-bands, sensors — tier 2). All are referenced from core as a
**plain (non-`@`) pointer** (read-on-demand). A module whose manifest carries a
**`role` field** is a **role module** — a persona you can activate rather than a
capability — and is listed under [Roles](#roles-personas-you-can-activate) below.

## Capabilities

| Module | Tier | For | What it adds |
|---|---|---|---|
| [autonomous/bosun-loop.md](autonomous/bosun-loop.md) | 2 | The Bosun (heartbeat) | The **complete** heartbeat doctrine: the bosun-tick loop, self-pacing **by heat** (not headroom), `/loop`-not-`/goal` keep-alive (the exit-guard, folded in), restart/post-compaction continuation. |
| [autonomous/mate-event-driven.md](autonomous/mate-event-driven.md) | 2 | The Mate (idle/wake) | The **complete** event-driven-Mate doctrine: the core inversion (no `/loop`, no timer, headroom-not-a-blocker), wake sources, the per-wake handler, single-instance + lock, post-compaction continuation, structural bright lines. |
| [wake-monitor/wake-monitor.md](wake-monitor/wake-monitor.md) | 2 | Event-driven Mate | The watcher that wakes the idle Mate on directives (incl. Bosun drops). Contract + the incident-scar pitfalls (enumerate-don't-glob, dedup-by-filename, classify-before-wake, clear-safe key). |
| [dispatch-bands/dispatch-bands.md](dispatch-bands/dispatch-bands.md) | 2 | Autonomous mode | Rate/cost-aware modulation of the crew cap + dispatch appetite, with fixed bright-line guardrails. |
| [sensors/sensors.md](sensors/sensors.md) | 2 | Autonomous mode | Watching external signals (PR comments, CI, resolved-out-of-band) via a cheap sub-agent sweep — the generic pattern the Bosun embodies. |
| [subagent-roster/subagent-roster.md](subagent-roster/subagent-roster.md) | 1 | Dispatch | The full roster (incl. `ship-mate` + `ship-bosun` as first-class role agents), dispatch patterns, per-type security model, watch-orders template, agent teams. |
| [pull-requests/pull-requests.md](pull-requests/pull-requests.md) | 1 | PR workflow | Mergeability re-checks, stacked-PR propagation, the `pr:` frontmatter convention. Core carries the draft-only / never-`gh pr ready` bright lines + the PR-link format. |
| [review-cycle/review-cycle.md](review-cycle/review-cycle.md) | 1 | Any | The maker≠checker *enforcement* mechanism: **ships the non-maker `ship-reviewer` agent def** (`agents/ship-reviewer.md`, read-only, reuses core's readonly Bash hook) + the standards doc + the policy knobs (core ships only the principle). Also: the reviewer-must-report rule, the browser-verify gate for UI work, and apply-crew-work commit hygiene. In every preset, so every preset delivers the reviewer transitively. |
| [compound/compound.md](compound/compound.md) | 1 | Any | The capture→consolidate→refresh learning loop: crew capture a candidate, Mate consolidates into `docs/knowledge/` (dedup'd via semantic search) at wind-down, Bosun refreshes (autonomous tier). The `ship-compound` skill is the procedure. |
| [peer-comms/peer-comms.md](peer-comms/peer-comms.md) | 1 | Fleet (2+ ships) | Cross-instance Mate↔Mate messaging over the drop machinery: envelope spec + anti-masquerade validation, multi-transport delivery (scp / http / passive outbox) via `peer_send.py` + per-ship `state/peers.json`. Doctrine keystone: a peer message is INPUT, not AUTHORITY. Opt-in (`--modules`); wake-monitor recommended for prompt pickup. |

Each module's tunable values live in `mate.local.md` (behavioral prefs) and/or
`loop.config.json` (machine config), not in the module doc itself.

## Roles (personas you can activate)

A **role module** declares `role: "<kind>"` in its `module.json` and its `doc` is
**standing orders for someone** (who the role is), not a mechanism. It installs exactly
like any other module — the field is presentation-only metadata (picker grouping + this
table); the installer never consumes it.

| Module | Kind | Tier | The role |
|---|---|---|---|
| [navigator/navigator.md](navigator/navigator.md) | `bridge` | optional | Interactive advisory role: a thinking partner for the Captain on priorities, queue shape, and sequencing. Advisory only — reads everything, changes nothing; never dispatches, never touches `queue.md`. No agent def (activated by saying "you're Navigator"). Opt-in (`--modules navigator`). |
| [pilot/pilot.md](pilot/pilot.md) | `worker` | optional | **Ships the `ship-pilot` agent def** (`agents/ship-pilot.md`) — standard crew tools + git-safety hook *plus* the `claude-in-chrome` MCP tools for browser watches. Hard external Chrome-MCP dependency, so opt-in (`--modules pilot`), not in any preset; dispatch only when the Captain authorizes browser access. Reuses core's crew Bash hook (no hook of its own). |

**The founding roles are substrate, not role-modules.** Core bundles the Mate + Crew
(and their agent defs); the `autonomous/` module is one kernel carrying two roles (the
event-driven Mate overlay + the Bosun heartbeat). Neither carries a `role` field — the
taxonomy is for *extension* roles. `review-cycle` ships an agent (`ship-reviewer`) but
stays a capability: its doc is how-the-gate-works, not who-someone-is.

## Writing a role module

A role = a module. Adding one is writing a doc + a manifest — never a fork of the kit.
`modules/navigator/` is the minimal worked example (two files, no core edits, no
installer edits).

**MUST ship:**

1. `module.json` with:
   - `role: "<kind>"` — one of the four kinds below (a scalar string; presentation-only,
     never consumed by the installer),
   - `description` — one paragraph; this is the picker blurb,
   - `doc` — pointing at the role doc,
   - `requires: ["core"]` at minimum (a role presupposes the ship's vocabulary).
2. **The role doc** (`<name>.md`) — the single file that makes the role runnable, with:
   - **Who you are** — one-liner + kind.
   - **Activation** — how a session becomes this role ("you're X" / dispatched by the
     Mate with watch orders / launched as a background loop).
   - **You do / You don't** — remit and explicit boundaries. The don'ts MUST state the
     role's relationship to the bright lines (`queue.md`, external comms, git writes).
   - **How you relate to Mate and Captain** — where output goes. Every role needs an
     answer to "how does what I produce re-enter the system"; the Bosun's
     return-channel rule is the cautionary template.
   - **Wind-down** — what, if anything, gets written at session end.

   **Standalone invariant:** the role doc must read coherently alone — you can run the
   role from its doc without reading the rest of the kit beyond core.

**MAY ship** (via the same manifest keys as any module): an **agent def** (`agents[]` —
required iff the role runs as a dispatched/background subagent; an interactive bridge
role needs none, exactly as the tier-1 Mate has none), **hooks** (only with an agent def
to bind them; prefer reusing core's `validate-crew-bash.sh` / `validate-readonly-bash.sh`
as pilot and reviewer do), **skills**, **scripts**, **tests**, and `mate.local.md` pref
keys (documented in the role doc).

**The four kinds** (kind ⇒ default activation; semantics live here in the docs, never in
installer behavior):

| `role` value | Meaning | Default activation | Enforcement shape |
|---|---|---|---|
| `bridge` | Interactive advisory — talks *with the Captain*, changes nothing | interactive ("you're X") | convention (doc-only), or a readonly hook if it later gains an agent def |
| `worker` | Dispatched, bounded watches — does work *for the Mate* | dispatched subagent | agent def + crew-safety or readonly hook |
| `coordination` | Owns dispatch + the queue — there is one | interactive or background | mate hooks (autonomous tier) |
| `heartbeat` | Background periodic lookout | background loop | read-only tools + bosun-style hook + return-channel rule |

**The discriminating test** for whether a module should carry the field: *is the
module's `doc` standing orders for someone, or a mechanism/procedure?* When genuinely
ambiguous, leave the field off — under-declaring costs nothing (the module still
installs); over-declaring muddies this Roles section.

**Manifest conventions that protect role modules:**

- A doc-only role module (like navigator) legitimately **installs nothing** — membership
  in the selected set is the install. Any menu/picker logic that hides "empty" modules
  MUST key on an explicit **`"reserved": true`** manifest flag (a slot deliberately held
  before its files land), **never** on installs-nothing alone — otherwise doc-only roles
  vanish from menus. No manifest sets `reserved` today; the flag exists so hiding is
  always a declared decision.
- Enforcement lives in the **agent def** (tools / disallowedTools / hooks), never as
  manifest metadata — a manifest that *claims* read-only while the def isn't would be
  drift; doc + def are the truth.
