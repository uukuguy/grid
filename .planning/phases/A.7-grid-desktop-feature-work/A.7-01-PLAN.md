<plan phase="A.7" name="grid-desktop Feature Work">
<objective>
Rebrand Octo Desktop → Grid Desktop, add agent/session IPC commands, fix auto-updater endpoint placeholder.
</objective>

<review_protocol>none</review_protocol>

<tasks>
- [ ] T1: Rebrand — Octo Desktop → Grid Desktop in tauri.conf.json (productName, identifier, window title, updater endpoint → grid-sandbox GitHub URL)
- [ ] T2: Add IPC commands — get_api_base, get_ws_url (return embedded server URLs), send_api_request (generic API proxy to embedded server, supports GET/POST/PUT/DELETE/PATCH)
- [ ] T3: Fix auto-updater endpoint — changed from placeholder GitHub URL to grid-sandbox releases
</tasks>

<verification>
- [ ] cargo build -p grid-desktop passes
- [ ] cargo test -p grid-desktop: 9/9 pass
</verification>
</plan>
