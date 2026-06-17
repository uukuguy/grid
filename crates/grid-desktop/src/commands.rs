//! Tauri IPC commands exposed to the WebView frontend.

use std::sync::atomic::Ordering;
use tauri::command;

use crate::server::SERVER_PORT;

#[command]
pub fn get_status() -> String {
    if SERVER_PORT.load(Ordering::SeqCst) > 0 {
        "running".to_string()
    } else {
        "starting".to_string()
    }
}

#[command]
pub fn get_port() -> u16 {
    SERVER_PORT.load(Ordering::SeqCst)
}

#[command]
pub fn get_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[derive(serde::Serialize)]
pub struct AppInfo {
    pub version: String,
    pub status: String,
    pub port: u16,
    pub platform: String,
    pub debug: bool,
}

#[command]
pub fn get_app_info() -> AppInfo {
    let port = SERVER_PORT.load(Ordering::SeqCst);
    AppInfo {
        version: env!("CARGO_PKG_VERSION").to_string(),
        status: if port > 0 {
            "running".to_string()
        } else {
            "starting".to_string()
        },
        port,
        platform: std::env::consts::OS.to_string(),
        debug: cfg!(debug_assertions),
    }
}

#[command]
pub fn get_dashboard_url() -> String {
    let port = SERVER_PORT.load(Ordering::SeqCst);
    format!("http://127.0.0.1:{}", port)
}

#[command]
pub fn get_api_base() -> String {
    let port = SERVER_PORT.load(Ordering::SeqCst);
    format!("http://127.0.0.1:{}", port)
}

#[command]
pub fn get_ws_url() -> String {
    let port = SERVER_PORT.load(Ordering::SeqCst);
    format!("ws://127.0.0.1:{}/ws", port)
}

#[derive(serde::Deserialize)]
pub struct ApiRequest {
    pub method: String,
    pub path: String,
    pub body: Option<String>,
}

#[derive(serde::Serialize)]
pub struct ApiResponse {
    pub status: u16,
    pub body: String,
}

#[command]
pub async fn send_api_request(req: ApiRequest) -> Result<ApiResponse, String> {
    let port = SERVER_PORT.load(Ordering::SeqCst);
    let url = format!("http://127.0.0.1:{}{}", port, req.path);

    let client = reqwest::Client::new();
    let request_builder: reqwest::RequestBuilder = match req.method.to_uppercase().as_str() {
        "GET" => client.get(&url),
        "POST" => client.post(&url),
        "DELETE" => client.delete(&url),
        "PATCH" => client.patch(&url),
        "PUT" => client.put(&url),
        _ => return Err(format!("Unsupported method: {}", req.method)),
    };

    let request_builder = if let Some(body) = req.body {
        request_builder.header("Content-Type", "application/json").body(body)
    } else {
        request_builder
    };

    let response = request_builder
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    let status = response.status().as_u16();
    let body = response.text().await.unwrap_or_default();

    Ok(ApiResponse { status, body })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_before_server_start() {
        // When SERVER_PORT is 0, status should be "starting"
        SERVER_PORT.store(0, Ordering::SeqCst);
        assert_eq!(get_status(), "starting");
    }

    #[test]
    fn status_after_server_start() {
        SERVER_PORT.store(3456, Ordering::SeqCst);
        assert_eq!(get_status(), "running");
        // Reset to avoid polluting other tests
        SERVER_PORT.store(0, Ordering::SeqCst);
    }

    #[test]
    fn port_returns_stored_value() {
        SERVER_PORT.store(8080, Ordering::SeqCst);
        assert_eq!(get_port(), 8080);
        SERVER_PORT.store(0, Ordering::SeqCst);
    }

    #[test]
    fn version_is_not_empty() {
        let version = get_version();
        assert!(!version.is_empty(), "version should not be empty");
    }

    #[test]
    fn app_info_reflects_current_state() {
        SERVER_PORT.store(0, Ordering::SeqCst);
        let info = get_app_info();
        assert_eq!(info.status, "starting");
        assert_eq!(info.port, 0);
        assert!(!info.version.is_empty());
        assert!(!info.platform.is_empty());

        SERVER_PORT.store(9090, Ordering::SeqCst);
        let info = get_app_info();
        assert_eq!(info.status, "running");
        assert_eq!(info.port, 9090);
        SERVER_PORT.store(0, Ordering::SeqCst);
    }

    #[test]
    fn dashboard_url_format() {
        SERVER_PORT.store(4321, Ordering::SeqCst);
        assert_eq!(get_dashboard_url(), "http://127.0.0.1:4321");
        SERVER_PORT.store(0, Ordering::SeqCst);
    }
}
