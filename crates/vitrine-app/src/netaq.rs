//! Credential isolation for the bundled NETAQ widget. Never exposes a token to JavaScript.
use base64::{engine::general_purpose::STANDARD, Engine};
use chacha20poly1305::{aead::{Aead, KeyInit}, ChaCha20Poly1305, Nonce};
use sha2::{Digest, Sha256};
use serde::Deserialize;
use serde_json::{json, Value};
use std::path::PathBuf;

const BUNDLE_DIGESTS: &[(&str, &str)] = &[
    ("today", "1d8eb0f0d46dfbfea3ca59d6cf0a660d004725066fe8860ab86a54b333473a3a"),
    ("week", "c3c988bd67e3a5227a494b260e3d189f8e5fd1ca845f62d793395e860bfbd96e"),
    ("month", "57b51c9c265c8db2eb6e767b95b403a1f12caa670d4351d2fb2a377e4546ea29"),
    ("tasks", "1506f33839e3fd1a2e7b73e0f59ae4bbcf01a6111f158c31fd6e65430b9bb8c1"),
    ("memo", "e6e2e4d1c4a531bdaa3ae1f28cd06dd6bdff57f31853ed009ade6a20fc33e562"),
];
const FEED_REQUEST: &str = "https://netaq.chobab.app/api/personal/calendar/widget/feed?view=";
const TASK_REQUEST: &str = "https://netaq.chobab.app/api/personal/calendar/widget/task";
const ALLOWED: [&str; 4] = ["https://netaq.chobab.app", "https://calendar.chobab.app", "https://calender.chobab.app", "https://chobab.app"];

#[derive(Deserialize)]
struct Credentials { origin: String, token: String, #[serde(default)] cache: std::collections::BTreeMap<String, Value>, #[serde(default)] webapp_shortcut: String }

fn decrypt_credentials(data: &[u8], key: &[u8]) -> Result<Credentials, &'static str> {
    if data.len() < 12 { return Err("연결 정보를 읽지 못했어요"); }
    let cipher = ChaCha20Poly1305::new_from_slice(key).map_err(|_| "보안 키를 읽지 못했어요")?;
    let plaintext = cipher.decrypt(Nonce::from_slice(&data[..12]), &data[12..]).map_err(|_| "연결 정보를 복원하지 못했어요")?;
    serde_json::from_slice(&plaintext).map_err(|_| "연결 정보를 읽지 못했어요")
}

pub fn trusted_bundle(package: &str, widget: &str, source: &[u8]) -> bool {
    package == "app.chobab.netaq.widgets" && BUNDLE_DIGESTS.iter().any(|(id,digest)| *id == widget && format!("{:x}", Sha256::digest(source)) == *digest)
}

fn feed_from_request<'a>(widget: &str, method: &str, url: &'a str) -> Option<(&'a str, &'a str)> {
    if method != "GET" { return None; }
    let request = url.strip_prefix(FEED_REQUEST)?;
    let (view,date) = request.split_once("&anchor=")?;
    let permitted = match widget { "today"|"memo"=>"day", "week"=>"week", "month"=>"month", "tasks"=>"tasks", _=>return None };
    if view != permitted || date.len() != 10 || !date.bytes().enumerate().all(|(i,c)| if i == 4 || i == 7 { c == b'-' } else { c.is_ascii_digit() }) { return None; }
    Some((view,date))
}
fn filtered_feed(widget: &str, body: &Value, cached: bool) -> Value {
    let mut result = match widget {
        "today" => json!({"events":body["events"],"tasks":body["tasks"],"captures":body["captures"]}),
        "week"|"month" => json!({"events":body["events"]}),
        "tasks" => json!({"events":body["events"],"captures":body["captures"]}),
        "memo" => json!({"note":body["note"],"noteDate":body["noteDate"]}),
        _ => json!({}),
    };
    if cached { result["cached"]=json!(true); } result
}

fn credentials() -> Result<Credentials, &'static str> {
    let path = PathBuf::from(std::env::var_os("APPDATA").ok_or("저장 공간을 열지 못했어요")?)
        .join("app.chobab.netaq.desktop").join("widget-v1.enc");
    let data = std::fs::read(&path).map_err(|_| "NETAQ 앱에서 계정을 연결해주세요")?;
    if data.len() < 12 { return Err("연결 정보를 읽지 못했어요"); }
    let entry = keyring::Entry::new("app.chobab.netaq.desktop.widget", "encryption-key").map_err(|_| "보안 저장소를 열지 못했어요")?;
    let key = STANDARD.decode(entry.get_password().map_err(|_| "NETAQ 앱에서 계정을 연결해주세요")?).map_err(|_| "보안 키를 읽지 못했어요")?;
    let auth = decrypt_credentials(&data, &key)?;
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

