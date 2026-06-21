#!/usr/bin/env python3
"""shipkit_init.py — the deterministic APPLY step for Loop Mode onboarding.

This is the plumbing the `/shipkit-init` interview skill calls once it has
gathered answers from the Captain. The conversational interview is the main
experience; this script is the small, idempotent, re-runnable apply step that
actually wires the bits. It does FIVE things, all safe to repeat:

  1. Write loop.config.json from loop.config.example.json, populated with answers.
  2. Write mate.local.md from mate.local.example.md, populated with the
     behavioral-preference (taste) answers the interview gathered.
  3. Symlink-or-copy the selected skills/ dirs into the target skills dir
     (default ~/.claude/skills; --skills-target overrides for testing).
  4. Seed state/status.json (delegates to status_writer.py --init).
  5. Print the smoke-test steps.

Two overlays, two concerns: BEHAVIORAL prefs (taste — thresholds, model roster,
report format, house notes) go in mate.local.md; MACHINE config (paths, ports,
hosts, watched repos) goes in loop.config.json. The Mate reads core mate.md and
then mate.local.md together at watch start.

PRESET -> MODULE mapping lives in PRESETS below — the ONE source of truth the
skill documents. Be honest about what shipkit ships TODAY: only `core` and the
`status-surface` reference UI exist. New modules slot into PRESETS as they land.

Idempotent by design: a second run is a safe no-op (config already populated,
skills already linked, state already seeded). Always offers --dry-run.

Stdlib only — no pip installs. Cross-platform (pathlib + json + shutil). On
Windows the skill install defaults to COPY (os.symlink there needs admin /
Developer Mode), and a symlink that fails at runtime falls back to a copy.

Usage
-----
  # From flags (the common path the skill uses):
  shipkit_init.py --preset standard --ship-root . --install-mode symlink

  # From a small JSON answers file (interview can write one):
  shipkit_init.py --answers /tmp/answers.json

  # Custom module set:
  shipkit_init.py --preset custom --modules core status-surface

  # Always-safe preview:
  shipkit_init.py --preset standard --dry-run

  # Testing against a throwaway skills dir (never the real ~/.claude):
  shipkit_init.py --preset full --skills-target /tmp/test-skills

Answers JSON shape (all keys optional; flags override file values):
  {
    "preset": "standard",
    "modules": ["core", "status-surface"],
    "ship_root": ".",
    "repos": ["/Users/you/dev/work/app"],
    "max_concurrent_crew": 2,
    "chat_surface": {"kind": "file", "path": "inbox/captain.md"},
    "headroom_signal_path": "state/context-gauge.json",
    "validator_cmd": null,
    "hosts_ports": {"status_surface": "http://127.0.0.1:8000"},
    "install_mode": "symlink",

    "prefs": {                       # BEHAVIORAL prefs -> mate.local.md
      "wind_down_threshold": "~70% context used",
      "max_concurrent_crew": "4",
      "pacing_fallback": "1200-1800s",
      "model_default": "opus",
      "review_policy": "all-crew-code-every-time",
      "report_format": "logseq-tabs",
      "chat_surface": "/thread",
      "search_tool": "qmd",
      "pr_review_cmd": "pr-buddy list",
      "loop_skill": "/loop /ship-tick",
      "github_org": "YourOrg",
      "pr_template": "TL;DR / Background / Modification / Result / How to verify / Checklist"
      # any pref key not supplied keeps the mate.local.example.md default verbatim.
      # House notes + the FIXED band guardrails carry through verbatim.
    },
    "house_notes": ["Restart service X by killing its PID; supervisor restarts it."]
  }

NOTE on prefs vs config: `max_concurrent_crew` and `chat_surface` appear in BOTH
overlays — the loop.config.json copy is the machine-readable value the heartbeat
code consumes; the mate.local.md copy is the human-doctrine value the Mate reads.
The interview gathers each once; this script writes both. Keep them consistent.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SHIPKIT_ROOT = SCRIPT_DIR.parent
DEFAULT_SKILLS_TARGET = Path.home() / ".claude" / "skills"

# On Windows, os.symlink needs admin rights or Developer Mode, so default to
# COPY there (a frozen snapshot) rather than symlink. POSIX defaults to symlink
# (tracks the repo). An explicit --install-mode / answers value always wins.
IS_WINDOWS = os.name == "nt"
DEFAULT_INSTALL_MODE = "copy" if IS_WINDOWS else "symlink"

# ---------------------------------------------------------------------------
# PRESET -> MODULE mapping. THE single source of truth (the skill documents it).
#
# HONESTY: only modules listed in MODULES with status "shipped" exist in the
# repo today. "planned" entries are placeholders that name the framework slot
# but ship NO code yet — the apply step skips them with a clear note. As real
# modules land, flip them to "shipped" and add their `skills`/`examples` dirs.
# ---------------------------------------------------------------------------

# Each module: which skill dirs and example dirs it installs, plus ship status.
MODULES = {
    "core": {
        "status": "shipped",
        "blurb": "heartbeat loop + status writer + input classifier (always on)",
        "skills": ["ship-watch-start", "ship-tick"],
        "examples": [],
        "mandatory": True,
    },
    "status-surface": {
        "status": "shipped",
        "blurb": "reference browser UI that renders status.json + a steer box",
        "skills": [],
        "examples": ["status-surface"],
        "mandatory": False,
    },
    # --- planned slots (NO code ships yet; named so the framework is visible) ---
    "pr-buddy": {
        "status": "planned",
        "blurb": "PR sensor that re-drops PR state (NOT YET IN SHIPKIT)",
        "skills": [],
        "examples": [],
        "mandatory": False,
    },
    "sentry-sweeps": {
        "status": "planned",
        "blurb": "Sentry error sweeps as a sensor (NOT YET IN SHIPKIT)",
        "skills": [],
        "examples": [],
        "mandatory": False,
    },
}

# A module is a "sensor" if it watches external repos/paths and re-drops state.
SENSOR_MODULES = {"pr-buddy", "sentry-sweeps"}

PRESETS = {
    "minimal": ["core"],
    "standard": ["core", "status-surface"],
    "full": ["core", "status-surface"],  # everything shipkit ships TODAY
    # "custom" is not a fixed set — the interview supplies an explicit module list.
}

PRESET_BLURBS = {
    "minimal": "headless loop only — the core heartbeat, no UI",
    "standard": "core + the status-surface UI so you can watch and steer in a browser",
    "full": "everything shipkit ships today (currently == standard; grows as modules land)",
    "custom": "pick your own module set from the toggle list",
}


# ---------------------------------------------------------------------------
# BEHAVIORAL PREFERENCE keys -> mate.local.md. These map 1:1 to the
# `<!-- PREF: key -->` seams in mate.md and to the value-bearing lines in
# mate.local.example.md. The interview gathers them (grouped); this script
# substitutes them into the example template. Any key the interview does NOT
# supply keeps the example's default value verbatim, so a partial answer set
# still yields a valid overlay.
#
# `module` ties a key to a module gate: the matching interview GROUP only shows
# if that module is selected, but the template carries the section regardless
# (with its example defaults) so the overlay stays complete.
# ---------------------------------------------------------------------------
# `primary` marks the 12 keys the interview asks about head-on (1:1 with the
# `<!-- PREF: key -->` seams in mate.md). The remaining keys are roster/sub-tier
# lines the interview presents as part of a cluster's "or tweak the roster?" —
# they substitute the same way if supplied, else keep the template default.
PREF_KEYS = {
    # Thresholds & pacing
    "wind_down_threshold": {"group": "thresholds", "module": None, "primary": True},
    "max_concurrent_crew": {"group": "thresholds", "module": None, "primary": True},
    "pacing_fallback": {"group": "thresholds", "module": None, "primary": True},
    # Model roster
    "model_default": {"group": "model_roster", "module": None, "primary": True},
    "model_escalate": {"group": "model_roster", "module": None, "primary": False},
    "model_lookout": {"group": "model_roster", "module": None, "primary": False},
    "model_speed": {"group": "model_roster", "module": None, "primary": False},
    # Review policy (review-cycle module)
    "review_policy": {"group": "review", "module": "review-cycle", "primary": True},
    "review_model": {"group": "review", "module": "review-cycle", "primary": False},
    "review_standards": {"group": "review", "module": "review-cycle", "primary": False},
    # Reporting & surfaces
    "report_format": {"group": "reporting", "module": None, "primary": True},
    "chat_surface": {"group": "reporting", "module": None, "primary": True},
    # Tools
    "search_tool": {"group": "tools", "module": None, "primary": True},
    "pr_review_cmd": {"group": "tools", "module": None, "primary": True},
    "loop_skill": {"group": "tools", "module": None, "primary": True},
    # Repos & org
    "github_org": {"group": "repos_org", "module": None, "primary": True},
    "pr_template": {"group": "repos_org", "module": None, "primary": True},
    # NOTE: the dispatch-bands `band_*` roster lines (band_abundant/normal/tight/
    # hysteresis/gauge_path) are prose-shaped rosters, not simple scalars — they
    # carry through verbatim from the template; the operator hand-edits the band
    # thresholds (the dispatch-bands cluster surfaces them for review). They are
    # intentionally NOT --pref-substitutable. See modules/dispatch-bands.md.
}


def _err(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def resolve_modules(preset: str | None, modules: list[str] | None) -> list[str]:
    """Return the ordered, deduped, core-first module list to install."""
    if modules:
        selected = list(modules)
    elif preset and preset != "custom":
        if preset not in PRESETS:
            _err(f"unknown preset {preset!r}. Known: {', '.join(PRESETS)} (or custom).")
        selected = list(PRESETS[preset])
    elif preset == "custom":
        _err("preset=custom requires --modules (or a 'modules' list in --answers).")
    else:
        _err("provide --preset or --modules (or an --answers file with one).")

    # core is always mandatory and first; dedupe preserving order.
    ordered: list[str] = ["core"]
    for m in selected:
        if m not in MODULES:
            _err(f"unknown module {m!r}. Known: {', '.join(MODULES)}.")
        if m not in ordered:
            ordered.append(m)
    return ordered


# ---------------------------------------------------------------------------
# Actions. Each returns a list of human-readable plan lines (what it did / would
# do). In --dry-run nothing touches disk; the same lines print prefixed [dry-run].
# ---------------------------------------------------------------------------

def load_answers(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _err(f"answers file not found: {path}")
    except json.JSONDecodeError as e:
        _err(f"answers file is not valid JSON: {e}")
    if not isinstance(data, dict):
        _err("answers file must be a JSON object.")
    return data


def build_config(answers: dict) -> dict:
    """Populate the example template with answers; null-safe defaults."""
    example_path = SHIPKIT_ROOT / "loop.config.example.json"
    try:
        example = json.loads(example_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _err(f"template missing: {example_path}")
    except json.JSONDecodeError as e:
        _err(f"loop.config.example.json is not valid JSON: {e}")

    # Start from the live config's shape (no underscore doc keys), filled from
    # the example for any missing field, then overwrite with answers.
    cfg = {
        "_comment": (
            "Generated by scripts/shipkit_init.py from loop.config.example.json. "
            "Safe to hand-edit; re-running shipkit_init only rewrites it if you "
            "pass --force-config. See loop.config.example.json for field docs."
        ),
        "ship_root": answers.get("ship_root", "."),
        "repos": answers.get("repos", []),
        "max_concurrent_crew": answers.get("max_concurrent_crew", 2),
        "chat_surface": answers.get("chat_surface"),
        "headroom_signal_path": answers.get("headroom_signal_path"),
        "validator_cmd": answers.get("validator_cmd"),
        "hosts_ports": answers.get("hosts_ports"),
    }
    return cfg


def write_config(cfg: dict, dry_run: bool, force_config: bool) -> list[str]:
    target = SHIPKIT_ROOT / "loop.config.json"
    if target.exists() and not force_config:
        # Idempotent: don't clobber an existing config unless asked.
        return [f"loop.config.json exists — left untouched (pass --force-config to regenerate)"]
    serialized = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        return [f"would write loop.config.json (ship_root={cfg['ship_root']!r}, "
                f"repos={len(cfg['repos'])}, max_crew={cfg['max_concurrent_crew']})"]
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(serialized, encoding="utf-8")
    os.replace(tmp, target)  # os.replace overwrites atomically on POSIX + Windows
    return [f"wrote loop.config.json (ship_root={cfg['ship_root']!r}, "
            f"repos={len(cfg['repos'])}, max_crew={cfg['max_concurrent_crew']})"]


def build_prefs(answers: dict) -> dict:
    """Collect behavioral-pref values from answers.

    Values may live under answers["prefs"][key] OR as a top-level answers[key]
    (e.g. chat_surface / max_concurrent_crew, which also feed loop.config.json).
    The prefs block wins for taste; we fall back to a stringified top-level
    value so the interview can supply each pref once. Missing keys are simply
    absent here and keep the example default at write time.
    """
    raw = answers.get("prefs") or {}
    if not isinstance(raw, dict):
        _err("answers 'prefs' must be a JSON object of key -> value.")
    prefs: dict[str, str] = {}
    for key in PREF_KEYS:
        val = raw.get(key)
        if val is None and key in ("max_concurrent_crew",):
            # max_concurrent_crew is shared with config; reuse the config value.
            val = answers.get("max_concurrent_crew")
        if val is None:
            continue
        prefs[key] = str(val)
    return prefs


def _substitute_pref_line(line: str, value: str) -> str:
    """Replace the value portion of a `key:   <value>   # comment` line,
    preserving the leading `key:` + its padding and any trailing `# comment`.
    """
    # Split off a trailing comment (the `#` that starts the inline comment).
    head, sep, comment = line.partition("#")
    # head looks like:  "key:      old value      "
    colon = head.index(":")
    key_part = head[:colon + 1]                      # "key:"
    pad_old = head[colon + 1:]                        # "      old value      "
    lead_ws = pad_old[:len(pad_old) - len(pad_old.lstrip())]  # padding after colon
    # Keep one trailing space before the comment if there was a comment.
    if sep:
        return f"{key_part}{lead_ws}{value}   {sep}{comment}".rstrip("\n") + "\n"
    return f"{key_part}{lead_ws}{value}".rstrip() + "\n"


def render_prefs(prefs: dict, house_notes: list[str] | None) -> str:
    """Produce mate.local.md text from mate.local.example.md, substituting
    collected pref values into their `key:` lines and (optionally) appending
    operator house notes. Unsupplied keys keep the example default verbatim.
    The FIXED band guardrails and the House-notes scaffold carry through as-is.
    """
    example_path = SHIPKIT_ROOT / "mate.local.example.md"
    try:
        text = example_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _err(f"template missing: {example_path}")

    out_lines: list[str] = []
    in_fence = False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            # A pref line inside a code fence looks like "key:   value   # ...".
            body = line.lstrip()
            matched = False
            for key in prefs:
                if body.startswith(f"{key}:"):
                    out_lines.append(_substitute_pref_line(line, prefs[key]))
                    matched = True
                    break
            if matched:
                continue
        out_lines.append(line)

    text = "".join(out_lines)

    # Retitle + reword the opening: it is no longer a blank template once
    # populated by /shipkit-init.
    text = text.replace(
        "# Mate — Local Preferences (template)\n",
        "# Mate — Local Preferences\n",
        1,
    )
    text = text.replace(
        "Copy this file to **`mate.local.md`** and fill in your values. The Mate reads",
        "Generated by `/shipkit-init` (scripts/shipkit_init.py) from "
        "`mate.local.example.md`.\nHand-edit anytime. The Mate reads",
        1,
    )

    if house_notes:
        # Replace the example placeholder bullets with the operator's notes.
        note_block = "\n".join(f"- {n}" for n in house_notes) + "\n"
        marker = "- (example) Restart service X"
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx] + note_block
        else:
            text = text.rstrip("\n") + "\n\n" + note_block
    return text


def write_prefs(answers: dict, dry_run: bool, force_prefs: bool) -> list[str]:
    target = SHIPKIT_ROOT / "mate.local.md"
    prefs = build_prefs(answers)
    house_notes = answers.get("house_notes")
    if house_notes is not None and not isinstance(house_notes, list):
        _err("answers 'house_notes' must be a JSON list of strings.")

    supplied = ", ".join(sorted(prefs)) if prefs else "(none — all defaults)"
    if target.exists() and not force_prefs:
        return [f"mate.local.md exists — left untouched (pass --force-prefs to "
                f"regenerate). Prefs that WOULD apply: {supplied}"]

    text = render_prefs(prefs, house_notes)
    if dry_run:
        lines = [f"would write mate.local.md from mate.local.example.md"]
        lines.append(f"  prefs applied ({len(prefs)}): {supplied}")
        if house_notes:
            lines.append(f"  house_notes: {len(house_notes)} line(s)")
        else:
            lines.append("  house_notes: (template placeholders kept)")
        return lines
    tmp = target.with_suffix(".md.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)  # os.replace overwrites atomically on POSIX + Windows
    lines = [f"wrote mate.local.md ({len(prefs)} pref(s) applied: {supplied})"]
    if house_notes:
        lines.append(f"  + {len(house_notes)} house note(s)")
    return lines


def _install_one(src: Path, dst: Path, mode: str, dry_run: bool) -> str:
    """Install a single dir (symlink or copy). Idempotent + safe."""
    label = dst.name
    if dst.exists() or dst.is_symlink():
        # Already there. If it's a symlink to the same source, perfect no-op.
        if dst.is_symlink():
            try:
                if dst.resolve() == src.resolve():
                    return f"{label}: already linked (no-op)"
            except OSError:
                return f"{label}: existing symlink is broken — leaving it (remove manually)"
            return f"{label}: a symlink already exists pointing elsewhere — left untouched"
        return f"{label}: target already exists (not a symlink) — left untouched"

    if dry_run:
        return f"{label}: would {mode} -> {dst}"

    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "symlink":
        try:
            os.symlink(src, dst, target_is_directory=True)
            return f"{label}: symlinked -> {dst}"
        except OSError as e:
            # Windows without admin/Developer Mode (WinError 1314) raises here.
            # Fall back to a copy so install still succeeds (frozen snapshot).
            shutil.copytree(src, dst)
            return (f"{label}: symlink failed ({e.strerror or e}); "
                    f"copied instead -> {dst}")
    shutil.copytree(src, dst)
    return f"{label}: copied -> {dst}"


def install_skills(module_list: list[str], skills_target: Path, mode: str,
                   dry_run: bool) -> list[str]:
    lines: list[str] = []
    src_root = SHIPKIT_ROOT / "skills"
    for m in module_list:
        meta = MODULES[m]
        if meta["status"] != "shipped":
            for s in meta["skills"]:
                lines.append(f"{m}/{s}: PLANNED module — no code ships yet, skipped")
            continue
        for skill in meta["skills"]:
            src = src_root / skill
            if not src.is_dir():
                lines.append(f"{skill}: source dir missing at {src} — skipped")
                continue
            lines.append(_install_one(src, skills_target / skill, mode, dry_run))
    if not any("symlink" in ln or "copied" in ln or "would" in ln or "already linked" in ln
               for ln in lines):
        lines.append("(no skill dirs to install for the selected modules)")
    return lines


def report_examples(module_list: list[str], dry_run: bool) -> list[str]:
    """Examples ship in-repo; we don't move them — just tell the user where."""
    lines: list[str] = []
    for m in module_list:
        meta = MODULES[m]
        if meta["status"] != "shipped":
            continue
        for ex in meta["examples"]:
            ex_dir = SHIPKIT_ROOT / "examples" / ex
            if ex_dir.is_dir():
                lines.append(f"{m}: reference UI at examples/{ex}/ "
                             f"(run its server per examples/{ex}/README.md)")
            else:
                lines.append(f"{m}: expected examples/{ex}/ missing — skipped")
    return lines


