# Production Usability — v3.9 RBAC + v3.10 EAASP Skeleton — 2026-07-26

## 结论

v3.9 路由授权目录与静态 auditor 已达到可合并状态：生产目录 134 个 method/path 条目全部有 `Public` 或 `Requires(Action)`，其中公开面严格为 3 条；Full mode 按匹配路由执行 RBAC，None/ApiKey 回归保持兼容。

## Walkthrough 证据

### 1. 生产目录 PASS

```text
$ make rbac-audit
RBAC route audit PASS: 134 routes
```

Auditor 检查重复 method/path、公开白名单对称性和 Action 可执行性，成功退出 0。

### 2. 人工断线路由 FAIL

`route_auditor::test_07_synthetic_unprotected_route_is_named` 构造 `POST /api/v1/unplugged` 并错误标记为 Public；auditor 返回包含完整 method/path 和 `not on public allowlist` 的 finding。该测试防止 auditor 空跑或无条件 PASS。

### 3. Action 与矩阵同步

Action 从 7 个业务词汇扩展为 20 个细粒度词汇；enum、snake_case 解析、Role × Action 生产策略和测试同步。独立安全复核发现并修复一次 Admin→ManageUsers 越权扩张，最终保持 Owner-only。

### 4. AuthMode 回归

| Gate | 结果 |
|---|---|
| `test_auth_modes` | 8/8 PASS |
| `multi_user_jwt` + auth endpoints + tenant RBAC + catalog | 29/29 PASS |
| engine role + expanded Action tests | 9 PASS |
| route resolver/enforcement tests | 3/3 PASS |
| route auditor tests | 2/2 PASS |
| `cargo check -p grid-server` | PASS |

未执行 `cargo test --workspace` 或 v3.7 的 175-test full baseline，遵守项目“完整套件需先询问”的规则；本次执行了所有受影响路径和 v3.8 四套密闭回归。

## v3.10 EAASP v2.0 平台骨架对齐

### Spec audit 与反例

- `make v3.10-spec-audit`：PASS；4 个 alignment 文件，37 个 section rows。
- `spec_audit::tests::synthetic_missing_tool_fails_with_named_finding` 删除 `memory_confirm` row 后产生 named finding；auditor tests 2/2 PASS。

### 有序 CI gate

| Gate | 结果 |
|---|---|
| `cargo check --workspace` | PASS（20 个既有 warning） |
| `make rbac-audit` | PASS，134 routes |
| `make v3.10-spec-audit` | PASS |
| `cargo test -p eaasp-certifier -- --test-threads=1` | 35/35 PASS |

`.github/workflows/ci.yml` 保持上述顺序后才进入既有 tests。v3.10 未改 route catalog、Role × Action、Owner-only 或 AuthMode 路径。

### MAT / PIPE 针对性证据

- L2 memory：19/19 PASS；Skill Registry v2 frontmatter：10/10 PASS。
- L4 MCP payload chain：5/5 PASS；L4 gRPC lifecycle + SSE governance：32/32 PASS。
- L3 gate/audit/policy/session validation：49/49 PASS。
- Rust Phase 3 compatibility：22/22 PASS（aggregate 3 + compaction 15 + retry 4）。

结论：L4→L1 真 gRPC 与 L2→L4→ConnectMCP payload chain 成立；ambient discovery env 不得替换 skill dependencies。OPA/five-stage、A2A/Event Room、Cowork 四卡、Ontology/ecosystem、生产 sandbox placement 和 crash recovery 仍是明确 deferred gaps。

### Phase 0.5 真实 Skill 单点验证

最低入口已恢复：`make dev-eaasp`，随后由 `eaasp-cli` 运行 `threshold-calibration` real skill。

本次 live run **未执行**：当前 shell 的 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` 均 unset，`scripts/dev-eaasp.sh` 会在 preflight fail-fast。按安全规则未读取 `.env`，也未伪造 live PASS。Hermetic S8/L4/L3 tests 覆盖相同治理与 orchestration code path，但不替代真实 LLM 单点验证。


- CI：`.github/workflows/ci.yml`，位于 `cargo check --workspace` 之后、workspace tests 之前
- 新路由流程：`docs/cli/USER_GUIDE.md` §12
- 矩阵参考：`docs/status/ROLE_ACTION_MATRIX_2026-07-26.md`
