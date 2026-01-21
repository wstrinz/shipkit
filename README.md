# Shipkit: Bounded-Context Orchestration for Claude Code

A minimal bootstrap package for running multi-agent Claude Code sessions with structured handoffs.

## The Problem

Claude Code sessions have finite context. Long-running work leads to "context rot" - degraded performance as the context fills with stale information. The solution is structured handoffs between fresh agent sessions.

## The Solution

Ship uses a nautical metaphor for role-based orchestration:

- **Captain** (human): Sets priorities, resolves escalations, makes strategic decisions
- **First Mate** (Claude): Coordinates operations, dispatches crew, manages the queue
- **Crew** (Claude agents): Execute bounded work sessions, write logs, terminate cleanly

## Quick Start

### 1. Copy shipkit to your project

```bash
cp -r shipkit/ your-project/ship/
```

### 2. Set up the directory structure

```bash
cd your-project/ship
mkdir -p inbox/escalations inbox/responses
mkdir -p projects/main/tickets
mkdir -p logs/main logs/mate
```

### 3. Configure your captain.md

Edit `captain.md` to set your:
- Current situation and context
- Priorities (Mate uses these to order the queue)
- Constraints on how work should be done
- Standing orders that apply to all work

### 4. Create your first ticket

You can create tickets manually or have the Mate do it:

**Manual:** Copy `templates/ticket.md` to `projects/main/tickets/FIRST-TICKET.md` and fill it in.

**Via Mate (recommended):** Add a note to `inbox/captain.md` describing the work, and tell the Mate to process it. The Mate will triage it and create a properly formatted ticket. This is often faster and ensures consistent formatting.

### 5. Add the ticket to the queue

Edit `queue.md` and add your ticket under "## Ready":
```
1. [FIRST-TICKET](projects/main/tickets/FIRST-TICKET.md) - description | last: 2024-01-15
```

### 6. Start the Mate

Tell Claude: "You're First Mate on this ship. Read ship/mate.md for your standing orders."

The Mate will:
- Read ship state
- Report status to you
- Dispatch crew when you give the go-ahead

### 7. Dispatch crew

Tell the Mate to dispatch on a ticket. They'll prepare watch orders and can launch crew as background agents.

## File Structure

```
ship/
  CLAUDE.md          # Entry point - explains the system
  captain.md         # Your priorities and constraints
  mate.md            # First Mate standing orders
  crew.md            # Crew standing orders
  queue.md           # Work queue (Mate-owned)
  inbox/
    captain.md       # Your inbox for quick thoughts
    escalations/     # Mate's messages to you
    responses/       # Your async responses
  projects/
    {project}/
      tickets/       # Work tickets
  logs/
    {project}/
      {ticket}/      # Watch logs per ticket
    mate/            # Daily mate logs
  templates/
    ticket.md        # Ticket template
```

## Key Concepts

### Logs are the handoff mechanism

When a crew session ends, it writes a log with:
- What was accomplished
- Current state
- Next steps
- Handoff confidence (1-5)

A fresh crew session reads the log and continues from there. No context is assumed to persist between sessions.

### Crew never touch queue.md

The queue is owned by the Mate. Crew only work on their assigned ticket and write logs. This prevents coordination conflicts.

### Bias toward checkpointing

If you'd be sad to lose it, commit it and write a log. Better to checkpoint too often than lose work to context limits.

### The Mate runs the loop

The Mate continuously:
1. Checks inbox
2. Checks active work
3. Dispatches if capacity
4. Stays present for steering

This keeps the ship responsive to your input while work progresses.

## Customization

Shipkit is a starting point. As you use it, you'll likely want to:

- Add project-specific context to role files
- Create additional templates
- Add knowledge docs for your domain
- Evolve the ticket format for your workflow

The system is designed to be adapted to your needs while preserving the core handoff mechanism.

## Troubleshooting

**Crew seems confused**: Check that logs have high handoff confidence. Low-confidence handoffs often indicate missing context.

**Queue gets stale**: Use the `last:` timestamps to spot tickets that haven't moved. Investigate blockers.

**Too much coordination overhead**: You may be over-decomposing work. Larger tickets can reduce dispatch frequency.

**Merge conflicts**: Parallel crew on the same repo can conflict. Consider work decomposition or serializing work.
