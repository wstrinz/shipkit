#!/usr/bin/env bash
# classify_input.sh <inputfile> → echoes "wake", "batch", or "silent"
#
# The Loop Mode INPUT-MODEL seam. Classify an incoming item (an inbox edit, a
# drop file from an external process, a queued signal) into one of three
# wake-classes:
#
#   WAKE   = a directive someone is waiting on → interrupt the loop NOW.
#   BATCH  = bookkeeping / sensor-noise → the live ticket frontmatter already
#            serves the Captain's views, so it is reconciled in ONE pass at the
#            next tick (the ship-tick "Check inbox / batch-reconcile" step).
#   SILENT = pure noise → don't wake AND don't surface. Recorded in the seen-set
#            (so it doesn't re-fire) and logged, but never lands on a wake OR a
#            batch surface. For sources that are genuinely log-only.
#
# CONSUMER SEMANTICS (the contract the wake-monitor + tick honor):
#   - The wake-monitor wakes the Mate ONLY on "wake".
#   - "batch" items are recorded in the seen-set (so they don't re-fire) but do
#     NOT wake — they drain at the next tick's reconcile pass.
#   - "silent" items are recorded in the seen-set too, but are suppressed from
#     BOTH the wake path AND the batch-reconcile surface (log-only).
#
# =========================================================================
# THE INPUT ENVELOPE (v1) — declared inputs
# =========================================================================
# Producers should DECLARE their intent rather than leave the classifier to
# guess. Every input may carry a small standard metadata header — YAML
# frontmatter for file-drops, the JSON-field equivalent for signal/thread
# events:
#
#   ---
#   shipkit_input: v1          # marks a declared input (the envelope marker)
#   source: status-surface     # producer id (free string)
#   kind: steer                # semantic type (steer|comment|status-request
#                              #   |notification|sensor-redrop|...)
#   wake_class: wake           # AUTHORITATIVE wake-class: wake | batch | silent
#   ---
#
# JSON equivalent (thread/signal events):
#   {"shipkit_input":"v1","source":"...","kind":"...","wake_class":"wake", ...}
#
# Only `wake_class` is authoritative; the others are descriptive (so undeclared
# legacy inputs still classify). A producer that declares `wake_class` controls
# its own fate; one that declares only `kind` gets the documented default; one
# that declares neither falls to the heuristic AND triggers a stderr warning so
# it gets noticed and migrated.
#
# THE 3-STEP CLASSIFIER LADDER:
#   1. `wake_class` declared  → use it verbatim (authoritative; no guessing).
#   2. else `kind` declared   → documented kind→class default table (below).
#   3. else                   → content heuristic, AND warn on stderr
#                               ("undeclared input <path> — heuristically
#                               classified <class>"). The warning is the point:
#                               the heuristic is a safety net, not the primary
#                               path, and undeclared sources get fixed over time.
#
# kind → class default table (step 2):
#   steer | comment | status-request | ask  → wake
#   notification                             → batch
#   sensor-redrop                            → batch
#   (any other / unrecognized kind)          → wake  (directive-leaning floor)
#
# -------------------------------------------------------------------------
# DEPLOYMENT OVERRIDE — edit the mapping blocks below for your sensors.
# -------------------------------------------------------------------------
# A fresh Ship has DIFFERENT sensors (no CI bot, a different chat surface) but
# the SAME classes. Map your own signal sources here; the shape is fixed, the
# signal list is configuration. These apply to the heuristic (step 3) path and
# the always-on self-author guard.
#
# BATCH_FILENAME_GLOBS : basename globs that are pure sensor-noise → batch.
#     Empty by default (no sensors assumed); add your own bot/CI prefixes.
#     Each entry must be a SINGLE token with no spaces (it's matched unquoted in
#     a `case`); use one array entry per pattern, e.g. ('pr-buddy-*' '*ci-failure*').
# BATCH_TYPES          : frontmatter `type:` values that are bookkeeping → batch.
# WAKE_TYPES           : frontmatter `type:` values that are directives → wake.
# SELF_AUTHOR_TAGS     : `source:` values that mean "the loop wrote this" → batch,
#     so the loop never wakes itself on its own surfaces.
#
# PRINCIPLE: default to WAKE when ambiguous — a missed steer costs more than an
# extra tick (this is the floor; never silently swallow something that might be
# a directive). `silent` is only ever reached via an explicit declaration.
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
  # Defer to the fixture runner if present; otherwise print the contract.
  runner="$(cd "$(dirname "$0")" && pwd)/../tests/test-classify-input.sh"
  if [ -x "$runner" ]; then
    exec "$runner"
  fi
  echo "classify_input.sh self-test (no fixture runner found):" >&2
  echo "  Run against a sample file: classify_input.sh <inputfile>" >&2
  echo "  3-step ladder: wake_class (authoritative) -> kind table -> heuristic." >&2
  echo "  Output is one of: wake | batch | silent" >&2
  echo "  Declared:  wake_class: wake|batch|silent  -> used verbatim" >&2
  echo "  kind only: steer|comment|status-request|ask -> wake;" >&2
  echo "             notification|sensor-redrop        -> batch" >&2
  echo "  Undeclared: content heuristic + a stderr warning" >&2
  exit 0
