<plan phase="A.6" name="web-platform/ Production">
<objective>
Fix web-platform/ gaps from A.0 audit: add ErrorBoundary, toast notifications, Markdown rendering, fix dashboard stats bug, wire user profile button. Target: production-grade React UI.
</objective>

<review_protocol>none</review_protocol>

<tasks>
- [ ] T1: Fix Dashboard stats copy-paste bug — all 3 StatsCards showed sessions.length; now computes filtered counts
- [ ] T2: Add Markdown rendering — install react-markdown + remark-gfm, create MarkdownRenderer component, update MessageBubble to use it for assistant messages
- [ ] T3: Add ErrorBoundary + Toast system — create ErrorBoundary class component with retry UI, create ToastContainer with success/error/warning/info variants, add toast atoms to ui.ts
- [ ] T4: Wire user profile button — user icon in Header now navigates to /sessions
</tasks>

<verification>
- [ ] tsc --noEmit passes
- [ ] vite build succeeds (451KB JS + 14KB CSS)
</verification>
</plan>
