# Shipkit: governance and durable state for Claude Code multi-agent work

Shipkit is a set of role docs, agent definitions, PreToolUse hooks and small scripts that you
clone into one directory, your **ship**. It runs on top of Claude Code's own multi-agent
features (background subagents, the `Agent` tool, `Monitor`, `/loop`, `SendMessage`,
auto-compaction) and adds what those don't provide:

- **Roles with enforced limits.** Each agent type runs under hooks that decide what it may run
  and write. Crew hooks refuse direct git commits and pushes, PR and issue edits, and edits to
  the queue. The autonomous Mate's hook refuses merge, mark-ready, PR reviews and comments,
  force-push and push to main. [What the hooks don't cover](#what-the-hooks-dont-cover) is
  listed below.
- **State that outlives sessions.** A queue, tickets and watch logs, all plain markdown in the
  ship directory. A fresh session continues from those files, not from a conversation, so work
  survives session ends, compactions, Mate rotations and model changes.
- **A human approval line.** Merging, marking ready, reviews, outside messages and deploys stay
  with you. The role docs say so for every seat. For crew and the autonomous Mate the hooks
  enforce the GitHub part, and they enforce your deploy, prod and chat commands once you add
  them to the Mate's hook.

**What it is not:**

- **Not a runtime or a scheduler.** It runs no service of its own. Dispatch, background
  sessions, monitors and loops are Claude Code's; the kit decides who uses them and what gets
  written down.
- **Not a sandbox.** The hooks stop an agent from crossing a line by accident. They are not
  containment against an agent that is trying to get around them. Run unattended agents
  inside a sandbox as well.
- **Not a UI.** The opt-in `console` module writes one state file for a console you build and
  host elsewhere.

**It is for you if** you run several Claude Code sessions a day across more than one repo,
want work to survive session ends and compactions, and want hard limits on what agents do
while you're away. **Skip it if** one long session per task works for you.

**New here?** The [Glossary](GLOSSARY.md) defines the vocabulary, [`examples/`](examples/)
is a fully worked (synthetic) ship, and [QUICKSTART.md](QUICKSTART.md) covers prerequisites
and troubleshooting.

## The model in 30 seconds

- **Captain**: you. You set priorities in `captain.md`, answer escalations, and own the
  irreversible steps: merge, mark ready, review, comment, deploy.
- **Mate** (First Mate): one Claude Code session that owns `queue.md`, turns your inbox into
  tickets, dispatches workers and reviews what they hand back. It is the only writer of the
  queue, and it (or you) commits the crew's work.
- **Crew**: background subagents. Each does one bounded **watch** on one ticket and ends by
  writing a log.
- **Tickets, logs and the queue are the memory.** Nothing is assumed to persist in a model's
  context.

Three more seats are optional: the **Bosun** (autonomous preset; a read-only heartbeat that
wakes the Mate only when something needs it), the **Navigator** (opt-in; strategy and ticket
shaping, never writes the queue) and the **Familiar** (opt-in; a standing command layer above
the Mate). Most ships need two seats: you and the Mate.
[`modules/familiar/README.md`](modules/familiar/README.md) has a table of which seat solves
which problem.

## Getting started

**The fast way: have Claude set it up for you.** Already in a Claude Code session? Paste
this and it does the rest:

> Clone `https://github.com/wstrinz/shipkit` into a directory named `ship` alongside my other repos — the clone
> IS the ship, don't create a separate ship dir. Then follow the clone's setup skill
> (`.claude/skills/shipkit-setup/SKILL.md`) to set the ship up, asking me its questions as
> you go.

Claude clones, checks prerequisites (it tells you if `jq` is missing), runs the setup
interview (or the three-question `--defaults` fast path), and verifies enforcement is armed.
Then pick up at [step 3](#3-restart-claude-code-then-run-your-first-watch) for your first
watch.

To drive it yourself, or to see what the setup does, here is the same path step by step.

### 1. Clone shipkit: the clone IS your ship

Ship is **per-machine, not per-project**: one directory coordinates work across all your
repos, and crew work in whatever repo a ticket points to. The shipkit clone itself is that
directory. **Don't create a separate "ship dir"**: the hooks live in this repo and the
installed agents point back into it, so a separate dir disarms them, and the installer fails
loudly if you try. One ship per machine is a current limitation: agent defs install globally
(`~/.claude/agents`) with one ship path baked into their hook commands.

```
git clone https://github.com/wstrinz/shipkit ship
cd ship
```

Put it wherever you keep your repos (e.g. `~/dev/ship`). The clone already contains the
working skeleton (`captain.md`, `queue.md`, `inbox/`, `projects/`, `logs/`, the role docs
`core/mate.md` and `core/crew.md`) plus the installer.

**Prerequisites:** `git`, `python3`, `bash`, and **`jq`** (the hooks parse their input with
jq, and the installer hard-fails without it: `brew install jq` / `apt-get install jq` /
`winget install jqlang.jq`). On Windows the hooks run under Git-Bash.

### 2. Run the setup

Open Claude Code in the clone and run:

> `/shipkit-setup`

The setup skill ships in the clone (`.claude/skills/shipkit-setup/`), so it resolves with no
install step first, for first setup, preset changes and upgrades alike. The fresh-machine
default is three questions (one is [where your data lives](#where-your-data-lives)) and one
command, `python3 shipkit_init.py --defaults`, which installs the **`core`** preset. The
setup verifies that enforcement is armed and **fails loudly if it isn't**. Coding agents:
don't hand-copy hooks or agents; run the setup skill, which calls `shipkit_init.py`.

### 3. Restart Claude Code, then run your first watch

Restart the session (Claude Code snapshots agent defs at session start), open it in the ship
dir, and run:

> `/ship-tour`

Lesson 1 takes the Mate role itself and walks one real cycle with you: read ship state, fill
in `captain.md` (the tour interviews you), run one real inbox item through the loop, wind
down. The other lessons (dispatching crew, the review gate, going autonomous, staying
current) are short and self-contained.

Without the tour, the manual boot line is:

> You're First Mate on this ship. Read `core/mate.md` for your standing orders.

### Upgrading an existing install?

Coming from v2, read [`UPGRADING.md`](UPGRADING.md) "v2 → v3" first. Preset changes and
older (pre-v2) installs also go through `/shipkit-setup`: the upgrade judgment is in
[`.claude/skills/shipkit-setup/upgrade.md`](.claude/skills/shipkit-setup/upgrade.md), and
`UPGRADING.md` is the runnable runbook (new machine, preset change, divergence, rollback,
platform assumptions).

## Presets and modules

Everything beyond `core/` is a module: a folder under `modules/` with a `module.json` (its
files, tier and `requires[]`) and a doc. A **preset** in [`presets.json`](presets.json) is a
list of module folders. `shipkit_init.py` installs a preset or an explicit `--modules` set and
resolves `requires[]` transitively. Re-runs are additive: the enabled set is recorded in
`state/install.json`, and a later run adds to it.

| Preset | Modules | What you get |
|---|---|---|
| `core` | `core`, `session-ceremony`, `subagent-roster`, `pull-requests`, `review-cycle`, `compound`, `queue-split` | A request/response Mate that you drive turn by turn; the crew, lookout and reviewer agents with their hooks; the compound learning loop; the queue split. No loop, no Bosun. |
| `autonomous` | everything in `core`, plus `autonomous`, `wake-monitor`, `dispatch-bands`, `sensors`, `night-economy` | The Mate runs as a background `ship-mate` agent woken by events, with its own hooks; the Bosun heartbeat; the Mate lock; watch rotation; the compaction hook pair. |

Start on `core`. Re-run `/shipkit-setup` with `autonomous` once you trust the bright lines;
it installs the delta.

These modules are in **no preset**. Opt in with `python3 shipkit_init.py --modules NAME
--ship-root .` (add `--dry-run` first):

- [`navigator`](modules/navigator/navigator.md): a strategy seat (`ship-navigator`) with allow-list hooks; it never writes `queue.md`.
- [`familiar`](modules/familiar/familiar.md): a standing command seat above the Mate (`ship-familiar`); pulls in `autonomous` and `wake-monitor`. Most ships don't need it: read [its README](modules/familiar/README.md) first.
- [`console`](modules/console/console.md): `state/console.json` and its only writer, `console_state.py`; every value carries `resolved_by`, and the console itself lives in its own repo.
- [`pilot`](modules/pilot/pilot.md): `ship-pilot`, crew plus the `claude-in-chrome` MCP tools, for browser watches you authorize.
- [`peer-comms`](modules/peer-comms/peer-comms.md): envelope spec and validator for durable drops between two ships; live talk uses native `SendMessage`.
- [`deploy`](modules/deploy/deploy.md): `validate-prod-guard.sh`, which asks before any `aws` command and mutating `sam` commands; wired to no agent, so you register it yourself.
- [`substrate-integrity`](modules/substrate-integrity/substrate-integrity.md): tamper detection for the kit's own hooks and defs; installing it arms nothing (see its "Known gaps").

[`modules/README.md`](modules/README.md) is the per-module catalog, maps where every file
lives, and explains how to add a module (modules are the only extension surface, including
for new agent types).

## Core concepts

### The queue and tickets

`queue.md` is the index of work, in sections: Ready, Active, In Review, Awaiting Captain,
Blocked, Backlog, Done. **Awaiting Captain** means the ship's part is done and you have a
concrete next action, and each entry states that action. Only the Mate writes the queue.

A ticket (`projects/{area}/tickets/{id}.md`) is the durable record for one unit of work: the
goal, acceptance criteria, the current state, what it's blocked on, and a watch history
linking every log. The queue line says whether and when to act; the ticket says how.

The `queue-split` module (in both presets) keeps `queue.md` short: parked Ready, Backlog,
Shelved and older Done entries move intact to `queue-archive.md`, which is not read at boot
([`modules/queue-split/queue-split.md`](modules/queue-split/queue-split.md)).

### Logs are the handoff

When a watch ends, the crew writes a log: what was done, where things stand, next steps, and
a handoff confidence (1-5). The next session reads the log and the ticket and continues. No
context persists between sessions; the files are the memory.

### Inbox and drops

You write to `inbox/captain.md`. Processes and other seats (the Bosun, Navigator, Familiar,
your own automation) write **drops** into `inbox/drops/`. The Mate triages both into tickets,
quick tasks or questions for you. Seats other than the Mate change the queue only by drop.

### One Mate holds the deck

The queue has one writer, so there is one Mate. In `core` that is by convention: you start
one Mate session. In `autonomous`, `/ship-watch-start` takes a lock (`state/mate-lock.json`)
that refuses a second Mate while it's fresh, and handing over to a new Mate is a rotation
(`/ship-watch-rotate`). Details:
[`modules/autonomous/mate-event-driven.md`](modules/autonomous/mate-event-driven.md).

### Hooks are the enforcement layer

The role docs say what each seat may do; the hooks make some of those lines mechanical. Each
agent def names its PreToolUse hooks in its frontmatter, and the installer substitutes the
ship path into them.

| Agent | Purpose | Writes | Enforcement |
|---|---|---|---|
| `ship-crew` | Standard watches (research and implementation) | Yes | Bash allow-list: no direct git writes, recursive rm, PR or issue edits, or mutating HTTP. Write/Edit guard on `queue.md`, `queue-archive.md`, `captain.md` and `inbox/`. |
| `ship-lookout` | Quick read-only checks | No | `disallowedTools` plus the read-only Bash hook |
| `ship-reviewer` (`review-cycle`) | Independent (non-maker) review | No | Read-only Bash hook |
| `ship-pilot` (`pilot`, opt-in) | Browser work you authorize | Yes, plus Chrome MCP | Crew's Bash hook and Write/Edit guard |
| `ship-mate` (`autonomous`) | The Mate as a background agent | Yes, broadly | Bash deny-list: `gh pr` merge, ready, review, comment, approve, close and edit; non-draft `gh pr create`; gh issue, repo and release writes; mutating `gh api`; force-push; push to main; and the generic infra verbs `serverless deploy`, `terraform apply/destroy`, mutating `kubectl`, `helm install/upgrade/uninstall`. MCP hook: write-named tools blocked by default. |
| `ship-bosun` (`autonomous`) | The heartbeat | Only through `bosun_emit.py` | No Write/Edit/Task; Bash allow-list |
| `ship-navigator` (`navigator`, opt-in) | Strategy seat | Its own lanes only | Positive allow-lists for writes and shell |
| `ship-familiar` (`familiar`, opt-in) | Command layer above the Mate | Its own lanes only | Positive allow-lists for writes and shell |

#### What the hooks don't cover

- **Scripts.** The crew allow-list admits interpreters and build wrappers (`python`, `ruby`,
  `node`, `bash`/`sh`, `make`, `npm run`, `npx`, `devbox`, `bundle exec`). The hook sees the
  command line, not what a script does, so "crew can't commit or push" holds for direct
  commands only.
- **Your deploy, prod-write and chat commands.** Beyond the generic infra verbs above, the
  Mate's Bash hook blocks nothing until you add patterns to `mate_check_deployment()` in
  `modules/autonomous/hooks/validate-mate-bash.sh` (the "PER-DEPLOYMENT OVERRIDE" section,
  which ships empty with commented examples). That file is synced from upstream with no local
  seam yet, so `pull-upstream.sh --apply` overwrites your patterns: keep a copy and re-apply
  them. The `deploy` module's guard is wired to no agent.
- **MCP writes, by name only.** `validate-mate-mcp.sh` treats an MCP call as a write when the
  tool name contains a write verb (`post`, `send`, `create`, `update`, `delete`, `comment`,
  `transition` and others). Anything that doesn't match counts as a read and passes. Writes
  are blocked by default; `SHIP_MATE_MCP_WRITE_BLOCK=0` switches to audit-and-allow (logged
  to `state/mate-mcp-writes.jsonl`). There is no confirm step.
- **The `core` Mate.** In the `core` preset the Mate is an ordinary Claude Code session, not
  a hooked agent. Its bright lines there are its standing orders (`core/mate.md` → "Autonomy
  & Bright Lines") plus your own permission prompts.

The installer fails loudly if a rendered hook path or interpreter doesn't resolve, and the
`jq`-parsing hooks fail closed without `jq`. The reasons are in [`DECISIONS.md`](DECISIONS.md).

### Running autonomous

The **Bosun** runs its own `/loop` and drops a note for the Mate only when something needs
Mate action. The **Mate** boots once via `/ship-watch-start`, then idles and wakes on events
(your inbox, Bosun drops, crew completions). Bring both up with
`modules/autonomous/scripts/ship-up.sh`; the doctrine is in
[`mate-event-driven.md`](modules/autonomous/mate-event-driven.md) and
[`bosun-loop.md`](modules/autonomous/bosun-loop.md). Run these agents in a sandbox as well
(on macOS, [agent-safehouse.dev](https://agent-safehouse.dev/) is one option).

### Compaction (autonomous)

The `ship-mate` def wires `modules/autonomous/hooks/compact-handoff.sh` (logic in
`scripts/compact_handoff.py`) on `PreCompact`, to write `state/precompact-handoff.md`, and on
`SessionStart` matcher `compact`, to tell the resumed Mate to re-anchor on the ship files. It
acts only when the payload's `agent_type` is `ship-mate`. **It has not yet been observed
firing in a live `claude --bg --agent ship-mate` session:** after your first compaction,
check that `state/precompact-handoff.md` was written.

## Where your data lives

A ship directory holds two things: the **kit** (generic, public, updated from upstream) and
your **data** (`captain.md`, `queue.md`, `queue-archive.md`, `inbox/`, `projects/`, `logs/`,
`state/`, `docs/`, `DECISIONS.local.md`). By default both live in the clone, whose `origin`
is the public kit, so never push your data there.

You can keep the data in its own repo instead, with `shipkit_init.py --data-root PATH` (for
example a nested private repo `ship-data/`, which the kit's `.gitignore` already ignores).
[`DATA.md`](DATA.md) covers how that works, daily use, known limits, whose data a work ship
holds, and whether to track `mate.local.md` and `DECISIONS.local.md`.

## Customization

Keep your changes in the seams, so upstream syncs don't revert them:

- Preferences, house notes and dated decisions go in `mate.local.md`, never in `core/mate.md`
  ([DATA.md](DATA.md#your-overlay-and-decisions-log) on tracking it).
- Extra crew commands go in `core/hooks/crew-allow-local.sh`: copy
  `core/templates/crew-allow-local.sh` there. The crew hook sources it if present, and
  `pull-upstream.sh` never touches it.
- Your own knowledge docs go in `docs/knowledge/`.
- A new capability, including a new agent type, is a new module
  ([modules/README.md](modules/README.md) → "Adding a module").

## Staying up to date

`scripts/pull-upstream.sh` syncs framework files (role docs, agents, hooks, scripts,
templates) from upstream shipkit into your ship directory. It never touches your ship's data
(the entries listed above, or a separate data root), and aborts before copying anything if an
upstream path would land there. It is a dry run by default; `--apply` copies. Run
`./scripts/pull-upstream.sh --help` for options. It copies new and changed files but does not
delete files upstream removed; [`UPGRADING.md`](UPGRADING.md) "v2 → v3" lists the ones v3
removed. Why the kit is shaped the way it is: [`DECISIONS.md`](DECISIONS.md).
