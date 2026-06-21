---
name: shipkit-init
description: >
  The conversational onboarding interview for Ship Loop Mode. Invoke once
  (`/shipkit-init`) when standing Ship up on a machine for the first time, or
  when adding modules to an existing install. The agent CONDUCTS a short
  interview — preset, modules, ship-root, skills-install method, watched repos,
  and the behavioral preferences (taste) that populate mate.local.md —
  using AskUserQuestion-style prompts, then calls the deterministic apply step
  (`scripts/shipkit_init.py`) with the gathered answers and prints the smoke
  test. Conversational front, deterministic apply. Not a per-tick loop skill;
  it runs ONCE and yields.
---

# /shipkit-init — onboarding interview for Loop Mode

You are conducting Ship Loop Mode bring-up for the Captain. This skill is the
**main onboarding experience**: you run a short conversational interview, then
hand the answers to the idempotent apply script. The script is plumbing — your
job is the *interview*, adapting and explaining trade-offs as you go.

**Install model:** **one ship per machine.** Do NOT ask about multiple ship-roots
or multi-location installs — there is a single ship-root for this machine. Lean
into that simplicity.

**The deal:** you ask (AskUserQuestion-style), the Captain answers, you call
`python3 scripts/shipkit_init.py` once with the gathered answers, then print the
smoke test. Re-runnable — the apply step is idempotent, so a second run (e.g.
adding a module later) is safe.

## What ships today (be honest in the interview)

The preset → module mapping is defined ONCE in `scripts/shipkit_init.py`
(`PRESETS` + `MODULES`) — that file is the source of truth; this section mirrors
it for the conversation. **Only `core` and `status-surface` exist as code
today.** Other module names are *framework slots* — they name where future
sensors/surfaces plug in, but ship NO code yet. Say so plainly if the Captain
asks for one; the apply step skips planned modules with a clear note.

| Module | Status | What it is |
|---|---|---|
| `core` | **shipped** (always on) | heartbeat loop + status writer + input classifier (`ship-watch-start`, `ship-tick`, `status_writer.py`, `classify_input.sh`) |
| `status-surface` | **shipped** | reference browser UI that renders `status.json` + a steer box (`examples/status-surface/`) |
| `pr-buddy` | *planned* | PR sensor that re-drops PR state — NOT YET IN SHIPKIT |
| `sentry-sweeps` | *planned* | Sentry error sweeps as a sensor — NOT YET IN SHIPKIT |

**Presets** (each is just a named module set; most Captains pick one):
- **minimal** — `core`. Headless loop, no UI.
- **standard** — `core` + `status-surface`. The recommended default: you get a
  browser surface to watch and steer.
- **full** — everything shipkit ships today (currently == standard; it grows as
  modules land — the preset *system* is the framework).
- **custom** — pick your own module set.

## The interview (ask in this order)

Use AskUserQuestion-style prompts — one decision at a time, each option with a
one-line "what it bundles." Adapt: skip a question if a prior answer settles it.

### (a) Preset
Ask which preset. Offer **minimal / standard / full / custom**, each with its
one-line blurb (above). Recommend **standard** for a first install. Record the
choice.

### (b) Modules
- If the Captain picked **custom**, present the toggle list (the `MODULES` table
  above). `core` is mandatory (always on) — don't offer to turn it off. Clearly
  mark *planned* modules as not-yet-shipped so they don't pick a no-op.
- Otherwise, show the preset's module set and let them adjust (add/drop a
  module). Confirm the final list.

### (c) Ship-root
Confirm the single ship-root for this machine. **Default: the shipkit dir / your
current working directory** (`.`). One ship per machine — this is the directory
where `queue.md`, `captain.md`, `projects/`, `logs/`, `state/` live and where you
launch `/ship-watch-start`. Accept `.` unless the Captain launches from
elsewhere, in which case capture the absolute path.

### (d) Skills install method
Ask **symlink vs copy** for installing the selected skill dirs into
`~/.claude/skills`:
- **symlink** (default) — the installed skills track this repo; `pull-upstream`
  / `git pull` updates them in place. Best when shipkit lives in a stable spot.
- **copy** — a frozen snapshot; survives moving/deleting the repo but won't pick
  up upstream changes automatically.
