# web/ UI Design Tokens

> **Source of truth:** This document locks the design tokens used across `web/`
> (Grid single-user workbench UI, leg B per ADR-V2-024). It mirrors
> `.planning/phases/03.7.2-web-production/03.7.2-UI-SPEC.md` and is the
> project-level reference for `gsd-ui-checker` and `gsd-ui-auditor`.
>
> **Lock rule:** Do NOT add new color tokens to `web/src/globals.css` `@theme`
> block without updating this doc. Do NOT introduce a third-party registry
> (shadcn, etc.) — the existing primitives cover the full surface.

---

## 1. Color Tokens

### 1.1 Theme tokens (declared in `web/src/globals.css` `@theme` block)

| Role | Hex | Tailwind class | Usage |
|------|-----|----------------|-------|
| Background | `#09090b` | `bg-background` | Page background, main canvas |
| Foreground | `#fafafa` | `text-foreground` | Primary text |
| Card | `#09090b` | `bg-card` | Card surface (same as bg in dark mode) |
| Card foreground | `#fafafa` | `text-card-foreground` | Card text |
| Primary | `#3b82f6` | `bg-primary`, `text-primary`, `ring-primary` | Primary action, focus ring, brand accent |
| Primary foreground | `#fafafa` | `text-primary-foreground` | Text on primary fills |
| Secondary | `#27272a` | `bg-secondary` | Secondary surfaces (hover, selected) |
| Secondary foreground | `#fafafa` | `text-secondary-foreground` | Text on secondary fills |
| Muted | `#27272a` | `bg-muted` | Muted backgrounds, code blocks |
| Muted foreground | `#a1a1aa` | `text-muted-foreground` | Helper text, captions, metadata |
| Accent | `#27272a` | `bg-accent` | Accent backgrounds |
| Accent foreground | `#fafafa` | `text-accent-foreground` | Accent text |
| Destructive | `#ef4444` | `bg-destructive`, `text-destructive` | Errors, destructive actions |
| Border | `#27272a` | `border-border` | All borders |
| Input | `#27272a` | `border-input` | Input field borders |
| Ring | `#3b82f6` | `ring-ring` | Focus ring (alias of primary) |
| Radius | `0.5rem` (8px) | `rounded-md` (default) | Default border-radius |

### 1.2 Inline palette extensions (semantic; do not redefine)

These are hard-coded Tailwind palette names already in use across `web/src/components/`
and `web/src/pages/`. They are part of the de facto design system.

| Color | Tailwind class | Used in |
|-------|----------------|---------|
| Success green | `bg-emerald-500` / `text-emerald-400` / `bg-green-950/80` | `ConnectionStatus`, `Toast` success variant |
| Warning yellow | `bg-yellow-500` / `bg-amber-950/80` | `ConnectionStatus`, `Toast` warning variant |
| Error red | `bg-red-500` / `bg-red-950/80` | `ConnectionStatus`, `Toast` error variant |
| Info blue | `bg-blue-950/80` | `Toast` info variant |
| **Memory cyan** | `bg-cyan-950/30`, `bg-cyan-950/80`, `border-cyan-600`, `border-cyan-700/50`, `text-cyan-200`, `text-cyan-400` | Memory toast + highlight pulse |

The memory cyan palette is the only addition for Phase 3.7.2; it sits adjacent
to primary blue on the color wheel but is distinct enough (10.2:1 contrast on
dark background, AAA) to clearly mark "memory write event" without colliding
with the primary-action accent.

---

## 2. Typography

| Role | Size | Weight | Line Height | Tailwind | Usage |
|------|------|--------|-------------|----------|-------|
| Body | 14px | 400 (regular) | 1.5 | `text-sm font-normal leading-normal` | Default body text, list items, table cells |
| Label | 12px | 400 (regular) | 1.4 | `text-xs font-normal leading-tight` | Form labels, badges, captions, tab labels, button text |
| Heading | 18px | 600 (semibold) | 1.25 | `text-lg font-semibold leading-tight` | Page titles, modal titles, section headers |
| Display | 24px | 600 (semibold) | 1.2 | `text-2xl font-semibold leading-tight` | Hero numbers, dashboard summaries |

