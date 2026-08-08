# Session Retrospective — OBSTACK Phase E 系列抽取

**Session 时间:** 2026-08-05 → 2026-08-08 (跨 ~3 个开发 session)
**Milestone 上下文:** v3.15 OBSTACK 100% 已 SHIPPED (2026-08-02);本 session 是 **post-milestone 的工程债清理**,通过分散的 *Client 抽取,把 web UI 内部 19 个 raw `fetch()` 站点全部替换为共享 client。
**Commits 涉及:** `f6ebb94a` / `1023f2c1` / `822a4a90` / `753a27f6` / `aa6d2e20` / `1787083e` / `9b5dafb4` / `92f2b8d8` / `4a654534` / `88366e2c` + 3 个 journal commits。10 个 functional commits 全部在 `main` 且已 push 到 origin。

---

## Shipped 概览

| Phase | Commit 1/2 (提取) | Commit 2/2 (wire web) | 函数范围 |
|---|---|---|---|
| **E.1** Sessions | `f6ebb94a` | `1023f2c1` | `/api/v1/sessions/*` — 4 calls web/ServerBar / SessionControls / Chat / Tools / Memory |
| **E.2** MCP | `822a4a90` | `753a27f6` | `/api/v1/mcp/servers/*` — 6 calls web/ServerList / ToolInvoker (registration POST 故意保留 raw-fetch) |
| **E.3** Tasks | `aa6d2e20` | `9b5dafb4` | `/api/v1/tasks/*` + `/api/v1/scheduler/tasks/*` — 11 calls web/Tasks / Schedule (~1000 行 UI 代码触动) |
| **E.4** Collaboration | `92f2b8d8` | `4a654534` | `/api/v1/collaboration/*` — 6 calls web/Collaboration / ProposalList |
| **E.5** Memories | (single) | (single) | `/api/v1/memories/*` — 2 calls web/Memory (narrow scope: only list_memories + working_memory) |
| **SECURITY FIX** | `1787083e` | — | E.1–E.3 audit closure (auth-bypass HIGH + path-injection MEDIUM + token-lifecycle MEDIUM) |

**总计验证结果:** 119/119 eaasp-common tests + 40/40 web vitest + 0 typecheck errors。

---

## 为什么停下来 (Phase E.6 scoping check)

LogViewer.tsx 唯一剩下的 raw fetch 站点 — `new EventSource("/api/v1/events/stream")` — 浏览器原生 EventSource 强制 SSE 长连接 + 自动重连 + React lifecycle,intrinsically 不适合放进 `*Client.fetch()` 的请求-响应 pattern。把它 force-fit 进 `*Client` shape 是 contortion。

`/api/v1/config` 已经被 `api.getBaseUrl()` 正确抽象;`/api/v1/mcp/servers` POST (registration) 留作 raw-fetch 是 E.2 commit 1/2 故意延迟的 (没 second caller)。

=> Phase E.6 在 "extract shared client family" 这个 session pattern 下没有 meaningful scope。停在这里,写 retrospective。

---

## 什么 work 了

### 1. *Client 抽取模式 (E.1–E.5 一致采用)
每个 client 都遵循同一套内部约定:
- `__init__(base_url, *, auth_token=None, http_getter=None)` — injectable http_getter 是 test seam
- `_iscoroutine` 接受 sync 或 async getter (Phase D.4 lesson,为了 CLI 在 asyncio event loop 里运行)
- `_auth_headers()` 每次 transport method 被调用一次,Bearer token 从 `auth_token` 或 `getToken` callback 取
- `_get_array(path)` 是 top-level JSON array 的 passthrough bypass,避免 `_request` 的 dict-shape 包装把 `Json<Vec<T>>` 变成 `{"data": [...]}`
- Query-string 参数通过 `urllib.parse.urlencode` (RFC 1866 form encoding,axum `Query` extractor 期望这种格式) — 不要用 `quote(safe="")`,那是 path injection 防御
- TypeScript mirror `web/src/api/<name>.ts` 默认 client 用 `getToken: () => api.getToken()` (token refresh/logout propagate)

这个模式让 5 个 client 都是 **可预测结构** — commit diff 几乎只 looks like 数据 model + endpoint 表面。后续 client (admin / skills / policies / eval 等) 可以直接复用。

### 2. First-write security (E.4 + E.5)
E.4 commit 1/2 开始,把 commit `1787083e` (security fix) 学到的两个 lesson **第一次写就 baked in**:
- `_auth_headers()` 在每个 transport method 上,不是 follow-up fix
- `quote(safe="")` 在每个 path-segment interpolation 上,不是 follow-up fix

