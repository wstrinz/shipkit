# Console: `state/console.json`

One machine-readable file that a console, dashboard or status page reads. **The console
computes nothing.** Every verdict, count and age is decided by the generator,
`modules/console/console_state.py`, which is the file's only writer. A render that works out a
verdict for itself is a bug in the render; that logic belongs in the generator.

The console itself is not part of the kit. Build it in its own repo and have it read only this
file, through a static server or a server that runs the generator on request. Its contract is
`console.schema.json` plus this doc.

## Run it

```bash
python3 modules/console/console_state.py                  # write state/console.json (atomic, 0644)
python3 modules/console/console_state.py --stdout         # print it instead
python3 modules/console/console_state.py --validate FILE  # check a file against the schema
```

Anything can run it: the Mate after a status write, a cron or launchd job, a `Monitor` loop,
or the console's server on each request (`--stdout`). It is cheap: pure file reads, with no
subprocesses and no network. It reads only regular files, never a FIFO or a device. It reads at
most 4 MB from any file, and only the last 64 KB of the Bosun heartbeat log. It writes nothing
except `state/console.json`. It refuses to write a document that fails its own schema, and it
refuses, with exit 2 and a message, when `state/` is missing or is a dangling data-root link.
It never creates `state/`.

`SHIP_ROOT` overrides the ship root. Root data files (`queue.md`) resolve through
`lib/ship_data.data_root()`, so a ship with a data root ([DATA.md](../../DATA.md)) works
unchanged.

**Serving it.** Paths inside the document are ship-relative or `<data-root>/…`, never absolute.
But some values are **file content passed through verbatim**: `seats.bosun.last_note`,
`queue.awaiting_captain`, `crew.active[].task`, the `status` strings and the drop `ledger`
fields. Every such string is capped at 300 characters, and any non-string is flattened to JSON
text, but nothing is redacted. Only serve the file to people who may read the queue and the
inbox, and escape every value when you render it.

## The claim

Every leaf a console shows is a claim:

```json
{"value": 3, "confidence": "derived", "resolved_by": "inbox/drops/*.md|*.json at top level …",
 "observed_at": "2026-11-12T19:58:00Z"}
```

- **`resolved_by`** is never empty. It names the file and field, or the rule, that the value
  came from. `claim()` raises without it, so a claim with no provenance can't reach disk.
- **`confidence`** is one of three values:
  - `observed`: read straight from a source.
  - `derived`: counted or computed from sources.
  - `unknown`: the source is absent, unreadable, unparseable or self-contradictory.

  An `unknown` claim carries the reason in `resolved_by` and usually a `null` value.
- **`observed_at`** is the source's own time (its stamp or its mtime), not the generation time.

Seats also carry a **verdict**, `{value, by}`. The value is one of:
- `fresh`: the heartbeat is inside the threshold;
- `stale`: it is past the threshold;
- `absent`: `state/` exists but holds no lock or log;
- `unknown`: `state/` itself is missing or a dangling link, the source is unreadable or empty,
  the stamp won't parse, or the stamp is in the future.

Each verdict uses its consumer's rule, so the console and the launcher can't disagree:
- **Mate:** follows `mate-lock.py`. The stamp is `heartbeat_at`, falling back to `acquired_at`.
  The seat is fresh while `age <= STALE_MINUTES × 60`.
- **Bosun:** follows `launch-bosun.sh`. The age is the heartbeat log's mtime, and the seat is
  fresh while `age <` the threshold.

  The last line's stamp is still reported as `last_beat_at`. Unlike the launcher, an empty log
  is `unknown`, not fresh, because no beat was recorded.

**`fresh` is a heartbeat claim, not a liveness proof.** A wedged seat can hold a fresh lock,
and a busy one can miss a beat. Nothing here claims a seat is alive or dead.

## Staleness and paint rules (for every reader)

