# Storage Advisor — Development Roadmap

> Companion to `DESIGN.md` (the what and why). This document covers the how and
> when: phases that each end in a runnable, demonstrable milestone. Phase numbers
> match DESIGN.md §8.
>
> **Version:** aligned to DESIGN.md v0.3 (2026-08-10). Phases 1–3 are carried
> forward from earlier versions; Phases 4–8 reflect the v0.3 direction (ongoing
> companion: monitoring, footprint, safe actions, offload).

**Guiding rule:** every phase must leave `main` in a state that could be
demonstrated end to end. A phase that produces nothing observable is too large and
should be split.

---

## Phase 1 — Ingestion — **complete**

**Goal:** run a scan and produce a correct, queryable snapshot in SQLite, robust to
permission and symlink errors.

**Delivered**
- Schema: `scans` + `files` with foreign key, indexes, and retention (all `scans`
  kept; `files` pruned beyond the last N = 12).
- Scanner on `os.scandir`: one `stat` per entry, per-entry error handling, batched
  inserts, streamed progress.
- CLI entry point for exercising the pipeline without a UI.

**Files:** `backend/database.py`, `backend/scanner.py`, `backend/scan_cli.py`,
`backend/test_scanner.py`, `backend/test_database.py`.

---

## Phase 2 — Large & Stale insight, end to end — **complete**

**Goal:** the first demonstrable version — scan, watch progress, see a ranked
"Large & Stale" list with evidence, reveal a file in Finder. Advise-only.

**Delivered**
- Analytics query: large *and* stale (`mtime`-based), ranked by `size × age`, with
  human-readable evidence.
- Sidecar protocol implemented: line-delimited JSON over stdio; a streaming `scan`
  command and a `top_large_stale` query.
- Rust glue: sidecar spawn, request routing, progress relay to the UI.
- React UI: scan controls, progress, results table, reveal in Finder.

**Files:** `backend/analyzer.py`, `backend/main.py`,
`frontend/src-tauri/src/lib.rs`, `frontend/src/App.tsx`, `ScanView`,
`ResultsTable`, `api.ts`.

---

## Phase 3 — Trends over time — **in progress**

**Goal:** show storage growth across scans ("storage grew 8 GB since April").

**Features**
- Query total size per completed scan over history.
- A trends view: a line/area chart of storage over scan history.

**Files/modules**
- `backend/analyzer.py` — `scan_trends` query (implemented).
- `backend/main.py` — `trends` command handler (implemented).
- `frontend/src/components/TrendsView.tsx` — chart (implemented).
- `frontend/src/api.ts` — `getTrends` wrapper (**remaining work**).

**Depends on:** Phase 2.

**Remaining work**
- Implement `getTrends()` in `api.ts` to connect the built chart to the working
  backend command.
- Backend trends tests; frontend build with the charting dependency.

**Notes**
- The trend reads from retained `scans` summaries, never from pruned `files` rows,
  so it spans full history.
- With only one scan there is no trend; the view shows an explicit empty state.

---

## Phase 4 — Auto-targeting and monitoring

**Goal:** remove the manual path entry and begin watching the disk. The app scans
the home directory automatically and tracks free space over time, flagging when
storage runs low.

**Features**
- Auto-scan the home directory (`~`) on launch; no path input. Handle the Full Disk
  Access prompt and the denied case gracefully.
- Record `disk_free_bytes` and `disk_total_bytes` on each scan.
- In-app timer: while open, periodically check free space and flag the user when it
  drops below a threshold.

**Files/modules**
- `backend/scanner.py` / a small target-resolution helper (home directory).
- `backend/database.py` — add `disk_*` columns to `scans`.
- `backend/analyzer.py` — free-space history query (extends the trends query).
- `frontend/src/` — remove the path input; add a disk-status / low-space indicator.

**Depends on:** Phase 3 (reuses the scan-history and trend plumbing).

**Considerations**
- Full Disk Access is a first-class state, not an error path.
- Disk-space capture should be part of the scan summary so a single history powers
  both the size trend and the free-space trend.

---

## Phase 5 — Footprint and goals

**Goal:** the app remembers across sessions — history, intended actions, and goals —
so storage cleanup becomes an ongoing, trackable effort rather than a one-shot
report.

