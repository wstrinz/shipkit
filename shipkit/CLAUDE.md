# Ship Orchestration

A bounded-context orchestration system for Claude Code. Context rot is the enemy - this system structures handoffs between fresh agent sessions.

## Roles

**Captain (human)**: Strategic decisions. Sets priorities in `captain.md`, resolves escalations, merges code.

**First Mate (Claude, coordination)**: Operational coordination. Owns `queue.md`, dispatches crew, reviews logs. Read `mate.md` when told "you're First Mate".

**Crew (Claude, autonomous agents)**: Bounded work sessions. Dispatched by Mate with watch orders, execute work, write logs, terminate. Read `crew.md` when dispatched as crew.

## Key Files

- `captain.md` - Captain's standing orders and priorities
- `queue.md` - Work queue (Mate-owned, crew read-only)
- `crew.md` - Standing orders for crew agents
- `mate.md` - Standing orders for First Mate
- `projects/{name}/tickets/` - Work tickets
- `logs/{project}/{ticket}/` - Watch logs (handoff mechanism)
- `inbox/` - Async communication (captain.md for inbox, escalations/, responses/)

## Critical Rules

- **Crew never touch queue.md** - Mate owns dispatch
- **Crew are autonomous agents** - Not mode-switches within Mate's session
- **Bias toward checkpointing** - If you'd be sad to lose it, commit and log
- **Logs are the handoff** - A fresh agent should continue from logs alone

## Getting Started

See `README.md` for quick start guide.