**Code/monospace**: `font-mono text-xs` (12px / 400 / 1.4) for IDs.

**Buttons always use `font-normal`** — not `font-medium`. This applies to every
new or changed interactive element in `web/` from this phase onward.

---

## 3. Spacing

| Token | Value | Tailwind | Usage |
|-------|-------|----------|-------|
| xs | 4px | `p-1`, `gap-1`, `m-1` | Icon gaps, tight padding |
| sm | 8px | `p-2`, `gap-2`, `m-2` | Compact element spacing |
| md | 16px | `p-4`, `gap-4`, `m-4` | Default element spacing |
| lg | 24px | `p-6`, `gap-6` | Section padding |
| xl | 32px | `p-8`, `gap-8` | Layout gaps |

**Component-internal padding minimum:** `px-2 py-1` (8px / 4px). All buttons,
badges, pills, and icon-only controls use at least these insets.

**Touch targets:** ≥ 44×44px on mobile (wrapping `min-h-11 min-w-11`).

---

## 4. Buttons

Universal state pattern (all interactive elements):

| State | Tailwind |
|-------|----------|
| Default | component-specific |
| Hover | 5–10% opacity / color shift |
| Active (pressed) | `active:scale-95` + color intensifies |
| Focus | `focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background` |
| Disabled | `opacity-50 cursor-not-allowed` (keep focusable for screen reader) |
| In-flight | `opacity-50 cursor-wait` + `aria-busy="true"` |

**Primary actions use `bg-primary text-primary-foreground`.**
**Destructive actions use `bg-destructive text-destructive-foreground` on hover/active.**
**Default-state Stop button is gray (`bg-secondary text-foreground`)**, not red —
the red tint appears on hover. Instant-stop semantics per D-08.

**No spinners.** Project convention: text feedback ("Sending...", "Stopping...")
in place of spinner icons.

---

## 5. Motion / Transition

| Duration | Tailwind | Usage |
|----------|----------|-------|
| Fast (150ms) | `transition-colors duration-150` | Color hover/active changes |
| Normal (200ms) | `transition-all duration-200` | Slide-in toasts, button press feedback |
| Slow (400ms) | `transition-all duration-400` | Page transitions (rare) |

**Easing:** `ease-out` for entries, `ease-in` for exits. No bouncy curves.

**Live indicator pulse:** `animate-pulse` (Tailwind built-in, 2s cycle).

**Reduced motion** (UI-SPEC §12.5): A `@layer base` block in `globals.css`
neutralizes animations + transitions when `prefers-reduced-motion: reduce`.

---

## 6. Iconography

**Library:** `lucide-react` 0.469. Stroke width: 2px (Lucide default).

| Size | Tailwind | Usage |
|------|----------|-------|
| 12px | `h-3 w-3` | Within pills, inline with text-xs |
| 14px | `h-3.5 w-3.5 fill-current` | Within buttons (Stop, Resume, Memory, Refresh) |
| 16px | `h-4 w-4` | Within buttons (default), tab labels |
| 20px | `h-5 w-5` | Toast leading icons |
| 48px | `h-12 w-12 text-muted-foreground` | Empty-state icons |

**Stop button icon:** `Square` (filled, universal "stop" symbol).
**Resume button icon:** `Play`.
**Memory toast + Memory empty state:** `Database` (concrete; not `Brain`).

---

## 7. Border / Radius / Shadow

| Property | Token | Tailwind | Usage |
|----------|-------|----------|-------|
| Border color | `--color-border` | `border-border` | All borders (1px default) |
| Radius (default) | `--radius: 0.5rem` (8px) | `rounded-md` | Buttons, inputs, cards, status badges |
| Radius (large) | 12px | `rounded-lg` | Toasts, modal panels |
| Radius (full) | 9999px | `rounded-full` | Live indicator dots, status pills |
| Shadow (elevated) | — | `shadow-lg` | Toasts |
| Backdrop blur | — | `backdrop-blur-sm` | Toasts (frosted glass feel) |

**No shadow** on cards, list items, badges, table rows. Borders provide separation.

---

## 8. Copywriting Contract (action labels)

