#!/usr/bin/env python3
"""queue_split.py: split the live queue into queue + queue-archive. Mate-only (the queue is Mate-owned).

  queue_split.py [--queue PATH] [--archive PATH] [--done-days N] [--park-ready ID,ID] [--today YYYY-MM-DD] [--apply] [-v]

Paths default to queue.md / queue-archive.md under $SHIP_ROOT (else the ship root this module lives in),
or under its data root when it has one (DATA.md; lib/ship_data.py), never the ship-root pointer stubs.
--done-days defaults to $SHIP_QUEUE_DONE_DAYS, else 14. The script reads no prefs file: the Mate passes its
`queue_done_days` pref (mate.local.md) as --done-days, or exports the variable.

Dry-run by default. Moves, from the live file into the archive (appended; an existing archive is merged):
  - `## Backlog`, `## Shelved` (and a stray `## Ready (parked)`): wholesale, heading notes included.
  - `## Done*` entries older than --done-days. Age = the newest `| key: YYYY-MM-DD` stamp; else the NEWEST
    valid `MM-DD` anywhere on the first line (a conservative max: one recent date keeps the entry live);
    else undated, which MOVES and is flagged. The date source is printed per entry.
  - `## Ready` entries whose first ticket link is one of --park-ready, into `## Ready (parked)`.
An entry is a column-0 list item (`N.`/`0a.`/`-`/`*`) plus every line up to the next entry or heading;
HTML comment blocks directly before an entry travel with it, blank lines directly after it too. Column-0
non-list lines (group headers such as `**GROUP**`) belong to the entry above them; the report flags every
moved entry that carries one. No entry text is rewritten. Archive Done is newest-first (moved entries go
on top); the other archive sections append. Before --apply the script proves the non-blank lines (section
headings aside) are EXACTLY the same multiset before and after, so a lost or a duplicated line refuses;
it writes the archive first and the queue second, re-reads both and re-checks, and restores the originals
if that fails. Lines split on "\\n" only, so U+2028 or form feeds inside an entry cannot make fake lines.
Known limits: a `## ` line or a list item inside a fenced code block is not recognised as such, and an
unindented continuation line is treated as part of the entry above it.
"""
import argparse
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from ship_data import data_root  # noqa: E402

DEFAULT_DONE_DAYS = 14
ARCHIVE_SECTIONS = ["Ready (parked)", "Backlog", "Shelved", "Done"]
WHOLESALE = {"Backlog", "Shelved", "Ready (parked)"}
ARCHIVE_TEMPLATE = Path(__file__).resolve().parent / "templates" / "queue-archive.md"
ARCHIVE_NOTE = (
    "# Queue Archive\n\n"
    "> **Owned by First Mate.** Crew: read only. **Not read at boot.** Parked Ready, Backlog, Shelved and\n"
    "> older Done live here, split out of the live queue by `queue_split.py` (modules/queue-split/).\n"
    "> Ticket status is unchanged: Ready (parked) = `ready`, Backlog = `backlog`, Shelved = `shelved`, Done = `done`.\n\n"
)

HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
ENTRY_RE = re.compile(r"^(?:\d+(?:\.\d+)?(?:[A-Za-z][A-Za-z0-9]*)?\.|[-*+])\s+\S")
STAMP_RE = re.compile(r"\|\s*[A-Za-z]+\s*:\s*(\d{4}-\d{2}-\d{2})")
MMDD_RE = re.compile(r"(?<![\d-])(\d{2})-(\d{2})(?![\d-])")
TICKET_RE = re.compile(r"\]\(projects/[^/)]+/tickets/([^/)]+?)\.md\)")


def ship_root():
    return Path(os.environ.get("SHIP_ROOT") or Path(__file__).resolve().parents[2])


def canon(name):
    if name == "Ready (parked)":
        return name
    return re.sub(r"\s*\(.*\)\s*$", "", name)


def is_blank(ln):
    return not ln.strip()


def split_lines(text):
    return re.findall(r"[^\n]*\n|[^\n]+", text)


class Entry:
    def __init__(self, head, body):
        self.head, self.body, self.tail = head, body, []

    def lines(self):
        return self.head + self.body + self.tail

    def first(self):
        return self.body[0].rstrip("\n")

    def col0_lines(self):
        out, in_comment = [], False
        for ln in self.body[1:]:
            if in_comment or ln.startswith("<!--"):
                in_comment = "-->" not in ln
            elif ln.strip() and not ln[0].isspace():
                out.append(ln.rstrip("\n"))
        return out


