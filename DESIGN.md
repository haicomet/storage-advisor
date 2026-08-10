# Storage Advisor — Design Document

> **Status:** Locked (v0.3, 2026-08-10). Supersedes v0.2.
> v0.3 redefines the product from a one-shot storage *advisor* into an ongoing
> storage *companion* that persists state across sessions, monitors free space,
> and safely acts on the user's behalf (Move to Trash, then offload to external
> storage). The architecture, ingestion engine, and safety principle from v0.2
> are retained and reused.

---

## 1. Overview

Storage Advisor is a storage-management companion for a single macOS user. The
operating system reports *where* bytes are (largest folders) but not *what is safe
to remove*, retains no history between sessions, and takes no action on the user's
behalf.

Storage Advisor addresses all three:

- **Usage-aware recommendations.** It surfaces specific files that are large and
  stale, with transparent evidence, rather than broad folder-size overviews.
- **Persistent footprint.** It remembers scan history, the actions it has taken,
  and the user's goals — so progress carries across launches.
- **Monitoring.** It tracks free space over time and flags when the disk is
  running low.
- **Safe action.** It helps the user delete or offload flagged files to external
  storage, with every action recorded, verified, and reversible.

The product is scoped to a single machine. There is no server component and no
network service.

## 2. Guiding principle: advise first, act only when safe

Trust is the product's core constraint. A single wrongly-deleted or lost-in-transit
file destroys user confidence permanently. Actions are therefore sequenced by risk,
and every action is **recorded before execution, verified, and reversible**:

1. **Advise + reveal in Finder** — zero risk. (Shipped.)
2. **Move to Trash** — reversible by design via the macOS Trash system API, never
   `rm`. Serves as the proof of the safe-action framework.
3. **Offload to external storage** — copy → verify → delete original, gated on
   successful verification and disconnect-safety. Reuses the same framework.

Destructive capabilities are never wired directly to the filesystem. The
safe-action framework (§6) is built once, before any destructive feature depends
on it.

## 3. Architecture

Python runs as a Tauri sidecar communicating over stdio. There is no local HTTP
server: a single-machine app gains nothing from a network port and avoids its
attack surface and packaging cost.

```
React UI ──invoke()──▶ Tauri (Rust shell) ──spawn + stdin/stdout──▶ Python (scan/analyze/act)
   ▲                                                                     │
   └──────────────── JSON results / progress events ────────────────────┘
                                             Python ◀──read/write──▶ SQLite
```

- **Frontend** — React + TypeScript, hosted in Tauri.
- **Backend** — a Python child process using a line-delimited JSON protocol.
  Requests are `{id, cmd, args}`; responses are zero or more `progress` events
  followed by exactly one terminal `result` or `error`.
- **Storage** — SQLite.
- **Filesystem access** — Python `os.scandir`, one `stat` per entry, results
  streamed to the database in batches.
- **Actions** — file moves and Trash operations run in the sidecar and are recorded
  to SQLite before and after execution (§6). A future background agent (§8, Phase
  8) can invoke the same scan unattended.

## 4. Data model — the footprint

The footprint is the persistent record that makes the app stateful across sessions.
It extends the existing `scans` and `files` tables with three new tables. The three
goal types (§5) are views over this model rather than independent features.

```
scans      (id, root_path, started_at, finished_at, status, total_bytes,
            disk_free_bytes, disk_total_bytes)          -- disk_* added in Phase 4
files      (id, scan_id → scans.id, filepath, size_bytes,
            last_modified, last_accessed, is_symlink, inode)

actions    (id, kind, filepath, dest_path, size_bytes, inode,
            status, created_at, completed_at, undo_token)
            -- kind ∈ {trash, offload}; this log is both the footprint and undo record
triage     (filepath, decision, decided_at)
            -- decision ∈ {keep, delete, offload, undecided}
goals      (id, kind, target_bytes, threshold_bytes, created_at, status)
            -- kind ∈ {free_amount, stay_above, triage}
```

**Retention.** All `scans` rows are kept indefinitely; each is a small summary that
powers full-history trends. Per-file rows in `files` are kept for the most recent
N = 12 scans and pruned beyond that. The `actions` table is never pruned — it is the
permanent record of every change made to the user's files. Disk-space history is
stored on `scans` (`disk_free_bytes`), so a single scan history drives both the
storage-size trend and the free-space trend.

## 5. Targeting, monitoring, and goals

### Scan target
The default scan target is the user's home directory (`~`). The application does not
require the user to enter a path. Home covers where personal clutter accumulates and
requires a single Full Disk Access grant. Scanning the whole startup disk (`/`) is
out of scope: it includes system files the app must never modify and multiplies
permission friction. Users may later add additional roots — for example, mounting an
external SSD to review what has already been offloaded.

