#!/usr/bin/env python3
"""console_state.py: the only writer of state/console.json (modules/console/console.md).

A console renders that file and computes nothing: every verdict and count is decided here. Every leaf is a claim
{value, confidence, resolved_by, observed_at}; `unknown` is first-class and never paints green, and a missing source
gives null, never a zero. Reads kit-native state only and writes nothing but state/console.json. No subprocesses,
no network. Stdlib only.

  console_state.py                  # write state/console.json (atomic, 0644)
  console_state.py --stdout         # print it instead (a server that generates on request)
  console_state.py --validate FILE  # check FILE against console.schema.json; exit 1 on a violation

SHIP_ROOT overrides the ship root (default: the ship this module lives in). Root data files resolve through
lib/ship_data.data_root(). Thresholds are the consumers' own: STALE_MINUTES (45) as mate-lock.py reads it,
BOSUN_STALE_SECS (2700, raised to 2x the cursor's pace_secs) as launch-bosun.sh reads it. CONSOLE_STALE_AFTER (600)
is the document's own staleness.
"""
import argparse
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "lib"))
from ship_data import STUB_MARKER, data_root  # noqa: E402

SCHEMA_ID = "shipkit-console/1"
SCHEMA_FILE = HERE / "console.schema.json"
GENERATOR = "modules/console/console_state.py"
CONFIDENCE = ("observed", "derived", "unknown")
LEDGER_CAP = 50
ITEMS_CAP = 20
STR_CAP = 300
TAIL_BYTES = 65536
HEAD_BYTES = 4096
MAX_BYTES = 4 * 1024 * 1024
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")
ENTRY_RE = re.compile(r"^(?:\d+(?:\.\d+)?(?:[A-Za-z][A-Za-z0-9]*)?\.|[-*+])\s+\S")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
NOT_MAILBOXES = {"drops", "processed"}


def ship_root():
    return Path(os.environ.get("SHIP_ROOT") or HERE.parents[1])


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_ts(value):
    if not isinstance(value, str) or not value.strip():
        return None
    v = value.strip().replace("Z", "+00:00")
    try:
        m = re.match(r"^(\d{8})T(\d{6})\+00:00$", v)
        dt = (datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S") if m
              else datetime.fromisoformat(v))
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def clip(value, n=STR_CAP):
    """File content passes through to the console, so every string is capped and non-scalars are flattened."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return (value if isinstance(value, str) else json.dumps(value))[:n]


def claim(value, confidence, resolved_by, observed_at=None):
    if confidence not in CONFIDENCE or not resolved_by:
        raise ValueError("a claim needs a known confidence and a non-empty resolved_by")
    return {"value": value, "confidence": confidence, "resolved_by": resolved_by,
            "observed_at": iso(observed_at) if isinstance(observed_at, datetime) else observed_at}


def unknowns(keys, why):
    return {k: claim(None, "unknown", why) for k in keys}


def frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    block = text[4:end] if end > 0 else ""
    return {k: v.strip().strip("\"'") for k, v in re.findall(r"^([A-Za-z_]+):[ \t]*(.*)$", block, re.M)}


def open_regular(path):
    """A read handle on a regular file, or None. O_NONBLOCK so a FIFO can't hang the open."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    fh = os.fdopen(fd, "rb")
    st = os.fstat(fh.fileno())
    if not stat.S_ISREG(st.st_mode):
        fh.close()
        return None, st
    return fh, st


def read_head(path, limit=HEAD_BYTES):
    try:
        fh, _ = open_regular(path)
    except OSError:
        return None
    if fh is None:
        return None
    with fh:
        return fh.read(limit).decode("utf-8", errors="replace")


