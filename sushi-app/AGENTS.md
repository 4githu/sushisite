## Project Configuration

- **Language**: TypeScript
- **Package Manager**: npm
- **Add-ons**: tailwindcss, mcp, sveltekit-adapter, better-auth, mdsvex, prettier, eslint, vitest, playwright, drizzle, paraglide, storybook

---

You are able to use the Svelte MCP server, where you have access to comprehensive Svelte 5 and SvelteKit documentation. Here's how to use the available tools effectively:

## Available Svelte MCP Tools:

### 1. list-sections

Use this FIRST to discover all available documentation sections. Returns a structured list with titles, use_cases, and paths.
When asked about Svelte or SvelteKit topics, ALWAYS use this tool at the start of the chat to find relevant sections.

### 2. get-documentation

Retrieves full documentation content for specific sections. Accepts single or multiple sections.
After calling the list-sections tool, you MUST analyze the returned documentation sections (especially the use_cases field) and then use the get-documentation tool to fetch ALL documentation sections that are relevant for the user's task.

### 3. svelte-autofixer

Analyzes Svelte code and returns issues and suggestions.
You MUST use this tool whenever writing Svelte code before sending it to the user. Keep calling it until no issues or suggestions are returned.

### 4. playground-link

Generates a Svelte Playground link with the provided code.
After completing the code, ask the user if they want a playground link. Only call this tool after user confirmation and NEVER if code was written to files in their project.

## Personal services UI and UX

- Before changing UI, identify the user's primary actions, completion rules, navigation destinations, and error recovery. Review whether the proposed layout makes those actions easier before implementation.
- Keep Aura and Calendar separate services. Aura owns clinic editing, student report navigation, and submission state; the shared calendar exposes general event URLs rather than dedicated Aura controls.
- A clinic is complete only when its required reports are submitted. Draft or ready reports do not count as complete.
- Use consistent, restrained surfaces and typography rather than unrelated blue/green panels, decorative gradients, or arbitrary accent cards.
- Keep weekday and all-day rows visible while a calendar's time grid scrolls. Daily planning uses 08:00 through 02:00 the following day.
- Verify key flows and inspect desktop/mobile screenshots before calling a UI change complete. Preserve unsaved work and distinguish network failure from expired authentication.
- For Ondo Calendar, avoid beige/paper backgrounds and a default blue-on-white theme. Use its dedicated calendar shell and semantic color roles; do not equate "polished" with simply making every surface muted. Review typography, action hierarchy, density, and navigation together.

- Aura manual classroom requests use the date clicked in the weekly header, including past/today/future dates. Show that day's text and verify actual clipboard content. The daily 09:00 scheduler's next-day rule must not restrict this manual copy UI. Keep the dialog to its date, message and copy action; do not reintroduce copy-only disclaimers or internal validation counts.

## User-approved action and release behavior

- Apply `/Users/sagi/Documents/Hermes-Workspace/20-shared/knowledge/product-ux.md` to UI changes. A normal action button executes directly; avoid redundant preview/checkbox/confirmation steps. Keep status feedback near the action without moving focus or scroll. Reserve confirmations for concrete irreversible loss.
- The local production frontend serves `build-node/handler.js` through `scripts/serve-production.mjs`. Build for it with `BUILD_TARGET=node BUILD_OUT=build-node npm run build`; a default Vercel build does not update that runtime. After relevant checks, deploy/restart the already-authorized `app.sushisite.frontend` and verify the served version. One owner completes this; no routine lead handoff or renewed approval.
