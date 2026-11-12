#!/usr/bin/env python3
"""familiar_drop.py — the Familiar's only door into inbox/drops/, and its mail archiver.

    familiar_drop.py send <draft> [--topic SLUG]   validate a draft under state/familiar/drafts/,
                                                    write it to inbox/drops/familiar-<UTC>-<slug>.md,
                                                    remove the draft
    familiar_drop.py validate <file>                check a drop; exit 1 and list the problems
    familiar_drop.py archive <name>                 move inbox/familiar/<name> to inbox/familiar/read/

The filename stamp is taken from the clock here, in UTC, never typed by the caller. Every path
is fixed relative to the ship root (SHIP_ROOT env overrides it for tests), so the helper cannot
be pointed at queue.md or a ticket. `validate()` is also what classify_input.py calls on any
drop that claims `source: familiar`.

A draft may leave out the defaults: source (familiar), shipkit_input (v1), authority
(standing), origin (familiar-initiative, standing only) and priority (normal). Stdlib only.
"""
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SHIP_ROOT = Path(os.environ.get("SHIP_ROOT", Path(__file__).resolve().parents[3])).resolve()

KINDS = ("steer", "ask", "status-request")
AUTHORITIES = ("standing", "relayed-explicit")
PRIORITIES = ("normal", "urgent")
WAKE_CLASSES = ("wake", "batch", "silent")
SECTIONS = ("# Objective", "## Bounds", "## Success condition", "## Report")
NAME_RE = re.compile(r"familiar-\d{8}T\d{6}Z(-[a-z0-9][a-z0-9-]*)?\.md")
DEFAULTS = (("shipkit_input", "v1"), ("source", "familiar"), ("authority", "standing"),
            ("priority", "normal"))


