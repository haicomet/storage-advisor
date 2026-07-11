# Storage Advisor — Development Roadmap

> Companion to `DESIGN.md` (the what/why). This is the how/when: phases that each end in a
> **runnable, demoable milestone**. Phase numbers match DESIGN.md §7.
> Difficulty is rated for a rising-junior CS major learning Python: ★ easy → ★★★★★ hard.

**Guiding rule:** every phase must leave `main` in a state you could screen-record. If a phase
doesn't produce something you can *show*, it's too big — split it.

---

## Phase 0 — Foundations & hygiene

**Goal:** a clean, reproducible project you can hand to another machine and run.

**Features / deliverables**
- Minimal pinned `requirements.txt` (replace the conda dump).
- A `README` "how to run" section (backend + frontend dev commands).
- Decide and *document* the JSON-over-stdio message shapes (request / progress / result / error).
- `.gitignore` covers `*.db`, `__pycache__`, `node_modules`, Tauri build output.

**Files/modules**
- `backend/requirements.txt`, `README.md`, `.gitignore`
- `docs/protocol.md` (new) — the stdio contract, even just as examples.

**Depends on:** nothing.

**Learn first**
- `pip freeze` vs. a hand-curated `requirements.txt`; why the current file's `file:///` paths
  break portability.
- Virtual environments (`python -m venv`), so your deps are isolated.

**Difficulty:** ★
**Pitfalls**
- Don't `pip freeze` your whole global env again — list only what you import (`pytest`, and
  later nothing heavy).
- Committing `storage_advisor.db` — add it to `.gitignore` now.

---

## Phase 1 — Ingestion that supports the product

**Goal:** run one command, scan a real directory, and end up with a correct, queryable
snapshot in SQLite — robustly (no crash on permissions/symlinks).

**Features**
- New schema: `scans` + `files` with foreign key and indexes (DESIGN.md §4).
- Retention: keep all `scans`, prune `files` beyond last N=12.
- Rewrite scanner on `os.scandir`: one stat per entry, per-file `try/except`, skip
  unreadable/broken entries, batch inserts (e.g. 1–5k rows), progress callback.
- A tiny CLI entry (`python -m backend.scan <path>`) so you can exercise it before any UI.

**Files/modules**
- `backend/database.py` (schema + upsert/prune + batched insert)
- `backend/scanner.py` (rewrite)
- `backend/scan_cli.py` (new, thin)
- `backend/test_scanner.py`, `backend/test_database.py` (new)

**Depends on:** Phase 0.