def seed_state(dry_run: bool) -> list[str]:
    status_path = SHIPKIT_ROOT / "state" / "status.json"
    writer = SCRIPT_DIR / "status_writer.py"
    # Idempotent: if status.json already has a real generated_at, leave it.
    if status_path.exists():
        try:
            doc = json.loads(status_path.read_text(encoding="utf-8"))
            if doc.get("generated_at"):
                return ["state/status.json already seeded (has generated_at) — no-op"]
        except (json.JSONDecodeError, OSError):
            pass  # malformed/empty — fall through and (re)seed
    if dry_run:
        return ["would seed state/status.json via status_writer.py --init"]
    if not writer.exists():
        _err(f"status_writer.py not found at {writer}")
    cmd = [sys.executable, str(writer), "--init", "--force"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        _err(f"status_writer.py --init failed: {res.stderr.strip() or res.stdout.strip()}")
    return [f"seeded state/status.json ({res.stdout.strip()})"]


def smoke_test_lines(module_list: list[str], skills_target: Path) -> list[str]:
    has_surface = "status-surface" in module_list
    lines = [
        "",
        "Smoke test (the acceptance):",
        "  1. Open Claude Code in the shipkit dir; say \"you're First Mate\".",
        "  2. Run /ship-watch-start — preflight prints and passes (or names a NO-GO).",
        "  3. Drop a directive (a chat message or an inbox steer) -> the loop WAKES.",
        "  4. Flip a bookkeeping item (a status/queue change) -> the loop does NOT",
        "     wake; it shows up reconciled at the next tick. (That asymmetry = the",
        "     input model working.)",
        "  5. One quiet tick logs a telemetry line + writes state/status.json;",
        "     ship-watch-start exits and ship-tick self-paces.",
    ]
    if has_surface:
        lines += [
            "  6. (status-surface) cd examples/status-surface && start its server,",
            "     open it in a browser, confirm it renders state/status.json.",
        ]
    lines += [
        "",
        f"Skills installed under: {skills_target}",
        "At watch start the Mate reads core mate.md AND your mate.local.md "
        "overlay together —",
        "  the overlay's values fill the <!-- PREF: key --> seams in core "
        "(taste lives in",
        "  mate.local.md; machine paths/ports/repos live in loop.config.json).",
        "Re-run shipkit_init.py any time — it is idempotent (safe no-op); "
        "use --force-prefs",
        "  to regenerate mate.local.md or --force-config for loop.config.json.",
    ]
    return lines


def main() -> None:
    p = argparse.ArgumentParser(
        prog="shipkit_init.py",
        description="Deterministic apply step for Loop Mode onboarding "
                    "(the /shipkit-init interview calls this).",
    )
    p.add_argument("--answers", metavar="PATH",
                   help="JSON answers file from the interview (flags override its values)")
    p.add_argument("--preset", choices=["minimal", "standard", "full", "custom"],
                   help="Preset module set (custom requires --modules)")
    p.add_argument("--modules", nargs="*",
                   help="Explicit module list (for --preset custom or to override)")
    p.add_argument("--ship-root", help="ship_root for loop.config.json (default '.')")
    p.add_argument("--max-concurrent-crew", type=int, dest="max_crew",
                   help="max_concurrent_crew for loop.config.json (default 2)")
    p.add_argument("--install-mode", choices=["symlink", "copy"], default=None,
                   help=f"How to install skill dirs (default {DEFAULT_INSTALL_MODE} "
                        "on this platform — symlink on POSIX, copy on Windows "
                        "since symlinks there need admin/Developer Mode)")
    p.add_argument("--skills-target", metavar="DIR",
                   help=f"Where skills go (default {DEFAULT_SKILLS_TARGET}). "
                        "Use a temp dir for testing — never the real ~/.claude in tests.")
    p.add_argument("--force-config", action="store_true",
                   help="Regenerate loop.config.json even if it exists")
    p.add_argument("--pref", action="append", metavar="KEY=VALUE", default=[],
                   help="A behavioral pref for mate.local.md (repeatable). "
                        f"Keys: {', '.join(PREF_KEYS)}. Overrides --answers prefs.")
    p.add_argument("--house-note", action="append", metavar="TEXT", default=[],
                   help="A free-form house note for mate.local.md (repeatable). "
                        "Overrides --answers house_notes.")
    p.add_argument("--force-prefs", action="store_true",
                   help="Regenerate mate.local.md even if it exists")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the plan; touch nothing on disk")
    args = p.parse_args()

    answers: dict = {}
    if args.answers:
        answers = load_answers(Path(args.answers))

    # Flags override answers-file values.
    preset = args.preset or answers.get("preset")
    modules = args.modules if args.modules is not None else answers.get("modules")
    if args.ship_root is not None:
        answers["ship_root"] = args.ship_root
    if args.max_crew is not None:
        answers["max_concurrent_crew"] = args.max_crew

    # --pref KEY=VALUE flags override the answers-file prefs block.
    if args.pref:
        merged = dict(answers.get("prefs") or {})
        for item in args.pref:
            if "=" not in item:
                _err(f"--pref expects KEY=VALUE, got {item!r}")
            k, v = item.split("=", 1)
            k = k.strip()
            if k not in PREF_KEYS:
                _err(f"unknown pref key {k!r}. Known: {', '.join(PREF_KEYS)}.")
            merged[k] = v.strip()
        answers["prefs"] = merged
    if args.house_note:
        answers["house_notes"] = list(args.house_note)

    install_mode = (args.install_mode or answers.get("install_mode")
                    or DEFAULT_INSTALL_MODE)
    skills_target = Path(args.skills_target).expanduser() if args.skills_target \
        else Path(answers.get("skills_target", DEFAULT_SKILLS_TARGET)).expanduser()

    module_list = resolve_modules(preset, modules)

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}shipkit init — preset={preset or 'custom'} "
          f"modules={module_list} mode={install_mode}")
    print(f"{prefix}skills target: {skills_target}")
    print()

    # Honesty: surface any planned (unshipped) modules the user selected.
    planned = [m for m in module_list if MODULES[m]["status"] != "shipped"]
    if planned:
        print(f"NOTE: these selected modules are PLANNED (no code ships yet) and "
              f"will be skipped: {', '.join(planned)}")
        print()

    cfg = build_config(answers)

    plan: list[str] = []
    plan.append("== loop.config.json (machine config) ==")
    plan += [f"  {ln}" for ln in write_config(cfg, args.dry_run, args.force_config)]
    plan.append("== mate.local.md (behavioral prefs / taste) ==")
    plan += [f"  {ln}" for ln in write_prefs(answers, args.dry_run, args.force_prefs)]
    plan.append("== skills ==")
    plan += [f"  {ln}" for ln in install_skills(module_list, skills_target,
                                                install_mode, args.dry_run)]
    ex_lines = report_examples(module_list, args.dry_run)
    if ex_lines:
        plan.append("== examples (reference UIs, run in-place) ==")
        plan += [f"  {ln}" for ln in ex_lines]
    plan.append("== state/status.json ==")
    plan += [f"  {ln}" for ln in seed_state(args.dry_run)]

    for line in plan:
        print(f"{prefix}{line}")

    for line in smoke_test_lines(module_list, skills_target):
        print(f"{prefix}{line}" if line else "")


if __name__ == "__main__":
    main()
