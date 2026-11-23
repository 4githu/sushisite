//! HTTP requests made on behalf of widgets (after permission checks).

use std::io::Read;
use std::time::Duration;

const MAX_BODY: u64 = 5 * 1024 * 1024;

fn agent() -> ureq::Agent {
    ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(20)))
        // A redirect would bypass the widget host allowlist checked before this request.
        .max_redirects(0)
        .http_status_as_error(false)
        .user_agent(concat!("Vitrine/", env!("CARGO_PKG_VERSION")))
        .build()
        .into()
}

/// Performs a request and returns the JSON payload for the widget's `fetch` event.
pub fn perform(
    id: u32,
    method: &str,
    url: &str,
    headers: &[(String, String)],
    body: Option<&str>,
) -> serde_json::Value {
    let result = (|| -> Result<serde_json::Value, String> {
        let agent = agent();
        let mut builder = ureq::http::Request::builder().method(method).uri(url);
        for (k, v) in headers {
            builder = builder.header(k, v);
        }
        let response = match body {
            Some(b) => agent.run(builder.body(b.to_string()).map_err(|e| e.to_string())?),
            None => agent.run(builder.body(()).map_err(|e| e.to_string())?),
        }
        .map_err(|e| e.to_string())?;
        let status = response.status();
        let mut hdrs = serde_json::Map::new();
        for (k, v) in response.headers() {
            if let Ok(v) = v.to_str() {
                hdrs.insert(k.as_str().to_string(), v.into());
            }
        }
        let mut text = String::new();
        response
            .into_body()
            .into_reader()
            .take(MAX_BODY)
            .read_to_string(&mut text)
            .map_err(|e| format!("reading body: {e}"))?;
        Ok(serde_json::json!({
            "id": id,
            "ok": status.is_success(),
            "status": status.as_u16(),
            "statusText": status.canonical_reason().unwrap_or(""),
            "headers": hdrs,
            "body": text,
        }))
    })();
    result.unwrap_or_else(|e| serde_json::json!({ "id": id, "error": e }))
}

#[cfg(test)]
mod tests {
    use super::perform;
    use std::io::{Read, Write};
    use std::net::TcpListener;
    use std::thread;

    #[test]
    fn redirects_are_not_followed_outside_the_permission_check() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = [0u8; 4096];
            let _ = stream.read(&mut request);
            stream.write_all(b"HTTP/1.1 302 Found\r\nLocation: http://127.0.0.1:9/not-allowed\r\nContent-Length: 0\r\nConnection: close\r\n\r\n").unwrap();
        });
        let result = perform(1, "GET", &format!("http://127.0.0.1:{port}/"), &[], None);
        server.join().unwrap();
        assert_eq!(result["status"], 302, "redirect must be returned, not followed: {result}");
    }
}
