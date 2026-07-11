# Sidecar Protocol (JSON-over-stdio)

> **Status:** contract definition (Phase 0). *Implemented* in Phase 2 — this file exists now
> so Phase 1 can design its return values to fit. Not code, just the agreement.

## How it works

Tauri (the Rust shell) spawns the Python backend as a child process. They talk over the
child's **stdin/stdout** using **line-delimited JSON** (one complete JSON object per line,
`\n`-terminated). No HTTP, no port.

```
Tauri ──(one JSON request per line on stdin)──▶ Python
Tauri ◀──(many JSON messages per line on stdout)── Python
```

**Two hard rules** (both are classic first-timer traps — see ROADMAP Phase 2 pitfalls):
1. **stdout is data only.** Every log/debug/traceback goes to **stderr**. A stray `print()` on
   stdout corrupts the channel.
2. **Flush after every message** (`print(json.dumps(msg), flush=True)` or run Python with
   `-u`). Without flushing, Python buffers and the UI hangs waiting.

## Requests (Tauri → Python)

```json
{ "id": "req-1", "cmd": "scan",           "args": { "path": "/Users/me" } }
{ "id": "req-2", "cmd": "top_large_stale", "args": { "limit": 200, "stale_months": 12 } }
```
- `id` — correlates responses to this request.
- `cmd` — the operation. Phase 1/2 commands: `scan`, `top_large_stale` (later: `trends`).

## Responses (Python → Tauri)

Every message carries the originating `id` and a `type`. A request produces zero-or-more
`progress` messages, then exactly one terminal message (`result` **or** `error`).

```json
{ "id": "req-1", "type": "progress", "data": { "files_seen": 12000, "current_dir": "/Users/me/Pictures" } }
{ "id": "req-1", "type": "result",   "data": { "scan_id": 7, "files_seen": 84213, "duration_ms": 5120 } }
{ "id": "req-2", "type": "result",   "data": { "items": [ /* file rows */ ] } }
{ "id": "req-1", "type": "error",    "error": { "code": "PERMISSION_DENIED", "message": "Full Disk Access required for /Users/me/Library" } }
```

### `file row` shape (returned by queries, rendered by the UI)
```json
{
  "filepath": "/Users/me/Movies/old.mov",
  "size_bytes": 4509715660,
  "last_modified": 1561939200,
  "size_human": "4.2 GB",
  "evidence": "4.2 GB · not modified since Jun 2019"
}
```

## Why define this in Phase 0

Phase 1's scanner/analyzer functions should **return plain dicts/lists that map cleanly onto
these shapes**. If you design the DB queries to already produce `file row`-shaped dicts, Phase
2 becomes "wire it up" instead of "reshape everything." Design to the contract now; implement
the transport later.
