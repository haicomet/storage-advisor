# Storage Advisor — Development Roadmap

> Companion to `DESIGN.md` (the what and why). This document covers the how and
> when: phases that each end in a runnable, demonstrable milestone. Phase numbers
> match DESIGN.md §8.
>
> **Version:** aligned to DESIGN.md v0.4 (2026-08-19). Phases 1–4 are complete.
> v0.4 adds Phase 4.5 (richer signals — Large-any-age + folder rollups) before the
> footprint/goals work, and makes triage folder-aware. Duplicates is scheduled as a
> later, separate phase (the only content-reading signal).

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

## Phase 3 — Trends over time — **complete**

**Goal:** show a trend across scans. Landed as **free space over time** ("am I
trending toward a full disk?"), which fits the monitoring direction better than
scanned-folder size.

**Delivered**
- `analyzer.disk_history` query + `disk_history` sidecar command + `get_disk_history`
  Rust command + `getDiskHistory()` wrapper.
- `TrendsView` renders "Free Space Over Time" (`disk_free_bytes` per scan).
- Reads retained `scans` summaries (with `disk_free_bytes`), never pruned `files`
  rows, so it spans full history. Explicit empty states for 0 and 1 scans.

**Note:** the earlier scanned-folder-size query (`scan_trends` / `get_trends`)
remains in the backend, unused; keep or remove at cleanup.

---

## Phase 4 — Auto-targeting and monitoring — **complete**

**Goal:** remove manual path entry and begin watching the disk.

**Delivered** (verified on macOS: auto-scan, disk status, and free-space chart all
working)
- Auto-scan the home directory (`~`) on launch; no path input. `start_scan` accepts
  an optional path (`None` → home). Permission-denied is a first-class UI state with
  Full Disk Access guidance.
- `disk.py` (target resolution + `shutil.disk_usage`); `disk_free_bytes` /
  `disk_total_bytes` recorded on each scan.
- `disk_status` command + `DiskStatusBar` (free/total, usage meter, low-space flag);
  in-app timer polls every 10 s.

---

## Phase 4.5 — Richer signals (offload candidates + folder cohorts)

**Goal:** broaden recommendations beyond the "Large & Stale" sliver so triage and
offload have a real menu of candidates — and make folders the primary unit. All
metadata-only: queries over the `files` rows already collected, no new scanning.

**Features**
- **Large (any age)** query — big files ranked by size, the primary *offload*
  candidate list (staleness is not a gate for offload; it is reversible).
- **Folder rollups** — directories ranked by **recursive** total size (a folder =
  its whole subtree). Surfaces the "school-year folder" cohort case.
- **No double-counting** — when totalling reclaimable space across a selection,
  collapse overlapping paths to their topmost selected ancestor so a parent and
  child are never counted twice (folder-level form of the §6 reclaimable-space rule).
- Signals split by action in the UI: **delete** view leads with stale; **offload**
  view leads with size / folders.

**Files/modules**
- `backend/analyzer.py` — `large_files(...)` and `folder_rollups(...)` queries.
- `backend/main.py` — `large_files` / `folder_rollups` commands.
- `frontend/src-tauri/src/lib.rs` — matching forwarder commands.
- `frontend/src/` — `types.ts` FolderRollup/large-file shapes; `api.ts` wrappers; an
  offload-candidates view (folders first, drill-down to files).

**Depends on:** Phase 4 (uses the populated `files` table).

**Considerations**
- Folder size is recursive, not direct-only; rank actionable folders above a size
  threshold and let the user drill down.
- Reclaimable totals must never double-count parent + child — same principle as
  APFS-clone reconciliation, practised here first on the cheaper folder case.
- Duplicates are explicitly *not* here — that signal reads file content and is a
  later, separate phase.

---

## Phase 5 — Footprint and goals

**Goal:** the app remembers across sessions — history, intended actions, and goals —
so storage cleanup becomes an ongoing, trackable effort rather than a one-shot
report.

**Features**
- New tables: `actions` (the action log / footprint), `triage` (keep/delete/offload
  decisions), `goals`. `triage` and `actions` key on a `path` that may be a
  **directory** (`is_dir`) — triage is folder-first (§4 of DESIGN).
- Three goal types as views over the footprint: free a target amount, stay above a
  threshold, and a persistent triage list.
- Goal progress surfaced in the UI and persisted across restarts.

**Files/modules**
- `backend/database.py` — `actions`, `triage`, `goals` tables (never prune
  `actions`; `path` + `is_dir`).
- `backend/analyzer.py` — goal-progress queries.
- `backend/main.py` — commands to create/read goals and record triage decisions.
- `frontend/src/` — a goals view; **folder-level** triage controls (keep/delete/
  offload on a cohort), individual files as the exception.

**Depends on:** Phase 4.5 (triage operates on the folder/large-file candidates it
produces) and Phase 4 (disk-space history).

**Considerations**
- Triage is folder-first: the unit is usually a cohort ("~/School/Fall2024"), not a
  single file. Drive it from the Phase 4.5 candidate lists.
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

## Duplicates — content-based detection (later, separate)

**Goal:** find redundant copies — the *safest* deletes, since the original remains.
Scheduled after offload: its story is strong but it must not block the cheap
Phase 4.5 signal wins, and it is the first feature that reads file *content*.

**Features**
- A size → partial-hash → full-hash funnel: group by `size_bytes`, then hash a
  prefix of same-size files, then full-hash only the survivors — so hashing cost
  stays proportional to actual duplication, not to the whole disk.
- Present duplicate sets with a safe default (keep one, offer to Trash the rest).

**Files/modules**
- `backend/scanner.py` / a new hashing module — the funnel (content reads).
- `backend/analyzer.py` — duplicate-set query; `backend/main.py` — command.
- `frontend/src/` — duplicate-sets view feeding the same triage/actions flow.

**Depends on:** Phase 6 (safe-action framework, for the delete). Independent of the
metadata signals, so it can slot in whenever content-hashing is worth the cost.

**Considerations**
- This is the only signal that reads bytes, not just metadata — budget for the cost
  and keep the funnel tight.
- Reconcile against inode/clone data (§Phase 7): two paths sharing one inode are not
  true duplicates to reclaim.

---

## Suggested order and rationale

Phases 1–4 establish, visualize, and monitor the data — the app is already proactive.
Phase 4.5 broadens the signal layer cheaply (Large-any-age + folder rollups) so the
following phases triage the *right* things — folder cohorts, not a stale sliver.
Phase 5 makes the app persistent (footprint + goals) on top of those candidates.
Phase 6 introduces safe action on the lowest-risk operation (Trash), and Phase 7
reuses that framework for the high-value, high-risk offload. Phase 8 extends
monitoring beyond the app's runtime. Duplicates is a later, self-contained addition —
the first content-reading signal — that reuses the Phase 6 action framework.

The dependency spine is 4 → 4.5 → 5 → 6 → 7, with 8 building on Phase 4's monitoring
and Duplicates hanging off Phase 6. Offload is deliberately last among the action
features: it is the riskiest operation and must inherit a safety framework already
proven on reversible actions. Folders are the primary unit of triage and offload
throughout (confirmed: the user's reclaimable clutter is folder-shaped).
