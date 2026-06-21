#!/usr/bin/env python3
"""shipkit_init.py — the deterministic APPLY step for Loop Mode onboarding.

This is the plumbing the `/shipkit-init` interview skill calls once it has
gathered answers from the Captain. The conversational interview is the main
experience; this script is the small, idempotent, re-runnable apply step that
actually wires the bits. It does FOUR things, all safe to repeat:

  1. Write loop.config.json from loop.config.example.json, populated with answers.
  2. Symlink-or-copy the selected skills/ dirs into the target skills dir
     (default ~/.claude/skills; --skills-target overrides for testing).
  3. Seed state/status.json (delegates to status_writer.py --init).
  4. Print the smoke-test steps.

PRESET -> MODULE mapping lives in PRESETS below — the ONE source of truth the
skill documents. Be honest about what shipkit ships TODAY: only `core` and the
`status-surface` reference UI exist. New modules slot into PRESETS as they land.

Idempotent by design: a second run is a safe no-op (config already populated,
skills already linked, state already seeded). Always offers --dry-run.

Stdlib only — no pip installs. Cross-platform (pathlib + json + shutil).

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
    "install_mode": "symlink"
  }
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
        data = json.loads(path.read_text())
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
        example = json.loads(example_path.read_text())
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
    tmp.write_text(serialized)
    os.rename(tmp, target)
    return [f"wrote loop.config.json (ship_root={cfg['ship_root']!r}, "
            f"repos={len(cfg['repos'])}, max_crew={cfg['max_concurrent_crew']})"]


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
        os.symlink(src, dst, target_is_directory=True)
        return f"{label}: symlinked -> {dst}"
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
            doc = json.loads(status_path.read_text())
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
        "Re-run shipkit_init.py any time — it is idempotent (safe no-op).",
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
                   help="How to install skill dirs (default symlink)")
    p.add_argument("--skills-target", metavar="DIR",
                   help=f"Where skills go (default {DEFAULT_SKILLS_TARGET}). "
                        "Use a temp dir for testing — never the real ~/.claude in tests.")
    p.add_argument("--force-config", action="store_true",
                   help="Regenerate loop.config.json even if it exists")
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

    install_mode = (args.install_mode or answers.get("install_mode") or "symlink")
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
    plan.append("== loop.config.json ==")
    plan += [f"  {ln}" for ln in write_config(cfg, args.dry_run, args.force_config)]
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
