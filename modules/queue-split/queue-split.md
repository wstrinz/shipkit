# Queue split: a lean live queue plus an archive

**Who reads this:** the Mate (the only writer of both files). **Tier 1**, in every preset. Core
works without it: with no archive file, every section stays in `queue.md` and both scripts below
treat the live file as the whole queue.

## Why

`queue.md` is read at every boot and every re-anchor. Left alone it fills with work nobody will
touch this week (Backlog), finished work (Done) and parked ideas, until the boot read is mostly
noise and the Mate starts skimming the part that matters. The split keeps the live file to what is
actionable *now* and moves the rest, intact, to `queue-archive.md`. Nothing is deleted: the
archive is where older entries go instead of being thinned away.

## The two files

| File | Sections | Read |
|---|---|---|
| `queue.md` (live) | Ready · Active · In Review · Awaiting Captain · Blocked · Done (recent) | At every boot and re-anchor |
| `queue-archive.md` | Ready (parked) · Backlog · Shelved · Done | **Not at boot.** On demand only |

Read the archive when you need it: promoting from Backlog, checking for a duplicate before
filing a ticket, looking up a shelved answer, answering "did we ever do X". A fresh archive is
seeded from [templates/queue-archive.md](templates/queue-archive.md).

**Ownership is the same as the live queue.** The Mate is the sole writer. The crew, readonly and
Bosun Bash hooks block any command naming `queue-archive.md`, and the crew Write/Edit guard blocks
it at the ship root. Others request changes by drop, as for `queue.md`.

**Moving an entry does not change its status.** Ready (parked) = `ready`, Backlog = `backlog`,
Shelved = `shelved`, Done = `done`. If you run a tool that syncs ticket status from queue
sections (a `validator_cmd`, a frontmatter sync), **teach it the archive sections in the same
change**. A sync loop that skips unrecognised headings will silently leave every archived
ticket on its old status, and nothing will tell you.

## The tools

Both are stdlib Python, dry-run first, Mate-only. Paths default to `queue.md` /
`queue-archive.md` under `$SHIP_ROOT` (else this kit's root); `--queue` / `--archive` override.

**`queue_split.py`** moves, from the live file into the archive:
- `## Backlog` and `## Shelved`, wholesale (heading notes included);
- `## Done*` entries older than the done-days threshold;
- `## Ready` entries named with `--park-ready ID,ID`, into `## Ready (parked)`.

```
python3 modules/queue-split/queue_split.py                  # dry run: per-section table + every move
python3 modules/queue-split/queue_split.py --apply          # write archive, then queue
python3 modules/queue-split/queue_split.py --park-ready ID1,ID2 --apply
```

It never rewrites entry text. Before writing it proves the non-blank lines of both files are the
same multiset before and after (a lost or duplicated line refuses), writes the archive before
the queue, re-reads both and restores the originals if the check fails. Read the dry run: it
flags **undated** Done entries (they move) and entries carrying a column-0 non-list line, which
is usually a group header that will travel with the entry above it.

**When:** at the wrap-up sweep, when Done (recent) or a Backlog section has grown past a screen.
Re-running is a no-op.

**`queue_move.py`** moves one entry between sections, across files if needed:

```
python3 modules/queue-split/queue_move.py --ticket ID --from "Awaiting Captain" --to Done --note "merged YYYY-MM-DD"
python3 modules/queue-split/queue_move.py --ticket ID --from Backlog --to Ready
```

Sections resolve in the live file first, then the archive. After a split, Ready (parked), Backlog
and Shelved exist only in the archive, so a move there crosses files. `--to Done` lands in the
live Done (recent); only `queue_split.py` ages Done entries into the archive. A move *from* Done
finds the entry in either file. It refuses unless `--ticket` matches exactly one entry in
`--from`. Both tools agree on what an entry is and ignore headings and entries inside HTML
comment blocks.

## Append, don't insert

New and moved entries go at the **end** of their section; `queue_move.py` does this by default
(`--at top` overrides). Done is the exception: it is newest-first, so Done moves land on top.

Position is priority. Inserting at the head of a section re-ranks everything below it, and any
tool that ties a ticket's recorded priority to its queue position (a validator, a sync) then
reports a mismatch on every one of them. If an entry's urgency doesn't match where it landed,
**say so in the entry text**, or renumber deliberately as its own edit.

## Shelved: answered, deliberately not built

Shelved is for work whose **answer is finished** and whose decision is **not to build it now**.
It fills a real gap. Backlog means *not started*, which is wrong because the research is done.
Done means *shipped*, which is wrong because nothing shipped. Blocked means waiting on someone,
and nobody is. Filed anywhere else, a finished design reads as unstarted, and the most
expensive part of it, the finished research, is lost.

**An entry needs ALL THREE. Two out of three is not a shelving.**

1. **The answer is complete and says so.** Design finished, options priced, recommendation
   stated. A reader can act on it without redoing the work.
2. **A named resurrection trigger.** Not "someday": *what specifically has to become true* for
   this to be worth building. A park without a trigger is a deletion with extra steps, so it
   goes to Backlog instead.
3. **The answer lives in your knowledge dir** (`knowledge_dir` in `mate.local.md`, e.g.
   `docs/knowledge/`) and can be found by someone who isn't looking for it. Title the doc as
   *the question someone will ask*, with the trigger in the text. This is the one that fails in
   practice: an answer parked inside a ticket's history, or in a queue section nobody reads, is
   invisible. **The shelving is not complete until that doc exists.**

**Mechanics:** stamp the entry `| shelved: YYYY-MM-DD` and link the knowledge doc from it; the
ticket's status becomes `shelved`. When the trigger fires, move it back
(`queue_move.py --from Shelved --to Ready`) and point the new watch at the doc.

**Shelving is internal.** It never closes a PR or an external tracker ticket; that is an outward
action and the Captain's. Reference them from the shelved entry and leave them open.

## Ready (parked)

Ready work that is deliberately *not next* (waiting on a quiet week, a teammate, a sequence).
It keeps status `ready`, so promoting it back is a move, not a re-triage.

## Dating Done entries

Age comes from the newest `| key: YYYY-MM-DD` stamp on the entry (`| done: …`, `| last: …`).
Without one, the newest `MM-DD` on the first line is used, read as this year unless that would
put it more than a day in the future. An entry with neither is **undated and moves**. Stamp Done
entries with a full date and the threshold does what you expect.

**Known limits:** a `## ` line or a list item inside a fenced code block is not recognised as
such. An HTML comment counts only when `<!--` starts the line. The tools differ on unindented
lines under an entry: `queue_split.py` keeps them with the entry above (and flags them), while
`queue_move.py` moves only the indented continuation lines, so indent continuations.

## Tunables

| Value | Where | Default |
|---|---|---|
| Done age threshold (days) | `queue_done_days` in `mate.local.md`; pass it as `--done-days`, or export `SHIP_QUEUE_DONE_DAYS` | 14 |
| Ship root | `$SHIP_ROOT` | the kit root |

The section set itself (what lives in the archive) is the contract above, not a tunable.
