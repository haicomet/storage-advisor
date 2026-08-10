# Storage Advisor — Progress Briefing

*A usage-aware macOS storage tool: it doesn't just tell you where your bytes are,
it tells you **what's safe to let go of** — with transparent evidence.*

---

## Where the project is

| Phase | Status | What it delivers |
|---|---|---|
| **1 — Ingestion** | ✅ Done | Fast, robust filesystem scan → queryable SQLite snapshot |
| **2 — One insight** | ✅ Done | "Large & Stale" ranked list w/ evidence + reveal-in-Finder |
| **3 — Trends** | 🔧 In progress | Storage-growth-over-time chart across scan history |
| **4 — macOS reality pass** | ⏭ Next | Make it trustworthy on a real, messy Mac |

**Phase 3 status:** backend query + IPC command are **complete and verified**;
the chart UI is **built**; one integration call (`getTrends` in the frontend)
remains to connect them.

---

## Architecture

```
 React + TypeScript UI
        │  invoke()
        ▼
 Rust (Tauri shell) ──spawn + stdin/stdout──▶ Python sidecar (scan + analyze)
        ▲                                            │
        └────── JSON results / progress events ──────┘
                                            Python ◀──▶ SQLite
```

No web server, no open port — a single-user desktop app talking to a local Python
process over line-delimited JSON.

---

## Design choice #1 — IPC as a Python sidecar over stdio

**Instead of a localhost HTTP server, the Rust shell spawns Python as a child
process and they exchange one JSON object per line over stdin/stdout.**

- **Why not a web server?** For a single-user app, HTTP adds a network port
  (attack surface), CORS/auth concerns, and packaging pain — for zero benefit.
  This keeps all of Python's power with none of that baggage.
- **One long-lived process, not spawn-per-request.** Each request carries an `id`;
  Rust keeps a map of pending requests, and a background thread reads Python's
  output and routes each response back to the caller awaiting it.
- **Streaming, not just request/response.** A scan emits many `progress` messages
  then one terminal `result`/`error` — so the UI shows live progress during long
  scans.
- **Two make-or-break rules, handled deliberately:** stdout is *data only* (logs go
  to stderr, or a stray print corrupts the channel); every message is flushed
  immediately (or Python buffers and the UI hangs). These are the classic traps
  that sink naive stdio IPC.

**Verified working — raw wire output (two scans, then a trends query):**
```json
{"id":"1","type":"result","data":{"scan_id":1,"files_seen":1,"total_bytes":5000000}}
{"id":"2","type":"result","data":{"scan_id":2,"files_seen":1,"total_bytes":20000000}}
{"id":"3","type":"result","data":{"points":[
  {"scan_id":1,"started_at":...,"total_bytes":5000000,"total_human":"5 MB"},
  {"scan_id":2,"started_at":...,"total_bytes":20000000,"total_human":"20 MB"}]}}
```
The IPC + backend work independently of the UI.

---

## Design choice #2 — File traversal that scans a whole home dir fast

**Rewrote the walker on `os.scandir` with an explicit stack and streaming batches:
one syscall per file, flat memory, and it survives a messy filesystem.**

- **One `stat` per file.** `os.scandir` returns entries *with* metadata attached,
  so size/mtime/inode come from a **single `entry.stat()`** call. The naive
  approach `stat()`s each file ~3×. Across hundreds of thousands of files,
  syscalls are the bottleneck — cutting 3→1 is the whole speed story.
- **Iterative, explicit stack** (not recursion) — no recursion-limit risk on deep
  trees, and precise control over what to descend into.
- **Streaming in batches of 2,000** (a generator) — never builds the whole file
  list in memory, so **memory stays flat** at 1K files or 1M, and progress appears
  almost immediately.
- **Robust by design** — per-entry `try/except` (a permission error or broken
  symlink is skipped, not fatal), `follow_symlinks=False`, and a skip-list for
  junk dirs (`node_modules`, `.git`, caches).

*Result: scans an entire home directory in seconds — because of the syscall and
memory design above, not magic.*

---

## Design principles running through it all

- **Advise first; act only when safe.** MVP only *recommends* — deletion is
  deliberately sequenced to a later, reversible "Move to Trash." Sequencing risk
  is the point.
- **Lead with `mtime`, not `atime`** — access-time is unreliable on macOS, so
  staleness evidence stays defensible.
- **`size × age` ranking is intentionally simple/explainable** — credibility rests
  on evidence a user can understand ("4.2 GB · not modified since Jun 2019").
- **Trends read the `scans` summary table, never `files`.** Per-file rows are
  pruned beyond the last 12 scans to bound DB size, but the tiny per-scan total is
  kept *forever* — so the growth chart spans full history for free. (A Phase-1
  decision made specifically to enable Phase 3 cheaply.)

---

## What's next — Phase 4: the macOS reality pass

**Goal: survive a real, messy Mac and stop over-promising.** Phases 1–3 prove the
concept; Phase 4 makes it *trustworthy on real data*.

1. **iCloud dataless files** — `stat`-ing cloud placeholders can *trigger
   downloads*; detect & skip so a scan doesn't silently pull down gigabytes.
2. **Hardlink / APFS-clone reconciliation** — two paths can share the same bytes
   (same inode); summing them **overstates reclaimable space**. Reconcile by inode
   before showing any "free X GB" number. *This is the credibility killer* — and
   ties straight back to the advise-first, trust-is-everything principle.
3. **Configurable thresholds in the UI** — tune "large"/"stale," and **re-query
   without re-scanning** (two distinct operations).
4. **Cancellable scans + clear permission messaging** — graceful handling when
   macOS Full Disk Access is denied, not an empty/crashed scan.

**Through-line:** Phase 4 is about *never lying to the user about reclaimable
space* — the heart of the product.

---

## Immediate next steps

1. Connect `getTrends()` in the frontend (the one remaining Phase 3 gap).
2. Fill in backend trends tests; run the frontend build (recharts).
3. End-to-end run in `tauri dev`; verify empty states.
4. Begin Phase 4.
