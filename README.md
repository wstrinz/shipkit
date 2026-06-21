# Ship: Bounded-Context Orchestration for Claude Code

Ship is a system for coordinating multiple Claude Code agent sessions around your engineering work. It structures handoffs between fresh sessions so context rot doesn't eat your progress.

## Quick Start

One move, entirely Claude-Code-driven — no manual `git clone` or `cd`.

**Open a terminal in the directory where you want the Ship to live** (often your
dev-work root, alongside your other repos), start Claude Code there, and paste this:

```
Clone https://github.com/wstrinz/shipkit into ./ship, then act as my First Mate:
read ./ship/README.md's Bootstrap Instructions and ./ship/mate.md to learn the
system, and run the onboarding interview in ./ship/skills/shipkit-init/SKILL.md to
set me up. Start with a one-paragraph overview and the first question.
```

Claude Code does the whole bring-up: it clones the repo into `./ship`, reads the
bootstrap docs, then conducts the onboarding interview (preset, where the ship
lives, your taste preferences), installs the skills, and seeds state. When it
finishes, open a fresh Claude Code session and say *"You're First Mate on this ship.
Read `mate.md`"* — then run **`/ship-watch-start`** to begin. The rest of this README
explains what you just set up.

> **Where to run it.** Ship is **one per machine**, living at `<dev-root>/ship`. You
> can run the Mate with `ship/` as the working directory, **or** from the parent
> dev-root so the Ship can also see and operate on sibling repos — the `ship_root`
> value in `loop.config.json` plus the watched-repos setting handle either layout.

