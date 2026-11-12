#!/usr/bin/env python3
"""Enumerate the shipkit FRAMEWORK files to sync from upstream, derived from the manifests so
the list can't go stale as the tiered layout grows. Prints one ship-root-relative path per
line for pull-upstream.sh to consume.

Sources:
  - presets.json + every module's module.json -> each module's agents/hooks/scripts/lib/
    templates/role_docs/doc/prefs_example/tests, plus the module.json itself.
  - the installer + manifest at root (shipkit_init.py, presets.json).
  - the top-level generic docs (README.md, CLAUDE.md, DATA.md) + the sync tooling.

NEVER synced: the ship's DATA (DATA_ENTRIES below; see DATA.md) and machine/taste files
(loop.config.json, mate.local.md). The .example variants ARE generic and ARE synced.

Usage: _sync_manifest.py [<upstream-dir>] [--local <ship-dir>]
  <upstream-dir>   where to enumerate from (default: this script's ship root)
  --local DIR      the ship being synced INTO: refuse (exit 1, print nothing) if any path
                   would land on its data — a data entry, or anywhere under its data root
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The ship's data, ship-root-relative. shipkit_init.py --data-root moves these into the data
# root: each dir is symlinked back; each file is left as a pointer stub, never a symlink
# (Claude Code's Edit/Write refuse file symlinks, and atomic-save writers replace them).
DATA_FILES = ("captain.md", "queue.md", "queue-archive.md", "DECISIONS.local.md")
DATA_DIRS = ("inbox", "logs", "projects", "state", "docs")
DATA_ENTRIES = DATA_FILES + DATA_DIRS

ROOT_FILES = [
    "README.md", "CLAUDE.md", "DATA.md", ".rgignore", "UPGRADING.md", "DECISIONS.md",
    "DECISIONS.local.example.md", "shipkit_init.py", "presets.json",
    "loop.config.example.json", "mate.local.example.md",
    "scripts/pull-upstream.sh", "scripts/_sync_manifest.py",
]

# Per-module manifest keys whose values are folder-relative file paths to sync.
FILE_KEYS = ("agents", "hooks", "scripts", "templates", "tests", "role_docs")


def module_dirs(ship_root: Path):
    """Every module folder = core/, ui/, and each modules/<name>/ that has a module.json."""
    dirs = []
    for special in ("core", "ui"):
        d = ship_root / special
        if (d / "module.json").is_file():
            dirs.append(d)
    modules = ship_root / "modules"
    if modules.is_dir():
        for d in sorted(modules.iterdir()):
            if (d / "module.json").is_file():
                dirs.append(d)
    return dirs


def sync_files(ship_root: Path) -> list:
    """Ship-root-relative paths of every framework file under `ship_root`."""
    ship_root = ship_root.resolve()
    out = []

    def add(path: Path):
        if path.is_file():
            # Normalize manifest paths that climb out of the module dir
            # (a "../<path>" entry collapses to its repo-relative form).
            r = str(Path(os.path.normpath(path)).relative_to(ship_root))
            if r not in out:
                out.append(r)

    for f in ROOT_FILES:
        add(ship_root / f)

    # modules/README.md catalog (generic)
    add(ship_root / "modules" / "README.md")

    for d in module_dirs(ship_root):
        manifest = d / "module.json"
        add(manifest)
        try:
            meta = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for key in FILE_KEYS:
            for relpath in meta.get(key, []):
                # skill dirs are folders, not files -> expand to their files
                target = d / relpath
                if target.is_dir():
                    for child in sorted(target.rglob("*")):
                        add(child)
                else:
                    add(target)
        for single in ("doc", "prefs_example"):
            if meta.get(single):
                add(d / meta[single])
        # skill folders are listed under "skills" as dir paths
        for relpath in meta.get("skills", []):
            sk = d / relpath
            if sk.is_dir():
                for child in sorted(sk.rglob("*")):
                    add(child)
        # the declared lib[] deps live in lib/ at root
        for libfile in meta.get("lib", []):
            add(ship_root / "lib" / libfile)
    return out


def _within(path: str, root: str) -> bool:
    # Casefolded: macOS and Windows filesystems are case-insensitive by default.
    path, root = path.casefold(), root.casefold().rstrip(os.sep)
    return path == root or path.startswith(root + os.sep)


def data_violations(local: Path, paths) -> list:
    """Sync paths that would write onto `local`'s data: a data entry by name, or anything
    that resolves into a data entry or into the data root its symlinks point at."""
    local_real = os.path.realpath(local)
    names = {e.casefold() for e in DATA_ENTRIES}
    protected = set()
    for entry in DATA_ENTRIES:
        link = local / entry
        protected.add(os.path.realpath(link))
        if link.is_symlink():
            data_root = os.path.dirname(os.path.realpath(link))
            # A data root that contains the kit would protect every framework path.
            if not _within(local_real, data_root):
                protected.add(data_root)
    bad = []
    for p in paths:
        real = os.path.realpath(local / p)
        if Path(p).parts[0].casefold() in names or any(_within(real, r) for r in protected):
            bad.append(p)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description="List the shipkit framework files to sync.")
    ap.add_argument("upstream", nargs="?", default=str(HERE.parent))
    ap.add_argument("--local", metavar="DIR")
    args = ap.parse_args(argv)
    out = sync_files(Path(args.upstream))
    if args.local:
        bad = data_violations(Path(args.local), out)
        if bad:
            print("ERROR: refusing to sync — these upstream paths would write into the "
                  "ship's data (see DATA.md):", file=sys.stderr)
            for p in bad:
                print(f"  {p}", file=sys.stderr)
            return 1
    for line in out:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