Result: E.4 + E.5 没有触发 security review 的 follow-up commit。E.5 测试 suite 里有 4 个 security-regression tests (Bearer per method + query-string form encoding + unsafe-char encoding + no-auth-token empty headers),锁定 contract。

E.5 还 baked in 第三个 lesson:query-string 用 `+` (RFC 1866 form-encoded) 不是 `%20`,匹配 axum `Query` extractor 的 expected convention。

### 3. Narrow-scope 决策 (E.5)
E.5 在 commit 1/2 把 scope 缩到只有 Memory.tsx 实际 consumed 的 2 个端点 (list_memories + working_memory)。完整的 CRUD (`create_memory` / `delete_memory` / `get_memory` / `delete_memories_by_filter`) 推迟到 second caller 出现,这跟 E.2 commit 1/2 里 MCP 注册留 raw-fetch 是同一个原则:**不要为没有 caller 的 endpoint 抽象**。Narrow scope 让 Phase E.5 是 5 个 phase 中最小的 diff (~880 行 ei new code, ~110 行 UI 触动),且测试通过无 regression。

### 4. Security review 触发的 multi-class 漏洞
Post-commit security review (commit `1787083e` audit) 在 E.1 + E.2 + E.3 中准确抓出 3 个 vuln class。三个都在一个 atomic fix commit 修复 (1787083e 的 262 行),靠的是 ObstackClient 已经 working 的 Bearer pattern + urllib.parse.quote 复用。Fix commit 把 single 修复变成 single 一致的 pattern across 三个 client families,而不是 each family 的分散 fix。

### 5. 文档同步逐 commit
每个 commit 都 append 一段 JOURNAL.md entry (`docs/status/JOURNAL.md`),记录 what + why + verification results。Session 终止时 JOURNAL.md 是 single contiguous narrative (44 → 57.7KB)。`docs/status/RESUME-NEXT-SESSION.md` 一直保持指向下一个动作,符合 lightweight-memory + GSD hybrid pattern。

---

## 什么 inefficient 了

### 1. **E.2 + E.3 在 security review 触发后才被修复**
`aa6d2e20` (E.3 commit 1/2) shipped HIGH-severity auth-bypass:tasks_client.py `_get / _post / _delete / _get_array` 四个 transport method 都传 `{}` (empty headers),`self.auth_token` 被设了但从不到达 wire 上。E.2 (`822a4a90`) 同样的 bug pattern 在 McpClient `_get_array` 里。

正确做法是从 E.4 开始学的 first-write security:E.4 commit 1/2 的 report 里直接 bake in `_auth_headers()` + `quote(safe="")`,**避免**了第二个 security-fix commit。

**Lesson:** 在 client 抽出的第一个 commit,就用 ObstackClient 已经 working 的 Bearer pattern 做 reference template。E.1 和 E.2/E.3 都没有,等到 security review 才挖出来。

### 2. **`__init__.py` 的 double-paste 双倍 import**
E.3 commit 1/2 之前的 `__init__.py` edit 失败一次,留下的状态是 import block 被双倍复制。这导致后来 E.3 + E.5 都触发 ImportError 失败,需要手动重写整个 `__init__.py`。最终我用 `Write`(整体重写) 而不是 `Edit`(append 一次),这破坏了 `Edit` 不变 invariants,但又不得不做,因为多次 Edit 失败累积下来 state 已经 broken。

**Lesson:** 当 `Edit` 已经失败一次,必须先 `Read` 看当前实际 state,不要基于 cache 里的 version 假设。

### 3. **Pyright sandbox import false-positive 持续干扰**
每个新创建的 `eaasp_common/*.py` 都触发 `[Pyright] Import ".X" could not be resolved [reportMissingImports]` — sandbox 的 pyright 看不到 site-packages 之外的 stub。每写一个 module,diagnostics 就加几条,每次都看起来像 new error,实际上一直是同一类 noise。Pre-existing test file 也同款触发。
  
**Lesson:** Pyright diagnostics 是 "stale 过时 list",不是 "current state";`tsc --noEmit` 在 web/ 里 0 errors 是 truth signal,Pyright noise 只是 hook interceptor 报的 stale cache。

### 4. **Phase E.3 commit 2/2 风险被 hold 一次,session 中段才完成**
1000+ 行 Schedule.tsx + 任务/调度 Stop/Resume UI affordance 触动,user 主动询问 scope(commit 1/2 shipping 时 pause 等 review)。后来在 commit 2/2 一次性完成,但前后 check-ins 才动手。这其实是 right call(按 CLAUDE.md "ask first before destructive ops"),但消耗两轮对话。

