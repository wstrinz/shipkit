# Ship Orchestration

A bounded-context orchestration system for Claude Code. Context rot is the enemy - this system structures handoffs between fresh agent sessions.

## Roles

**Captain (human)**: Strategic decisions. Sets priorities in `captain.md`, resolves escalations, merges code.

**First Mate (Claude, coordination)**: Operational coordination. Owns `queue.md`, dispatches crew, reviews logs. Read `core/mate.md` when told "you're First Mate".

**Crew (Claude, autonomous subagents)**: Bounded work sessions. Dispatched by Mate as custom subagents, execute work, write logs, terminate.

## Subagent Types

Crew are dispatched as custom subagents (`~/.claude/agents/ship-*.md`) with enforced tool restrictions:

| Type | Purpose | Write access | Safety |
|------|---------|-------------|--------|
| `ship-crew` | Standard watches (research + implementation) | Yes | Allow-list hook blocks git writes, rm -rf, gh writes; Write/Edit path guard on ship state (queue.md, captain.md, inbox/) |
| `ship-lookout` | Quick read-only checks | No (enforced) | disallowedTools + allow-list hook for Bash |

Standing orders are baked into each subagent's system prompt. See `core/mate.md` for dispatch patterns.

## Key Files

- `captain.md` - Captain's standing orders and priorities
- `queue.md` - Work queue (Mate-owned, crew read-only)
- `core/crew.md` - Standing orders for crew agents (also baked into ship-crew subagent)
- `core/mate.md` - Standing orders for First Mate (request/response base; `modules/autonomous/mate-event-driven.md` is the autonomous overlay)
- `presets.json` + each `module.json` - the tiered install manifest (`shipkit_init.py` reads them); modules are the single extension surface (see `modules/README.md`)
- `DECISIONS.md` - the framework's design decisions + the failures behind them (doctrine states rules once; the why lives here). This ship's own dated incidents/rulings go in `DECISIONS.local.md` (gitignored; seed from the example)
- `projects/{name}/tickets/` - Work tickets
- `logs/{project}/{ticket}/` - Watch logs (handoff mechanism)
- `inbox/` - Incoming items (captain.md for inbox, drops/ for external processes)
- `DATA.md` - where the ship's data lives. If `logs/`, `state/` and the other data dirs are symlinks, the ship has a separate data root: `captain.md`, `queue.md`, `queue-archive.md` and `DECISIONS.local.md` live at its top (e.g. `ship-data/queue.md`), and the root copies are pointer stubs, so read and edit the data-root paths. Commit data in the data repo. If a search from the ship root finds no data, search by explicit path (`rg x logs/`) or with `rg -L`
- `core/hooks/` + `modules/autonomous/hooks/` - Hook scripts for subagent enforcement (tiered)

## Critical Rules

- **Crew never touch queue.md** - Mate owns dispatch, enforced by hook
- **Crew are autonomous agents** - Not mode-switches within Mate's session
- **Crew can't commit/push** - Enforced by PreToolUse hook on ship-crew
- **Bias toward checkpointing** - If you'd be sad to lose it, commit and log
- **Logs are the handoff** - A fresh agent should continue from logs alone

## Getting Started

See `README.md` for bootstrap instructions.
