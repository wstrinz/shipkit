# Module: Compound (turn finished work into durable, reusable knowledge)

**Optional capability module.** Core `mate.md` ships the *principle* in one paragraph
(housekeeping → "consolidate knowledge from recent learnings"). This module is the
*mechanism* — the gate, the doc format, the dedup procedure, and the seams it
rides — for operators who want the learning loop to close **every watch, by default**
instead of whenever someone remembers. The operative procedure lives in the
`ship-compound` skill; this doc is the meaning behind it.

Adapted from Every's [compound-engineering](https://github.com/EveryInc/compound-engineering-plugin)
`/ce-compound` (MIT). We keep its three good ideas — capture while context is fresh,
dedup before you write, refresh what goes stale — and drop its rigid
`docs/solutions/<category>/` tree, because Ship pairs well with a **semantic-search index**
over the vault (e.g. qmd). Flat `docs/knowledge/` + light tags + semantic retrieval beats a
category forest you have to keep filed.

## Why it's a module, not pure core

The compounding bet is the same one Ship already makes: each unit of work should make the
next one cheaper. The antibody it adds is against **re-derivation debt** — the next watch
(or a fresh session, or a teammate without your context) solving a problem you already
solved because the lesson never left your head or your `/compact`'d transcript.

But *capturing* has a real cost: not every watch produces a durable lesson, and a
knowledge store that captures everything is noise that no one trusts. So core states
the principle; you pick the **capture policy** here, and the **gate** below keeps the
store honest.

## The shape: retrieve → capture → consolidate → refresh

Ship already separates *who writes when* (crew write, Mate commits, Bosun sweeps).
Compound rides that grain instead of fighting it — four phases on existing seams, not
one monolithic command:

