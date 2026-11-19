# Shared notebook

Both hosts import `NotebookWorkspace.svelte`:

- NETAQ drive: `personal-project/pdf/PdfWorkspace.svelte` is a prop-only wrapper.
- Standalone: the independent app's `App.svelte` is an import-only wrapper using the same `$lib` source alias.

The notebook mounts the **existing** `PersonalTextEditor.svelte`. Its `toolbarTarget` action places that instance's unchanged `EditorToolbar` in the notebook settings row. Extensions, custom keyboard handlers, selection state, color picker, attachment handling and `?` help belong to PersonalTextEditor; there is no copied toolbar or separate Tiptap configuration. Existing editor consumers keep their default layout.

`drive-adapter.ts` reads legacy `pdf:<resourceId>` without writing to it. PDF coordinates are converted using the matching source-page viewport. The v2 manifest uses `pdf:<resourceId>:v2`; page arrays are gzip-compressed, content-addressed and split below the document API's 500KB limit. All page chunks are committed before the revision-checked manifest. Concurrent manifest writes fail safely. The old data remains available for rollback.

`storage.ts` keeps standalone data in IndexedDB and separates the immutable PDF buffer from annotation saves. It reads existing standalone backups/storage. Live strokes use an imperative canvas and only commit immutable vector points at pointer-up. History stores structural copies, not full point serialization. Autosave is deferred while the pen is down. Final pointer-up coordinates and capture-loss cleanup are handled explicitly.

PDF.js worker, CMaps, standard fonts and WASM are served from the same installed version. `scripts/release-notebook.mjs` synchronizes those assets, type-checks, builds both hosts and restarts the NETAQ frontend. Run `npm run release:notebook` from the main repository. `NETAQ_NOTEBOOK_HOST` can override the standalone checkout directory. Keep its source alias pointed at this repository; do not copy the module to the host.

Verification: `npm run check`; `npx vitest run` for `geometry.test.ts` and `page-storage.test.ts`. Browser checks cover the original editor's custom shortcuts, closed-by-default help, rapid pen contacts, scroll blocking, persistence, document modes, desktop/mobile layout and the actual uploaded PDF. Synthetic pen input is not a real Surface latency measurement.
