# Mate — Local Preferences (template)

Copy this file to **`mate.local.md`** and fill in your values. The Mate reads
`mate.md` (the general-core doctrine), **then this file**, at watch start; the
values here override and extend the `<!-- PREF: key -->` seams in core. `/shipkit-init`
can populate this for you conversationally — each entry below maps to one interview
question and one core seam.

**This file is yours.** `pull-upstream` updates core `mate.md` freely and **never
touches `mate.local.md`** (add it to `.gitignore` if you don't want it tracked).
Hand-edit it anytime; the core doc stays generic so updates don't collide.

**Two overlays, two concerns.** *Behavioral* preferences (taste — thresholds, model
roster, report format, house notes) live **here**. *Machine* config (paths, ports,
hosts, watched repos) lives in **`loop.config.json`** — see `loop.config.example.json`.
Keep machine specifics out of this file and taste out of the config.

---

## Thresholds & pacing

```
wind_down_threshold:   ~70% context used   # core "Watches and Days" + Heartbeat wind-down.
                                            #   <70% keep going; 70–80% find a seam; 80%+/compaction → wind down promptly.
max_concurrent_crew:    4                   # flat crew cap. The dispatch-bands module varies this by rate (see below).
pacing_fallback:        1200–1800s          # steady-state heartbeat wake interval. Avoid ~300s (worst case for prompt-cache TTL).
                                            #   Shorten only when shepherding a known-fast external thing (a CI run).
```

## Dispatch bands (if you run the dispatch-bands module)

Rate/cost-aware modulation of crew cap + dispatch appetite. See
[modules/dispatch-bands.md](modules/dispatch-bands.md) for the concept and how to
set the thresholds. Example roster:

```
band_gauge_path:        state/context-gauge.json   # the capacity gauge the bands read (rate_pct, rate_reset_mins)
band_abundant:  rate < 50% OR reset < 20m   → crew cap 6, fill slots freely, speculative work OK
band_normal:    50–80% AND reset > 20m      → crew cap 4, queued work only, no speculative dispatch
band_tight:     ≥ 80% AND reset > 20m       → crew cap 2, hold autonomous dispatch, Mate goes light
band_hysteresis: cross threshold ~5m before switching (don't flap)
# Guardrails (these are FIXED, not tunable): Captain-directed work always dispatches, any band;
# authority tiers / bright lines NEVER vary with rate; stale/missing gauge → assume NORMAL.
```

## Model roster

```
model_default:    opus     # default crew + pilot model. Code-writing crews default here.
model_escalate:   fable     # ~2x cost; per-dispatch escalation for design-heavy / ambiguous / multi-constraint watches
model_lookout:    haiku    # read-only lookouts + PR-review first pass
model_speed:      sonnet   # when a specific speed premium applies (many parallel lightweight watches, simple well-specified changes)
# Corollary: if a faster model IS the implementer on a watch, pair it with a stronger-model reviewer gate.
```

## Review policy (if you run the review-cycle module)

```
review_policy:    all-crew-code-every-time   # options: off | significant-only | all-crew-code-every-time | rate-gated
review_model:     opus                       # the non-maker ship-reviewer model
review_standards: docs/knowledge/crew-code-standards.md   # the standards doc the reviewer checks against
```
See [modules/review-cycle.md](modules/review-cycle.md) for the enforcement mechanism.

## Reporting & surfaces

```
report_format:    logseq-tabs   # standup format. e.g. plain bullets | logseq-tabs (tab-indented bullets in a code block) | tool-specific
chat_surface:     /thread       # where the Captain reads (terminal | a chat surface | an inbox file). Surface substantive work HERE.
                                #   Multiple targeted replies > one mega-summary when a turn touches several threads.
```

## Tools

```
search_tool:      qmd           # your semantic-search-across-the-vault command (if any)
pr_review_cmd:    pr-buddy list  # your PR-review entry point (if any) — the start-of-watch PR pass
loop_skill:       /loop /ship-tick   # the command that starts/paces your heartbeat (if you run Loop Mode)
```

## Repos & org

```
github_org:       YourOrg       # for PR links: https://github.com/YourOrg/{repo}/pull/{number}
pr_template:      TL;DR / Background / Modification / Result / How to verify / Checklist
                                # your PR template's section headings — keep the structure, match prose length to change size
```

---

## House notes (free-form)

Anything else the operator wants the Mate to carry every watch — environment
quirks, standing exceptions, named teammates, escalation contacts, recurring
gotchas. This section is unstructured on purpose; pin what matters to you.

- (example) Restart service X by killing its PID; the supervisor auto-restarts it.
- (example) Default infra asks go to the Platform team, not a named person.
- (example) Personal/throwaway projects skip the PR draft ceremony — merge straight to main.