class Section:
    def __init__(self, heading, name):
        self.heading, self.name = heading, name
        self.canon = canon(name) if name else None
        self.preamble, self.entries, self.trailer = [], [], []

    def lines(self):
        out = [self.heading] if self.heading else []
        out += self.preamble
        for e in self.entries:
            out += e.lines()
        return out + self.trailer

    def nbytes(self):
        return len("".join(self.lines()).encode())


def split_pending(pending):
    i = 0
    while i < len(pending) and is_blank(pending[i]):
        i += 1
    return pending[:i], pending[i:]


def parse_body(sec, lines):
    pending, cur, in_comment = [], None, False
    for ln in lines:
        if in_comment:
            in_comment = "-->" not in ln
            pending.append(ln)
        elif ln.startswith("<!--"):
            in_comment = "-->" not in ln
            pending.append(ln)
        elif is_blank(ln):
            pending.append(ln)
        elif ENTRY_RE.match(ln):
            if cur is None:
                sec.preamble += pending
                head = []
            else:
                cur.tail, head = split_pending(pending)
            cur = Entry(head, [ln])
            sec.entries.append(cur)
            pending = []
        elif cur is None:
            sec.preamble += pending + [ln]
            pending = []
        else:
            cur.body += pending + [ln]
            pending = []
    if cur is None:
        sec.preamble += pending
    else:
        cur.tail, sec.trailer = split_pending(pending)


class Doc:
    def __init__(self, text):
        raw = split_lines(text)
        self.sections = []
        top = Section(None, None)
        self.top = top
        chunk, cur, in_comment = [], top, False
        for ln in raw:
            m = None if in_comment else HEADING_RE.match(ln)
            if m:
                parse_body(cur, chunk)
                cur, chunk = Section(ln, m.group(1).strip()), []
                self.sections.append(cur)
            else:
                if in_comment or ln.startswith("<!--"):
                    in_comment = "-->" not in ln
                chunk.append(ln)
        parse_body(cur, chunk)

    def text(self):
        return "".join(self.top.lines() + [ln for s in self.sections for ln in s.lines()])

    def find(self, name):
        return next((s for s in self.sections if s.canon == name), None)

    def stats(self):
        return [(s.name, len(s.entries), s.nbytes()) for s in self.sections]


def archive_seed():
    """Text of a brand-new archive: the module's template, else the built-in note plus bare sections."""
    seed = read(ARCHIVE_TEMPLATE)
    if seed is not None:
        return seed
    doc = Doc(ARCHIVE_NOTE)
    for name in ARCHIVE_SECTIONS:
        add_section(doc, name)
    return doc.text()


def separate(doc, sections):
    """A section whose entries changed ends in a blank line before the next heading (blank lines are not data)."""
    for s in sections:
        out = s.lines()
        if s is not doc.sections[-1] and out and not is_blank(out[-1]):
            s.trailer.append("\n")


def add_section(doc, name):
    s = Section(f"## {name}\n", name)
    s.preamble, s.trailer = ["\n"], ["\n"]
    doc.sections.append(s)
    return s


def ensure_nl(entry):
    if entry.lines() and not entry.lines()[-1].endswith("\n"):
        (entry.tail or entry.body)[-1] += "\n"


def append_entries(section, entries):
    if section.entries:
        ensure_nl(section.entries[-1])
    for e in entries:
        ensure_nl(e)
    section.entries += entries


