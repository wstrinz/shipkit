# Module: Subagent Roster (dispatch depth)

**Depth doc for crew dispatch.** Core `mate.md` → "Dispatch Details" carries the
*act* of dispatching (pop a unit of work → prepare orders → dispatch a background
crew → never block → update queue) plus the two types a minimal operator needs:
**`ship-crew`** (a standard background watch) and **`ship-lookout`** (a cheap
read-only check). That inline kernel is enough to dispatch and stay safe. This
module holds the *depth*: the full four-type roster, the dispatch code patterns,
the per-type security model, the watch-orders template, and agent teams. It's a
**plain (non-`@`) reference** — read on demand, and the tick skills backstop-force
it when a watch needs a pilot, a reviewer, or a team.

## The full subagent roster

Ship defines custom subagent types (`~/.claude/agents/ship-*.md`). These provide
**enforced** tool restrictions and baked-in standing orders — no need to include
`crew.md` in every prompt. Choose the type that fits the job:

| Type | When to use | Tools | Enforcement |
|------|-------------|-------|-------------|
| `ship-crew` | Standard watches (research + implementation) | All (with git safety hook) | Hook blocks git commit/push/reset, queue.md writes |
| `ship-pilot` | Browser interaction (screenshots, UI verification, form testing) | All + Chrome MCP tools (with git safety hook) | Same as crew + Chrome tools. **Only dispatch when the Captain explicitly authorizes browser work.** |
| `ship-lookout` | Quick checks, "does X exist?", lightweight read-only analysis | Read-only | disallowedTools: Write, Edit; read-only Bash allow-list |
| `ship-reviewer` | Independent (non-maker) review of crew code or PRs | Read-only + Bash | Hook blocks `gh` approve/comment/merge and all git write ops |

## Dispatch patterns

```
# Standard crew watch (research or implementation)
Task tool:
  subagent_type: "ship-crew"
  run_in_background: true
  model: "<your default crew model — mate.local.md>"
  prompt: |
    WATCH ORDERS: {ticket-id}
    ...

# Browser interaction (Captain must explicitly authorize)
Task tool:
  subagent_type: "ship-pilot"
  run_in_background: true
  prompt: |
    WATCH ORDERS: {ticket-id}
    ... (include Chrome-specific guidance: pages to visit, what to screenshot)

# Quick lookout check (no log needed)
Task tool:
  subagent_type: "ship-lookout"
  run_in_background: true
  prompt: "Check if X exists in the codebase at /path/to/repo"

# Independent reviewer (e.g. the review cycle, or a PR-review agent team)
Task tool:
  subagent_type: "ship-reviewer"
  run_in_background: true
  prompt: "Review the uncommitted diff in /path/to/repo for correctness + standards"
```

## Model selection

Pick the model to the task: a stronger model where wrong paths are expensive (most
code-writing watches), a faster/cheaper one for bounded, well-specified work and for
read-only lookouts/reviewers. Your concrete model roster — the default crew model
and any escalation tier — lives in `mate.local.md`. (Rate/cost-aware modulation of
your appetite and crew cap is the [dispatch-bands](dispatch-bands.md) module.)

## Security model (enforced per subagent by PreToolUse hooks)

- `ship-crew`: git safety — blocks commit, push, add, reset, revert, merge, rebase,
  clean, rm -rf, queue.md writes, and `gh` write ops. Allows checkout, branch,
  status, diff, log, fetch, show, plus dev commands.
- `ship-pilot`: same git safety as crew, plus Chrome MCP tools. Only when the
  Captain authorizes browser work.
- `ship-lookout`: cannot write or edit files; Bash restricted to read-only.
- `ship-reviewer`: cannot write files; hook blocks `gh` approve/comment/merge and
  git write ops.

## Watch orders format

```
---
WATCH ORDERS: {ticket-id}

Ticket: projects/{project}/tickets/{id}.md
Branch: {branch-name}
Previous log: {path or "first watch"}
Goal: {one line}
Focus: {any specific guidance or constraints}
Chrome tools: {no | yes — only if Captain explicitly requested}
---
```

**Include relevant reference docs** in watch orders:

```
## Reference Docs
- {path-to-ship}/docs/knowledge/{relevant}.md
- {path-to-ship}/logs/{project}/{ticket}/ (previous logs)
```

**Chrome tools restriction:** by default, crew should NOT use browser automation
tools. Only enable Chrome tools when the Captain explicitly requests a watch that
requires browser interaction, and say so explicitly in the orders.

## Agent teams (optional)

For coordinated parallel work where multiple agents share a task list or
communicate results — the canonical case is PR review — use agent teams (a
team-creating call + Task dispatches with a shared `team_name`). Standalone Task
dispatches are fine for ordinary parallel watches; teams are for when agents need
to coordinate.