Auto-scanning `~` triggers a macOS Full Disk Access prompt. A denied grant is
handled with clear messaging, never an empty or crashed scan.

### Monitoring
Monitoring is delivered in two stages:

- **In-app timer (Phase 4).** While the application is open, it periodically reads
  free space and, when free space falls below a threshold, flags the user and links
  to current recommendations.
- **Background agent (Phase 8).** A macOS LaunchAgent runs the sidecar scan while
  the application is closed and posts a low-space notification. This delivers the
  full "return the next day" experience and is deferred because unattended execution
  introduces additional lifecycle and safety requirements.

### Goals
Three goal types share one underlying engine:

- **Free a target amount** (`free_amount`) — sum of completed `actions.size_bytes`
  since the goal was created, measured against `target_bytes`.
- **Stay above a threshold** (`stay_above`) — the latest `scans.disk_free_bytes`
  measured against `threshold_bytes`, enforced by the monitor.
- **Triage list** (`triage`) — the `triage` table filtered to `undecided`, letting
  the user work through flagged files over time.

## 6. Safe-action framework

The framework is built once and reused by every destructive feature. Each action
proceeds through four stages:

1. **Record intent** — write an `actions` row with `status = 'pending'` *before*
   touching the filesystem.
2. **Execute** — perform the operation in the sidecar.
3. **Verify** — for an offload, confirm the destination copy matches the source (by
   size and checksum) *before* the original is removed. A cross-volume move is
   always copy → verify → delete original, never a blind move.
4. **Commit or undo** — mark the action `done` with an `undo_token` and expose a
   reversal path (restore from Trash, or move back from external storage).

The following macOS realities are safety-critical and are addressed as part of
offload (Phase 7):

- **APFS clones and hardlinks.** Two paths may share the same bytes (same inode).
  Offloading a clone frees no space; sizes are reconciled by inode before any
  reclaimable-space figure is shown.
- **iCloud dataless files.** Copying or stat-ing a cloud placeholder triggers a
  download. Placeholders are detected and skipped rather than offloaded.
- **Volume disconnect mid-copy.** The destination volume can be removed during an
  offload. Because intent is recorded and the copy is verified before deletion, an
  interrupted offload leaves the original intact and the action `pending`.

## 7. Recommendation signals

- **Stale** — `last_modified` older than N months (default 12, configurable).
  Recommendations lead with `mtime`; macOS `atime` is unreliable and treated as
  best-effort only.
- **Large** — top percentile by `size_bytes`, or above a fixed threshold (e.g.
  100 MB).
- **Large & Stale** — the flagship signal: large *and* stale, ranked by
  `size × age`. This ranked list is the source of candidate files for Trash and
  offload, not merely a report.

## 8. Phased plan

Detailed milestones are in `ROADMAP.md`.

- **Phases 1–2 (complete)** — ingestion; Large & Stale insight end-to-end
  (advise + reveal in Finder).
- **Phase 3 (in progress)** — storage trend over scan history.
- **Phase 4** — auto-target home directory, record disk-space per scan, in-app
  low-space flag.
- **Phase 5** — footprint and goals: `actions`, `triage`, and `goals` tables; the
  three goal views; persistence across sessions.
- **Phase 6** — safe-action framework and Move to Trash.
- **Phase 7** — offload to external storage, including inode and iCloud
  reconciliation and disconnect-safety.
- **Phase 8** — background agent: unattended scans and low-space notifications.

## 9. Success criteria

- Launches and auto-scans the home directory without crashing on permission,
  iCloud, or symlink edge cases.
- Persists its footprint — scan history, actions, and goals — across restarts.
- Flags low disk space and links it to specific Large & Stale recommendations.
- Records, verifies, and can reverse every destructive action, with no data lost on
  an interrupted offload and no overstated reclaimable-space figure.
- Operates entirely on the local machine with no open network port.

## 10. Decision log (2026-08-10, v0.3)

1. The product is an ongoing storage companion — persistent footprint, monitoring,
   and safe actions — rather than a one-shot advisor. The existing engine and
   architecture are reused.
2. Monitoring ships as an in-app timer first (Phase 4); a background LaunchAgent is
   deferred to Phase 8.
3. The safe-action framework is built before any destructive feature. Move to Trash
   (Phase 6) is its first, reversible proof; offload (Phase 7) reuses it.
4. The default scan target is the home directory; whole-disk scanning is out of
   scope for the MVP.
5. All three goal types (free-amount, stay-above, triage) are implemented as views
   over a single footprint engine (§4).
6. The v0.2 "macOS reality pass" is folded into offload (Phase 7) as a set of safety
   prerequisites rather than a standalone phase.
