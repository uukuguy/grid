# Production Usability — Route Authorization Catalog — 2026-07-26

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

## 运维路径

- 本地：`make rbac-audit`
- CI：`.github/workflows/ci.yml`，位于 `cargo check --workspace` 之后、workspace tests 之前
- 新路由流程：`docs/cli/USER_GUIDE.md` §12
- 矩阵参考：`docs/status/ROLE_ACTION_MATRIX_2026-07-26.md`
