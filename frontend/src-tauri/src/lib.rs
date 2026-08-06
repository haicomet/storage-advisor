// lib.rs — Tauri (Rust) shell: spawns the Python sidecar and bridges it to the UI.
use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};
use std::sync::{atomic::{AtomicUsize, Ordering}, Arc, Mutex};
use std::thread;
use tauri::{AppHandle, Emitter, Manager, State};

// stores IPC pipes and routing map safely in memory so Tauri
// commands can access them across different threads
type PendingRequests = Arc<Mutex<HashMap<String, std::sync::mpsc::Sender<Result<Value, String>>>>>;

struct SidecarState {
    stdin: Mutex<std::process::ChildStdin>,
    requests: PendingRequests,
}

fn spawn_sidecar(app: &AppHandle, requests: PendingRequests) -> std::process::ChildStdin {
    // launches the daemon unbuffered (-u) from the root project directory
    let mut child = Command::new("python")
        .args(["-u", "-m", "backend.main"])
        .current_dir("../../") // step up out of frontend/src-tauri/ to the project root
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit()) // let Python error logs pass straight to our terminal
        .spawn()
        .expect("Failed to spawn Python sidecar. Ensure you are running this from the right directory.");

    let stdin = child.stdin.take().expect("Failed to open stdin pipe");
    let stdout = child.stdout.take().expect("Failed to open stdout pipe");
    
    let app_clone = app.clone();

    // spawn a background thread to endlessly read from the Python stdout pipe
    thread::spawn(move || {
        let reader = BufReader::new(stdout);
        
        for line in reader.lines() {
            let line = match line {
                Ok(l) => l,
                Err(_) => break, // EOF received, pipe closed, thread dies cleanly
            };

            // parse the JSON-over-stdio line
            if let Ok(msg) = serde_json::from_str::<Value>(&line) {
                let msg_type = msg["type"].as_str().unwrap_or("");
                let req_id = msg["id"].as_str().unwrap_or("").to_string();

                if msg_type == "progress" {
                    // progress events don't resolve a promise. they are broadcasted
                    // to the entire React app using Tauri's event emitter.
                    let _ = app_clone.emit("scan-progress", &msg["data"]);
                } 
                else if msg_type == "result" {
                    // find the sleeping React request and wake it up with the data
                    if let Some(channel) = requests.lock().unwrap().remove(&req_id) {
                        let _ = channel.send(Ok(msg["data"].clone()));
                    }
                } 
                else if msg_type == "error" {
                    // find the sleeping React request and wake it up with a failure
                    if let Some(channel) = requests.lock().unwrap().remove(&req_id) {
                        let err_msg = msg["error"]["message"].as_str().unwrap_or("Unknown error").to_string();
                        let _ = channel.send(Err(err_msg));
                    }
                }
            }
        }
    });

    stdin
}

// helper router
static REQ_COUNTER: AtomicUsize = AtomicUsize::new(1);

fn send_request(
    cmd: &str,
    args: Value,
    state: State<'_, SidecarState>,
) -> Result<Value, String> {
    let req_id = format!("req_{}", REQ_COUNTER.fetch_add(1, Ordering::SeqCst));
    
    // create a one-time-use channel for this specific request
    let (tx, rx) = std::sync::mpsc::channel();
    state.requests.lock().unwrap().insert(req_id.clone(), tx);
    
    let payload = json!({
        "id": req_id,
        "cmd": cmd,
        "args": args
    });
    
    let mut req_str = payload.to_string();
    req_str.push('\n'); // line-delimited JSON requires the newline
    
    // lock the stdin pipe, write string, and forcefully flush it
    {
        let mut stdin = state.stdin.lock().unwrap();
        stdin.write_all(req_str.as_bytes()).map_err(|e| e.to_string())?;
        stdin.flush().map_err(|e| e.to_string())?;
    }
    
    // block this specific command thread until the background listener
    // drops a response into our channel (Tauri commands run in a threadpool
    // so this won't freeze the UI)
    rx.recv().map_err(|_| "Sidecar Python process died unexpectedly".to_string())?
}

// Tauri commands (exposed to React)

#[tauri::command]
async fn start_scan(path: String, state: State<'_, SidecarState>) -> Result<Value, String> {
    send_request("scan", json!({ "path": path }), state)
}

#[tauri::command]
async fn top_large_stale(limit: Option<u32>, stale_months: Option<u32>, state: State<'_, SidecarState>) -> Result<Value, String> {
    send_request(
        "top_large_stale",
        json!({ "limit": limit, "stale_months": stale_months }),
        state,
    )
}

#[tauri::command]
async fn get_trends(state: State<'_, SidecarState>) -> Result<Value, String> {
    // Forward to the Python sidecar's `trends` command. No args for the MVP.
    // Modeled on top_large_stale; returns the raw { points: [...] } result Value.
    send_request("trends", json!({}), state)
}

#[tauri::command]
fn reveal_in_finder(filepath: String) -> Result<(), String> {
    #[cfg(target_os = "macos")]
    {
        let status = std::process::Command::new("open")
            .arg("-R")
            .arg(&filepath)
            .status()
            .map_err(|e| format!("Failed to execute 'open': {}", e))?;

        if !status.success() {
            return Err(format!("macOS could not find or open: {}", filepath));
        }
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            // when the app starts, spawn the Python daemon and save its
            // pipes/state into Tauri's managed memory.
            let requests_map: PendingRequests = Arc::new(Mutex::new(HashMap::new()));
            let stdin_pipe = spawn_sidecar(app.handle(), requests_map.clone());
            
            app.manage(SidecarState {
                stdin: Mutex::new(stdin_pipe),
                requests: requests_map,
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            start_scan,
            top_large_stale,
            get_trends,
            reveal_in_finder
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