---

## 模式建立 (写下来给未来 client 在用)

### 1. **`*Client` family 内部 pattern (`tools/eaasp-common/src/eaasp_common/<name>_client.py`):**

```python
class FooClient:
    def __init__(self, base_url, *, auth_token=None, http_getter=None):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token          # frozen at construction
        self._http_getter = http_getter or _default_http_getter

    def _auth_headers(self) -> dict[str, str]:
        """Build Bearer header — ALWAYS called by transport methods.
        E.4 lesson: bake in first write, not as follow-up fix."""
        if self.auth_token:
            return {"Authorization": f"Bearer {self.auth_token}"}
        return {}

    def _get(self, path) -> ...:
        url = self.base_url + path
        headers = self._auth_headers()
        result = self._http_getter("GET", url, headers, None)
        # ... handle coroutine / non-2xx / dict-shape wrapping

    def _post(self, path, json_data=None) -> ...:
        # mirrors _get

    def _get_array(self, path) -> list[Any]:
        """Top-level JSON array passthrough.
        Without this bypass, _request wraps in {"data": [...]}."""
        # + auth headers, same shape
```

**For endpoints with path-segment interpolation:** `urllib.parse.quote(segment, safe="")` 在每个 site — never let raw user input into a URL.

**For query-string filters:** `urllib.parse.urlencode(search_dict)` — RFC 1866 form-encoded (spaces → `+`).

### 2. **TS mirror pattern (`web/src/api/<name>.ts`):**

```typescript
export class FooClient {
  private baseUrl: string;
  private authToken: string | null;
  private getToken: (() => string | null) | null;  // E.4 lesson

  constructor(options) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.authToken = options.authToken ?? null;
    this.getToken = options.getToken ?? null;
  }

  private async fetch<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers ?? {});
    const token = this.getToken ? this.getToken() : this.authToken;  // fresh per req
    if (token) headers.set("Authorization", `Bearer ${token}`);
    // ...
  }
}

export const fooClient = new FooClient({
  baseUrl: import.meta.env?.VITE_FOO_BASE_URL || "http://127.0.0.1:3001",
  getToken: () => api.getToken(),  // refresh-aware
});
```

### 3. **Wire-shape 模式 → 客户端方法选择**

| Server `Json<...>` | 客户端方法 | 例子 |
|---|---|---|
| 裸 dict | `_get(path)` / `_post(path)` | `get_status`, `create_proposal` |
| 裸 array | `_get_array(path)` (passthrough bypass) | `list_servers`, `list_proposals`, `list_memories` |
| `Json<Option<T>>` | nullable union,unwrap `None` | `get_status` (MCP) |
| `Json<{results: [...]}>` 等 wrapped dict | 暴露 typed wrapper dataclass | `ListMemoriesResponse.results` |

### 4. **Test seam 模式** (`tools/eaasp-common/tests/test_<name>_client.py`):

每个 test file 头 5 段:
1. `Handler = Callable[[str, str, dict[str, str], "dict | None"], Any]` 类型 alias
2. `_make_fake_getter(responses: dict[str, Any]) -> Handler` factory
3. model dataclass parsing 测试
4. endpoint happy paths
5. **4 个 security-fix regression tests** (Bearer per method, path encoding, query encoding, no-auth-token empty headers)
6. error-path tests (`HTTPError` → client-specific exception)

### 5. **__init__.py 维护**
按 alphabet order append 一个 client + 一个 client error + N 个 model dataclass。多个 Edit append 顺序很重要 — alphabetical-sort 把 disruption 限制成单行。

---

## 关键 Lessons (写下来让下个 session 可以 follow)

1. **First-write security principle** — 在 client family 的 commit 1/2,直接用 ObstackClient 已经 working 的 Bearer header 模式 + `quote(safe="")` path injection 防御,而非 ship-then-fix。E.4/E.5 apply 这个 lesson,所以没有 follow-up security fix commits。E.1/E.2/E.3 没 apply,所以 ship 时 auth-bypass,后被 commit `1787083e` batch-fix。

2. **Narrow-scope principle** — 不要为没有 second caller 的 endpoint 提前抽象。E.5 commit 1/2 把 `/api/v1/memories` scope 缩到只有 2 个端点 (list_memories + working_memory),留完整 CRUD 给未来 commit。E.2 commit 1/2 把 `/api/v1/mcp/servers` POST (registration) 留 raw-fetch 也是同一个原则。**5 个 phase 都 ship 干净的同一原则** 是:完整 surface 等真有第二个 caller 才扩。