class Generator:
    def __init__(self, root, now, mate_stale_s, bosun_stale_s):
        self.root, self.now = Path(root), now
        self.data = data_root(self.root)
        self.mate_stale_s, self.bosun_stale_s = mate_stale_s, bosun_stale_s
        self.sources = []
        self.last_mtime = None

    def label(self, path):
        for base, prefix in ((self.data, "<data-root>/"), (self.root, "")):
            if base is self.data and self.data == self.root:
                continue
            try:
                return prefix + path.relative_to(base).as_posix()
            except ValueError:
                pass
        return path.name

    def age(self, dt):
        return int((self.now - dt).total_seconds()) if dt else None

    def note(self, name, path, state, mtime=None):
        self.sources.append({"name": name, "path": self.label(path), "state": state,
                             "modified_at": iso(mtime), "age_s": self.age(mtime)})

    def read(self, name, rel_or_path, parse=None, tail=False):
        """(value, None, False) or (None, why, absent). `absent` is True only when the file is missing from a
        directory that exists: a missing state/ (or a dangling data-root link) proves nothing about the file."""
        path = rel_or_path if isinstance(rel_or_path, Path) else self.root / rel_or_path
        label, self.last_mtime = self.label(path), None
        try:
            fh, st = open_regular(path)
        except (FileNotFoundError, NotADirectoryError):
            self.note(name, path, "absent")
            if path.parent.is_dir():
                return None, label + " absent", True
            return None, "%s/ absent, so %s is unknown" % (self.label(path.parent), label), False
        except OSError as exc:
            self.note(name, path, "unreadable")
            return None, "%s unreadable (%s)" % (label, exc.__class__.__name__), False
        mtime = datetime.fromtimestamp(st.st_mtime, timezone.utc)
        if fh is None:
            self.note(name, path, "unreadable", mtime)
            return None, label + " is not a regular file", False
        with fh:
            if tail:
                fh.seek(max(0, st.st_size - TAIL_BYTES))
            raw = fh.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            self.note(name, path, "unreadable", mtime)
            return None, "%s is larger than %d bytes" % (label, MAX_BYTES), False
        if raw.startswith(STUB_MARKER.encode()):
            self.note(name, path, "unreadable", mtime)
            return None, label + " is a data-root pointer stub and the data root did not resolve", False
        try:
            text = raw.decode("utf-8", errors="replace" if tail else "strict")
            value = parse(text) if parse else text
        except (ValueError, RecursionError) as exc:
            self.note(name, path, "unreadable", mtime)
            return None, "%s unreadable (%s)" % (label, exc.__class__.__name__), False
        self.note(name, path, "read", mtime)
        self.last_mtime = mtime
        return value, None, False

    def json_obj(self, name, rel):
        def parse(text):
            obj = json.loads(text)
            if not isinstance(obj, dict):
                raise ValueError("not an object")
            return obj
        return self.read(name, rel, parse)

    def listdir(self, d):
        """(entries, None) or (None, (source state, why))."""
        try:
            if not stat.S_ISDIR(d.stat().st_mode):
                return None, ("unreadable", self.label(d) + "/ is not a directory")
            return list(d.iterdir()), None
        except (FileNotFoundError, NotADirectoryError):
            return None, ("absent", self.label(d) + "/ absent")
        except OSError as exc:
            return None, ("unreadable", "%s/ unreadable (%s)" % (self.label(d), exc.__class__.__name__))

    def regular(self, entries, suffixes):
        """[(path, mtime)] of regular files, oldest first; one moved away mid-scan is skipped."""
        out = []
        for p in entries:
            if p.suffix not in suffixes or p.name.startswith("."):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                out.append((p, datetime.fromtimestamp(st.st_mtime, timezone.utc)))
        return sorted(out, key=lambda pm: (pm[1], pm[0].name))

    def scan(self, name, d, suffixes):
        """(files, None) or (None, why); records the directory as a source either way."""
        entries, err = self.listdir(d)
        if err:
            self.note(name, d, err[0])
            return None, err[1]
        files = self.regular(entries, suffixes)
        self.note(name, d, "read", files[-1][1] if files else None)
        return files, None

    def freshness(self, stamp, threshold, by, inclusive):
        age = self.age(stamp)
        if stamp is None:
            return {"value": "unknown", "by": "%s missing or unparseable" % by}
        if age < 0:
            return {"value": "unknown", "by": "%s is in the future (clock skew?)" % by}
        fresh = age <= threshold if inclusive else age < threshold
        return {"value": "fresh" if fresh else "stale",
                "by": "%s is %ds old; the threshold is %ds" % (by, age, threshold)}

    def age_claim(self, stamp, by):
        age = self.age(stamp)
        if age is None or age < 0:
            return claim(None, "unknown", by + " is missing, unparseable or in the future")
        return claim(age, "derived", "generated_at minus " + by)

    def install(self):
        rec, why, _ = self.json_obj("install", "state/install.json")
        if rec is None:
            return {"claims": unknowns(("modules", "preset"), why)}
        mods = rec.get("modules")
        ok = isinstance(mods, list) and all(isinstance(m, str) for m in mods)
        at = parse_ts(rec.get("updated_at"))
        src = "state/install.json:"
        return {"claims": {
            "modules": claim([clip(m) for m in mods] if ok else None, "observed" if ok else "unknown",
                             src + "modules" + ("" if ok else " is not a list of names"), at),
            "preset": claim(clip(rec["preset"]), "observed", src + "preset (null = a custom module set)", at)
            if "preset" in rec else claim(None, "unknown", src + "preset not set")}}

    def mate(self):
        src, thr = "state/mate-lock.json", self.mate_stale_s
        lock, why, absent = self.json_obj("mate-lock", src)
        claims = {"stale_after_s": claim(thr, "derived", "STALE_MINUTES (default 45), as mate-lock.py reads it")}
        if lock is None:
            claims.update({k: claim(None, "observed" if absent else "unknown", why)
                           for k in ("lock_holder", "acquired_at", "heartbeat_at", "heartbeat_age_s")})
            by = why + ": no seat holds the lock" if absent else why
            return {"verdict": {"value": "absent" if absent else "unknown", "by": by}, "claims": claims}
        field = "heartbeat_at" if lock.get("heartbeat_at") else "acquired_at"
        hb, beat = parse_ts(lock.get(field)), parse_ts(lock.get("heartbeat_at"))
        claims.update({
            "lock_holder": claim(clip(lock.get("session_id")), "observed", src + ":session_id", hb),
            "acquired_at": claim(clip(lock.get("acquired_at")), "observed", src + ":acquired_at", hb),
            "heartbeat_at": claim(iso(beat), "observed" if beat else "unknown", src + ":heartbeat_at", beat),
            "heartbeat_age_s": self.age_claim(hb, "%s:%s" % (src, field))})
        verdict = self.freshness(hb, thr, "%s:%s" % (src, field), inclusive=True)
        return {"verdict": verdict, "claims": claims}

    def bosun(self):
        src = "state/bosun-heartbeat.log"
        cursor, cwhy, _ = self.json_obj("bosun-cursor", "state/bosun-last-sweep.json")
        pace = (cursor or {}).get("pace_secs")
        thr = self.bosun_stale_s
        if isinstance(pace, (int, float)) and not isinstance(pace, bool) and pace > 0:
            thr = max(thr, int(pace) * 2)
        swept = parse_ts((cursor or {}).get("_updated"))
        claims = {
            "stale_after_s": claim(thr, "derived", "max(BOSUN_STALE_SECS (default 2700), 2 x "
                                   "state/bosun-last-sweep.json:pace_secs), as launch-bosun.sh"),
            "last_sweep_at": claim(iso(swept), "observed" if swept else "unknown", cwhy or (
                "state/bosun-last-sweep.json:_updated" + ("" if swept else " missing or unparseable")), swept)}
        text, why, absent = self.read("bosun-heartbeat", src, tail=True)
        mtime = self.last_mtime
        lines = [ln for ln in (text or "").splitlines() if ln.strip()]
        if not lines:
            why = why or src + " is empty: no beat recorded"
            claims.update({k: claim(None, "observed" if absent else "unknown", why)
                           for k in ("last_beat_at", "last_note", "heartbeat_age_s")})
            return {"verdict": {"value": "absent" if absent else "unknown", "by": why}, "claims": claims}
        stamp, _, body = lines[-1].partition("\t")
        beat = parse_ts(stamp)
        claims.update({
            "last_beat_at": claim(iso(beat), "observed" if beat else "unknown", src + ": last line's stamp", beat),
            "last_note": claim(clip(body), "observed", src + ": last line's note", beat),
            "heartbeat_age_s": self.age_claim(mtime, src + " mtime (as launch-bosun.sh)")})
        verdict = self.freshness(mtime, thr, src + " mtime (as launch-bosun.sh)", inclusive=False)
        return {"verdict": verdict, "claims": claims}

    def status(self):
        st, why, _ = self.json_obj("status", "state/status.json")
        now = (st or {}).get("now") if isinstance((st or {}).get("now"), dict) else {}
        at = parse_ts((st or {}).get("generated_at"))
        fields = {"doing": now.get("doing"), "since": now.get("since"), "tick": (st or {}).get("tick"),
                  "wake_reason": (st or {}).get("wake_reason"), "next_wake": (st or {}).get("next_wake"),
                  "validator": (st or {}).get("validator"), "written_at": iso(at)}
        keys = {"doing": "now.doing", "since": "now.since", "written_at": "generated_at"}
        claims = unknowns(fields, why) if st is None else {
            k: claim(clip(v), "observed" if v is not None else "unknown",
                     "state/status.json:" + keys.get(k, k) + ("" if v is not None else " not set"), at)
            for k, v in fields.items()}
        crew = (st or {}).get("crew")
        if st is not None and isinstance(crew, list):
            items = [{k: clip(str(c.get(k, ""))) for k in ("name", "ticket", "task", "dispatched")}
                     for c in crew if isinstance(c, dict)]
            crew_claims = {"active": claim(items[:ITEMS_CAP], "observed",
                                           "state/status.json:crew[] (first %d)" % ITEMS_CAP, at),
                           "count": claim(len(items), "observed", "state/status.json:crew[] length", at)}
        else:
            crew_claims = unknowns(("active", "count"), why or (
                "state/status.json has no crew[] (only a UI module writes it); queue.counts.Active is the "
                "queue's view"))
        return {"claims": claims}, {"claims": crew_claims}

    def queue(self):
        path = self.data / "queue.md"
        text, why, _ = self.read("queue", path)
        if text is None:
            return {"claims": unknowns(("counts", "awaiting_captain"), why)}
        counts, awaiting, section, fenced = {}, [], None, False
        for ln in COMMENT_RE.sub("", text).split("\n"):
            if ln.startswith("```"):
                fenced = not fenced
            if fenced:
                continue
            m = HEADING_RE.match(ln)
            if m:
                name = clip(m.group(1), 100)
                section = name if name == "Ready (parked)" else re.sub(r"\s*\(.*\)\s*$", "", name)
                counts.setdefault(section, 0)
            elif section and ENTRY_RE.match(ln):
                counts[section] += 1
                if section == "Awaiting Captain" and len(awaiting) < ITEMS_CAP:
                    awaiting.append(clip(re.sub(r"^\S+\s+", "", ln.strip())))
        rel, at = self.label(path), self.last_mtime
        return {"claims": {
            "counts": claim(counts, "derived", "column-0 list entries per `## ` section of %s, "
                            "HTML comments and fenced blocks skipped" % rel, at),
            "awaiting_captain": claim(awaiting, "derived", "first line of each entry under `## Awaiting "
                                      "Captain` in %s (first %d)" % (rel, ITEMS_CAP), at)}}

    def tickets(self):
        projects = self.root / "projects"
        entries, err = self.listdir(projects)
        if err:
            self.note("tickets", projects, err[0])
            return {"claims": unknowns(("total", "by_status"), err[1])}
        files = []
        for proj in sorted(entries):
            sub, err = self.listdir(proj / "tickets")
            if err and err[0] == "unreadable":
                self.note("tickets", proj / "tickets", "unreadable")
                return {"claims": unknowns(("total", "by_status"), err[1])}
            files += self.regular(sub or [], (".md",))
        by = {}
        for p, _ in files:
            text = read_head(p)
            if text is None:
                by["unreadable"] = by.get("unreadable", 0) + 1
                continue
            m = re.search(r"^\*\*Status:\*\*\s*(.*)$", text, re.M)
            raw = frontmatter(text).get("status") or (m.group(1) if m else "")
            w = re.match(r"[A-Za-z][\w-]*", raw.strip())
            word = clip(w.group(0).lower(), 60) if w else "unset"
            by[word] = by.get(word, 0) + 1
        newest = max((mt for _, mt in files), default=None)
        self.note("tickets", projects, "read", newest)
        by_src = ("projects/*/tickets/*.md: the first word of frontmatter `status:`, else of the `**Status:**` "
                  "line, else unset")
        return {"claims": {"total": claim(len(files), "derived", "count of projects/*/tickets/*.md", newest),
                           "by_status": claim(by, "derived", by_src, newest)}}

    def mail(self):
        inbox = self.root / "inbox"
        entries, err = self.listdir(inbox)
        self.note("inbox", inbox, err[0] if err else "read")
        boxes = None
        if not err:
            boxes = {}
            for d in sorted(entries):
                if d.name in NOT_MAILBOXES or d.name.startswith(".") or not d.is_dir():
                    continue
                unread, _ = self.scan("mail:" + d.name, d, (".md",))
                boxes[clip(d.name, 100)] = {
                    "unread": len(unread) if unread is not None else None,
                    "newest": clip(unread[-1][0].name) if unread else None,
                    "oldest_unread_at": iso(unread[0][1]) if unread else None}
        text, why, _ = self.read("captain-inbox", "inbox/captain.md")
        lines = [ln for ln in COMMENT_RE.sub("", text or "").splitlines()
                 if ln.strip() and not re.match(r"^\s*(#|>|---\s*$)", ln)]
        box_rule = ("inbox/<box>/*.md at top level, per box other than %s; a box's read/ subdir is read mail; "
                    "an unreadable box has null counts" % ", ".join(d + "/" for d in sorted(NOT_MAILBOXES)))
        return {"claims": {
            "boxes": claim(boxes, "derived", box_rule) if boxes is not None else claim(None, "unknown", err[1]),
            "captain_inbox_lines": claim(
                None if text is None else len(lines), "unknown" if text is None else "derived",
                why or "inbox/captain.md lines that are not headings, quotes, rules or comments",
                self.last_mtime)}}

    def drops(self):
        d = self.root / "inbox" / "drops"
        files, why = self.scan("drops", d, (".md", ".json"))
        processed, pwhy = self.scan("drops-processed", d / "processed", (".md", ".json"))
        src = "inbox/drops/*.md|*.json at top level (not yet moved to processed/)"
        out = {"processed": claim(len(processed), "derived", "inbox/drops/processed/*.md|*.json")
               if processed is not None else claim(None, "unknown", pwhy)}
        if files is None:
            out.update(unknowns(("pending", "oldest_pending_at", "ledger"), why))
            return {"claims": out}
        ledger = []
        for p, at in reversed(files[-LEDGER_CAP:]):
            text = read_head(p, 262144) or ""
            try:
                meta = json.loads(text) if p.suffix == ".json" else frontmatter(text)
            except (ValueError, RecursionError):
                meta = {}
            meta = meta if isinstance(meta, dict) else {}
            ledger.append({"name": clip(p.name), "at": iso(at),
                           **{k: clip(meta[k], 200) if isinstance(meta.get(k), str) else None
                              for k in ("source", "wake_class", "authority")}})
        newest = files[-1][1] if files else None
        out.update({
            "pending": claim(len(files), "derived", src, newest),
            "oldest_pending_at": claim(iso(files[0][1]) if files else None, "derived",
                                       "oldest mtime among " + src, newest),
            "ledger": claim(ledger, "derived", "newest-first, first %d of %s; source/wake_class/authority "
                            "from each drop's frontmatter (JSON keys for .json)" % (LEDGER_CAP, src), newest)})
        return {"claims": out}


