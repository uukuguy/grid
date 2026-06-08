# Phase 7.2 Deferred Items (Out-of-Scope Discoveries)

## Pre-existing Issues

### 1. eaasp-skill-registry v2_frontmatter_test failure (unrelated to D11)

- **Discovered during:** Task 2 — `cargo test -p eaasp-skill-registry`
- **Test:** `tests/v2_frontmatter_test.rs::parse_skill_extraction_example_skill`
- **Failure:** `assertion failed: qualifieds.contains(&"l2:memory.search".to_string())`
- **Impact on Phase 7.2:** None. This is a V2 frontmatter parser issue in the example skill YAML, unrelated to D11's scope filter implementation. D11 scope filter tests (`tests/scope_filter.rs`) both pass.
- **D11 acceptance criterion:** `cargo test -p eaasp-skill-registry` exits 0 is unmet due to this pre-existing failure, but the D11-specific scope-filter tests (2/2) pass. Full L2 Python suite (134 PASS) unaffected.
- **Recommendation:** File as a future D-item for the V2 frontmatter parser team or resolve during Phase 8.4 L2 Table Stakes.
