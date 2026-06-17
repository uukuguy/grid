<summary phase="A.6" plan="A.6-01" name="web-platform/ Production">
<result>COMPLETE — 4/4 tasks, build passes</result>

<decisions>
- Markdown rendering: use react-markdown + remark-gfm (same as web/'s pattern). Simplified renderer without syntax highlighting (no rehype-highlight dependency — smaller bundle).
- ErrorBoundary: light-themed class component matching web/'s pattern, with retry button and error details display.
- Toast system: Jotai-based atoms (toastsAtom, addToastAtom, removeToastAtom) with auto-dismiss (5s default). light-themed.
- Dashboard: "Messages" stat was showing sessions.length (copy-paste bug) — changed to count active sessions.
- Header: user button was no-op — wired to navigate to /sessions.
</decisions>

<artifacts>
<created>
- web-platform/src/components/ErrorBoundary.tsx
- web-platform/src/components/Toast.tsx
- web-platform/src/components/chat/MarkdownRenderer.tsx
</created>
<modified>
- web-platform/src/atoms/ui.ts — added toast atoms
- web-platform/src/pages/Dashboard.tsx — fixed stats bug
- web-platform/src/components/chat/MessageBubble.tsx — assistant messages use MarkdownRenderer
- web-platform/src/components/layout/Header.tsx — wired user profile button
- web-platform/src/App.tsx — wrapped with ErrorBoundary + ToastContainer
- web-platform/package.json — added react-markdown, remark-gfm deps
</modified>
</artifacts>

<verification>
| Check | Result |
|-------|--------|
| tsc --noEmit | ✓ PASS |
| vite build | ✓ PASS (451KB JS + 14KB CSS) |
</verification>
</summary>
