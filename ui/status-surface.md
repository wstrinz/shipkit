# Module: Ship UI (TIER 3 — the thread-first browser surface)

The Ship UI is the browser console the Captain actually steers from: an installable PWA
that renders ship state and takes steers. It is **tier 3** — it sits on top of the
autonomous kernel (tier 2), which produces the state it reads and consumes the steers it
writes.

> **The implementation ships on the stacked UI PR**, which fills this `ui/` folder. This
> folder + its `module.json` reserve the tier slot in the manifest/preset system so
> `--preset ui` resolves; the UI PR adds the actual files here. **The reference
> implementation is VENDORED from a live ship's `ui/thread/`** — see "Vendoring" below —
> **not yet locked** (the live seed is still maturing; this doc describes the target shape
> so the tier slot and the doctrine are ready when it locks).

## The primitive is the thread, not the dashboard

Ship's earliest UI sketch was a status *dashboard* — render `status.json`, offer a steer
box. Live operation reversed that: **the conversation thread is the primary surface.** The
Captain reads the thread (what the Mate said, what landed, what's awaiting them) and steers
by replying into it; the status chip and every panel are *accretions* on top of that one
page, not the other way round.

So the UI is built **thread-first**:

- **The thread page (`/thread`) is the primitive core** — ONE page, made genuinely
  excellent: fast, responsive, installable, offline-shell. It renders the append-only
  conversation log and lets the Captain steer by posting into it. Everything else is
  optional weight on top.
- **The status chip is the first accretion** — a small always-visible indicator of what the
  Mate is doing right now (`status.json` → `now.doing` / `now.since` + a freshness dot). It
  rides the thread page; it is not a separate dashboard.
- **Panels roll in one at a time** — queue, tickets, approvals, on-call, briefing. Each is
  an accretion the page is *structured* to accept, but none is built until it earns its
  place. The page ships useful with zero panels. Don't build a "panel framework" ahead of
  the first panel.

The bet: a single page that is genuinely great beats a feature-complete dashboard that's
merely adequate. Radically small on purpose — no framework, no build step, a page you can
read top to bottom.

## What it consumes and writes (the contract, not the code)

The UI is a **frozen-contract, disposable-render** surface: swap the render freely as long
as it reads the same state and writes well-formed steers.

- **The thread log** — an append-only record of captain/mate messages (on the live seed,
  `state/watch-thread.jsonl`: one JSON object per line, `{ts, role, text, ref?, images?,
  reply_to?}`, oldest first). Rendered live; never mutated by the page.
- **`state/status.json`** — the status chip reads it. Field contract:
  [../lib/status.schema.md](../lib/status.schema.md). The UI renders the contract and never
  imports the writer Python.
- **`inbox/drops/`** — the steer box writes a drop here; `lib/classify_input.py` routes it
  to a `wake`-class item the Mate's wake-monitor picks up. Every Captain write goes through
  this declared-envelope drop path — the page never writes ship state directly.
- **Attachments** (optional, if the seed supports it) — image attachments ride the steer
  payload and land in a shared attachment store, byte-compatible with whatever wrote them,
  so the Mate and any other surface read them identically.

This makes the UI a **runtime-orders-after** dependency on the autonomous tier (a thread
log + `status.json` must exist to render), expressed as `requires: ["autonomous"]` in
`module.json`.

### The drop-shape seam (the one config point the vendored UI must expose)

The steer box writes a drop, and **the drop's shape is a per-deployment seam, not a
constant.** Two shapes are in the wild:

- A **minimal envelope** — a generic `{type: "steer", text}` drop that `classify_input.py`
  routes to `wake`. Portable; the shipkit default.
- A **deployment-specific shape** — e.g. a live ship whose `captain_monitor` keys off a
  specific frontmatter block (`status: inbox` / `type: steer` / `source: <surface>` /
  `tags: [captain-steer]`) and filename convention (`captain-ui-{stamp}-{slug}.md`). The
  monitor won't wake on a drop that doesn't match its expected shape.

The vendored UI **must expose the drop shape as configuration** (the frontmatter keys, the
filename pattern, the classify contract it targets) rather than hardcoding one operator's
shape. When vendoring the live seed, this is the field most likely to be operator-specific —
pull it out into config, don't ship the seed's literal `source: ship.html` / `captain-ui-*`
values as the shipkit default.

## Vendoring the reference implementation

The reference UI is **vendored from a live ship's `ui/thread/`**, not authored in shipkit
from scratch — same principle as the rest of shipkit: extract proven practice, don't
speculate. The live seed is a small no-framework server (`server.ts` under Bun) + a
data-free shell (`index.html` + `app.css` + `app.js`) + a service worker + generated icons,
serving `/thread`, `/thread.json`, `/status.json`, an SSE `/events` stream, `POST /inbox`
for steers, and (optionally) `/attachments/*`.

**Not yet locked.** Do not vendor until the Captain locks the live seed as the base — it's
still maturing (snappiness, attachments, PWA polish landed across recent watches; more may
follow). When it locks, vendoring means: copy the seed's files into this `ui/` folder, then
**genericize** — strip the operator's concrete ship paths, ports, hostnames, and the
literal drop shape (see the seam above) into config/defaults, keep the mechanism. Update
`module.json` to list the vendored files and this doc to point at them.

Until then this folder holds only the doc + `module.json` (the reserved tier slot).

## The transition: front-and-proxy, flip pages one at a time

When a ship already has an incumbent UI server and you're standing up the thread-first one,
**don't cut over in a single swap** — you'd lose every not-yet-ported page at once. Use the
**transition reverse-proxy pattern:**

1. **The new server fronts the origin.** Point the external entry (the tailnet/HTTPS proxy,
   the bookmark) at the *new* thread-first server, not the incumbent. The incumbent keeps
   running locally on its own port.
2. **Unported paths proxy to the incumbent.** The new server serves `/thread` (and whatever
   else it has ported) natively; every other path it reverse-proxies to the incumbent
   (`SHIP_INCUMBENT`-style env pointing at the old server). The Captain loses nothing — every
   page still resolves — while only the ported pages are actually native.
3. **Flip pages proxy → native one at a time.** As each panel gets built into the new
   server, it stops proxying that path and serves it natively. The incumbent shrinks to
   whatever hasn't been ported yet, and eventually retires.

Two gotchas the live transition hit, worth carrying:

- **Both servers must share one ship-root.** They read/write the same state files; a
  `SHIP_ROOT` mismatch means the two surfaces disagree. Point both at the same root.
- **Service-worker cache must be an explicit shell ALLOWLIST, never a blocklist.** A
  blocklist SW ("cache everything except these paths") will cache-first the *proxied* pages
  and serve them stale forever (a stale `/approvals` that never updates). Cache only the
  named shell assets (html/css/js/icons); never cache proxied paths, the thread JSON, the
  status JSON, the SSE stream, or the steer POST.

## PWA / secure-context notes

- **Install** requires a secure context: `127.0.0.1` in dev, or an HTTPS origin (e.g. a
  tailnet `serve` URL) on a phone. `standalone` display opens it chrome-free.
- **`POST` (the steer path) is unauthenticated** — keep the proxy **tailnet-only, never a
  public tunnel.** The server should bind loopback only and rely on the proxy for reach.
- **Bump the shell version** when you change html/css/js/icons so the SW drops old caches on
  activate; the update lands on next launch.
