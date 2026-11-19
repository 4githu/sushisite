# Margin PDF workspace

PdfWorkspace.svelte is the new notebook-first PDF module. The Drive preview imports it directly; the existing PdfEditor.svelte remains the daily planner implementation.

- PDF.js handles source parsing in a worker. Source metadata is resolved on visited pages, source bytes are requested explicitly for export, and backing canvases are capped at 16 million pixels each.
- Current input is drawn incrementally on a temporary canvas. Completed strokes are stored as PDF-coordinate vectors and projected paths are cached per stroke/viewport. perfect-freehand (MIT) creates pressure outlines; export uses the same outlines with pdf-lib.
- ink.ts provides selection, clipboard and partial erasing. workspace.ts contains lazy notebook initialization, render budgeting and legacy path geometry. ink-path.ts contains the shared pressure contour.
- The document adapter retains the existing /documents/pdf:<resourceId> revision protocol, private local recovery and conflict handling. The original PDF stays separate; PDF export combines it with vector annotations.
- Public props: resourceId, url, name. Resource identity must remain stable for the lifetime of the component; remount it when the selected file changes.
- CSS --margin-surface, --margin-ink, --margin-border and --margin-canvas can be supplied by a host.

Validation: 10 PDF unit tests, 4 browser flows against the served production build (864-page synthetic source, real lasso selection, persistence/export, 390px layout, 1,500 existing strokes without SVG mutations during active input), and actual signed-in sample upload/save/reload.

Limits: the 864-page fixture has simple pages; it is not a scanned-textbook throughput benchmark. Pen hardware/palm rejection needs device testing. Google Drive streaming currently has no range forwarding in the existing backend, and can fall back to a full source transfer. History currently retains up to 40 notebook snapshots, so very heavily annotated books need a later operation-based history/persistence design. Searchable PDF text selection/search, full-document thumbnail scrolling and offline synchronization are not implemented here. Page source metadata is backward compatible via optional sourceReady; pressure contours via optional geometry='outline'.

References:
- https://github.com/mozilla/pdf.js/wiki/Frequently-Asked-Questions
- https://github.com/steveruizok/perfect-freehand
- https://github.com/szimek/signature_pad
- Figma https://www.figma.com/design/Xmf3xJ0o8icUjrggWAW4K2?node-id=19-108


UI redesign: the Drive opens a dedicated full-screen notebook, following the original Figma 1440x1000 editor: 72px document header, 45px document tab, 80px icon toolbar, 188px page rail and 302px optional notes panel. At tablet/mobile widths the panels become overlays, the toolbar scrolls horizontally, and the document is fitted on initial open. Closing saves pending work before returning to the original library scroll position. Keyboard focus stays in the workspace while it is open.

Reference patterns: Goodnotes document view and active tool controls (https://support.goodnotes.com/hc/en-us/articles/13682253498767-Improved-User-Interface), OneNote web navigation (https://support.microsoft.com/en-us/onenote/onenote-for-web-help-and-learning/basic-tasks-in-onenote-for-the-web), Samsung Notes pen color/thickness toolbar (https://insights.samsung.com/2025/03/27/10-tips-for-increased-productivity-with-samsung-notes/). Figma icons and compressed Noto Sans KR/Manrope fonts are served locally, including OFL license files.

Surface follow-up: PdfWorkspace now stays embedded in the Drive preview; it no longer locks the document body or traps focus. Its toolbar is 64px, lasso is always first, and tool icons use the Lucide set with its license. The drawing surface uses touch-action:none at both the SVG and scroll container; panning is explicit via the Hand tool. During active contact non-passive wheel cancellation and scroll-position guarding prevent scrolling. resolvePenTool distinguishes barrel button (buttons&2 / button2 => lasso) from inverted eraser (buttons&32 / button5 => erase), retaining the chosen tool after release. Clicking SVG text opens inline editing without switching tools. Lasso dragging accepts the entire selected bounds, not only nearby stroke samples.

Regression evidence includes CDP pen/barrel input, pen erasing, wheel suppression during contact, and text click editing. The inverted eraser hardware flags are covered by a pure unit test because CDP cannot emit that hardware button faithfully. This is not a physical Surface Pro hardware certification. Updated Figma: https://www.figma.com/design/Xmf3xJ0o8icUjrggWAW4K2?node-id=22-125
