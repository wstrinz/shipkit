#!/usr/bin/env python3
"""queue_move.py: move one queue entry to another section. Mate-only (the queue is Mate-owned).

  queue_move.py --ticket ID --from "Awaiting Captain" --to Done --note "merged 10-03 (gh)"
  queue_move.py --ticket ID --from "Awaiting Captain" --to Done --replace "- [ID](...) - one line"
  queue_move.py ... [--at top|end] [--dry-run] [--queue PATH] [--archive PATH]

Paths default to queue.md / queue-archive.md under $SHIP_ROOT (else the ship root this module lives in).

An entry is a column-0 list line linking the ticket (`N.`, `0a.`, `1.2.`, `-`, `*`, `+`: the markers
queue_split.py recognises) plus the indented continuation lines under it. Headings and entries inside an
HTML comment block are ignored, as in queue_split.py. --ticket must match exactly ONE entry in --from,
else it refuses. --at picks where it lands in the target section: `end` (after the last non-blank
line) or `top` (after the section's leading comment blocks and blank lines). Default: `top` for Done
(newest-first), `end` everywhere else, because the queue appends and never inserts (an insert silently
re-ranks everything below it). --note appends " | <note>" to the entry's first line. --replace swaps the
whole entry for the given text. Priority numbers are left alone; renumbering is the Mate's call.

Sections resolve in the live file first, then the archive (when it exists). After a split, Ready
(parked), Backlog and Shelved exist only in the archive, so moves there cross files; Done resolves to the
live "Done (recent)" and only queue_split.py ages entries into the archive's Done. The target file is
written before the source file (a crash duplicates the entry, never loses it).
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from queue_split import ARCHIVE_SECTIONS, ENTRY_RE, HEADING_RE, canon, ship_root  # noqa: E402


def comment_mask(lines):
    """True for every line of an HTML comment block, by the same rule queue_split parses with."""
    mask, inside = [], False
    for l in lines:
        hit = inside or l.startswith("<!--")
        mask.append(hit)
        if hit:
            inside = "-->" not in l
    return mask


def sections(lines):
    out, cur = {}, None
    for i, (l, hidden) in enumerate(zip(lines, comment_mask(lines))):
        m = None if hidden else HEADING_RE.match(l)
        if m:
            cur = m.group(1).strip()
            out[cur] = [i, len(lines)]
            prev = [k for k in out if k != cur]
            if prev:
                out[prev[-1]][1] = min(out[prev[-1]][1], i)
    return out


def write_atomic(path, lines):
    mode = path.stat().st_mode & 0o7777 if path.exists() else 0o644
    fd, tmp = tempfile.mkstemp(prefix=".qmove-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(lines))
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def where(files, name):
    """[(file key, heading)] that can hold `name`, live file first. The archive counts only if it exists."""
    archived = canon(name) in ARCHIVE_SECTIONS
    live = [("live", h) for h in sections(files["live"]) if h == name or (archived and canon(h) == canon(name))]
    arch = []
    if files["arch"] is not None and archived:
        arch = [("arch", h) for h in sections(files["arch"]) if canon(h) == canon(name)]
    return live + arch


def insert_at(rest, d0, d1, at):
    if at == "top":
        hidden = comment_mask(rest)
        ins = d0 + 1
        while ins < d1 and (not rest[ins].strip() or hidden[ins]):
            ins += 1
        return ins
    filled = [i for i in range(d0 + 1, d1) if rest[i].strip()]
    return filled[-1] + 1 if filled else d0 + 1


def main(argv=None):
    root = ship_root()
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--at", choices=("top", "end"), help="default: top for Done, end otherwise")
    ap.add_argument("--note")
    ap.add_argument("--replace")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--queue", default=str(root / "queue.md"))
    ap.add_argument("--archive", default=str(root / "queue-archive.md"))
    a = ap.parse_args(argv)

    paths = {"live": Path(a.queue), "arch": Path(a.archive)}
    def load(p):
        with open(p, encoding="utf-8", newline="") as f:
            return f.read().split("\n")

    files = {"live": load(paths["live"]), "arch": load(paths["arch"]) if paths["arch"].exists() else None}

    dst = where(files, a.dst)
    if not dst:
        sys.exit(f"no section '## {a.dst}' (have: {', '.join(sections(files['live']))})")
    link = f"[{a.ticket}]("
    found = []
    for key, head in where(files, a.src):
        s0, s1 = sections(files[key])[head]
        hidden = comment_mask(files[key])
        hit = [i for i in range(s0 + 1, s1) if not hidden[i] and ENTRY_RE.match(files[key][i]) and link in files[key][i]]
        found += [(key, s1, i) for i in hit]
    if len(found) != 1:
        sys.exit(f"REFUSED: {len(found)} entries for {a.ticket} in '{a.src}' (lines {[(k, i + 1) for k, _, i in found]})")
    skey, s1, start = found[0]
    lines = files[skey]
    end = start + 1
    while end < s1 and lines[end].startswith((" ", "\t")) and lines[end].strip():
        end += 1
    entry = lines[start:end]
    if a.replace:
        entry = a.replace.split("\n")
    elif a.note:
        entry[0] = f"{entry[0]} | {a.note}"

    files[skey] = lines[:start] + lines[end:]
    dkey, dhead = dst[0]
    at = a.at or ("top" if canon(dhead) == "Done" else "end")
    rest = files[dkey]
    d0, d1 = sections(rest)[dhead]
    ins = insert_at(rest, d0, d1, at)
    before = [""] if rest[ins - 1].startswith("## ") else []
    after = [""] if ins < len(rest) and rest[ins].startswith("## ") else []
    files[dkey] = rest[:ins] + before + entry + after + rest[ins:]
    print(f"{a.ticket}: '{a.src}' ({skey}) L{start + 1}-{end} ({end - start} lines) → {at} of '{dhead}' ({dkey}, L{ins + 1})")
    if a.dry_run:
        print("  first line:", entry[0][:160])
        return
    for key in dict.fromkeys([dkey, skey]):
        write_atomic(paths[key], files[key])


if __name__ == "__main__":
    main()
