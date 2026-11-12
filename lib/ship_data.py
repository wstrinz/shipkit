"""Where the ship's data lives (DATA.md). With a data root, the data dirs are symlinks into
it and the root data files (captain.md, the queue files, DECISIONS.local.md) live at its top;
without one, everything is in the ship dir. Stdlib only."""

import os
from pathlib import Path


def data_root(ship_root) -> Path:
    """The directory holding the root data files: the parent of `state/`'s link target when
    `state/` is a symlink, else the ship dir itself."""
    state = Path(ship_root) / "state"
    if state.is_symlink():
        return Path(os.path.realpath(state)).parent
    return Path(ship_root)
