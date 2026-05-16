# Phase 5.0 Gray Areas Research — Hook Envelope Baseline

**Author:** GSD discuss-phase advisor mode
**Date:** 2026-05-19
**Phase:** Phase 5.0 — Engine Hardening (grid-cli + grid-server)
**Source docs:** ADR-V2-006, D134, D120, D93, D151

---

## Executive Summary

Three gray areas identified in the Hook Envelope Baseline topic (Phase 5.0). The core mismatch is between **what the ADR specifies** (flat top-level fields in Stop envelopes) and **what shipped hook scripts implement** (dual-path checks for both flat and `.output.*` nested formats).

---

## Gray Area 1: `.output.*` backward-compat in shipped hooks — dead code or intentional hedge?

### What the ADR says
ADR-V2-006 §2.3 defines the Stop envelope as **flat top-level**:

```json
{
  "event": "Stop",
  "skill_id": "threshold-calibration",
  "draft_memory_id": "mem_abc123",   // top-level
  "evidence_anchor_id": "anc_xyz789", // top-level
  ...
}
```

### What the shipped hooks do
Both shipped hooks check **both** paths:

```bash
# check_output_anchor.sh
has_top_anchor() {
  echo "$input" | jq -e '(.evidence_anchor_id // "") | length > 0'
}
has_output_anchor() {
  echo "$input" | jq -e '(.output // {} | .evidence_anchor_id // "") | length > 0'
}
if has_top_anchor || has_output_anchor; then
  echo '{"decision":"allow"}'
fi
```

```bash
# check_final_output.sh
has_top_both() { ... top-level ... }
has_output_both() { ... .output nested ... }
if has_top_both || has_output_both; then
  echo '{"decision":"allow"}'
fi
```

Both scripts carry the comment:
> "Older engines nested the final assistant output under `.output.*`. Accept either for forward/backward compat."

### Evidence from codebase
| Source | Path checked | Notes |
|---|---|---|
| `crates/grid-engine/src/hooks/context.rs` | `HookContext` | **Flat top-level** fields; no `.output` nesting |
| `crates/grid-engine/src/agent/harness.rs` | `last_draft_memory_id`, `last_evidence_anchor_id` | Threaded into top-level Stop envelope |
| Rust `HookContext::to_json()` | Serializes flat | No `.output` wrapper |
| Python runtime envelope producer | Likely flat (same ADR source) | Must verify |

### Options
1. **Remove `.output.*` checks** — these are dead code since the engine only emits flat. Reduces complexity and aligns with ADR.
2. **Keep as hedge** — if there's any legacy runtime or external integration that still emits `.output.*`, the checks guard against breakage. But this should be confirmed with D134.
3. **Version-flag the hooks** — add `envelope_version: "2"` field; hooks check version and reject old format.

### Recommendation
**Option 1 with a deprecation timeline**: Remove `.output.*` checks in Phase 5.0 and add a comment explaining that the compat paths were removed in v5.0 per ADR-V2-006. If any downstream system still emits `.output.*`, this will surface as a hook failure and can be re-added.

---

## Gray Area 2: Python runtime parity — verified or assumed?

### What we know
- Rust `HookContext` is fully specified (ADR-V2-006 §2)
- Python runtime has `hook_substitution.py` and `ScopedHookHandler`
- D151 (harness envelope wiring) tests Rust dispatch site

### What we don't know
- Does Python runtime produce the **same** JSON shape as Rust?
- Is the Python `HookContext` struct a parallel implementation or a direct port?
- Is there a parity test that compares actual output bytes between Rust and Python?

### Options
1. **Trust ADR alignment** — both runtimes were built from the same ADR spec, assume parity.
2. **Add explicit parity test** — `hook_envelope_parity_test.rs` (from the scout) may already exist; verify its coverage.
3. **Cross-runtime snapshot test** — run both runtimes with the same skill, compare hook stdin bytes.

### Recommendation
**Verify with existing tests first** (per scout report: `hook_envelope_parity_test.rs` — 10 tests). If that test exists and passes, Gray Area 2 is closed. If not, it's a D120 gap that needs a new test.

---

## Gray Area 3: D134 entry "落盘" claim — fully shipped or partially shipped?

### What D134 says
> 2026-04-16 | D134 | **新增** 🟡 P1-defer | 已落盘 skill hooks（`threshold-calibration` + `skill-extraction`）— 含示例 hooks、substitution vars、contract tests

### Conflict
D134 was registered at Phase 4.2 but says "**P1-defer**". The `examples/skills/` hooks are shipped (confirmed). But:
- Are the **contract tests** (ADR-V2-006 §6) shipped?
- The scout notes `hook_envelope_parity_test.rs` and `harness_envelope_wiring_test.rs` as "ACTIVE"
- But no mention of `test_hook_envelope.py` coverage for Python runtime

### Options
1. **Treat D134 as done** — hooks shipped, tests active, topic is closed.
2. **Audit D134 scope** — verify all three items from the D134 description are actually delivered.

### Recommendation
**Close D134 in Phase 5.0** with a brief verification: confirm `test_hook_envelope.py` exists and covers the Stop envelope contract. If it exists and passes, D134 is fully shipped. If not, this becomes a new task under Phase 5.0.

---

## Decision Matrix

| Gray Area | Priority | Confidence | Recommended Action |
|---|---|---|---|
| GA1: `.output.*` compat | Medium | High | Remove dead compat paths in Phase 5.0; document removal |
| GA2: Python parity | Low | Medium | Verify `hook_envelope_parity_test.rs` coverage; close if green |
| GA3: D134 completeness | Low | High | Audit contract test coverage; close if all items present |

---

## Verification Checklist

- [ ] Read `hook_envelope_parity_test.rs` — confirm 10 tests cover Stop envelope parity
- [ ] Read `harness_envelope_wiring_test.rs` — confirm D151 wiring is tested
- [ ] Read `crates/grid-engine/src/hooks/context.rs` — confirm `draft_memory_id` and `evidence_anchor_id` are top-level
- [ ] Search for Python `test_hook_envelope.py` — confirm Python contract suite exists
- [ ] Confirm `.output.*` compat paths are **only** in shipped hook scripts, not in engine code
