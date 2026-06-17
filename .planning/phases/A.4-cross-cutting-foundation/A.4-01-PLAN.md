<plan phase="A.4" name="Cross-Cutting Foundation">
<objective>
Merge web/ and web-platform/ design systems, extract shared ApiClient, standardize brand name to "Grid". Creates the cross-cutting foundation for all subsequent Wave 2+3 frontend phases.
</objective>

<review_protocol>none</review_protocol>

<tasks>
- [ ] T1: Extract shared ApiClient pattern — create `web/src/api/` with typed `ApiClient` class, mirror web-platform/'s pattern but adapted for web/'s simpler auth model (grid_token localStorage). Create `web/src/api/types.ts` with `ApiError` interface. (web-platform/ already has this; web/ gets it now.)
- [ ] T2: Add `cn()` utility to web-platform/ — create `web-platform/src/lib/utils.ts` with the same `cn()` utility using clsx + tailwind-merge that web/ uses.
- [ ] T3: Standardize design tokens across both apps — convert web-platform/'s `globals.css` to use `@theme` block with same CSS variable names as web/ (but light-theme values for web-platform/'s light color palette). Add `border-color` reset and system font stack consistent with web/.
- [ ] T4: Standardize brand name "Octo" → "Grid" in web-platform/ — update index.html title, Login page heading, and NavRail logo text.
- [ ] T5: Clean up vestigial tailwind.config.js — remove hardcoded `primary: #2563eb` from web-platform/ config; retain file as anchor with a comment pointing to the @theme block in globals.css.
</tasks>

<verification>
- [ ] web/ type checks pass (tsc -b --noEmit)
- [ ] web-platform/ type checks pass (tsc -b --noEmit)
- [ ] web/ production build succeeds (vite build)
- [ ] web-platform/ production build succeeds (vite build)
- [ ] web/ tests pass (vitest run — 9/9)
- [ ] web-platform/ has no test suite (pre-existing)
</verification>

<notes>
**Design decisions:**
- Did NOT convert all web/ raw-fetch pages to use the new ApiClient — that's a separate refactor phase. The ApiClient is now available for new code and migration over time.
- web/ and web-platform/ use different themes (dark vs light) but share the same @theme variable names, making future component sharing and theme switching possible.
- The `web/vite.config.ts` had a pre-existing missing `@/` alias for Vite's Rollup bundler (tsconfig had paths, but Vite needs resolve.alias). Fixed as part of this phase since it blocked the build.
</notes>
</plan>