**Features**
- New tables: `actions` (the action log / footprint), `triage` (per-file
  keep/delete/offload decisions), `goals`.
- Three goal types as views over the footprint: free a target amount, stay above a
  threshold, and a persistent triage list.
- Goal progress surfaced in the UI and persisted across restarts.

**Files/modules**
- `backend/database.py` — `actions`, `triage`, `goals` tables (never prune
  `actions`).
- `backend/analyzer.py` — goal-progress queries.
- `backend/main.py` — commands to create/read goals and record triage decisions.
- `frontend/src/` — a goals view and per-file triage controls in the results table.

**Depends on:** Phase 4 (goals reference disk-space history and, later, actions).

**Considerations**
- Goals are three views over one engine (action log + disk-space history + triage
  tags); model the shared engine once.
- The `actions` table is defined here but only populated once actions ship (Phase
  6); reads should tolerate an empty log.

---

## Phase 6 — Safe-action framework and Move to Trash

**Goal:** the app can act on files safely. Build the record → execute → verify →
undo machinery once, and prove it with the lowest-risk action: Move to Trash.

**Features**
- Safe-action framework: record intent in `actions` before touching the filesystem;
  execute in the sidecar; mark done with an undo token.
- Move to Trash via the macOS Trash system API (reversible; never `rm`).
- Undo path (restore from Trash) surfaced in the UI.

**Files/modules**
- `backend/actions.py` (new) — the framework and the Trash operation.
- `backend/main.py` — `move_to_trash` / `undo_action` commands.
- `frontend/src/` — action buttons on recommendations; footprint/undo view.

**Depends on:** Phase 5 (writes to the `actions` table).

**Considerations**
- Every action is recorded before execution so an interrupted operation is
  recoverable.
- This framework is the foundation offload depends on; get record/verify/undo right
  here before adding cross-volume moves.

---

## Phase 7 — Offload to external storage

**Goal:** move cold files to an external volume (e.g. an SSD) safely, reusing the
Phase 6 framework. This is the highest-risk feature and the strongest user value.

**Features**
- Detect available external volumes as offload destinations.
- Offload as copy → verify → delete-original: the original is removed only after the
  destination copy is verified by size and checksum.
- Reconcile hardlinks / APFS clones by inode before reporting reclaimable space.
- Detect and skip iCloud dataless placeholders.
- Survive destination disconnect mid-copy: the original is preserved and the action
  remains `pending`.

**Files/modules**
- `backend/actions.py` — the offload operation and verification.
- `backend/scanner.py` / `backend/analyzer.py` — inode reconciliation; iCloud
  placeholder detection.
- `frontend/src/` — destination selection; offload progress and verification state.

**Depends on:** Phase 6 (framework) and Phase 4 (targeting).

**Considerations**
- Never overstate reclaimable space: shared-inode bytes are not freed by offloading
  a clone.
- Never trigger an iCloud download in the course of an offload.
- Verification before deletion is non-negotiable — a blind cross-volume move is not
  acceptable.

---

## Phase 8 — Background agent

**Goal:** deliver monitoring when the app is closed — the full "return the next day"
experience.

**Features**
- A macOS LaunchAgent that runs the sidecar scan on a schedule while the app is
  closed.
- Low-space notifications that deep-link back into the app's recommendations.

**Files/modules**
- A LaunchAgent plist and install/uninstall flow.
- Reuse of the Phase 4 scan and monitoring logic.

**Depends on:** Phase 4 (monitoring) and Phase 6/7 (so notifications can point at
actionable recommendations).

**Considerations**
- Unattended execution must be conservative: scan and notify only. It must never
  take a destructive action without explicit user confirmation in the app.
- Lifecycle matters: install, update, and cleanly uninstall the agent.

---

## Suggested order and rationale

Phases 1–3 establish and visualize the data. Phase 4 makes the app proactive
(auto-target + monitoring) and Phase 5 makes it persistent (footprint + goals) —
together turning a report into a companion. Phase 6 introduces safe action on the
lowest-risk operation, and Phase 7 reuses that same framework for the high-value,
high-risk offload. Phase 8 extends monitoring beyond the app's runtime.

The dependency spine is 4 → 5 → 6 → 7, with 8 building on Phase 4's monitoring.
Offload is deliberately last among the action features: it is the riskiest
operation and must inherit a safety framework that has already been proven on
reversible actions.
