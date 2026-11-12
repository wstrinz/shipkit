#!/bin/bash
# validate-navigator-bash.sh — PreToolUse hook (matcher Bash) for the ship-navigator agent.
#
# The Navigator's shell is a POSITIVE allow-list: read-only inspection commands, git and gh
# reads, and `claude agents`. No helpers. Default is DENY. Without it the write allow-list
# would be decoration: core's read-only lane admits `env CMD`, `xargs CMD` and `> file`, so a
# Navigator could `printf … > inbox/drops/familiar-….md` and pose as the Familiar.
#
# The checker between the SHIP-POSITIVE-LANE markers is shared verbatim with
# modules/familiar/hooks/validate-familiar-bash.sh (hooks stay self-contained single files);
# a test diffs the two blocks. Only the config above the markers differs.
#
# Fails CLOSED: missing python3, an unreadable payload, unbalanced quotes, or the checker
# crashing all exit 2.
set -u
SHIP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "navigator-bash DENY: python3 not on PATH (fail closed)" >&2
  exit 2
fi

# read -d '' rather than $(cat <<EOF): bash 3.2 parses quotes and backticks inside a heredoc
# that sits in a command substitution, and the checker below contains both.
read -r -d '' PY <<'EOF'
SEAT = "navigator"
HELPERS = {}
HELPER_HINT = ""

# ==== SHIP-POSITIVE-LANE v1 ====
# Rules, in order:
#   - no backtick anywhere; no `$` outside single quotes (escape-aware); no unquoted `{`
#     other than a bare `{}` (brace expansion would rebuild option names the checks compare);
#   - redirects only to /dev/null or between fds 0-2; no `<`, `>`, `&`, `(` otherwise;
#   - `#` is NOT a comment to the lexer, so nothing after it hides from the checks;
#   - no glob characters in an option-shaped word;
#   - the command splits on | || && ; and newline, and EVERY segment must pass `allowed()`.
# Nothing on the list writes a file except the helpers, and each helper path-locks its own
# writes. Quoted operators are read as operators (shlex cannot tell them apart): that only
# splits a command into more segments, so it over-blocks, never under-blocks.
import json, os, re, shlex, sys

root = os.path.realpath(sys.argv[1])


def deny(msg):
    sys.stderr.write("%s-bash DENY: %s\n" % (SEAT, msg))
    sys.exit(2)


try:
    payload = json.loads(sys.stdin.read())
except Exception:
    deny("malformed PreToolUse payload (fail closed)")
if not isinstance(payload, dict):
    deny("malformed PreToolUse payload (fail closed)")
cmd = (payload.get("tool_input") or {}).get("command")
if cmd is None or (isinstance(cmd, str) and not cmd.strip()):
    sys.exit(0)
if not isinstance(cmd, str):
    deny("malformed command (fail closed)")
cwd = payload.get("cwd") or os.getcwd()

cmd = re.sub(r"(?<!\\)((?:\\\\)*)\\\n", r"\1", cmd)


def unsafe(text):
    """The first shell feature the checks below cannot see through, or None."""
    if "`" in text:
        return "backtick (command substitution)"
    quote, i = None, 0
    while i < len(text):
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = None
        elif c == "\\":
            i += 1
        elif c == "$":
            return "$-expansion (single-quote a literal $ in a search pattern)"
        elif c == '"':
            quote = None if quote == '"' else '"'
        elif quote is None and c == "'":
            quote = "'"
        elif quote is None and c == "{" and text[i + 1:i + 2] != "}":
            return "unquoted { (brace expansion)"
        i += 1
    return None


why = unsafe(cmd)
if why:
    deny("no %s in the %s's shell" % (why, SEAT))

cmd = re.sub(r"(?:(?<=\s)|^)(?:[0-2]?>&[0-2]|(?:[0-2]|&)?>\s*/dev/null)(?=\s|;|\||&&|$)", " ", cmd)

SEPS = {"|", "||", "&&", ";", ";;"}
try:
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|<>()")
    lex.whitespace_split = True
    lex.commenters = ""
    tokens = list(lex)
except ValueError:
    deny("unbalanced quotes (fail closed)")

segments, cur = [], []
for t in tokens:
    if t in SEPS:
        segments.append(cur)
        cur = []
    elif t and set(t) <= set(";&|<>()"):
        deny("operator %r is not allowed: no file redirects, background jobs or subshells. "
             "Write with the Write tool on an allowed path." % t)
    elif t.startswith("-") and re.search(r"[*?\[\]]", t):
        deny("a glob in an option (%r) could expand to an option the checks never saw" % t)
    else:
        cur.append(t)
segments.append(cur)
segments = [s for s in segments if s]
if not segments:
    deny("no command found (fail closed)")

READ_ONLY = {
    "cat", "head", "tail", "wc", "ls", "stat", "file", "du", "df", "pwd", "echo", "printf",
    "grep", "egrep", "fgrep", "cut", "tr", "column", "basename", "dirname", "realpath",
    "diff", "true", "false", "which", "jq", "sort", "uniq", "tree", "rg", "find", "date", "cd",
}
FIND_ACTIONS = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0",
                "-fprintf", "-fls"}
GIT_READ = {"status", "log", "diff", "show", "rev-parse", "ls-files", "blame", "describe",
            "shortlog", "grep", "ls-tree", "cat-file", "branch", "remote", "worktree"}
GH_READ = {("pr", "view"), ("pr", "list"), ("pr", "checks"), ("pr", "diff"), ("pr", "status"),
           ("run", "view"), ("run", "list"), ("issue", "view"), ("issue", "list"),
           ("repo", "view")}