| Element | Label |
|---------|-------|
| Stop button | "Stop" (verb, single word) |
| Resume button | "Resume" |
| Submit task | **"Send task"** (action-specific; replaces "Submit") |
| Delete task | "Delete" |
| New session | (icon only — `Plus`) |
| Refresh | "Refresh" |
| Stop toast on failure | title "Failed to stop" / message "Try again, or refresh the page." |
| Resume toast on failure | title "Failed to resume" / message "Try again, or refresh the page." |
| Memory toast | title "Memory written" / message "Stored: {first 60 chars}…" |

**No "Submit"** — UI-SPEC §11.1 mandates action-specific CTA labels.

---

## 9. Accessibility (WCAG 2.1 AA)

| Element | aria-* |
|---------|--------|
| Stop button | `aria-label="Stop session ${truncateId(sessionId)} (⌘. / Ctrl+.)"` |
| Resume button | `aria-label="Resume session ${truncateId(sessionId)}"` |
| In-flight buttons | `aria-busy="true"`, `aria-disabled="true"` |
| Live indicator | `aria-label="Agent is ${state}"` (decorative dot + parent label) |
| Memory toast | `role="alert"` + `aria-live="polite"` |
| Icon-only buttons | `aria-label` (mandatory) |

**Keyboard:** Tab order = visual order. `Cmd+.` (macOS) / `Ctrl+.` invokes Stop
when `sessionStatusAtom === "running"`. Native `Enter`/`Space` for buttons.

**Color contrast** (key pairs):

| Foreground | Background | Ratio |
|------------|------------|-------|
| `#fafafa` | `#09090b` | 18.8:1 (AAA) |
| `#a1a1aa` | `#09090b` | 9.4:1 (AAA) |
| `#3b82f6` | `#09090b` | 5.7:1 (AA) |
| `#22d3ee` (cyan-400) | `#09090b` | 10.2:1 (AAA) |

---

## 10. Responsive Breakpoints

Tailwind 4 defaults:

| Breakpoint | Min width | Target |
|------------|-----------|--------|
| (default) | 0px | Mobile portrait (degraded) |
| `sm` | 640px | Mobile landscape |
| `md` | 768px | Tablet portrait |
| `lg` | 1024px | Tablet landscape / small laptop |
| `xl` | 1280px | **Primary target — desktop dashboard** |
| `2xl` | 1536px | Large monitor |

**Primary target:** ≥ 1280×800.

**Touch targets:** ≥ 44×44px on mobile (≤ 767px). SessionControls mobile fallback
uses sticky bottom bar with `min-h-11 min-w-11` buttons.

---

## 11. Verification Commands

```bash
# 1. Confirm no new dependencies in web/package.json
diff <(git show main:web/package.json | jq -S '.dependencies, .devDependencies') \
     <(jq -S '.dependencies, .devDependencies' /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web/package.json)

# 2. Confirm no new color tokens in globals.css @theme block
git diff main -- web/src/globals.css | grep -E '^\+.*--color-' | head
# Expected: 0 new tokens

# 3. Confirm all changed buttons use font-normal
grep -RnE 'rounded-md.*(font-medium|font-semibold|font-bold)' web/src/components/SessionControls.tsx web/src/pages/Tasks.tsx

# 4. Confirm component-internal padding ≥ px-2 py-1
grep -RnE 'px-1 py-|px-0\.5 py-' web/src/components/SessionControls.tsx web/src/pages/Tasks.tsx
# Expected: 0 violations

# 5. Confirm vitest tests pass
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web && npm run test 2>&1 | tail -20

# 6. Confirm vite build passes
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web && npm run build 2>&1 | tail -10

# 7. Confirm tsc passes
cd /Users/sujiangwen/sandbox/SGAI/grid-sandbox/web && npx tsc -b 2>&1 | tail -10
```

---

*Document version: 2026-07-20 (Phase 3.7.2 Plan 02)*
*Mirror: `.planning/phases/03.7.2-web-production/03.7.2-UI-SPEC.md`*

Generated-By: Claude (claude-opus-4-8) via Claude Code CLI
Co-Authored-By: claude-flow <ruv@ruv.net>