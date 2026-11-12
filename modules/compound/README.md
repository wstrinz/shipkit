# compound

Turn finished work into durable, reusable learnings, so the next session doesn't
re-solve a problem you already solved.

The doctrine is [compound.md](compound.md); the procedure is the
[`ship-compound` skill](skills/ship-compound/SKILL.md). This page is the overview.

## What you need

compound was built as a module of Ship, a multi-session orchestration kit for Claude
Code. Some of it depends on Ship and some doesn't:

| Piece | Needs Ship? |
|---|---|
| **Capture one learning on the spot** (`/ship-compound "<one-liner>"`) | No. Any repo with a `docs/knowledge/` directory. |
| **Consolidate at a wind-down** (`/ship-compound`) | Mostly. It harvests `## Learning candidate` blocks from Ship's watch logs (`logs/mate/<date>.md`, `logs/<project>/<ticket>/*.md`), which Ship's crew agents write at the end of each task. Without those logs there's nothing to harvest, unless you write the same blocks into your own session notes. |
| **Retrieve** (search the store at the start of a task) and **refresh** (flag stale docs) | Mostly. Both are wired into Ship's roles (the dispatcher and crew search first; a background lookout agent flags stale docs). Outside Ship, retrieve is a habit you add to your own agent instructions: search `docs/knowledge/` before non-trivial work. |
| **Dedup before writing** | No, but it works best with semantic search. It uses [qmd](https://github.com/tobi/qmd) if you have it, and otherwise falls back to keyword search over `docs/knowledge/`, which catches fewer duplicates. |

## Install and run

**With shipkit:** compound is in both presets, so a normal setup installs it
(`/shipkit-setup`, or `python3 shipkit_init.py --defaults`; see the
[top-level README](../../README.md)). The skill lands in `~/.claude/skills/ship-compound/`.

**Without shipkit:** copy `skills/ship-compound/` into `~/.claude/skills/` (or a
project's `.claude/skills/`). Put `compound.md` at `modules/compound/compound.md` in the
repo you run from, or change that path in the skill: the skill reads it for the gate and
the doc format. Without Ship's config files the skill uses its defaults
(`docs/knowledge/`, candidates-only).

Two invocations:

- `/ship-compound` at the end of a session or a wind-down: gather the session's
  learning candidates, gate them, dedup, and write or update the docs.
- `/ship-compound "<one-liner>"`: capture a single learning from the current context now.

## What it writes

**One learning per file**, flat in `docs/knowledge/<slug>.md`, with light frontmatter
(`kind`, `track`, `scope`, `tags`, `solved`, `source`, `status`, optional `verified`).
The title states the lesson or the question the doc answers, so the title line is the
TL;DR. The body follows one of two tracks:

- **bug:** Problem · What didn't work · Root cause · Fix · Prevention
- **knowledge:** Context · Guidance · Why it matters · When it applies

`scope` is `employer` (the default) or `personal`. It records whose lesson it is, which
matters if you use a ship at work. A `personal` doc may be published outside the ship
only after the [scrub gate](scrub-gate.md).

An existing doc that covers the same ground gets updated instead of duplicated. A
replaced doc is marked `status: superseded` and points at its replacement; nothing is
deleted.

**The gate.** Capture a learning only when:

1. a non-trivial problem was solved **and verified working**, or
2. a reusable insight, decision, or pattern emerged that the next session would
   otherwise re-derive (a gotcha, a convention, a "why we did it this way", a dead end
   worth signposting).

Don't capture routine work that went to plan, pure status ("shipped X"), one-off facts
that belong in a ticket, or anything already written down. A store that captures
everything is noise nobody trusts.

## Alternatives

For a standalone, maintained compounder, see Every's
[compound-engineering plugin](https://github.com/EveryInc/compound-engineering-plugin).
