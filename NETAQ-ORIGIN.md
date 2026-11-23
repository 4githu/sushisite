# NETAQ desktop engine integration (in progress)

Based on Vitrine commit `58d8b6e54033d32577beeeebf2c59ada5a6dff4c` (MIT); see LICENSE and https://github.com/vitrine-org/vitrine. This is an isolated source copy, not a completed or distributable NETAQ widget.

Vitrine places interactive widgets under Windows desktop icons, implements grid editing, persists layout and supports autostart. It uses a custom renderer rather than WebView2, so the existing NETAQ WebView and session cannot be dropped in unchanged.

Security audit: the upstream fetch handler checks the initial host against widget permissions, but its HTTP agent follows redirects by default. NETAQ's copy disables redirects so a redirected request cannot evade that check. The generic widget storage is not a secure credential vault; do not put NETAQ tokens in widget settings or storage. A native, allowlisted, encrypted credential and feed bridge is required before a real account can be connected. No remote source is trusted to run shell commands.

Remaining: implement NETAQ-only credential/feed bridge and widget, bundle engine with the existing NETAQ installer without installing a second app, validate layout and restart on Windows, and release through signed updater. The Windows app and installer have not yet been changed by this source copy.
