# Reader AI integration contract

## Owner-only web API

Both operations use the existing Sushi `mainauth` identity and the server's configured owner and Hermes home; never send or trust an owner ID or profile path. The browser must obtain the user's consent before sending selected text or image to the external model. These calls do not upload the whole PDF. The provider's retention and costs are governed by its own terms.

`POST /api/personal/reader/translate` is the existing text contract.

`POST /api/personal/reader/explain-image`, `Content-Type: application/json`:

```json
{"image":{"mime_type":"image/png","base64":"<raw base64, no data URL prefix>"},"caption":"optional","context":"optional","target_language":"Korean"}
```

MIME is `image/png` or `image/jpeg`. Decoded bytes <= 768 KiB; request <= 1100 KiB; caption <= 2000 characters; context <= 6000; target language <= 64. Image bytes, caption and context are passed to the provider, not persisted by this endpoint. Success: `200 {"explanation":"..."}`, `Cache-Control: no-store`. Provider receives image as a data URL through the normal Hermes `ctx.llm.complete` multimodal messages interface.

Unauthenticated 401; owner/provider not configured or other user 503 (`translation_provider_unavailable`); invalid payload 400 (`invalid_image`/`invalid_image_context`); oversized JSON 413 (`request_too_large`); non-JSON 415; forbidden Origin 403; provider failure 502 (`image_provider_error`). No automatic retry: caller may explicitly retry; a new attempt is a new provider call. Closing the HTTP connection cancels and reaps the local child; it cannot guarantee that the external service has stopped or will not charge for a request already accepted. Exact per-owner content-type and allowed-Origin restrictions match the translation route.

## Controlled deployment handoff (not executed)

The deployed backend is owned by Codex; do not replace or restart it from this worktree. Once the code has been accepted into the release used by the backend, the operator needs to update the **two plugin source files** in the already-installed owner profile, enable the plugin through the official CLI, and set server environment before restarting through its deployment mechanism. Example commands, after confirming the two paths and owner ID (no credential values needed):

```sh
SRC='/Users/sagi/Documents/Codex/2026-11-05/new-chat/work/release-20261123/reader-publish/sushi-fast/personal_project/reader_translation/hermes_plugin'
HOME_DIR='/Users/sagi/.hermes/profiles/personalbackend'
install -m 644 "$SRC/__init__.py" "$HOME_DIR/plugins/paiper-reader-translation/__init__.py"
install -m 644 "$SRC/plugin.yaml" "$HOME_DIR/plugins/paiper-reader-translation/plugin.yaml"
HERMES_HOME="$HOME_DIR" hermes plugins enable paiper-reader-translation --no-allow-tool-override
```

Backend process environment contract:

```text
READER_TRANSLATION_PROVIDER=hermes_personal_owner
READER_TRANSLATION_PERSONAL_OWNER_ID=<server-confirmed positive numeric Sushi user ID>
READER_TRANSLATION_HERMES_EXECUTABLE=/Users/sagi/.hermes/hermes-agent/.hermes/bin/hermes
READER_TRANSLATION_HERMES_HOME=/Users/sagi/.hermes/profiles/personalbackend
```

The operator must inject these through the actual backend service manager's maintained configuration; do not put credentials in these settings. Reader uses `app.sushisite.backend`, independently of Rehear. `ops/reader/install_backend.py` mounts only the accepted Reader module and two authenticated routes, preserves unrelated shared-backend changes, and restarts the existing service once with rollback on health failure. The owner ID is a required deployment argument, confirmed from the actual signed-in account.

## Evidence and limitations

In this worktree the Reader tests passed, and a temporary HTTPS candidate with a synthetic `mainauth` identity called the actual owner-profile host `ctx.llm` for both a synthetic sentence and a generated two-bar image. Both returned HTTP 200; no-auth 401, non-owner 503, invalid image 400. A separate actual TLS client disconnect against a synthetic slow provider reaped the child process. The original candidate used a scratch runner to load the current plugin with the official PluginContext. A subsequent recheck found the installed owner-profile plugin matches the worktree and successfully repeated the temporary HTTPS test through the actual installed `hermes paiper-reader-explain-image` command, with a generated JPEG matching the frontend's MIME. Neither operating-service update nor real Sushi browser login was performed or validated.
