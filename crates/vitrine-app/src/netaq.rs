//! Credential isolation for the bundled NETAQ widget. Never exposes a token to JavaScript.
use base64::{engine::general_purpose::STANDARD, Engine};
use chacha20poly1305::{aead::{Aead, KeyInit}, ChaCha20Poly1305, Nonce};
use sha2::{Digest, Sha256};
use serde::Deserialize;
use serde_json::{json, Value};
use std::path::PathBuf;

const BUNDLE_SHA256: &str = "de08a0a56db6f7bd8dddd61b086f5f2a8eb4132459868ac6a53691277cff7f51";
const REQUEST: &str = "https://netaq.chobab.app/api/personal/calendar/widget/feed?view=day&anchor=";
const TASK_REQUEST: &str = "https://netaq.chobab.app/api/personal/calendar/widget/task";
const ALLOWED: [&str; 4] = ["https://netaq.chobab.app", "https://calendar.chobab.app", "https://calender.chobab.app", "https://chobab.app"];

#[derive(Deserialize)]
struct Credentials { origin: String, token: String, #[serde(default)] cache: std::collections::BTreeMap<String, Value>, #[serde(default)] webapp_shortcut: String }

pub fn trusted_bundle(package: &str, widget: &str, source: &[u8]) -> bool {
    package == "app.chobab.netaq.widgets" && widget == "today"
        && format!("{:x}", Sha256::digest(source)) == BUNDLE_SHA256
}

fn date_from_request<'a>(method: &str, url: &'a str) -> Option<&'a str> {
    if method != "GET" { return None; }
    let date = url.strip_prefix(REQUEST)?;
    if date.len() != 10 || !date.bytes().enumerate().all(|(i,c)| if i == 4 || i == 7 { c == b'-' } else { c.is_ascii_digit() }) { return None; }
    Some(date)
}

fn credentials() -> Result<Credentials, &'static str> {
    let path = PathBuf::from(std::env::var_os("APPDATA").ok_or("저장 공간을 열지 못했어요")?)
        .join("app.chobab.netaq.desktop").join("widget-v1.enc");
    let data = std::fs::read(&path).map_err(|_| "NETAQ 앱에서 계정을 연결해주세요")?;
    if data.len() < 12 { return Err("연결 정보를 읽지 못했어요"); }
    let entry = keyring::Entry::new("app.chobab.netaq.desktop.widget", "encryption-key").map_err(|_| "보안 저장소를 열지 못했어요")?;
    let key = STANDARD.decode(entry.get_password().map_err(|_| "NETAQ 앱에서 계정을 연결해주세요")?).map_err(|_| "보안 키를 읽지 못했어요")?;
    let cipher = ChaCha20Poly1305::new_from_slice(&key).map_err(|_| "보안 키를 읽지 못했어요")?;
    let plaintext = cipher.decrypt(Nonce::from_slice(&data[..12]), &data[12..]).map_err(|_| "연결 정보를 복원하지 못했어요")?;
    let auth: Credentials = serde_json::from_slice(&plaintext).map_err(|_| "연결 정보를 읽지 못했어요")?;
    if !ALLOWED.contains(&auth.origin.as_str()) || auth.token.is_empty() || auth.token.len() > 200 || auth.token.contains(['\r','\n']) { return Err("연결 정보를 확인해주세요"); }
    Ok(auth)
}

/// Only the bundled widget may use this to open the user's chosen installed web app.
pub fn open_app() {
    if let Ok(auth) = credentials() {
        let shortcut = std::path::Path::new(&auth.webapp_shortcut);
        if shortcut.is_file() && shortcut.extension().and_then(|s|s.to_str()).is_some_and(|s|s.eq_ignore_ascii_case("lnk")) {
            crate::shellapi::open(&auth.webapp_shortcut);
            return;
        }
    }
    // The host is bundled at <install>/desktop-engine/; start the already installed NETAQ app.
    if let Some(exe) = std::env::current_exe().ok().and_then(|p|p.parent()?.parent().map(|d|d.join("netaq-desktop.exe"))) {
        if exe.is_file() { crate::shellapi::open(&exe.to_string_lossy()); }
    }
}

