# Where your data lives

A ship directory holds two different things:

- **The kit**: role docs, agent defs, hooks, scripts and modules. Generic and public, and
  updated from upstream.
- **Your ship's data**: what running the ship produces. It's specific to you and your work,
  and it's often confidential.

By default both live in the one clone. You can keep the data in a separate **data root**
instead, so it gets its own repo, its own remote and its own access rules.

## What counts as data

| Entry | What it holds |
|---|---|
| `captain.md` | your standing orders and priorities |
| `queue.md`, `queue-archive.md` | the work queue and its archive |
| `inbox/` | your inbox and drops from other processes |
| `projects/` | tickets |
| `logs/` | watch logs and daily Mate logs |
| `state/` | reconciled state and per-machine runtime files (the runtime files are gitignored) |
| `docs/` | knowledge docs (`docs/knowledge/`, the compound store) and anything else you write |
| `DECISIONS.local.md` | this ship's own incidents and rulings |

The authoritative lists are `DATA_FILES` and `DATA_DIRS` in `scripts/_sync_manifest.py`. Two
files stay in the
kit dir (both gitignored there) because they aren't data: `mate.local.md` is your working
style, and `loop.config.json` is this machine's config.

## Three places it can live

1. **In the ship dir** (the default, and how every ship before v3 works). This is fine for a
   personal ship that you never push. The clone's `origin` is the public kit, so never push
   your data there.
2. **A nested private repo, `ship-data/`.** This is the recommended layout for work. The kit's
   `.gitignore` ignores `ship-data/`, and it's a git repo of its own with a private remote.
   For work data, use a remote your employer owns (more on this below).
3. **A path elsewhere**, such as an existing data repo or a directory on an encrypted volume:
   `--data-root /abs/path`.

## How it works

`shipkit_init.py --data-root PATH` moves the data into `PATH`, treating directories and files
differently:

- **Directories** (`inbox/`, `logs/`, `projects/`, `state/`, `docs/`) are moved and a
  **symlink** is left at the old path. Every doc, hook and script that writes `logs/...` or
  `state/...` keeps working unchanged, and so do Claude Code's Edit and Write.
- **Root files** (`captain.md`, `queue.md`, `queue-archive.md`, `DECISIONS.local.md`) move to
  the top of the data root (`ship-data/queue.md`). The old path keeps a short **pointer stub**
  that names the new location, never a symlink, because a file symlink breaks writers.
  Claude Code's Edit and Write refuse to write through one. Atomic-save writers (`sed -i`,
  most editors, a script that writes a temp file and renames it) silently replace the symlink
  with a regular file, which splits the data in two.

So with a data root, **read and edit the root files at their data-root paths**. Kit scripts find
them with `lib/ship_data.py`, which takes the data root to be wherever the `state/` link
points. The crew write guard protects both paths. An agent that follows a doc to `queue.md`
finds the stub, and the stub tells it where to go.

The installer refuses, and moves nothing, if an entry already exists in both places. The one
exception is a fresh clone's placeholders (the kit's template `queue.md`, `captain.md`,
`inbox/captain.md` and `.gitkeep` files). They give way to an existing data root, but only
when they're byte-identical to what the kit ships. An edited or committed real queue always
conflicts. Comparisons go by file identity, so case variants (`LOGS/x` on macOS) can't slip
through. If a move fails part-way, the error lists what was done, and re-running the same
command resumes.

`scripts/pull-upstream.sh` never writes into the data. Before copying anything, it checks every
upstream path against the data entries and the data root those entries link into. If any path
would land there, the sync aborts with an error.

## Set it up

New ship, or an existing one whose data you want to move (stop the Mate and Bosun first, so
nothing writes to `state/` or `inbox/` mid-move):

```
python3 shipkit_init.py --defaults --data-root ship-data --dry-run
python3 shipkit_init.py --defaults --data-root ship-data
cd ship-data && git init && git add -A && git commit -m "Ship data"
git remote add origin <your private remote>
```

Run the `git init` straight away. Until `ship-data/` is a repo of its own, it's just an
ignored directory inside the kit clone, and `git clean -fdx` there would delete it. Once it
has its own `.git`, git skips it unless you pass `-f` twice.

(`/shipkit-setup` asks this question for you. `--data-root` combines with `--preset` the same
way it does with `--defaults`.)

New machine with an existing data repo: clone the kit and the data repo, then run
`python3 shipkit_init.py --defaults --data-root <path-to-data-repo>`.

## Living with it

- **Edit the root files in the data root**: `ship-data/queue.md`, not `queue.md`.
- **Commit data in the data repo** (`cd ship-data`, or wherever your data root is). The kit
  clone can't see past the symlinks.
- **The kit clone stays quiet, mostly.** The installer adds the links and the untracked stubs
  to the clone's local `.git/info/exclude`, so they don't show as untracked and `git add -A`
  won't pick them up. It can't use the tracked `.gitignore`, because that would hide an
  in-repo ship's real `logs/`. The kit's own placeholders still show as modified (the stubs
  in `captain.md` and `queue.md`) or deleted (`inbox/captain.md` and the `.gitkeep` files).
  That's expected. Don't commit them in the kit clone.
- **Update the kit with `scripts/pull-upstream.sh`.** It ignores git state and never touches
  the data. `git pull` also works until upstream edits one of those placeholders, at which
  point git refuses because of your local change. Don't stash: stashing restores the
  placeholders over your links and stubs. Use `pull-upstream.sh` instead.
- **Searching.** `rg`, `find` and Claude Code's Grep don't follow a symlinked directory
  while walking from the ship root. For `ship-data/`, the kit's `.rgignore` un-ignores the
  nested repo, so `rg term` run from the ship root still finds the data, under
  `ship-data/...` paths. For a data root outside the ship, name the path (`rg term logs/`),
  use `rg -L`, or search the data root directly. `find` needs `-L`. Point a search index
  (qmd or similar) at the data root.
- **Windows** needs symlink permission (Developer Mode). Without it the installer stops before
  moving anything.
- **Hooks**: the crew write guard resolves symlinks and ignores case, so it blocks writes to
  `ship-data/queue.md` just as it blocks writes to `queue.md`.
- **Scripts that write the queue files** must resolve them through `lib/ship_data.py`.
  Writing `queue.md` at the ship root would only overwrite the stub.

## Whose data is it?

*This is not legal advice. Your employment agreement and your employer's policies decide what
you may keep, and they override anything here.*

If you use a ship for work, its data is the employer's: tickets, logs, the queue, `state/`,
system docs and incident data. Keep it in a repo the employer can audit, revoke and retain,
which means an org-owned private remote, not your personal account. What's yours is the kit,
your `mate.local.md`, and generic lessons about tools and agents.

Knowledge docs can be either. The compound module tags each one at capture with
`scope: employer` (the default) or `scope: personal`. A `personal` doc stays in the data root
until it passes the [scrub gate](modules/compound/scrub-gate.md), which also holds the full
breakdown of what belongs to whom.
