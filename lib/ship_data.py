"""Where the ship's data lives (DATA.md). With a data root, the data dirs are symlinks into
it and the root data files (captain.md, the queue files, DECISIONS.local.md) live at its top;
without one, everything is in the ship dir. Stdlib only."""

import os
from pathlib import Path

STUB_MARKER = "<!-- shipkit: data-root pointer -->"


def is_stub(path) -> bool:
    try:
        return Path(path).read_text(encoding="utf-8").startswith(STUB_MARKER)
    except (OSError, UnicodeDecodeError):
        return False


def data_root(ship_root) -> Path:
    """The directory holding the root data files. That is the parent of `state/`'s link
    target, but only when it is evidently a data root (the ship-root queue.md is a pointer
    stub, or that parent holds a queue.md); otherwise the ship dir itself."""
    ship = Path(ship_root)
    state = ship / "state"
    if state.is_symlink():
        parent = Path(os.path.realpath(state)).parent
        if is_stub(ship / "queue.md") or (parent / "queue.md").is_file():
            return parent
    return ship