1. **Document.** If `now − generated_at > stale_after_s` (default 600, set with `--stale-after` or
   `CONSOLE_STALE_AFTER`), if `generated_at` won't parse, or if `schema` isn't
   `shipkit-console/1`, render the whole document as unknown and show its age.
2. **Verdicts are true as of `generated_at`.** Show ages from `observed_at`, not from when the
   page loaded.
3. **Unknown never paints green.** Only a `fresh` verdict in a non-stale document may.
   `unknown`, `absent` and `stale` never may, and neither may a `null` count. A zero is a
   finding, but a `null` is not a zero.

## Sections

| Section | Claims | Source |
|---|---|---|
| `install` | `modules`, `preset` (`null` = a custom module set; key missing = `unknown`) | `state/install.json` |
| `seats.mate` | `lock_holder`, `acquired_at`, `heartbeat_at`, `heartbeat_age_s`, `stale_after_s` | `state/mate-lock.json`. Threshold `STALE_MINUTES` (45), the variable `mate-lock.py` reads |
| `seats.bosun` | `last_beat_at`, `last_note`, `heartbeat_age_s`, `stale_after_s`, `last_sweep_at` | `state/bosun-heartbeat.log` (mtime and last line), `state/bosun-last-sweep.json`. Threshold = max(`BOSUN_STALE_SECS` (2700), 2 × `pace_secs`), as `launch-bosun.sh` |
| `status` | `doing`, `since`, `tick`, `wake_reason`, `next_wake`, `validator`, `written_at` | `state/status.json` core fields ([lib/status.schema.md](../../lib/status.schema.md)) |
| `crew` | `active` (first 20 of `{name, ticket, task, dispatched}`), `count` | `status.json` `crew[]`. A headless loop never writes it, so it is `unknown`, not zero, and `queue.counts.Active` gives the queue's view |
| `queue` | `counts` (`{section: entries}`), `awaiting_captain` (first line of each, first 20) | `queue.md` at the data root: column-0 list entries per `## ` section, skipping HTML comments and fenced blocks |
| `tickets` | `total`, `by_status` | `projects/*/tickets/*.md`: the first word of frontmatter `status:`, else of the `**Status:**` line, else `unset` |
| `mail` | `boxes` (`{box: {unread, newest, oldest_unread_at}}`), `captain_inbox_lines` | `inbox/<box>/*.md` at top level for every box except `drops/` and `processed/`. A box's `read/` subdir is read mail |
| `drops` | `pending`, `oldest_pending_at`, `ledger` (newest first, 50, `{name, at, source, wake_class, authority}`), `processed` | `inbox/drops/*.md\|*.json` at top level; `inbox/drops/processed/` |

`sources[]` lists every input the generator tried, files and directories alike (`inbox/`,
`inbox/drops/`, `inbox/drops/processed/`, `projects/`, each mailbox). Each one is `read`,
`absent` or `unreadable`, with `modified_at` and `age_s`.

A missing or unreadable source shows up in that list, and its claims become `unknown` with a
`null` value. It is never skipped silently, and it never turns into a zero. A missing
`projects/` gives `tickets.total: null`, not `0`; an empty `projects/` gives `0`. An unreadable
`projects/*/tickets/` makes both ticket claims `unknown`. An unreadable mailbox shows
`unread: null`. A stamp that can't be placed in UTC (an extreme offset) counts as unparseable.

## Extending it

A module adds a top-level section, or a seat under `seats`, by wrapping `build()` and adding
`{"claims": {…}}` (a seat adds a `verdict` too). The schema accepts any extra top-level key
that is a claims section, so extensions validate without editing `console.schema.json`. The
rules don't change: every claim gets `resolved_by`, and an unknown stays unknown. Cap any list
you add.

**Deliberately absent:** cost/rate/fuel, on-call, PR overlays and harness-internal liveness
signals (session transcripts, daemon logs). Those are per-installation, and they belong in
the module that owns the data, not in the kit's generator.
