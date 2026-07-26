# VERIFY：Certifier 覆盖面

## 当前 contract-v1.2.0 surface

v3.10 冻结 `proto/eaasp/runtime/v2/`：17 RuntimeService RPC + 4 HookService RPC。`eaasp-certifier` 的职责仍是 L1 substitutability，而不是声称认证整个 EAASP 平台。

| 规范域 | 当前 certifier 证据 | 状态 |
|---|---|---|
| §8.5 Runtime Interface Contract | `verifier.rs` method probes；`v2_must_methods.rs` | certified |
| §9.1 Runtime tiers/capability report | `selector.rs` / runtime pool / verify report | partial |
| §13 Hook boundary | HookService contract tests + cross-runtime contract suite | certified（wire） |
| §9.4 Sandbox tiers | capability reporting，未验证 gVisor/Firecracker placement | not_certified |
| §7.7 Memory Engine | L2 Python tests，不属于 L1 certifier | not_certified |
| §6.9 Approval chain | 当前无五阶段 verifier | not_certified |
| §5 L4 orchestration | L4 Python tests，不属于 L1 certifier | partial |
| §14 A2A / §4 Cowork | contract-v1.2.0 无 surface | not_certified |

## 21 RPC 审计边界

VERIFY-02 的正确解释：现有 Phase 3 contract suites 保持对 21 RPC 的 PASS/XFAIL 行为与 7 runtime substitutability；v3.10 不为平台层“凑”新 RPC。`make v2-phase3-e2e-rust` 是 Rust-side guard；完整外部 runtime matrix 需要对应 runtime 服务可用。

## Spec audit 规则

`eaasp-certifier spec-audit` 将验证这些文档是完整、非空且包含必需骨架标记：

- 5 层：L0-L5（L5 是逻辑层，因此表中共六行含 protocol）
- 3 管道：Hook / Data flow / Session control
- 4 卡：Event / Evidence / Action / Approval
- L4→L1 gRPC、L2 MCP→L4→ConnectMCP、OPA/5-stage、Sandbox tiers
- deferred rows必须包含 owner，不允许 silent drift

审计器**不**把 `missing` 文本本身当失败；已声明、已分配 owner 的缺口是诚实基线。若必需 section/marker 被删除、文件缺失、状态无法识别或 deferred 无 owner，则退出 1。

## CI 兼容

顺序保持：

1. `cargo check --workspace`
2. `make rbac-audit`
3. `make v3.10-spec-audit`
4. targeted / existing CI tests

因此 v3.9 route catalog、Owner-only 与 AuthMode 语义继续是前置 gate，v3.10 不覆盖或绕过它们。