pub fn perform(widget: &str, id: u32, method: &str, url: &str, body: Option<&str>) -> Value {
    let task = if ["today", "tasks"].contains(&widget) && method == "POST" && url == TASK_REQUEST {
        let Some(request) = body.and_then(|b| serde_json::from_str::<Value>(b).ok()) else { return json!({"id":id,"error":"할 일을 확인해주세요"}); };
        let source = request["source"].as_str().unwrap_or("");
        let item = request["id"].as_str().unwrap_or("");
        if !["event", "capture"].contains(&source) || item.is_empty() || item.len() > 200 || !request["done"].is_boolean() { return json!({"id":id,"error":"할 일을 확인해주세요"}); }
        Some(json!({"source": source, "id": item, "done":request["done"]}).to_string())
    } else { None };
    let feed = feed_from_request(widget, method, url);
    if feed.is_none() && task.is_none() { return json!({"id":id,"error":"지원하지 않는 요청입니다"}); }
    let auth = match credentials() { Ok(v) => v, Err(_) => return json!({"id":id,"ok":false,"status":401,"body":""}) };
    let headers = [("Authorization".to_string(), format!("Bearer {}", auth.token)), ("Content-Type".to_string(), "application/json".to_string())];
    if let Some(task) = task {
        let target = format!("{}/api/personal/calendar/widget/task", auth.origin);
        let response = crate::net::perform(id, "POST", &target, &headers, Some(&task));
        return json!({"id":id,"ok":response["ok"],"status":response["status"],"body":"{}"});
    }
    let (view,date) = feed.unwrap();
    let target = format!("{}/api/personal/calendar/widget/feed?view={}&anchor={}", auth.origin, view, date);
    let response = crate::net::perform(id, "GET", &target, &headers, None);
    // The daily feed may also contain private notes: return only fields used by the widget.
    if response["ok"] == true {
        if let Some(body) = response["body"].as_str().and_then(|s| serde_json::from_str::<Value>(s).ok()) {
            let filtered = filtered_feed(widget, &body, false);
            return json!({"id":id,"ok":true,"status":200,"body":filtered.to_string(),"headers":{}});
        }
        return json!({"id":id,"error":"일정을 읽지 못했어요"});
    }
    // Reuse the existing app's encrypted cache; never show it after an explicit 401.
    if response["status"].as_u64() != Some(401) {
        if let Some(body) = auth.cache.get(&format!("{view}:{date}")) {
            let filtered = filtered_feed(widget, body, true);
            return json!({"id":id,"ok":true,"status":200,"body":filtered.to_string(),"headers":{}});
        }
    }
    json!({"id":id,"ok":false,"status":response["status"],"body":""})
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test] fn decrypts_existing_tauri_storage_format() {
        let key = [7u8;32]; let nonce = [9u8;12];
        let cipher = ChaCha20Poly1305::new_from_slice(&key).unwrap();
        let plaintext = br#"{"origin":"https://netaq.chobab.app","token":"example","cache":{}}"#;
        let mut blob = nonce.to_vec(); blob.extend(cipher.encrypt(Nonce::from_slice(&nonce), plaintext.as_slice()).unwrap());
        let auth = decrypt_credentials(&blob, &key).unwrap();
        assert_eq!(auth.token, "example");
        assert!(decrypt_credentials(&blob, &[8u8;32]).is_err());
        assert!(decrypt_credentials(&blob[..5], &key).is_err());
    }
    #[test] fn requests_are_strictly_limited() {
        for (widget,view) in [("today","day"),("week","week"),("month","month"),("tasks","tasks"),("memo","day")] {
            let url=format!("{FEED_REQUEST}{view}&anchor=2026-11-24");
            assert!(feed_from_request(widget,"GET",&url).is_some());
            assert!(feed_from_request(widget,"POST",&url).is_none());
            assert!(feed_from_request(widget,"GET",&format!("{url}&other=1")).is_none());
        }
        assert!(feed_from_request("week","GET",&format!("{FEED_REQUEST}day&anchor=2026-11-24")).is_none());
        assert!(feed_from_request("memo","GET","https://evil.example/").is_none());
    }
    #[test] fn private_notes_are_visible_only_to_memo() {
        let body=json!({"note":"secret", "noteDate":"2026-11-24", "events":[], "tasks":[], "captures":[]});
        assert!(filtered_feed("today",&body,false).get("note").is_none());
        assert!(filtered_feed("week",&body,false).get("note").is_none());
        assert_eq!(filtered_feed("memo",&body,true)["note"],"secret");
    }
    #[test] fn task_rejects_untrusted_payload_before_loading_credentials() {
        let bad = perform("tasks", 7, "POST", TASK_REQUEST, Some(r#"{"source":"event","id":"1","done":"true"}"#));
        assert!(bad["error"].is_string());
        let bad = perform("tasks", 7, "POST", TASK_REQUEST, Some(r#"{"source":"evil","id":"1","done":true}"#));
        assert!(bad["error"].is_string());
        let bad = perform("tasks", 7, "POST", "https://evil.example/task", Some(r#"{"source":"event","id":"1","done":true}"#));
        assert!(bad["error"].is_string());
    }
    #[test] fn unknown_bundles_cannot_access_credentials() { assert!(!trusted_bundle("app.chobab.netaq.widgets", "today", b"untrusted")); }
}