Default to **symlink** on macOS/Linux unless the Captain wants a detached copy.
**On Windows the apply step defaults to copy** (os.symlink there needs admin /
Developer Mode), and a symlink that fails at runtime falls back to a copy — so on
Windows, prefer/accept copy unless the Captain has Developer Mode on.

### (e) Watched repos — ONLY if a sensor-type module is selected
A *sensor* module (e.g. `pr-buddy`, `sentry-sweeps`) watches external repos.
**Only ask this if the final module set includes a sensor module.** Since no
sensor module ships today, you will normally **skip this question entirely**. If
a sensor is somehow selected, gather the repo paths for `loop.config.json`'s
`repos`; otherwise leave `repos` empty (the preflight git sweep just skips).

### (f) Behavioral preferences (taste) — write `mate.local.md`

This is where you populate the Mate's **behavioral-prefs overlay**,
`mate.local.md`. Core `mate.md` ships generic doctrine that refers to configured
values generically ("your configured X") and force-loads this overlay via its
`@mate.local.md` reference; this phase fills in the Captain's taste. (Machine
specifics — paths, ports, repos — went into `loop.config.json` above; taste goes
here. Two overlays, two concerns.) The Mate reads core `mate.md` **and**
`mate.local.md` together at watch start.

**Don't fire 12 separate prompts.** Group into a few clusters, mirroring the
sections of `mate.local.example.md`. For each cluster, show the example/default
value (from `mate.local.example.md`) and let the Captain **accept-default** (the
common path — just say "defaults") or set their own. Conversational and skimmable.
A Captain who accepts every default still gets a complete, valid overlay (the
script carries the example defaults verbatim for anything unanswered).

Module-gated clusters appear **only if that module is in the final set**:
- **Dispatch bands** cluster → only if `dispatch-bands` selected.
- **Review policy** cluster → only if `review-cycle` selected.

The clusters and the `mate.local.md` / core-seam keys each maps to:

| Cluster | Always? | `mate.local.md` keys it sets |
|---|---|---|
| **Thresholds & pacing** | always | `wind_down_threshold`, `max_concurrent_crew`, `pacing_fallback` |
| **Dispatch bands** | only if `dispatch-bands` on | the `band_*` roster (defaults usually fine) + FIXED guardrails (not tunable) |
| **Model roster** | always | `model_default` (+ the `model_escalate`/`model_lookout`/`model_speed` tiers — defaults usually fine) |
| **Review policy** | only if `review-cycle` on | `review_policy` (+ `review_model`, `review_standards`) |
| **Reporting & surfaces** | always | `report_format`, `chat_surface` |
| **Tools** | always | `search_tool`, `pr_review_cmd`, `loop_skill` |
| **Repos & org** | always | `github_org`, `pr_template` |
| **House notes** | always (optional) | free-form lines — environment quirks, escalation contacts, standing exceptions |

Notes:
- `max_concurrent_crew` and `chat_surface` are **shared** with `loop.config.json`
  (machine code reads the config copy; the Mate reads the overlay copy). Ask once;
  the apply step writes both. Keep them consistent.
- The **FIXED band guardrails** and the **House-notes scaffold** carry through to
  the written file verbatim — you don't ask about the guardrails (they never vary).
- Sub-tier model keys (`model_escalate`/`lookout`/`speed`) and
  `review_model`/`review_standards` rarely need changing — present them as part of
  their cluster's "or tweak the roster?" and accept the template defaults unless
  the Captain adjusts. They ARE substitutable (pass them in `prefs`/`--pref` if
  tweaked); anything unset keeps the template default.
- The `band_*` roster (`band_abundant`/`normal`/`tight`/`hysteresis`/`gauge_path`)
  is prose-shaped, not simple scalars — it carries through **verbatim** from the
  template and the operator hand-edits the thresholds. The dispatch-bands cluster
  surfaces it for review; it is not `--pref`-substitutable.

Pass the gathered taste values to the apply step as a `prefs` block in the
`--answers` JSON (recommended — it carries all 12 keys + `house_notes` cleanly),
or as `--pref key=value` flags (handy for a one- or two-value override). See the
Apply section for the shapes.

## Apply — call the script once

Once you have the answers, invoke the deterministic apply step. Two equivalent
ways (pick whichever is cleaner for the answers you gathered):

