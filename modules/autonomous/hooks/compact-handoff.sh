#!/bin/bash
# PreCompact + SessionStart(compact) hook for the ship-mate seat (wired in agents/ship-mate.md).
# Logic and seat guard: scripts/compact_handoff.py. Exit 2 would block compaction, so always 0.
HERE="$(cd "$(dirname "$0")" && pwd)"
python3 "$HERE/../scripts/compact_handoff.py" || true
exit 0
