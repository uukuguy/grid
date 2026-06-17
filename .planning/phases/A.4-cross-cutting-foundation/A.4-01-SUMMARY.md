<summary phase="A.4" plan="A.4-01" name="Cross-Cutting Foundation">
<result>COMPLETE — 5/5 tasks, all verification checks pass</result>

<decisions>
- Shared ApiClient pattern: created `web/src/api/` with class-based `ApiClient` mirroring web-platform/'s pattern but using `grid_token` localStorage instead of JWT. Existing raw-fetch pages not migrated — left for future phase.
- Design tokens: standardized both apps to use `@theme` blocks with same variable names. web/ uses dark palette, web-platform/ uses light palette. Variable surface is identical.
- Brand name: "Octo Platform" → "Grid Platform" in web-platform/'s index.html, Login page, and NavRail.
- Vestigial config: cleaned tailwind.config.js of hardcoded `primary: #2563eb` (conflicted with CSS vars); kept file as anchor.
- Bug fix (pre-existing): added `resolve.alias` for `@/` path to web/vite.config.ts — was missing and causing build failure.
</decisions>

<artifacts>
<created>
- web/src/api/client.ts — ApiClient class
- web/src/api/types.ts — ApiError, ApiClientOptions types
- web/src/api/index.ts — barrel export
- web-platform/src/lib/utils.ts — cn() utility
</created>
<modified>
- web/vite.config.ts — added @/ resolve alias
- web-platform/src/globals.css — @theme block with standardized tokens
- web-platform/index.html — title: Octo → Grid
- web-platform/src/pages/Login.tsx — heading: Octo → Grid
- web-platform/src/components/layout/NavRail.tsx — logo: "O" → "Grid"
- web-platform/tailwind.config.js — cleaned hardcoded color
</modified>
</artifacts>

<verification>
| Check | Result |
|-------|--------|
| web/ tsc --noEmit | ✓ PASS |
| web-platform/ tsc --noEmit | ✓ PASS |
| web/ vite build | ✓ PASS (dist 677KB JS + 45KB CSS) |
| web-platform/ vite build | ✓ PASS (dist 261KB JS + 11KB CSS) |
| web/ vitest run | ✓ 9/9 PASS |
| web-platform/ tests | N/A (no test suite) |
</verification>

<outstanding>
- None for this phase. Next: Phase A.5 grid-platform Hardening.
</outstanding>
</summary>
