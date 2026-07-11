# Storage Advisor — Revised Design & MVP Plan

> Status: **decisions locked** (v0.2). Supersedes the architecture notes in `README.md`.
> Reviewer decisions from 2026-07-11 folded in (see §9). Not yet implemented.

> **Context:** personal portfolio project by a rising junior CS major who is learning
> Python. Goals ranked: (1) a genuinely useful, demoable MVP; (2) code a reviewer respects
> for its judgment (safety, scoping, data modeling); (3) a credible path toward an
> enterprise story *after* MVP. These goals shape the decisions below.

---

## 1. Problem statement (one paragraph)

The OS tells users *where* their bytes are (biggest folders); it does not tell them *what
is safe to let go of*. Storage Advisor uses filesystem **metadata + usage signals** to turn
"500 GB used" into "here are specific files that are large, old, and untouched — and here's
the evidence." The differentiator is **usage-aware, not just size-aware** insight.

**MVP audience:** a single macOS user analyzing their own home directory. The enterprise /
tiering ambition is a **deliberate post-MVP phase (§7, Phase 4+)**, not part of the MVP — it
implies a different (server/distributed) architecture and must not influence MVP decisions.
Keeping it sequenced (not deleted) is intentional: it's the portfolio "where this goes next"
story, told without letting it distort the MVP build.

## 2. Core product principle

**Advise first; act only when the action is safe by construction.** Trust is the whole game —
one wrongly-deleted precious file ends the product's credibility. So actions are sequenced by
risk, not shipped all at once:

- **MVP** — advise + open in Finder. Zero-risk; proves the insight is trustworthy before the
  app is allowed to touch anything.
- **v1.1** — "Move to Trash." A *reversible-by-design* action (macOS Trash via the system API,
  **never `rm`**), so it's a real feature a reviewer respects *because* it's safe.
- **v2** — permanent delete / move-to-external, gated behind dry-run + undo.

Deliberately sequencing risk is itself the impressive part; a delete button on day one is not.

## 3. Revised architecture

**Decision (locked): Python as a Tauri sidecar over stdio. No FastAPI, no HTTP server.**
Python is the right call here because the developer is learning Python and it reuses the
existing `scanner.py` / `database.py`. But a long-lived localhost HTTP server is the
highest-effort, highest-risk piece and adds an attack surface for zero product value on a
single-machine app — so we keep Python and drop the web server.

**What "sidecar over stdio" means:** Tauri spawns the Python process as a child and
communicates over stdin/stdout (line-delimited JSON), instead of Python running a web server
on a port. Same Python skills; none of the packaging/security baggage of a network API.

```
React UI ──invoke()──▶ Tauri (Rust shell) ──spawn + stdin/stdout──▶ Python (scan + analyze)
   ▲                                                                     │
   └──────────────── JSON results / progress events ────────────────────┘
                                             Python ◀──read/write──▶ SQLite
```

- **Frontend:** React + TypeScript in Tauri (keep).
- **Backend:** Python child process, JSON-over-stdio protocol. Requests: `{cmd, args}`.
  Responses: progress events + a final result, one JSON object per line.
- **Storage:** SQLite (keep) — correct choice at this scale; do not over-engineer.
- **FS access:** Python `os.scandir` (faster than `pathlib.rglob` — returns stat data
  without a second syscall).

> **On the README's async claim:** `async` gives concurrency, not parallelism. A recursive
> disk walk is blocking IO work — running it in the sidecar process already keeps it off the
> UI thread, which is what actually matters. Don't reach for `asyncio` here; a plain worker
> loop that streams progress lines is simpler and correct.

> **FastAPI is worth learning** — just on a project that needs a real network API (a hosted
> service, a mobile client, the future enterprise server in Phase 4+). Not here.

## 4. Data model (must exist before any "trends" feature)

The current schema cannot express snapshots, rescans, or trends. Proposed:

```
scans        (id, root_path, started_at, finished_at, status)
files        (id, scan_id → scans.id, filepath, size_bytes,
              last_modified, last_accessed, is_symlink, inode)
-- indexes on files(scan_id), files(size_bytes), files(last_accessed)
```

