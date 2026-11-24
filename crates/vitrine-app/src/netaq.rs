//! Credential isolation for the bundled NETAQ widget. Never exposes a token to JavaScript.
use base64::{engine::general_purpose::STANDARD, Engine};
use chacha20poly1305::{aead::{Aead, KeyInit}, ChaCha20Poly1305, Nonce};
use sha2::{Digest, Sha256};
use serde::Deserialize;
use serde_json::{json, Value};
use std::path::PathBuf;

const BUNDLE_SHA256: &str = "ba4ad791486c3682704097c5523e0fa81a0a362f6bc06245a3d25febd7b6eed5";
const REQUEST: &str = "https://netaq.chobab.app/api/personal/calendar/widget/feed?view=day&anchor=";
const ALLOWED: [&str; 4] = ["https://netaq.chobab.app", "https://calendar.chobab.app", "https://calender.chobab.app", "https://chobab.app"];

#[derive(Deserialize)]
struct Credentials { origin: String, token: String, #[serde(default)] cache: std::collections::BTreeMap<String, Value> }

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

pub fn perform(id: u32, method: &str, url: &str) -> Value {
    let Some(date) = date_from_request(method, url) else { return json!({"id":id,"error":"지원하지 않는 요청입니다"}); };
    let auth = match credentials() { Ok(v) => v, Err(_) => return json!({"id":id,"ok":false,"status":401,"body":""}) };
    let target = format!("{}/api/personal/calendar/widget/feed?view=day&anchor={}", auth.origin, date);
    let response = crate::net::perform(id, "GET", &target, &[("Authorization".to_string(), format!("Bearer {}", auth.token))], None);
    // The daily feed may also contain private notes: return only fields used by the widget.
    if response["ok"] == true {
        if let Some(body) = response["body"].as_str().and_then(|s| serde_json::from_str::<Value>(s).ok()) {
            let filtered = json!({"events":body["events"], "tasks":body["tasks"]});
            return json!({"id":id,"ok":true,"status":200,"body":filtered.to_string(),"headers":{}});
        }
        return json!({"id":id,"error":"일정을 읽지 못했어요"});
    }
    // Reuse the existing app's encrypted cache; never show it after an explicit 401.
    if response["status"].as_u64() != Some(401) {
        if let Some(body) = auth.cache.get(&format!("day:{date}")) {
            let filtered = json!({"events":body["events"], "tasks":body["tasks"], "cached":true});
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
    #[test] fn unknown_bundles_cannot_access_credentials() { assert!(!trusted_bundle("app.chobab.netaq.widgets", "today", b"untrusted")); }
}