def entry_date(entry, today):
    """(date | None, how). Newest `| key: YYYY-MM-DD` stamp, else the newest valid MM-DD anywhere on the
    first line (a date more than a day ahead of today is read as last year's), else undated."""
    stamps = []
    for m in STAMP_RE.finditer("".join(entry.body)):
        try:
            stamps.append(datetime.strptime(m.group(1), "%Y-%m-%d").date())
        except ValueError:
            pass
    if stamps:
        return max(stamps), "stamp"
    found = []
    for m in MMDD_RE.finditer(entry.first()):
        try:
            d = date(today.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            continue
        if d > today + timedelta(days=1):
            d = d.replace(year=d.year - 1)
        found.append((d, m.group(0)))
    if found:
        d, token = max(found)
        return d, f"MM-DD {token} of {len(found)}"
    return None, "undated"


def primary_ticket(entry):
    m = TICKET_RE.search(entry.first())
    return m.group(1) if m else None


def snippet(entry):
    return re.sub(r"\s+", " ", entry.first())[:96]


def detail(entry, how):
    return (snippet(entry), how, len(entry.lines()), len(entry.col0_lines()))


def plan(queue, archive, done_days, park_ids, today):
    """Mutate both Docs in place; return (moves, unmatched_park_ids). moves: (src, dst, entry_count, detail list)."""
    moves = []
    dest = {n: archive.find(n) or add_section(archive, n) for n in ARCHIVE_SECTIONS}
    cutoff = today - timedelta(days=done_days)
    matched = {primary_ticket(e) for e in dest["Ready (parked)"].entries}
    shrunk = []

    for sec in list(queue.sections):
        if sec.canon in WHOLESALE:
            target = dest[sec.canon]
            if any(not is_blank(l) for l in sec.preamble):
                if sec.entries:
                    sec.entries[0].head = sec.preamble + sec.entries[0].head
                else:
                    target.trailer = sec.preamble + target.trailer
            append_entries(target, sec.entries)
            if any(not is_blank(l) for l in sec.trailer):
                target.trailer += sec.trailer
            moves.append((sec.name, target.name, len(sec.entries), [detail(e, "wholesale") for e in sec.entries]))
            queue.sections.remove(sec)
        elif sec.canon == "Done":
            keep, gone = [], []
            for e in sec.entries:
                d, how = entry_date(e, today)
                (keep if d and d >= cutoff else gone).append((e, d, how))
            sec.entries = [e for e, _, _ in keep]
            if gone:
                ents = [e for e, _, _ in gone]
                for e in ents:
                    ensure_nl(e)
                dest["Done"].entries[0:0] = ents
                shrunk.append(sec)
                moves.append((sec.name, "Done", len(gone), [detail(e, f"{how} -> {d}" if d else how) for e, d, how in gone]))
        elif sec.canon == "Ready" and park_ids:
            keep, gone = [], []
            for e in sec.entries:
                tid = primary_ticket(e)
                if tid in park_ids:
                    matched.add(tid)
                    gone.append(e)
                else:
                    keep.append(e)
            sec.entries = keep
            if gone:
                append_entries(dest["Ready (parked)"], gone)
                shrunk.append(sec)
                moves.append((sec.name, "Ready (parked)", len(gone), [detail(e, "parked") for e in gone]))
    separate(archive, [dest[canon(dst)] for _, dst, n, _ in moves if n])
    separate(queue, shrunk)
    return moves, sorted(set(park_ids) - matched)


def data_lines(*texts):
    """Multiset of non-blank lines across `texts`, section headings (outside comments) excluded."""
    out = Counter()
    in_comment = False
    for text in texts:
        for ln in split_lines(text):
            if not in_comment and HEADING_RE.match(ln):
                continue
            if in_comment or ln.startswith("<!--"):
                in_comment = "-->" not in ln
            if ln.strip():
                out[ln.rstrip("\n")] += 1
        in_comment = False
    return out


def multiset_diff(before, after):
    """(missing, extra) as Counters; both empty means exactly equal."""
    return before - after, after - before


def atomic_write(path, text):
    d = os.path.dirname(os.path.abspath(path))
    mode = os.stat(path).st_mode & 0o7777 if os.path.exists(path) else 0o644
    fd, tmp = tempfile.mkstemp(prefix=".qsplit-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def read(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except FileNotFoundError:
        return None


def table(label, before, after):
    b, a = {n: (c, y) for n, c, y in before}, {n: (c, y) for n, c, y in after}
    rows = []
    for n in list(dict.fromkeys([x[0] for x in before] + [x[0] for x in after])):
        bc, by = b.get(n, (0, 0))
        ac, ay = a.get(n, (0, 0))
        rows.append(f"  {label:<8} {n:<22} {bc:>4} entries {by:>8,} B  ->  {ac:>4} entries {ay:>8,} B")
    return rows


def report_diff(verb, before, after):
    missing, extra = multiset_diff(before, after)
    if not missing and not extra:
        return True
    print(f"internal error: line multiset {verb} ({sum(missing.values())} lost, {sum(extra.values())} duplicated or added); refusing", file=sys.stderr)
    for label, c in (("lost", missing), ("extra", extra)):
        for l in list(c)[:5]:
            print(f"  {label}: {l[:100]}", file=sys.stderr)
    return False


def run(args):
    out = sys.stdout
    if args.done_days < 0:
        print("--done-days must be >= 0", file=sys.stderr)
        return 2
    q_text = read(args.queue)
    if q_text is None:
        print(f"queue not found: {args.queue}", file=sys.stderr)
        return 2
    a_text = read(args.archive)
    today = datetime.strptime(args.today, "%Y-%m-%d").date() if args.today else date.today()
    park = {p.strip() for p in (args.park_ready or "").split(",") if p.strip()}

    a_base = a_text if a_text is not None else archive_seed()
    queue, archive = Doc(q_text), Doc(a_base)
    if queue.text() != q_text or archive.text() != a_base:
        print("internal error: parse/serialize round trip differs; refusing", file=sys.stderr)
        return 2
    q_before, a_before = queue.stats(), archive.stats()
    before = data_lines(q_text, a_base)
    moves, unmatched = plan(queue, archive, args.done_days, park, today)
    if unmatched:
        print(f"--park-ready: no Ready entry has these as its first ticket link: {', '.join(unmatched)}", file=sys.stderr)
        return 2

    q_new, a_new = queue.text(), archive.text()
    if not report_diff("would change", before, data_lines(q_new, a_new)):
        return 2

    print(f"queue_split ({'APPLY' if args.apply else 'dry run'}), today {today}, done-days {args.done_days}", file=out)
    print(f"queue   {args.queue}: {len(q_text.encode()):,} B -> {len(q_new.encode()):,} B", file=out)
    print(f"archive {args.archive}: {len((a_text or '').encode()):,} B{'' if a_text is not None else ' (new)'} -> {len(a_new.encode()):,} B", file=out)
    print("\nPer section (entries, bytes), before -> after:", file=out)
    for row in table("queue", q_before, queue.stats()) + table("archive", a_before, archive.stats()):
        print(row, file=out)
    print("\nMoves:", file=out)
    if not moves:
        print("  none", file=out)
    undated = col0 = 0
    for src, dst, n, rows in moves:
        flagged = sum(1 for r in rows if r[3])
        col0 += flagged
        print(f"  {src} -> {dst}: {n} entries" + (f" ({flagged} with column-0 non-list lines)" if flagged else ""), file=out)
        for snip, how, nlines, ncol0 in rows:
            undated += how == "undated"
            if args.verbose or how != "wholesale" or ncol0:
                print(f"    [{how}] {nlines} lines{f', COL0={ncol0}' if ncol0 else ''}: {snip}", file=out)
    if undated:
        print(f"\n  {undated} Done entries are UNDATED (no stamp, no MM-DD on the first line) and were moved.", file=out)
    if col0:
        print(f"\n  {col0} moved entries carry column-0 non-list lines (group headers?): they moved WITH the entry above them. Check them.", file=out)

    if not args.apply:
        print("\n(dry run: nothing written; re-run with --apply)", file=out)
        return 0
    atomic_write(args.archive, a_new)
    atomic_write(args.queue, q_new)
    back_q, back_a = read(args.queue), read(args.archive)
    if not report_diff("changed after write", before, data_lines(back_q or "", back_a or "")):
        atomic_write(args.queue, q_text)
        if a_text is None:
            os.unlink(args.archive)
        else:
            atomic_write(args.archive, a_text)
        print("restored the original files", file=sys.stderr)
        return 3
    print("\nwritten: archive, then queue; both re-read and the line multiset re-checked", file=out)
    return 0


def main(argv=None):
    root = data_root(ship_root())
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--queue", default=str(root / "queue.md"))
    ap.add_argument("--archive", default=str(root / "queue-archive.md"))
    # A string default goes through type=int, so a bad $SHIP_QUEUE_DONE_DAYS is a clean usage error.
    ap.add_argument("--done-days", type=int, default=os.environ.get("SHIP_QUEUE_DONE_DAYS") or str(DEFAULT_DONE_DAYS),
                    help=f"archive Done entries older than this (default $SHIP_QUEUE_DONE_DAYS, else {DEFAULT_DONE_DAYS})")
    ap.add_argument("--park-ready", default="")
    ap.add_argument("--today", help="pin the clock (YYYY-MM-DD); tests and replays")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true", help="list wholesale-moved entries too")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
