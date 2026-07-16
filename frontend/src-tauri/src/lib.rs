// lib.rs — Tauri (Rust) shell: spawns the Python sidecar and bridges it to the UI.
//
// Responsibilities (ROADMAP Phase 2):
//   1. Spawn the Python backend as a sidecar child process.
//   2. Expose #[tauri::command] functions the React app calls via invoke().
//   3. Write JSON request lines to the sidecar's stdin, read its stdout lines,
//      and relay `progress` messages to the UI as Tauri events while returning
//      the terminal `result` to the awaiting invoke().
//
// See docs/protocol.md for the wire format. This file is the transport glue; no
// product logic lives here.

// TODO: sidecar handle
//   - The Python process is long-lived (one child, many requests). Store its
//     stdin (and a way to route stdout lines back to the right request id) in
//     Tauri managed state so commands can reuse it. tauri-plugin-shell's
//     sidecar() API is the idiomatic spawn path — add it to Cargo.toml and
//     register the sidecar binary in tauri.conf.json (`externalBin`).
//   - In `tauri dev` you may run the interpreter directly (python -u
//     -m backend.main) instead of a bundled binary; defer PyInstaller bundling
//     to Phase 5 (ROADMAP).

/// Start a scan; stream progress to the UI, resolve with the final result.
///
/// TODO:
///   - Accept `path: String`. Write a {cmd:"scan", args:{path}} request line to
///     the sidecar stdin.
///   - For each stdout line: if type=="progress", emit a Tauri event
///     (e.g. app.emit("scan-progress", data)) the JS api.ts listens for; if
///     type=="result"/"error", resolve/reject this command.
///   - Return the result payload (or an Err mapped from the protocol error).
#[tauri::command]
fn start_scan(_path: String) -> Result<(), String> {
    // TODO: implement
    Err("not implemented".into())
}

/// Query the ranked "Large & Stale" list for the latest scan.
///
/// TODO:
///   - Accept optional limit / stale_months. Send {cmd:"top_large_stale", args}
///     and return the `items` array from the sidecar's `result` message.
///   - This is request/response (no progress) — simpler than start_scan.
#[tauri::command]
fn top_large_stale(_limit: Option<u32>, _stale_months: Option<u32>) -> Result<(), String> {
    // TODO: implement
    Err("not implemented".into())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        // TODO: register commands once implemented:
        //   .invoke_handler(tauri::generate_handler![start_scan, top_large_stale])
        // TODO: spawn the sidecar in .setup() and stash its handle in
        //   app.manage(...) so the commands above can reach it.
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