> **On Windows?** See [Running on Windows](#running-on-windows) — Python and the status surface run natively; the bash classifier + hooks want WSL or Git-Bash.

---

## How it works

You're the **Captain**. You set priorities, make decisions, and steer. Claude Code acts as your **First Mate** — it manages a work queue, dispatches background agents (**Crew**) for bounded tasks, and keeps you informed. Crew sessions write structured logs when they finish, so the next session can pick up cleanly without assuming any context persists.

Ship lives in a single directory on your machine (not inside any one repo). It coordinates work across whatever repos and projects you point it at.

## Your role as Captain

**Day-to-day you'll:**
- Start a Claude Code session and tell it to be your First Mate
- Drop tasks, ideas, and priorities into `captain.md` and `inbox/captain.md`
- Steer the Mate: approve dispatches, review findings, make calls on scope
- Commit and push when the Mate reports work is ready (crew can't push)
- Merge PRs and make external communications (comments, reviews, Slack)

**The Mate handles:**
- Reading ship state and reporting status
- Dispatching crew to work on tickets in the background
- Processing your inbox items into tickets
- Tracking progress across the queue

**You don't need to:**
- Manually manage logs or ticket formatting
- Write watch orders (the Mate does this)
- Remember what happened last session (that's what logs are for)

## Getting started

### 1. Bootstrap your ship

Use the [Quick Start](#quick-start) above: paste the single bootstrap instruction into Claude Code from the directory where you want the Ship to live. Claude Code clones the repo into `./ship`, then runs the onboarding interview — asking where the ship directory should live and what you're working on — and wires everything up. (The agent-facing detail lives in [Bootstrap Instructions](#bootstrap-instructions-for-claude-code) and `skills/shipkit-init/SKILL.md`.)

### 2. Start your first Mate session

Once bootstrapped, start a Claude Code session with your ship directory as the working directory (or as an additional context path), and tell it:

> You're First Mate on this ship. Read `mate.md` for your standing orders.

The Mate will read ship state, report status, and ask for steering.

### 3. Start working

Drop work items into `inbox/captain.md` — the Mate will triage them into tickets. Or just tell the Mate what you want done. It'll dispatch crew, track progress, and report back.

---

## Bootstrap Instructions (for Claude Code)

**If you're a coding agent reading this:** follow these steps to set up Ship on this machine. Adapt paths and details to the current environment. Ask the Captain questions where noted.

### 1. Choose the ship directory

Ship is **per-machine, not per-project.** It lives in a single directory and coordinates work across repos. Ask the Captain where they'd like it, or default to somewhere alongside their repos (e.g., `~/dev/work/ship/` or `~/ship/`).

### 2. Create the directory structure

```
{ship-dir}/
  captain.md           # Captain's priorities (from templates/captain.md)
  queue.md             # Work queue (from templates/queue.md)
  CLAUDE.md            # System entry point (from this repo)
  mate.md              # First Mate standing orders (from this repo)
  crew.md              # Crew standing orders (from this repo)
  inbox/
    captain.md         # Captain's inbox for quick thoughts
    drops/             # Items from external processes
      .gitkeep
  projects/
    {area}/            # Organize by area (e.g., "main", "infra", "frontend")
      tickets/
  logs/
    {area}/            # Watch logs per ticket
    mate/              # Daily mate logs
  docs/
    knowledge/         # Accumulated knowledge (env config, patterns, etc.)
  scripts/             # Hook scripts for subagent enforcement
```

Initialize it as a git repo (`git init`). Ship state benefits from version control — it's the coordination substrate.

### 3. Install hook scripts

Copy `scripts/validate-crew-bash.sh` and `scripts/validate-readonly-bash.sh` from this repo to `{ship-dir}/scripts/`. Make them executable (`chmod +x`).

### 4. Install subagent definitions

Ship uses custom Claude Code subagents. Copy the files from `agents/` in this repo to `~/.claude/agents/`, **replacing `{SHIP_DIR}`** in hook command paths with the absolute path to the ship directory.

For example, if the ship directory is `/Users/will/dev/work/ship/`, then `{SHIP_DIR}/scripts/validate-crew-bash.sh` becomes `/Users/will/dev/work/ship/scripts/validate-crew-bash.sh`.

**If ship-* agents already exist at `~/.claude/agents/`:** This machine already has a Ship instance. The hook scripts are generic (git safety, not project-specific), so unless the existing agents point to a different ship directory with different hooks, they're probably fine as-is. Check the hook paths — if they point to a valid ship scripts directory, leave them alone. If they're stale or point to a removed directory, overwrite them.

### 5. Set up captain.md

Create `{ship-dir}/captain.md` from `templates/captain.md`. If working interactively, ask the Captain:
- What's their current situation?
- What are the top priorities?
- Any constraints on how work should be done?
- Any standing orders (e.g., "always run tests", "commit frequently")?

### 6. Create initial project areas

Ask the Captain what repos or areas of work they manage. Create `projects/{area}/tickets/` and `logs/{area}/` for each. Common patterns:
- One area per repo (`drip/`, `frontend/`, `infra/`)
- One area per domain (`backend/`, `integrations/`, `devops/`)
- Just `main/` if they're focused on a single codebase

### 7. Verify

The Mate should be able to read ship state and report status. Tell Claude Code: "You're First Mate on this ship. Read `{ship-dir}/mate.md` for your standing orders." It should read the queue, captain.md, and inbox, then report that everything is empty and ready for work.

---

## What's in Shipkit

| Directory | Contents | Purpose |
|-----------|----------|---------|
| `agents/` | `ship-crew.md`, `ship-lookout.md` | Custom subagent definitions (install to `~/.claude/agents/`) |
| `scripts/` | `validate-crew-bash.sh`, `validate-readonly-bash.sh` | PreToolUse hook scripts for enforced safety |
| `templates/` | `ticket.md`, `captain.md`, `queue.md` | Templates for ship-specific files |
| `modules/` | `wake-monitor.md`, `loop-exit-guard.md`, `dispatch-bands.md`, `review-cycle.md`, `sensors.md` | Optional extension docs layered on the core `mate.md` |
| `roles/` | `README.md`, `_template/` | Extension roles directory (add custom roles here) |
| Root | `mate.md`, `mate.local.example.md`, `crew.md`, `CLAUDE.md` | Role standing orders + the prefs-overlay template (copy to ship directory) |

## How the Mate doc composes (core + overlay + config + modules)

The First Mate's standing orders are split so the **general doctrine** can be
updated from upstream without ever colliding with **your local taste** or **your
machine specifics**:

| Layer | File | Owns | Updated by |
|---|---|---|---|
| **Core doctrine** | `mate.md` | The operating doctrine true for any operator. No concrete numbers — core refers to configured values generically ("your configured X") and force-loads the overlay once via an `@mate.local.md` reference. | `pull-upstream` (freely) |
| **Behavioral prefs** | `mate.local.md` | Your taste: wind-down threshold, crew cap, model roster, report format, review policy, house notes. Resolves core's "your configured X" seams. | You (hand-edit or `/shipkit-init`) — **never** touched by `pull-upstream` |
| **Machine config** | `loop.config.json` | Paths, ports, hosts, watched repos, the flat crew cap. | `/shipkit-init` (then hand-edit) |
| **Modules** | `modules/*.md` | Optional capabilities (wake-monitor, dispatch-bands, review cycle, sensors, loop exit-guard) **and depth docs** (loop-mode, subagent-roster, pull-requests) pared out of core sections that stay functional inline. Each referenced one line from core. | `pull-upstream` (the docs); you toggle which capabilities you run |

**Reference convention — `@` vs plain.** Core distinguishes two reference flavors,
and the form tells the reader (operator or agent) *when* to read it:

- **`@path`** = **force-load up front** — load-bearing, read at watch start every
  time. Used sparingly; `@mate.local.md` is the main one (the Loop-Mode skills read
  every `@`-ref on launch).
- **plain `path`** (no `@`) = **read-on-demand enrichment** — core's inline summary
  is enough to function; the referenced doc adds depth. The tick skills
  **backstop-force** a plain reference at the moment a tick genuinely needs it
  (e.g. the full preflight card on first tick, PR mechanics when reaping a PR
  watch) rather than always loading it up front.

This keeps **core `mate.md` standalone-functional**: every pared section retains
enough inline to operate without reading any reference; the modules add depth, never
load-bearing for basic operation.

**Composition is read-order, not a build step.** There is no templating engine and
no generated combined file. At watch start the Mate reads, in order:

1. **`mate.md`** — the general-core doctrine (refers to configured values
   generically; force-loads the overlay via its `@mate.local.md` reference).
2. **`mate.local.md`** — your behavioral prefs; its values **resolve and extend**
   core's "your configured X" seams.
3. **`captain.md` + the watch orders** — priorities and the specific task.

The Mate does the merge by reading both docs, exactly as it already reads
`mate.md` + `captain.md`. `loop.config.json` supplies machine values to the skills;
the modules are read on demand when core references them. A core-only operator with
no `mate.local.md` still has a complete, working doctrine — the seams describe
*what* to tune; the overlay just says *to what*.

**Onboarding populates the overlays.** `/shipkit-init` (below) conducts a short
interview whose questions map 1:1 to the configurable seams core refers to: machine
questions → `loop.config.json`; taste questions (wind-down threshold, default crew
model, report format, which modules to run) → `mate.local.md` + the chosen
`modules/*`. Copy `mate.local.example.md` → `mate.local.md` to start by hand.

## Key Concepts

### Ship is per-machine

One ship directory coordinates all your work across repos. Crew agents work in whatever repo the ticket points to, but ship state (queue, tickets, logs) lives in the ship directory.

### Subagent types

Crew are dispatched as custom subagents with enforced tool restrictions:

| Type | Purpose | Write access | Safety |
|------|---------|-------------|--------|
| `ship-crew` | Standard watches (research + implementation) | Yes | Allow-list hook blocks git writes, rm -rf, gh writes |
| `ship-lookout` | Quick read-only checks | No (enforced) | disallowedTools + allow-list hook for Bash |

### Logs are the handoff

When a crew session ends, it writes a log with what was accomplished, current state, next steps, and handoff confidence (1-5). A fresh session reads the log and continues. No context persists between sessions — logs are the memory.

### Crew can't commit

Crew write code and logs, but destructive git operations (commit, push, reset) are blocked by a PreToolUse hook. The Mate or Captain handles commits. This keeps handoffs clean and prevents runaway agents from pushing broken code.

### The Mate runs the loop

The Mate continuously: checks inbox, checks active work, dispatches if capacity, stays present for steering. Crew run in the background. The Captain can steer the Mate at any time without waiting for crew to finish.

## Customization

Shipkit is a starting point. As you use it, you'll likely:

- Add knowledge docs for your environment (`docs/knowledge/env-config.md`)
- Create additional subagent types for specialized work
- Extend crew permissions with `scripts/crew-allow-local.sh` (see below)
- Add project-specific hooks for domain-specific safety rules
- Evolve the role docs as you learn what works for your team

The core mechanism (watches + logs + structured dispatch) stays stable while everything else adapts.

### Extending crew permissions

The crew bash allow-list (`scripts/validate-crew-bash.sh`) is synced from upstream. To add project-specific commands (e.g., `aws`, `kubectl`) without losing them on upstream pulls, copy `templates/crew-allow-local.sh` to `scripts/crew-allow-local.sh` in your ship directory and add your rules. The validation script sources it automatically if present, and `pull-upstream.sh` never touches it.

## Enabling Loop Mode

By default the Mate runs **request/response** — it acts when you invoke it. **Loop
Mode** is an opt-in, additive mode in which the Mate runs a **self-pacing
heartbeat** instead: it keeps its own time, waking on your directives, on crew
completions, and on a fallback timer, and reconciling ship state every tick.
Nothing in request/response changes — Loop Mode is inert until you start it.

Loop Mode runs **headless**. The browser status surface, gauges, dispatch bands,
and sensors are **optional modules** layered on top; the loop needs none of them.

### Recommended: the onboarding interview (`/shipkit-init`)

The easiest way to enable Loop Mode is the **conversational interview**. Install
the onboarding skill and run it — the agent asks what you want and wires it:

1. **Install the init skill** — symlink (or copy) `skills/shipkit-init/` into
   `~/.claude/skills/`.
2. **Run `/shipkit-init`** in Claude Code from the ship directory. It conducts a
   short interview:
   - **Preset** — `minimal` (headless core only) / `standard` (core +
     status-surface UI, the recommended default) / `full` (everything shipkit
     ships) / `custom` (pick your own modules).
   - **Modules** — adjust the preset's set, or toggle individually for `custom`.
     Today shipkit ships two modules: **core** (always on) and **status-surface**
     (the reference browser UI). Other module names you may see are *planned*
     framework slots that ship no code yet — the interview is honest about which
     is which.
   - **Ship-root** — confirm the single ship-root for this machine (default: the
     current dir). **One ship per machine.**
   - **Skills install** — symlink (tracks the repo) vs copy (frozen snapshot).
     Defaults to symlink on macOS/Linux, copy on Windows (symlinks there need
     admin/Developer Mode).
   - **Watched repos** — only asked if you select a sensor module.
3. The interview then runs `scripts/shipkit_init.py` (idempotent, with a
   `--dry-run` preview): it writes `loop.config.json` from your answers,
   installs the selected skills, seeds `state/status.json`, and prints the smoke
   test below. Re-run it any time to add a module — it's a safe no-op for
   anything already installed.

### Manual fallback (hand-edit the config)

If you'd rather wire it by hand (or script it), the steps the interview automates
are:

1. **Skills** — symlink (or copy) `skills/ship-watch-start/` and `skills/ship-tick/`
   into `~/.claude/skills/`. (On Windows, prefer copy — see [Running on Windows](#running-on-windows).)
   The status-surface UI is not a skill — it ships as `examples/status-surface/`
   and runs in place; see its README.
2. **Config** — edit `loop.config.json` (the one config touch). Set `ship_root`,
   your `repos`, and `max_concurrent_crew`; optionally a `chat_surface`,
   `headroom_signal_path`, and `validator_cmd`. See `loop.config.example.json` for
   a fully-documented reference — every field is explained inline.
3. **Seed state** — run `python3 scripts/status_writer.py --init` to write a fresh
   `state/status.json` (the six CORE fields at tick 0). This is the loop's
   persistent state — it survives compaction and lets the Mate pace itself.
4. **mate.md** — the **Loop Mode** section in `mate.md` carries the semantics
   (self-pacing, the wake-classes, the wind-down triple-signal rule, post-compaction
   continuation). Nothing to edit; it's there as soon as you adopt Loop Mode.
5. **Launch** — open Claude Code in the ship directory, "you're First Mate," then
   run **`/ship-watch-start`**. It runs preflight, then hands off to
   `/loop /ship-tick`, which self-paces from there. No browser needed.

**Smoke test (the acceptance):**
- Preflight prints and passes (or names a NO-GO).
- Drop a **directive** (a chat message or an inbox steer) → the loop **wakes**.
- Flip a **bookkeeping** item (a status/queue change) → the loop does **NOT** wake;
  it shows up reconciled at the next tick. *That asymmetry is the input model
  working.*
- One quiet tick logs a telemetry line + writes `status.json`; `ship-watch-start`
  exits and `ship-tick` self-paces.

**The pieces:**

| File | Role |
|------|------|
| `skills/shipkit-init/SKILL.md` | The onboarding interview — conducts the conversational bring-up, then calls the apply step |
| `scripts/shipkit_init.py` | Deterministic, idempotent apply step the interview calls (writes config, installs skills, seeds state) |
| `skills/ship-watch-start/SKILL.md` | Start/resume: preflight → launch `/loop /ship-tick` once → stop |
| `skills/ship-tick/SKILL.md` | One tick: orient → reap → reconcile → inbox → dispatch → telemetry → write state → pace |
| `scripts/status_writer.py` | Reference writer for the CORE `state/status.json` fields (modules extend the schema) |
| `scripts/classify_input.sh` | The input-model seam: `<input>` → `wake` \| `batch` \| `silent`. Reads the declared **input envelope** (`wake_class` authoritative → `kind` table → content heuristic+warn); see the header block for the contract |
| `state/status.json` | The loop's persistent state (seeded by `status_writer.py --init`) |
| `loop.config.json` | The single config seam — ship root, repos, chat surface, machine specifics |

## Running on Windows

Ship runs on Windows, with one caveat: the bash pieces want a POSIX shell.

| Piece | On Windows |
|---|---|
| `scripts/shipkit_init.py`, `scripts/status_writer.py` | **Native.** Stdlib Python 3, `pathlib` paths, UTF-8 I/O. The skill install **defaults to copy** (not symlink — Windows symlinks need admin/Developer Mode), and a symlink that fails at runtime falls back to a copy automatically. |
| `examples/status-surface/server.py` | **Native.** Python 3 stdlib HTTP server, no build step. |
| `scripts/classify_input.sh` + `tests/test-classify-input.sh` | **Needs a POSIX shell.** These are bash; run them under **WSL** or **Git-Bash**. They don't run in `cmd`/PowerShell. |
| `scripts/validate-crew-bash.sh`, `scripts/validate-readonly-bash.sh` (the crew hooks) | **Needs a POSIX shell.** Bash hook scripts — point Claude Code's hook config at the WSL/Git-Bash interpreter. |
| Skills install location (`~/.claude/skills`) | **Native.** Resolves to your Windows home via `pathlib`; the apply step copies skill dirs there. |

**Bottom line:** Python + the status surface work natively; the bash classifier and crew hooks want WSL or Git-Bash. We deliberately did **not** port the bash to PowerShell — a POSIX shell is the simpler dependency. If you're a heavy Windows user, WSL is the smoothest path (one Linux environment for the whole kit); Git-Bash works for the standalone scripts.

## Staying up to date

`scripts/pull-upstream.sh` syncs framework files (role docs, agents, scripts, templates) from upstream shipkit into your ship directory. It never touches project-specific files (`captain.md`, `queue.md`, projects, logs). Dry run by default — run `./scripts/pull-upstream.sh --help` for options. Run it periodically (e.g., when starting a new project phase) to check for upstream improvements.