def is_abbrev(arg, longname):
    """GNU-style tools accept any unambiguous prefix of a long option (`--o` for --output)."""
    if not arg.startswith("--"):
        return False
    name = arg[2:].split("=", 1)[0]
    return bool(name) and longname.startswith(name)


def short_has(arg, letters):
    """A short-option cluster (`-ao`) that contains any of `letters`."""
    return bool(re.match(r"^-[A-Za-z0-9]", arg)) and any(c in arg[1:] for c in letters)


def resolve(path, here):
    return os.path.realpath(os.path.join(here or "/", os.path.expanduser(path)))


def helper_ok(argv, here):
    if argv[0] in ("python3", "python", "bash", "sh"):
        if len(argv) < 2:
            return False
        script, args = argv[1], argv[2:]
    else:
        script, args = argv[0], argv[1:]
    if here is None and not os.path.isabs(os.path.expanduser(script)):
        return False
    rp = resolve(script, here)
    if not rp.startswith(root + os.sep):
        return False
    rel = os.path.relpath(rp, root).replace(os.sep, "/")
    if rel not in HELPERS:
        return False
    is_py = rel.endswith(".py")
    if argv[0] in ("python3", "python") and not is_py:
        return False
    if argv[0] in ("bash", "sh") and is_py:
        return False
    pinned = HELPERS[rel]
    return pinned is None or tuple(args) in pinned


def git_ok(args):
    while args and args[0].startswith("-"):
        if args[0] == "--no-pager":
            args = args[1:]
        elif args[0] == "-C" and len(args) > 1:
            args = args[2:]
        else:
            return False
    if not args or args[0] not in GIT_READ:
        return False
    sub, rest = args[0], args[1:]
    for a in rest:
        if is_abbrev(a, "output") or is_abbrev(a, "ext-diff"):
            return False
        if sub == "grep" and (is_abbrev(a, "open-files-in-pager") or short_has(a, "O")):
            return False
    if sub == "branch":
        listing = {"-a", "-r", "-v", "-vv", "--all", "--remotes", "--verbose", "--list", "-l",
                   "--show-current", "--contains", "--merged", "--no-merged"}
        if any(a.startswith("-") and a not in listing for a in rest):
            return False
        if any(not a.startswith("-") for a in rest) and not ({"--list", "-l", "--contains",
                                                                "--merged", "--no-merged"} & set(rest)):
            return False
    if sub == "remote" and rest not in ([], ["-v"]) and (not rest or rest[0] not in ("show", "get-url")):
        return False
    if sub == "worktree" and rest[:1] != ["list"]:
        return False
    return True


def gh_ok(args):
    if len(args) >= 2 and (args[0], args[1]) in GH_READ:
        return True
    if not args or args[0] != "api":
        return False
    for i, a in enumerate(args):
        if re.match(r"^-[a-zA-Z]*[fF]|^--(field|raw-field|input)(=|$)", a):
            return False
        m = re.match(r"^(?:-[a-zA-Z]*X|--method)=?(.*)$", a)
        if m:
            method = m.group(1) or (args[i + 1] if i + 1 < len(args) else "")
            if method.upper() != "GET":
                return False
    return True


def operands(rest):
    out, opts = [], True
    for a in rest:
        if opts and a == "--":
            opts = False
        elif not opts or a == "-" or not a.startswith("-"):
            out.append(a)
    return out


def allowed(argv, here):
    w = argv[0]
    if helper_ok(argv, here):
        return True
    if w in READ_ONLY:
        rest = argv[1:]
        if w == "find" and FIND_ACTIONS & set(rest):
            return False
        if w == "sort" and any(is_abbrev(a, "output") or is_abbrev(a, "compress-program")
                               or short_has(a, "o") for a in rest):
            return False
        if w == "rg" and any(a.startswith("--pre") for a in rest):
            return False
        if w == "tree" and any(short_has(a, "o") for a in rest):
            return False
        if w == "file" and any(short_has(a, "C") or is_abbrev(a, "compile") for a in rest):
            return False
        if w == "date" and any(is_abbrev(a, "set") or (short_has(a, "s") and not a.startswith("-I"))
                               for a in rest):
            return False
        if w == "uniq" and len(operands(rest)) > 1:
            return False
        return True
    if w == "git":
        return git_ok(argv[1:])
    if w == "gh":
        return gh_ok(argv[1:])
    if w == "claude":
        return argv[1:] in (["agents"], ["agents", "--json"])
    return False


here = cwd
for seg in segments:
    if not allowed(seg, here):
        deny("%r is not on the %s's shell allow-list. Allowed: file inspection and search, git "
             "and gh reads, `claude agents`%s. Anything else is a command to the Mate."
             % (" ".join(seg)[:120], SEAT, (", " + HELPER_HINT) if HELPERS else ""))
    if seg[0] == "cd":
        # bare `cd` and `cd -` land somewhere this checker cannot see, so later relative
        # helper paths are refused.
        if len(seg) == 1 or seg[1] == "-" or here is None:
            here = None
        else:
            here = resolve(seg[1], here)
sys.exit(0)
# ==== end SHIP-POSITIVE-LANE ====
EOF

# -I: isolated mode, so a json.py or re.py in the session's cwd cannot shadow the stdlib.
python3 -I -c "$PY" "$SHIP_DIR"
rc=$?
[ "$rc" -eq 0 ] && exit 0
exit 2
