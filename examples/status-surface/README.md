# status-surface — the minimal reference UI

A tiny, zero-dependency status surface for a Loop-Mode Ship. It renders the
loop's `state/status.json` and lets the Captain drop a steer from a browser —
phone or desktop.

This is the **minimal reference exemplar**, not the whole UI. It deliberately
shows only the core `status.json` contract plus a steer box. Richer surfaces
(SSE live-update, a hot-list, ticket/card pages, push notifications, gauges)
are **separate optional modules** layered on top — not this.

## Run

```sh
python3 server.py
```

Then open <http://localhost:8000>. No `npm`, no `pip`, no build step —
Python 3 stdlib only, cross-platform.

By default it reads/writes the shipkit checkout this file lives in
(`../../state/status.json` and `../../inbox/drops/`). Override with env vars
if your ship lives elsewhere:

```sh
SHIP_ROOT=/path/to/ship PORT=8080 python3 server.py
```

## What it shows

- **Now** — `now.doing`, how long ago `now.since` was, and the `now.wake` reason.
- **Tick** — the monotonic loop counter.
- **Next wake** — when/why the loop next plans to wake.
- **Validator** — the loop's self-check state (green when `CLEAN`).
- **Last actions** — the most recent `last_actions[]`.

The page polls `GET /status.json` every 5 seconds. If a field is absent (a
headless loop writes only the core fields), it simply isn't shown.

## The steer box

Typing a steer and pressing **Send** issues `POST /steer`, which writes a
well-formed drop into `inbox/drops/` carrying the declared input envelope
(`shipkit_input: v1`, `source: status-surface`, `kind: steer`,
`wake_class: wake`). Because `wake_class` is declared, `classify_input.py`
reads it verbatim (no heuristic guessing) and the drop rides the normal
`classify_input → wake` path, so the loop wakes and responds to it the same way
it would any Captain steer — no special casing.

## Endpoints

| Method | Path           | Does                                                       |
|--------|----------------|-----------------------------------------------------------|
| `GET`  | `/`            | serves `index.html`                                       |
| `GET`  | `/status.json` | returns the loop's `state/status.json` (read fresh)       |
| `POST` | `/steer`       | writes a `type: steer` drop into `inbox/drops/`           |

## The contract it renders

The surface reads only the **core** `status.json` fields, so it works against a
headless seed:

```jsonc
{
  "tick": 0,
  "wake_reason": "captain-launch",
  "now":  { "doing": "...", "since": "<ISO>", "wake": "..." },
  "next_wake": "HH:MM <tz> (reason)",
  "last_actions": ["..."],
  "validator": "CLEAN ✅"   // optional — omitted if no validator module
}
```

Rich fields a preset might add (`hot_list`, `ready_for_you`, `crew[]`, …) are
ignored here by design.
