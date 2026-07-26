# Role × Action Matrix — 2026-07-26

> 权威实现：`crates/grid-engine/src/auth/roles.rs`。本表用于 v3.9 运维与评审，不替代代码和测试。

| Action | Viewer | User | Admin | Owner |
|---|:---:|:---:|:---:|:---:|
| Read | ✓ | ✓ | ✓ | ✓ |
| CreateSession | — | ✓ | ✓ | ✓ |
| RunAgent | — | ✓ | ✓ | ✓ |
| ManageMcp | — | — | ✓ | ✓ |
| ManageSkills | — | — | ✓ | ✓ |
| ManageUsers | — | — | — | ✓ |
| ManageConfig | — | — | — | ✓ |
| ManageAudit | — | — | ✓ | ✓ |
| ManageHooks | — | — | ✓ | ✓ |
| ManageMemories | — | — | ✓ | ✓ |
| ManageProviders | — | — | ✓ | ✓ |
| ManageSecrets | — | — | ✓ | ✓ |
| ManageSandbox | — | — | ✓ | ✓ |
| ManageScheduler | — | — | ✓ | ✓ |
| ManageSecurity | — | — | ✓ | ✓ |
| ManageCollaboration | — | — | ✓ | ✓ |
| ManageKnowledgeGraph | — | — | ✓ | ✓ |
| ManageEval | — | — | ✓ | ✓ |
| ManageMetering | — | — | ✓ | ✓ |
| ManageAgents | — | — | ✓ | ✓ |

## 不变量

- Viewer 仅可读取。
- User 增加会话创建与 Agent 执行。
- Admin 增加业务运行域管理，但不能管理用户或全局配置。
- Owner 对所有 Action 始终成功。
- Action enum、解析器、生产矩阵和 `rbac_action_matrix` 测试必须在同一逻辑变更中同步。