def parse(text):
    """Split a drop into (ordered [(key, value)], body, problems)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], text, ["no frontmatter (the file must start with ---)"]
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return [], text, ["frontmatter is not closed (no second ---)"]
    pairs, problems = [], []
    for ln in lines[1:end]:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*?)\s*$", ln)
        if not m:
            problems.append("unparseable frontmatter line: %r" % ln[:80])
            continue
        val = m.group(2)
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        else:
            val = re.sub(r"\s+#.*$", "", val)
        pairs.append((m.group(1), val))
    return pairs, "\n".join(lines[end + 1:]), problems


def validate(text, basename=None):
    """Return a list of problems; empty means a well-formed Familiar command."""
    pairs, body, problems = parse(text)
    if not pairs and problems:
        return problems
    seen = {}
    for k, v in pairs:
        if k in seen:
            problems.append("duplicate frontmatter key %r (a second value could smuggle a "
                            "different meaning past a first-match reader)" % k)
        seen.setdefault(k, v)
    fm = seen
    if fm.get("source") != "familiar":
        problems.append("source must be 'familiar' (got %r)" % fm.get("source"))
    if fm.get("kind") not in KINDS:
        problems.append("kind must be one of %s (got %r)" % ("|".join(KINDS), fm.get("kind")))
    if fm.get("authority") not in AUTHORITIES:
        problems.append("authority must be one of %s (got %r)"
                        % ("|".join(AUTHORITIES), fm.get("authority")))
    if not fm.get("origin"):
        problems.append("origin is required (a Captain message reference, or "
                        "familiar-initiative)")
    if fm.get("priority", "normal") not in PRIORITIES:
        problems.append("priority must be one of %s" % "|".join(PRIORITIES))
    if "wake_class" in fm and fm["wake_class"] not in WAKE_CLASSES:
        problems.append("wake_class must be one of %s" % "|".join(WAKE_CLASSES))
    if "role" in fm:
        problems.append("a Familiar command carries no role: key (it never speaks as the "
                        "Captain)")
    if fm.get("authority") == "relayed-explicit":
        if fm.get("origin") in (None, "", "familiar-initiative"):
            problems.append("relayed-explicit needs an origin naming the Captain instruction "
                            "being relayed")
        if not re.search(r"^## Authorized action\s*$", body, re.M):
            problems.append("relayed-explicit needs a '## Authorized action' section stating "
                            "the exact action the Captain authorized")
    for heading in SECTIONS:
        if not re.search(r"^%s\s*$" % re.escape(heading), body, re.M):
            problems.append("missing section %r" % heading)
    if basename is not None and not NAME_RE.fullmatch(basename):
        problems.append("filename %r is not familiar-YYYYMMDDTHHMMSSZ[-slug].md (send drops "
                        "with familiar_drop.py, which stamps it)" % basename)
    return problems


def with_defaults(text):
    pairs, body, problems = parse(text)
    if problems:
        return text
    keys = {k for k, _ in pairs}
    for k, v in DEFAULTS:
        if k not in keys:
            pairs.append((k, v))
    if "origin" not in keys and dict(pairs).get("authority") == "standing":
        pairs.append(("origin", "familiar-initiative"))
    head = "\n".join("%s: %s" % kv for kv in pairs)
    return "---\n%s\n---\n%s\n" % (head, body.rstrip("\n"))


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:48].strip("-") or "command"


def _inside(path, parent):
    p = os.path.realpath(path)
    parent = os.path.realpath(parent)
    return p.startswith(parent + os.sep)


def send(draft, topic=None, now=None):
    drafts = SHIP_ROOT / "state" / "familiar" / "drafts"
    if not _inside(draft, drafts):
        raise SystemExit("refused: drafts must live under %s" % drafts)
    text = with_defaults(Path(draft).read_text(encoding="utf-8"))
    problems = validate(text)
    if problems:
        raise SystemExit("refused, the draft is not a valid command:\n  - "
                         + "\n  - ".join(problems))
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    slug = slugify(topic or Path(draft).stem)
    out_dir = SHIP_ROOT / "inbox" / "drops"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Written in full under a hidden non-.md name, then hard-linked into place: a watcher never
    # sees a half-written drop, and os.link refuses an existing name (no overwrite).
    tmp = out_dir / (".familiar-%s-%d.tmp" % (stamp, os.getpid()))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        try:
            fh = os.fdopen(fd, "w", encoding="utf-8")
        except BaseException:
            os.close(fd)
            raise
        with fh:
            fh.write(text)
        for n in range(1, 100):
            final = out_dir / ("familiar-%s-%s%s.md" % (stamp, slug, "" if n == 1 else "-%d" % n))
            try:
                os.link(tmp, final)
            except FileExistsError:
                continue
            os.unlink(draft)
            return final
    finally:
        os.unlink(tmp)
    raise SystemExit("refused: 99 drops already share stamp %s and slug %s" % (stamp, slug))


def archive(name):
    if "/" in name or "\\" in name or not name.endswith(".md") or name.startswith("."):
        raise SystemExit("refused: give a bare mail filename from inbox/familiar/, e.g. note.md")
    mailbox = SHIP_ROOT / "inbox" / "familiar"
    src = mailbox / name
    if not src.is_file() or src.is_symlink():
        raise SystemExit("refused: no such mail %s" % src)
    dst_dir = mailbox / "read"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / name
    if dst.exists():
        raise SystemExit("refused: %s already exists" % dst)
    os.replace(src, dst)
    return dst


def main(argv):
    usage = ("usage: familiar_drop.py send <draft> [--topic SLUG] | validate <file> | "
             "archive <name>")
    if len(argv) < 3:
        print(usage, file=sys.stderr)
        return 2
    cmd, arg = argv[1], argv[2]
    if cmd == "send":
        topic = None
        if argv[3:5] and argv[3] == "--topic" and len(argv) == 5:
            topic = argv[4]
        elif len(argv) != 3:
            print(usage, file=sys.stderr)
            return 2
        print(send(arg, topic))
        return 0
    if cmd == "validate" and len(argv) == 3:
        p = Path(arg)
        problems = validate(p.read_text(encoding="utf-8"), basename=p.name)
        for prob in problems:
            print("- " + prob)
        print("ok" if not problems else "%d problem(s)" % len(problems))
        return 1 if problems else 0
    if cmd == "archive" and len(argv) == 3:
        print(archive(arg))
        return 0
    print(usage, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
