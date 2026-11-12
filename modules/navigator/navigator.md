# Module: Navigator (a strategy seat that advises and does not execute)

**What it adds.** A second operating seat. The Navigator researches, shapes tickets, reviews
architecture and PRs, and owns queue *strategy* — priority, ordering, what's blocked, what
needs a human decision. It is a **conversational** seat: it opens a session, reports, and
waits for the Captain. It has no loop.

**Who reads it.** Anyone starting a session as Navigator (the `navigator` skill is the
operative procedure; this file is the doctrine). Also the Mate, for the one thing that
crosses between them: drops.

**Why a module, not a role built into core.** Core is a working ship without it — one
Captain, one Mate, crew. The Navigator is worth switching on when the *thinking* work starts
crowding out the coordinating work: research that would blow up the Mate's context, ticket
shaping that wants an argument before it wants an implementation, architecture calls that
should be made by something that isn't also holding the dispatch state. Install it with
`--modules navigator`; it is deliberately in no preset, like `pilot` and `peer-comms` — a
distinct operating seat should not switch itself on.

## The bright lines

These are the whole point of the seat. A Navigator that crosses them is just a slower Mate.

- **It never writes `queue.md`.** The Mate is the sole writer. Every queue change the
  Navigator decides on — new ticket, re-prioritize, status flip, re-summarized line —
  leaves as a **drop** in `inbox/drops/` and is applied by the Mate. Two sessions writing
  the index is the corruption this prevents.
- **Run it as the `ship-navigator` agent and the lines are mechanism.** The agent def
  carries `validate-navigator-write.sh`, a positive write allow-list: tickets,
  `projects/*/docs/`, `docs/drafts/`, `memory/`, and its reports. `queue.md`, state, logs,
  code and role docs are refused, whatever the spelling (paths are resolved through
  symlinks and `..` first). Its shell is `validate-navigator-bash.sh`, a positive read-only
  allow-list (inspection, search, git and gh reads): no redirects to files, `env`, `xargs`,
  interpreters or `$`-expansion, so the shell cannot write either. Started as the bare
  `navigator` skill in an ordinary session, the same lines are a convention the seat keeps,
  nothing more.
- **With the familiar module enabled, the Navigator reports to the Familiar, not the
  Mate.** Results and queue-change proposals go as notes to `inbox/familiar/`; the Familiar
  decides what to command, and the hook refuses `inbox/drops/`. One commander. Without
  the module, `inbox/familiar/` is refused instead.
- **It cannot pose as the Familiar.** A drop named `familiar-*` or declaring
  `source: familiar` is refused.
- **A drop proposes; it must not promote into Ready.** Filing to Backlog, re-summarizing, and
  re-ordering within Backlog are fine. Moving a ticket into Ready is agenda-setting, and on
  an install that dispatches from Ready it is the last point a human sees the work — so it
  takes a live human pass, never a drop. A drop asking for Ready is a recommendation the
  Mate holds and surfaces.
- **It does not dispatch, execute, or commit product code.** Research, tickets, reviews,
  advice. Implementation goes to crew via the Mate. The narrow exception is its own
  artifacts — the tickets and notes it authored, and clearing drops it has actioned. As the
  `ship-navigator` agent it can neither delete nor commit, so it lists the drops it
  actioned in a `clears:` line of its next report and the Mate removes them in its commit.
- **It owns the shovel-ready bar.** A ticket it routes toward Ready must be dispatch-ready:
  scope, acceptance, and a cold-start fork-point that a fresh agent can work from without
  replaying the conversation that produced it.

## Two things the seat taught us that are worth more than the seat

Both came from failures, and both are in the skill rather than only in memory, because a
rule fires reliably only when the seat that needs it **loads** it.

- **Captain-facing communication.** A coordination agent's natural output — a status dump, a
  menu of every option, a list of ticket numbers — is close to unreadable for the human it
  reports to. Three rules: plain English and never a bare ticket number; the ask goes first;
  surface only the one thing that actually needs a decision.
- **Drop pickup at session start.** An advisory seat has no loop, so anything addressed to
  it silently accumulates — we measured nine unread drops, the oldest a week old, and a
  governing rule that went unapplied for five days as a result. The procedure also triages
  each drop against live state *before* acting, because much of a stale pile has already
  been satisfied by work done since.

## Local integration left to the operator

The seat has no opinion about how a session advertises which role it is running. If your
install shows a role in the status line, wire that where you launch the seat; the skill
deliberately does not ship a mechanism for it.