**Flags** (simple cases):
```
python3 scripts/shipkit_init.py \
  --preset <minimal|standard|full|custom> \
  [--modules core status-surface ...]   # required iff preset=custom \
  --ship-root <. | /abs/path> \
  --install-mode <symlink|copy> \
  [--max-concurrent-crew N] \
  [--pref key=value ...]               # behavioral prefs -> mate.local.md \
  [--house-note "free-form line" ...]   # repeatable
```

**Answers file** (richer answers — chat_surface, headroom path, repos, **and the
full taste block**): write a small JSON answers file (shape documented at the top
of `scripts/shipkit_init.py`) and pass `--answers <path>`. Put the taste values in
a `"prefs"` object and house notes in a `"house_notes"` list, e.g.:
```json
{
  "preset": "standard", "ship_root": ".", "max_concurrent_crew": 4,
  "prefs": {
    "wind_down_threshold": "~70% context used", "pacing_fallback": "1200-1800s",
    "model_default": "opus", "review_policy": "all-crew-code-every-time",
    "report_format": "logseq-tabs", "chat_surface": "/thread",
    "search_tool": "qmd", "pr_review_cmd": "pr-buddy list",
    "loop_skill": "/loop /ship-tick", "github_org": "YourOrg",
    "pr_template": "TL;DR / Background / Modification / Result / How to verify / Checklist"
  },
  "house_notes": ["Restart service X by killing its PID; supervisor restarts it."]
}
```
Any pref key you omit keeps the `mate.local.example.md` default verbatim, so you
only need to list the ones the Captain changed. `--pref key=value` flags override
the answers-file `prefs`; `--house-note` flags override `house_notes`.

**Always preview first.** Run with `--dry-run` and show the Captain the plan
before applying for real. Then run the same command without `--dry-run`.

The apply step (idempotent — safe to re-run):
1. Writes `loop.config.json` from `loop.config.example.json` populated with the
   answers (leaves an existing config untouched unless `--force-config`).
2. Writes `mate.local.md` from `mate.local.example.md` populated with the taste
   answers — substitutes the collected `prefs` values into their `key:` lines and
   the house notes, carrying the FIXED band guardrails + the House-notes scaffold
   verbatim (leaves an existing `mate.local.md` untouched unless `--force-prefs`).
3. Symlinks-or-copies the selected modules' skill dirs into `~/.claude/skills`
   (override the target with `--skills-target <dir>` — used only for testing,
   never point tests at the real `~/.claude`).
4. Seeds `state/status.json` via `status_writer.py --init` (no-op if already
   seeded).
5. Prints the smoke test.

## After applying — print the smoke test

The script prints the smoke test; relay it and confirm the acceptance with the
Captain:
- Core `mate.md` **and** `mate.local.md` are read together at watch start — the
  overlay resolves core's "your configured X" seams (confirm `mate.local.md` was
  written with the Captain's taste; spot-check a value or two).
- `/ship-watch-start` preflight prints and passes (or names a NO-GO).
- A **directive** (chat / inbox steer) **wakes** the loop.
- A **bookkeeping** change does **NOT** wake — it reconciles at the next tick.
- One quiet tick logs a telemetry line + writes `status.json`; `ship-watch-start`
  exits and `ship-tick` self-paces.
- (If `status-surface` was installed) the reference UI renders `status.json`.

## Bounds
- Run **once** per onboarding/module-add. This is not a per-tick loop skill.
- **One ship per machine** — never set up multiple ship-roots or multi-location
  installs.
- **Be honest about shipped vs planned.** Never imply a *planned* module works;
  the apply step skips them and says so.
- The preset → module mapping lives in `scripts/shipkit_init.py` — if it and this
  doc disagree, the script wins (update this doc to match).
- Always `--dry-run` and show the plan before the real apply.
- Don't hand-edit `loop.config.json`, `mate.local.md`, or `state/status.json`
  here — the apply step owns those writes during onboarding (hand-editing either
  overlay later is a fine manual fallback; the script only rewrites them with
  `--force-config` / `--force-prefs`, so it never clobbers a later edit).
- `mate.local.md` is the **behavioral-prefs** overlay (taste). Keep machine
  specifics (paths, ports, repos) out of it — those belong in `loop.config.json`.