**Learn first**
- `os.scandir` vs `pathlib.rglob` and why `DirEntry.stat()` avoids extra syscalls.
- SQLite basics: foreign keys (and that they're **off by default** — `PRAGMA foreign_keys=ON`),
  indexes, transactions, and `executemany` batching.
- Python exception handling around filesystem calls (`PermissionError`, `FileNotFoundError`,
  `OSError` for broken symlinks).
- `pytest` fixtures (`tmp_path`) — you already have one to build on.

**Difficulty:** ★★★
**Pitfalls**
- **The 3× `stat()` bug** in the current scanner — cache one `stat` result.
- Building the entire file list in memory before inserting — stream in batches or a huge home
  dir will spike memory and delay first feedback.
- Recursion via `rglob` follows into places you don't want (e.g. `Library`, `.Trash`) — decide
  what to skip.
- Forgetting `PRAGMA foreign_keys=ON` means your FK silently does nothing.

---

## Phase 2 — One insight, end-to-end (the demoable MVP) ⭐

**Goal:** the first version you'd actually show someone. Click "Scan", watch progress, see a
ranked "Large & Stale" list with evidence, click a file to reveal it in Finder.

This is where the sidecar wiring happens — the riskiest integration in the project, so it gets
its own phase.

**Features**
- Analytics query: "Large & Stale" (large AND `mtime` older than threshold), ranked by
  `size × age`. Return top ~200 with path, size, last-modified, human-readable evidence.
- **Sidecar protocol implemented:** Tauri spawns Python; JSON lines over stdio; a `scan`
  command that streams progress then a final result; a `top_large_stale` query command.
- Rust glue in Tauri: spawn sidecar, forward `invoke` calls, relay progress events to the UI.
- React UI: Scan button → progress bar → results table → "Reveal in Finder" (advise-only, no
  delete).

**Files/modules**
- `backend/analyzer.py` (new — the query)
- `backend/main.py` (finally non-empty — the stdio loop / command dispatcher)
- `frontend/src-tauri/src/lib.rs` (spawn + `invoke` commands), `tauri.conf.json` (register
  the sidecar binary + `externalBin`)
- `frontend/src/App.tsx` (replace the starter template), a `ScanView` + `ResultsTable`
  component, an `api.ts` wrapper around `invoke`.

**Depends on:** Phase 1 (needs a populated DB + scanner).

**Learn first**
- Tauri sidecar / `externalBin` config, and Tauri commands (`#[tauri::command]`) + `invoke`
  from JS. (This is the single biggest new-concept load in the project.)
- How to bundle Python as a runnable binary (PyInstaller) OR run the interpreter in dev — pick
  the **dev path first**, defer bundling to Phase 5.
- Reading/writing line-delimited JSON on stdin/stdout in Python (`sys.stdin`, `print(flush=True)`).
- React state for async/streaming updates (progress events), and rendering a list.
- macOS "reveal in Finder" (`open -R` or Tauri's shell/opener API).

**Difficulty:** ★★★★★ (integration-heavy; budget the most time here)
**Pitfalls**
- **stdio buffering** — Python buffers stdout by default; without `flush=True` (or `-u`) the UI
  hangs waiting for output. Classic first-timer trap.
- Mixing protocol JSON and stray `print()` debug lines on the same stdout stream corrupts the
  channel — send logs to **stderr**, data to stdout.
- macOS TCC: scanning `~` triggers a Full Disk Access prompt; handle the denied case gracefully
  instead of showing an empty/crashed scan.
- Trying to bundle the app (codesigning, PyInstaller) *now* — that's a rabbit hole; stay in
  `tauri dev` until Phase 5.
- Scope creep: resist adding a second insight here. One insight, working, wins.

---

## Phase 3 — Trends over time

**Goal:** the app tells a story across scans: "your Downloads grew 8 GB since April."

**Features**
- Query total size (and optionally per-top-folder) per `scan` over time.
- A trends view: a simple line/area chart of storage over scan history.

**Files/modules**
- `backend/analyzer.py` (add trend query)
- `frontend/src/` (a `TrendsView` + a chart component)

**Depends on:** Phase 2 (needs the sidecar + multiple scans in history).

**Learn first**
- SQL `GROUP BY` / aggregates over the `scans`↔`files` join.
- A React charting lib (Recharts is the gentle default). **Before writing chart code, read the
  `dataviz` skill** — it'll keep the chart clean and accessible.
- Date handling for the x-axis (epoch → display).

**Difficulty:** ★★
**Pitfalls**
- With only one scan there's no trend — seed the UI with an empty/"come back after another
  scan" state so it doesn't look broken.
- Retention pruning (N=12) means old *file* rows are gone, but `scans` totals persist — make
  sure the trend reads from retained aggregates, not pruned per-file rows. (Consider storing a
  `total_bytes` summary column on `scans` at scan time so trends never depend on `files`.)

---

## Phase 4 — Robustness & the macOS reality pass

**Goal:** it survives a real, messy home directory and stops surprising the user.

**Features**
- Handle iCloud dataless placeholders (detect, skip, don't trigger downloads).
- Reconcile hardlinks/APFS clones by inode before reporting any "reclaimable" number.
- Configurable staleness/large thresholds in the UI.
- Cancellable scans; clear permission-denied messaging.

**Files/modules**
- `backend/scanner.py`, `backend/analyzer.py`, a small `settings` store, UI settings panel.

**Depends on:** Phase 2 (and benefits from 3).

**Learn first**
- macOS filesystem specifics: `atime` unreliability, `st_ino`/hardlinks, `SF_DATALESS` /
  iCloud attributes, why "duplicate bytes ≠ reclaimable bytes" on APFS.

**Difficulty:** ★★★★
**Pitfalls**
- Over-promising freed space (the clone/hardlink trap) — this is the credibility killer flagged
  in DESIGN.md §2.
- Threshold changes should re-query, not re-scan — keep those two actions distinct in the UI.

---

## Phase 5 — Packaging & distribution

**Goal:** a `.app` (or `.dmg`) someone can double-click — portfolio-shareable.

**Features**
- Bundle Python (PyInstaller) as the Tauri `externalBin`.
- `tauri build`; app icon; first-run experience.

**Files/modules**
- `frontend/src-tauri/tauri.conf.json`, build scripts, CI (optional GitHub Actions).

**Depends on:** a working Phase 2 (bundling a broken app helps no one).

**Learn first**
- PyInstaller one-file vs one-dir; how Tauri resolves sidecar binaries per-platform (the
  `-<target-triple>` suffix convention).
- macOS codesigning/notarization basics (or the "unsigned app" caveats for a portfolio demo).

**Difficulty:** ★★★★
**Pitfalls**
- Path assumptions that work in `tauri dev` but break in the bundle (relative paths, cwd,
  locating the DB) — use app-data dirs, not cwd.
- Notarization is fiddly; for a portfolio it's fine to document "right-click → Open" rather than
  pay for/fight the full Apple flow.

---

## Phase 6+ — Post-MVP (pick based on portfolio goals)

- **v1.1 — Move to Trash** (reversible; system API, never `rm`). Difficulty ★★.
- **v2 — Duplicate detection** (size → partial-hash → full-hash funnel). Difficulty ★★★★; the
  first genuinely expensive/content-reading feature. Great algorithms talking point.
- **Phase 4+ enterprise exploration** (server model, tiering, cost). This is where a real
  network API (FastAPI) finally earns its place — and where the FastAPI you wanted to learn
  belongs.

---

## Suggested order & why

`0 → 1 → 2` gets you a **demoable MVP** as fast as safely possible. `3` adds the "wow" (trends)
cheaply on top of existing plumbing. `4` makes it trustworthy on real data. `5` makes it
shareable. Everything past that is optional depth you add based on what you want the portfolio
to say. Resist reordering to do the "fun" parts (dedupe, enterprise) before the MVP runs —
that's how portfolio projects end up 60% done and undemoable.