| Phase | Who | When (seam) | Writes? |
|---|---|---|---|
| **Retrieve** | Mate (injects), Crew (searches) | Dispatch: the Mate runs your knowledge search for the ticket's problem (e.g. `qmd query "<ticket problem>" -c <knowledge-collection> -n 5`) and pastes the top few hits into the watch orders. Crew search the same scope before non-trivial work. | Nothing — the crew's candidate block then reports whether an existing doc **applied / was missing / was wrong** |
| **Capture** | Crew | End of a crew watch (`crew.md` → "Ending a Watch") | A *candidate* block in the watch log (crew can't commit — by invariant) |
| **Consolidate** | Mate | Wind-down retro + housekeeping (`mate.md` → "Sessions and Logs" wrap-up / "Ship Maintenance & Housekeeping"; the full sweep is `modules/session-ceremony/session-ceremony.md` → "End of session") | The durable `docs/knowledge/` doc, committed in the same sweep; then refresh the index so the next search sees it |
| **Refresh / detect** | Bosun | Per-tick delta sweep (autonomous tier — `modules/autonomous/bosun.md`) | Nothing — read-only; *surfaces* stale or capture-worthy items, Mate acts |

Scope the retrieve search to **knowledge docs only** (e.g. a separate index collection
over `knowledge_dir`). Searched together with logs, the store's hits get crowded out by
the watch logs that produced them.

**Why this split (and not the alternatives):**

- **Retrieve is split across Mate and crew** because the Mate knows the ticket at
  dispatch and the crew knows the problem once it's in the code. It also makes the
  store's use measurable: every candidate block says whether an existing doc applied,
  was missing, or was wrong, which is a free citation signal.
- **Capture must be crew-side** so it happens while context is fresh — the whole CE
  insight. By wind-down the crew's transcript is gone; only the log survives, so the
  fidelity (what was tried, what failed, the root cause) has to be written *at* the
  watch, not reconstructed after.
- **Consolidate must be Mate-side** because crew can't commit and don't hold the
  whole-knowledge-base view needed to dedup. The Mate already runs a reliable retro at
  wind-down that ends in a commit — fold the write there and it lands for free.
- **Refresh is Bosun's** (autonomous tier only) because it's standing maintenance (is any
  old learning now wrong?) — but the Bosun is **read-only**, so it flags and the Mate
  writes. This phase is a future enhancement; the loop is complete with capture +
  consolidate alone, and a core-only (no-Bosun) operator simply skips it.

The standalone invariant holds: a core-only operator with no Bosun still gets the full
loop by running `/ship-compound` by hand at the end of a session.

## The gate (keep the store honest)

Capture a learning **only** when one of these is true:

1. A **non-trivial problem was solved** *and verified working* — not a typo, not an
   obvious fix, not "the test was flaky and passed on rerun."
2. A **reusable insight, decision, or pattern** emerged that a future watch would
   otherwise re-derive — a gotcha, a convention, a "why we did it this way," a
   dead-end worth signposting.

**Do not capture:** routine implementation that went to plan, pure status ("shipped
X"), one-off facts that belong in the ticket, or anything already written down. When
in doubt, a *candidate* is cheap (it's one block in a log the crew is writing anyway);
the Mate is the filter that decides whether it becomes a durable doc.

`bug` vs `knowledge` track (mirrors CE, kept light):

- **bug** — something broke and was fixed. Sections: *Problem · What didn't work ·
  Root cause · Fix · Prevention*.
- **knowledge** — a pattern, convention, or decision worth keeping. Sections:
  *Context · Guidance · Why it matters · When it applies*.

## The candidate block (crew capture)

When a watch trips the gate, the crew appends this to its log — that's the whole
crew-side cost. No new file, no commit, rides the log it already writes:

```
## Learning candidate
- **track:** bug | knowledge
- **scope:** employer | personal   (default employer; see "Scope" below)
- **one-liner:** <the lesson in one sentence>
- **tags:** <comma-separated: modules, tech, error class>
- **what's durable:** <problem + root cause + fix, OR the pattern/decision — be
  concrete; this is the fresh-context detail the Mate can't reconstruct later>
- **prevention/when-it-applies:** <how to avoid recurrence, or when to reach for this>
- **existing-doc:** applied <path> | missing (should have existed) | wrong <path> (what was off) | n/a
```

If a watch trips the gate but the crew is out of headroom, a one-liner under the log's
`## Notes` ("learning candidate: <one-liner>") is an acceptable minimum — the Mate
expands it from the log + diff during consolidate.

## The durable doc (Mate consolidate)

Lives at `docs/knowledge/<slug>.md`. **Flat directory** — no category tree; semantic
search does retrieval. One learning per file. House style is light: a `# Title` that
states the lesson (or the question the doc answers), a provenance line, prose sections.
Add this minimal frontmatter so the index and any future board can filter:

```yaml
---
kind: learning              # learning | runbook | reference | decision
track: bug                  # bug | knowledge — nothing else; topical labels go in tags
scope: employer             # employer | personal — default employer; see "Scope"
tags: [auth, retries]       # modules + tech + error class; freeform
solved: 2026-01-15          # date the lesson was earned
source: logs/app/LOGIN-RETRY/2026-01-15-1000.md   # the watch that earned it
status: active              # active | draft | superseded | stale (not current/solved: those are active)
verified: 2026-09-28 @1a2b3c4   # YYYY-MM-DD @<sha|n/a>; omit if never re-checked
---
```

**`verified:`** is the day you actually re-checked the doc's claims against code or live
state, and `@` the commit you checked them at (the cited repo's sha), or `@n/a` for a
process or live-state doc with no single repo. Free text may follow the sha; only the
leading date needs to be machine-readable. A freshness check is cheap and worth having
(on the autonomous tier it fits the Bosun's heartbeat as one quiet line, not a drop):
list each doc **cited** in a recent log or inbox file (e.g. the last 14 days) whose
`verified:` is missing, unparseable, or old (e.g. over 60 days). The most-cited rows are
the ones to re-verify when you next consolidate in that area.

**Merging docs:** the merged doc keeps redirect stubs (`status: superseded`,
`superseded_by: <path>`) at the old paths so links still resolve, **and each stub is
excluded from the search index** so it can't take a retrieval slot from the doc it
points to. If your index config isn't versioned, keep a way to regenerate the exclusion
list (every `status: superseded` doc).

Keep it light on purpose — Ship's knowledge docs are prose-led, not schema-heavy
(contrast the rich ticket-frontmatter schema, which is canonical *state*; a learning
is not state). `status: superseded` + a link to the replacement is how a learning
dies; don't delete it.

### Scope: whose learning is it?

Every learning carries `scope:`, set at capture. This field records who it belongs to; it
does not say where the doc is stored. Both kinds live in `docs/knowledge/`, inside the
ship's data ([DATA.md](../../DATA.md)).

- **`employer`** (the default) applies to a learning about the employer's systems,
  codebase, customers, incidents or internal process, or one that only makes sense
  alongside them. When unsure, use `employer`.
- **`personal`** applies to a generic lesson about tools, agents or working practice that
  would still hold at a different employer, and that names nothing internal.

`personal` makes a learning *eligible* to leave the ship's data. It doesn't clear it to
leave. Before a `personal` doc is published or copied anywhere outside the data, it goes
through the [scrub gate](scrub-gate.md). Set `personal` deliberately, one doc at a time.
Never re-tag docs in bulk.

## Dedup before you write (the semantic-search step)

This is the step that keeps the store from rotting into near-duplicates. Before
writing a candidate, the Mate runs semantic search and decides (your search command is
in `mate.local.md` — e.g. `qmd query "<one-liner + tags>" -n 5`):

| Overlap | Action |
|---|---|
| **High** — an existing doc covers the same problem + root cause + fix | **Update** it. Fold in the fresher detail, add a `last_updated:` line. Don't create a second doc that immediately drifts. |
| **Moderate** — same area, different angle | **Create** new; cross-link both. |
| **Low / none** | **Create** new. |

After writing or updating, refresh the index so the next dedup query sees it (your
index-refresh command is in `mate.local.md` / `CLAUDE.md`).

## Discoverability (already mostly handled)

CE's `/ce-compound` ends by editing `CLAUDE.md`/`AGENTS.md` so agents know the store
exists. Ship's equivalent is one standing expectation: **before non-trivial work in a
documented area, search `docs/knowledge/` first** (the retrieve phase). `mate.md` lists
the semantic-search tool; if your `crew.md` lacks a search-first line, add it (see
Wiring below) — a store no one searches doesn't compound.

A short **traps preamble** that every seat loads at start (a capped list of the
costliest gotchas, each one line linking to its full doc) complements search: search
finds a doc when you know to ask; the preamble catches the trap you didn't know to
search for. Keep it capped; to add a line, drop or merge one.

## Policy knobs (`mate.local.md`)

```
compound_policy:    off | candidates-only | full-every-winddown   # default: candidates-only
knowledge_dir:      docs/knowledge                                 # where durable docs live
compound_model:     <model for the consolidate pass>               # dedup/judgment wants a strong model
refresh_owner:      mate | bosun | off                             # who runs the stale-learning sweep
share_target:       off | <dir in a shared repo>                   # optional share lane (below); default off
```

- **`off`** — principle only, no candidate blocks, no enforced consolidate. Capture by
  hand with `/ship-compound` when you feel like it.
- **`candidates-only`** (default) — crew emit candidate blocks; the Mate consolidates
  blessed ones at wind-down. The honest middle: cheap on the hot path, durable docs
  only for things that earned it.
- **`full-every-winddown`** — every wind-down runs a full consolidate pass over the
  session's logs whether or not crew flagged candidates (the Mate re-reads for missed
  lessons). Highest assurance, highest token cost.

## Wiring (one line each into the seams)

Compound is inert until it's referenced from the seams. The five pointers:

- **`crew.md` → start of a watch:** "Before non-trivial work in a documented area, search
  `docs/knowledge/` for the problem (and read any docs the orders name)."
- **`crew.md` → "Ending a Watch":** insert a capture step *before* "Say Watch complete"
  — "If this watch tripped the compound gate (`modules/compound/compound.md`), append a
  `## Learning candidate` block to your log."
- **Wind-down ceremony / retro** (`mate.md` → "Sessions and Logs" close step and the
  consolidate-learnings line under "Ship Maintenance & Housekeeping";
  `modules/session-ceremony/session-ceremony.md` → "End of session"): add — "run
  `/ship-compound` over this session's logs before the commit."
- **Dispatch** (`mate.md` / your watch-orders template): run the knowledge search for the
  ticket's problem and paste the top hits into the orders (the retrieve phase).
- **`modules/README.md`** table: register the module (capability / Any / "the
  retrieve→capture→consolidate→refresh learning loop").

Optionally, on the autonomous tier the Bosun's per-tick reap can backstop-force this
module when a watch it's reaping reports a solved non-trivial problem with no candidate
block — a nudge, not a gate.

## Optional: the share lane (publish to a team surface)

Some learnings are about the codebase, environment, or ops your team shares, not about
the ship's own mechanics. With `share_target` set, those are mirrored to a shared repo
your teammates can read:

- **At `/ship-compound` time,** classify each committed learning. Team-relevant → also
  write a **de-shipped copy** to `share_target`: strip Mate/Captain/watch jargon and
  ship-relative links, and never carry credentials, customer identifiers, or internal
  hostnames. Ship-internal learnings stay home.
- **Cadence ~weekly:** diff `knowledge_dir` since the last publish stamp (one ISO date in
  a `state/` file), mirror the new team-relevant entries, push, update the stamp.
- **Push mechanics:** if your Mate's Bash hook blocks pushes, carve out exactly one
  explicit-URL push to the share remote (`git push <url> main`), never a bare
  `git push`, and cover the carve-out with a hook test.
- **Shape the target for graduation:** if a learning may later move into a repo's own
  docs, mirror that repo's docs layout so it can move without a rewrite.

The share lane is outbound only; teammates contributing back is a separate design, not
this lane. It also stays inside the employer: a team repo is the employer's, so the lane
can carry `employer` learnings. Publishing anything beyond the employer is the
[scrub gate](scrub-gate.md)'s job, not this lane's.