- One row in `scans` per scan run → enables growth-over-time by comparing scans.
- `files` rows belong to a scan → rescans are new snapshots, not blind appends.

**Retention (locked):** keep **all `scans` rows forever** — one tiny row per run, so years of
history costs almost nothing and powers the long-term trend chart. Keep **per-file rows only
for the last N scans** (default `N = 12`); prune older `files` rows on each new scan. The
`files` table is the only thing that bloats (hundreds of thousands of rows per scan), so
bounding *it* keeps the DB small while the size-over-time trend is never lost.

## 5. Defining the signals (the actual product)

These need concrete, *user-visible* thresholds — not adjectives:

- **Stale:** `last_modified` older than N months (default 12, configurable). On macOS,
  **`atime` is unreliable** (often disabled/relatime) — treat "last accessed" as best-effort
  and lead with `mtime`.
- **Large:** top percentile by `size_bytes`, or > threshold (e.g. 100 MB).
- **Flagship insight = "Large & Stale"** = large AND stale, ranked by `size × age`.

Duplicate detection is **deferred to v2** (it's the expensive, content-reading feature).

## 6. macOS realities to handle (not optional)

- **TCC / Full Disk Access:** scanning `~` triggers permission prompts; scanner must catch
  `PermissionError` per-file and continue, not crash.
- **iCloud dataless files:** stat-ing placeholders can trigger downloads — detect & skip.
- **APFS clones / hardlinks:** two "duplicate" paths may share storage → "reclaimable GB"
  can be overstated. Reconcile by inode before showing any "free X GB" number.
- **Broken symlinks / permission errors mid-walk** must not abort the scan.

## 7. Phased MVP plan

**Phase 0 — Hygiene (small, do first)**
- Replace `requirements.txt` (currently a machine-specific conda dump; won't install
  anywhere) with a minimal pinned list.
- Architecture confirmed: Python stdio sidecar (§3).
- Define the JSON-over-stdio protocol (request/response/progress shapes).

**Phase 1 — Ingestion that actually supports the product**
- Migrate schema to `scans` + `files` with indexes and the retention rule (§4).
- Rewrite scanner: `os.scandir` with one stat per file (currently 3× via `rglob`), stream in
  batches, per-file error handling, progress reporting, cancellation.

**Phase 2 — One insight, end-to-end (this is the demoable MVP)**
- "Large & Stale files" query + a single UI view: ranked list with evidence
  ("4.2 GB · untouched since 2019"), open-in-Finder. Advise-only, no delete.

**Phase 3 — Trends**
- Growth-over-time using the `scans` history.

**v1.1 — First safe action**
- "Move to Trash" via the macOS system API (reversible; never `rm`).

**v2 — Content & heavier actions**
- Duplicate detection (size → partial-hash → full-hash funnel).
- Permanent delete / move-to-external, gated behind dry-run + undo.
- Configurable thresholds.

**Phase 4+ — Enterprise exploration (post-MVP, the "where it goes next" story)**
- Multi-machine / server model, storage-tiering recommendations, cost modeling. Different
  architecture (this is where a real network API — e.g. FastAPI — earns its place). Kept as a
  sequenced future, explicitly *not* allowed to influence MVP decisions.

## 8. Success criteria for MVP

- Scan `~` without crashing on permission/iCloud/symlink edge cases.
- Show a trustworthy ranked "Large & Stale" list with transparent evidence.
- Rescan produces a new snapshot; DB is queryable for trends.
- No open network port; no destructive action.

## 9. Decisions (resolved 2026-07-11)

1. **Architecture → Python stdio sidecar** (§3). Python chosen for the learning goal + code
   reuse; delivered as a Tauri sidecar over stdio, not a FastAPI HTTP server.
2. **Enterprise → sequenced as Phase 4+, not deleted** (§1, §7). Out of MVP scope; kept as the
   post-MVP portfolio story.
3. **Retention → all `scans` forever, `files` for last N=12** (§4).
4. **Actions → advise-only MVP, then "Move to Trash" (reversible) in v1.1, heavier actions in
   v2** (§2). This resolves the earlier "unsure": we don't skip actions, we *sequence them by
   risk* so the first action shipped is safe by construction.