fi

f="${1:?usage: classify_input.sh <inputfile>   (or --test for the contract)}"
base=$(basename "$f")

# Read declared envelope fields. Tolerant of both YAML (key:) and JSON ("key":)
# shapes; missing file/fields are non-fatal (empty string).
read_field() {
  # $1 = field name. Echoes the first scalar value, or "" if absent.
  # Matches YAML (key: val at line start) AND inline JSON ({"key":"val",...}):
  # the key must be preceded by start-of-line, '{', ',', or whitespace so a
  # bare `kind` never matches a substring like `some_kind`.
  grep -m1 -E "(^|[[:space:],{])\"?$1\"?[[:space:]]*:" "$f" 2>/dev/null \
    | sed -E "s/.*[^_a-zA-Z]$1\"?[[:space:]]*:[[:space:]]*\"?//; s/^$1\"?[[:space:]]*:[[:space:]]*\"?//; s/[\"[:space:],}].*//" \
    || true
}

wake_class=$(read_field wake_class)
kind=$(read_field kind)
type=$(read_field type)
source=$(read_field source)

# Self-authored surfaces must never wake the loop (always-on guard, applies
# regardless of declaration — the loop shouldn't wake itself even if a self-
# authored producer mistakenly stamped wake_class: wake).
for tag in ${SELF_AUTHOR_TAGS[@]+"${SELF_AUTHOR_TAGS[@]}"}; do
  if [ "$source" = "$tag" ]; then echo batch; exit 0; fi
done

# --- STEP 1: wake_class declared → authoritative -------------------------
case "$wake_class" in
  wake|batch|silent) echo "$wake_class"; exit 0 ;;
  "") : ;;  # not declared — fall through
  *)
    echo "classify_input: unknown wake_class '$wake_class' in $f — ignoring declaration, falling through" >&2
    ;;
esac

# --- STEP 2: kind declared → documented kind→class default table ---------
if [ -n "$kind" ]; then
  case "$kind" in
    steer|comment|status-request|ask) echo wake; exit 0 ;;
    notification|sensor-redrop)        echo batch; exit 0 ;;
    *)                                 echo wake; exit 0 ;;  # directive-leaning floor
  esac
fi

# --- STEP 3: content heuristic (safety net) + WARN -----------------------
# No declaration → fall back to the legacy heuristic and warn so the source
# gets noticed and migrated.

# 3a. Filename-glob sensor-noise → batch (checked first; cheapest).
#     The ${arr[@]+...} guard keeps an EMPTY array safe under `set -u` on the
#     macOS-default bash 3.2 (a bare ${arr[@]} on an empty array is "unbound").
for g in ${BATCH_FILENAME_GLOBS[@]+"${BATCH_FILENAME_GLOBS[@]}"}; do
  # shellcheck disable=SC2053
  case "$base" in
    $g)
      echo "classify_input: undeclared input $f — heuristically classified batch" >&2
      echo batch; exit 0
      ;;
  esac
done

# 3b. Legacy frontmatter `type:` classification.
heuristic="wake"
for t in ${WAKE_TYPES[@]+"${WAKE_TYPES[@]}"}; do
  if [ "$type" = "$t" ]; then heuristic="wake"; break; fi
done
for t in ${BATCH_TYPES[@]+"${BATCH_TYPES[@]}"}; do
  if [ "$type" = "$t" ]; then heuristic="batch"; break; fi
done
# (No recognized type — e.g. a plain chat message — stays the "wake" floor.)

echo "classify_input: undeclared input $f — heuristically classified $heuristic" >&2
echo "$heuristic"