pub fn perform(id: u32, method: &str, url: &str, body: Option<&str>) -> Value {
    let task = if method == "POST" && url == TASK_REQUEST {
        let Some(request) = body.and_then(|b| serde_json::from_str::<Value>(b).ok()) else { return json!({"id":id,"error":"할 일을 확인해주세요"}); };
        let source = request["source"].as_str().unwrap_or("");
        let item = request["id"].as_str().unwrap_or("");
        if !["event", "capture"].contains(&source) || item.is_empty() || item.len() > 200 || !request["done"].is_boolean() { return json!({"id":id,"error":"할 일을 확인해주세요"}); }
        Some(json!({"source": source, "id": item, "done":request["done"]}).to_string())
    } else { None };
    let date = date_from_request(method, url);
    if date.is_none() && task.is_none() { return json!({"id":id,"error":"지원하지 않는 요청입니다"}); }
    let auth = match credentials() { Ok(v) => v, Err(_) => return json!({"id":id,"ok":false,"status":401,"body":""}) };
    let headers = [("Authorization".to_string(), format!("Bearer {}", auth.token)), ("Content-Type".to_string(), "application/json".to_string())];
    if let Some(task) = task {
        let target = format!("{}/api/personal/calendar/widget/task", auth.origin);
        let response = crate::net::perform(id, "POST", &target, &headers, Some(&task));
        return json!({"id":id,"ok":response["ok"],"status":response["status"],"body":"{}"});
    }
    let date = date.unwrap_or("");
    let target = format!("{}/api/personal/calendar/widget/feed?view=day&anchor={}", auth.origin, date);
    let response = crate::net::perform(id, "GET", &target, &headers, None);
    // The daily feed may also contain private notes: return only fields used by the widget.
    if response["ok"] == true {
        if let Some(body) = response["body"].as_str().and_then(|s| serde_json::from_str::<Value>(s).ok()) {
            let filtered = json!({"events":body["events"], "tasks":body["tasks"], "captures":body["captures"]});
            return json!({"id":id,"ok":true,"status":200,"body":filtered.to_string(),"headers":{}});
        }
        return json!({"id":id,"error":"일정을 읽지 못했어요"});
    }
    // Reuse the existing app's encrypted cache; never show it after an explicit 401.
    if response["status"].as_u64() != Some(401) {
        if let Some(body) = auth.cache.get(&format!("day:{date}")) {
            let filtered = json!({"events":body["events"], "tasks":body["tasks"], "captures":body["captures"], "cached":true});
            return json!({"id":id,"ok":true,"status":200,"body":filtered.to_string(),"headers":{}});
        }
    }
    json!({"id":id,"ok":false,"status":response["status"],"body":""})
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn requests_are_strictly_limited() {
        assert!(date_from_request("GET", &format!("{REQUEST}2026-11-24")).is_some());
        assert!(date_from_request("POST", &format!("{REQUEST}2026-11-24")).is_none());
        assert!(date_from_request("GET", &format!("{REQUEST}2026-11-24&other=1")).is_none());
        assert!(date_from_request("GET", "https://evil.example/").is_none());
    }
    #[test] fn task_rejects_untrusted_payload_before_loading_credentials() {
        let bad = perform(7, "POST", TASK_REQUEST, Some(r#"{"source":"event","id":"1","done":"true"}"#));
        assert!(bad["error"].is_string());
        let bad = perform(7, "POST", TASK_REQUEST, Some(r#"{"source":"evil","id":"1","done":true}"#));
        assert!(bad["error"].is_string());
        let bad = perform(7, "POST", "https://evil.example/task", Some(r#"{"source":"event","id":"1","done":true}"#));
        assert!(bad["error"].is_string());
    }
    #[test] fn unknown_bundles_cannot_access_credentials() { assert!(!trusted_bundle("app.chobab.netaq.widgets", "today", b"untrusted")); }
}