def build(root, now, stale_after=600, mate_stale_s=None, bosun_stale_s=None):
    g = Generator(root, now,
                  mate_stale_s or int(os.environ.get("STALE_MINUTES", "45")) * 60,
                  bosun_stale_s or int(os.environ.get("BOSUN_STALE_SECS", "2700")))
    status, crew = g.status()
    body = {"install": g.install(), "seats": {"mate": g.mate(), "bosun": g.bosun()}, "status": status,
            "crew": crew, "queue": g.queue(), "tickets": g.tickets(), "mail": g.mail(), "drops": g.drops()}
    return {"schema": SCHEMA_ID, "generated_at": iso(now), "generator": GENERATOR, "stale_after_s": stale_after,
            "sources": g.sources, **body}


JSON_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float),
              "boolean": bool, "null": type(None)}


def _is(value, t):
    if t in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, JSON_TYPES[t])


def validate(inst, schema, root=None, path="$"):
    """The JSON Schema subset console.schema.json uses: $ref, type, const, enum, pattern, minLength,
    minimum, required, properties, additionalProperties, items."""
    root = root or schema
    errs = []
    if "$ref" in schema:
        errs += validate(inst, root["$defs"][schema["$ref"].split("/")[-1]], root, path)
    types = schema.get("type")
    if types and not any(_is(inst, t) for t in (types if isinstance(types, list) else [types])):
        return errs + ["%s: expected %s" % (path, types)]
    if "const" in schema and inst != schema["const"]:
        errs.append("%s: expected %r" % (path, schema["const"]))
    if "enum" in schema and inst not in schema["enum"]:
        errs.append("%s: %r not in %s" % (path, inst, schema["enum"]))
    if isinstance(inst, str):
        if len(inst) < schema.get("minLength", 0):
            errs.append("%s: shorter than %d" % (path, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append("%s: %r does not match %s" % (path, inst, schema["pattern"]))
    if _is(inst, "number") and "minimum" in schema and inst < schema["minimum"]:
        errs.append("%s: below %s" % (path, schema["minimum"]))
    if isinstance(inst, dict):
        props, extra = schema.get("properties", {}), schema.get("additionalProperties", True)
        errs += ["%s: missing %s" % (path, k) for k in schema.get("required", []) if k not in inst]
        for k, v in inst.items():
            if k in props:
                errs += validate(v, props[k], root, "%s.%s" % (path, k))
            elif extra is False:
                errs.append("%s: unexpected %s" % (path, k))
            elif isinstance(extra, dict):
                errs += validate(v, extra, root, "%s.%s" % (path, k))
    if isinstance(inst, list) and "items" in schema:
        for i, v in enumerate(inst):
            errs += validate(v, schema["items"], root, "%s[%d]" % (path, i))
    return errs


def write(out, text):
    """None, or why the write was refused. state/ is never created here: a missing one means the ship (or its
    data-root link) is broken, and creating it would turn the next run's `unknown` seats into `absent`."""
    if not out.parent.is_dir():
        return "state/ absent (missing, or a dangling data-root link); the generator never creates it"
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=".console.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o644)
        os.replace(tmp, out)
    except OSError as exc:
        return "cannot write state/console.json (%s: %s)" % (exc.__class__.__name__, exc.strerror or exc)
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stdout", action="store_true", help="print instead of writing state/console.json")
    ap.add_argument("--validate", metavar="FILE", help="check FILE against the schema and exit")
    ap.add_argument("--stale-after", type=int, default=int(os.environ.get("CONSOLE_STALE_AFTER", "600")))
    args = ap.parse_args(argv)
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    if args.validate:
        try:
            errs = validate(json.loads(Path(args.validate).read_text(encoding="utf-8")), schema)
        except (OSError, ValueError, RecursionError) as exc:
            errs = ["$: unreadable (%s)" % exc.__class__.__name__]
        print("\n".join(errs) or "valid: " + args.validate)
        return 1 if errs else 0
    root = ship_root()
    doc = build(root, datetime.now(timezone.utc), args.stale_after)
    errs = validate(doc, schema)
    if errs:
        print("refused: the generated document violates the schema:\n" + "\n".join(errs), file=sys.stderr)
        return 2
    text = json.dumps(doc, indent=2) + "\n"
    if args.stdout:
        sys.stdout.write(text)
        return 0
    err = write(root / "state" / "console.json", text)
    if err:
        print("refused: " + err, file=sys.stderr)
        return 2
    print("wrote state/console.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
