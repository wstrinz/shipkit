#!/usr/bin/env bash
# classify_input.sh <inputfile> → echoes "wake" or "batch"
#
# The Loop Mode INPUT-MODEL seam. Classify an incoming item (an inbox edit, a
# drop file from an external process, a queued signal) into:
#
#   WAKE  = a directive someone is waiting on → interrupt the loop NOW.
#   BATCH = bookkeeping / sensor-noise → the live ticket frontmatter already
#           serves the Captain's views, so it is reconciled in ONE pass at the
#           next tick (the ship-tick "Check inbox / batch-reconcile" step).
#
# The wake-monitor calls this on each net-new item and only wakes the Mate on
# "wake". Batch-class items are still recorded in the seen-set (so they don't
# re-fire) but do NOT wake — they drain at the next tick's reconcile.
#
# PRINCIPLE: default to WAKE when ambiguous — a missed steer costs more than an
# extra tick (this is the floor; never silently swallow something that might be
# a directive).
#
# -------------------------------------------------------------------------
# DEPLOYMENT OVERRIDE — edit the two mapping blocks below for your sensors.
# -------------------------------------------------------------------------
# A fresh Ship has DIFFERENT sensors (no CI bot, a different chat surface) but
# the SAME classes. Map your own signal sources here; the shape is fixed, the
# signal list is configuration.
#
# BATCH_FILENAME_GLOBS : basename globs that are pure sensor-noise → batch.
#     Empty by default (no sensors assumed); add your own bot/CI prefixes.
#     Each entry must be a SINGLE token with no spaces (it's matched unquoted in
#     a `case`); use one array entry per pattern, e.g. ('pr-buddy-*' '*ci-failure*').
# BATCH_TYPES          : frontmatter `type:` values that are bookkeeping → batch.
# WAKE_TYPES           : frontmatter `type:` values that are directives → wake.
# Self-authored items (`source: mate`, or your loop's own author tag) → batch,
#     so the loop never wakes itself on its own surfaces.
# -------------------------------------------------------------------------

set -euo pipefail

# --- mapping blocks (override per deployment) ---------------------------
BATCH_FILENAME_GLOBS=(
  # 'pr-buddy-*'      # example: a CI bot that re-drops unchanged PR state
  # '*ci-failure*'    # example: CI failure re-drops (poll live state at tick time)
)
BATCH_TYPES=(status-applied close-applied)
WAKE_TYPES=(steer comment status-request ask)
SELF_AUTHOR_TAGS=(mate)   # values of `source:` that mean "the loop wrote this"
# ------------------------------------------------------------------------

if [ "${1:-}" = "--test" ]; then
  echo "classify_input.sh self-test:" >&2
  echo "  Run against a sample file: classify_input.sh <inputfile>" >&2
  echo "  Expected mappings (with default config):" >&2
  echo "    type: steer | comment | status-request | ask   -> wake" >&2
  echo "    type: status-applied | close-applied            -> batch" >&2
  echo "    source: mate                                    -> batch" >&2
  echo "    (no recognized type, e.g. a plain chat message) -> wake" >&2
  echo "  To test, create a fixture file and pass it as the argument." >&2
  exit 0
fi

f="${1:?usage: classify_input.sh <inputfile>   (or --test for the contract)}"
base=$(basename "$f")

# 1. Filename-glob sensor-noise → batch (checked first; cheapest).
#    The ${arr[@]+...} guard keeps an EMPTY array safe under `set -u` on the
#    macOS-default bash 3.2 (a bare ${arr[@]} on an empty array is "unbound").
for g in ${BATCH_FILENAME_GLOBS[@]+"${BATCH_FILENAME_GLOBS[@]}"}; do
  # shellcheck disable=SC2053
  case "$base" in
    $g) echo batch; exit 0 ;;
  esac
done

# 2. Frontmatter-driven classification. Tolerant of both YAML (type:) and
#    JSON ("type":) shapes; missing file/fields are non-fatal.
type=$(grep -m1 -E '^[[:space:]]*"?type"?[[:space:]]*:' "$f" 2>/dev/null | sed -E 's/.*type"?[[:space:]]*:[[:space:]]*"?//; s/["[:space:],].*//' || true)
source=$(grep -m1 -E '^[[:space:]]*"?source"?[[:space:]]*:' "$f" 2>/dev/null | sed -E 's/.*source"?[[:space:]]*:[[:space:]]*"?//; s/["[:space:],].*//' || true)

# Self-authored surfaces must never wake the loop.
for tag in ${SELF_AUTHOR_TAGS[@]+"${SELF_AUTHOR_TAGS[@]}"}; do
  if [ "$source" = "$tag" ]; then echo batch; exit 0; fi
done

# Directives → wake.
for t in ${WAKE_TYPES[@]+"${WAKE_TYPES[@]}"}; do
  if [ "$type" = "$t" ]; then echo wake; exit 0; fi
done

# Bookkeeping → batch.
for t in ${BATCH_TYPES[@]+"${BATCH_TYPES[@]}"}; do
  if [ "$type" = "$t" ]; then echo batch; exit 0; fi
done

# Ambiguous (no recognized type — e.g. a plain chat message) → wake.
echo wake