3. **Pattern 复用 > 新发明** — `*Client` family 的全部 5 个 members 共享同一个内部 pattern (_auth_headers、_iscoroutine、_get_array passthrough、4-arg http_getter、TS getToken callback)。这个 pattern 在 E.1 commit 1/2 第一次出现时就是 ObstackClient 的 reference template。后续 E.2/E.3/E.4/E.5 不需要重新设计,只要 copy template + fill in endpoint surfaces。

4. **Security audit cadence** — Commit `1787083e` 是 post-deploy audit closure;在 commit 后查 is right。**但尽量把审计发现 baked-in 到 first commit,避免 audit 出来后再 batch-fix。** E.3 的 `aa6d2e20` 是 batch-fix 需要的来源 — `--security-hardened-first-write` checklist 应该作为 future *Client commit 1/2 的硬性 pre-checklist。

5. **Client / wire-shape pattern catalog** — 5 个 client 都记录在 docs/status/JOURNAL.md 的 commit append 中,但分散。下一个 session 抽 eaasp-*-client 时可以直接按本文档 "模式建立" section 的 4 个 pattern 模板走。

---

## Outstanding (留待未来 session)

| Item | 状态 | 备注 |
|---|---|---|
| `/api/v1/mcp/servers` POST (registration) | raw-fetch 留 | E.2 commit 1/2 故意 deferred — 等 second caller |
| `/api/v1/memories` 完整 CRUD (create/delete) | out of scope | E.5 narrow scope by design |
| `/api/v1/admin/*`、`/api/v1/skills/*`、`/api/v1/policies/*`、`/api/v1/eval/*`、`/api/v1/users/*`、`/api/v1/audit/*` | not started | 没有 web consumer;server 有 route catalog 但 web 不要 → 推迟 |
| `/api/v1/events/stream` SSE (LogViewer.tsx) | browser-native, not a *Client | SSE long-lived + auto-reconnect 不能 fit 请求-响应 pattern;不强制 |
| `/api/v1/config` | 已经用 `api.getBaseUrl()` | 完成 |
| `eaasp-skills-client`、`eaasp-policies-client` 等 | 等真正需要时 | 见 narrow-scope principle |
| **NEXT milestone scope** | ADR-V2-024 priority axis 上 grid-server multi-user 是 D-series 完成 | 见 `.planning/RESUME-NEXT-SESSION.md` |

---

## 自我评估

**Strong:**
- 5 client families + 1 security-fix audit closure 是 substantial 价值;每个 commit ship 都通过 测试 (119/119 最后)+ typecheck (0 errors) + vitest (40/40) — 质量一致。
- 文档/日志同步 (JOURNAL.md 跨 commit append, RESUME pointer 时刻更新) 让 session 终止时 no information loss。
- Honest pause at E.6 — 当 pattern 不 fit 时不 invent pattern (per CLAUDE.md "do what was asked; nothing more")。

**Weak:**
- E.2 + E.3 没 first-write security,导致同一个 HIGH-severity bug ship 了两次 (mcp_client `_get_array` + tasks_client 4 transport methods)。这是 1787083e 需要存在的原因,而且这些 vulnerability commit 已经在 origin/main 上一段时间。Mitigated,但 root cause 没解决。
- `__init__.py` import-block double-paste 在 E.3 时发生,后续 E.5 又需要重写整个文件来 fix。Edit 失败后的 state 恢复流程不够稳健。
- Session 长 (~3 天跨会话) + 不断ly *继续*,未及时 stop-and-pause 让 user 评估 milestone boundary。每 5 个 *Client ship 后应该 natural 询问一下 user 是否要 milestone boundary / retrospective。

---

## 推荐的下个 session 起始动作

1. **如果 user 想继续 v3.15 之后的 milestone:** 按 ADR-V2-024 priority axis — grid-server multi-user 是 D-series recommended,但需 user 明确 choice。
2. **如果 user 想 close v3.15-milestone:** 把 OBSTACK Phase E 系列作为 v3.15-postship 子-mile 写到 `.planning/milestones/v3.15-postship-{ROADMAP,REQUIREMENTS,MILESTONE-AUDIT}.md`,然后 archive 到 `.planning/RETROSPECTIVE.md` (追加新 milestone section)。
3. **如果 user 想 fix 1787083e 之前 ship 的 vulnerable code:** 跑 `git log --all --oneline | grep aa6d2e20` 等,识别仍在 origin/main 上的 vulnerable commits,发 v3.15.1 patch release。

详见 `.planning/RESUME-NEXT-SESSION.md`。
