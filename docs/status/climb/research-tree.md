# Research Tree — v3.16 OBSTACK product surface

> Deterministic summary; 3 cycles logged. Do not edit manually.

**Best local acceptance score:** 75/100
**Phase:** executing
**Last cycle:** 3
**Next hypothesis:** H-004
**Next action:** Dispatch the next ranked pending hypothesis

## Active hypotheses

- **H-001** [confirmed] (dashboard-contract-reuse): Complete the existing web OBSTACK surface with typed SSE and evidence-derived stats, alerts, and optimization guidance
- **H-002** [confirmed] (cli-obstack-surface): Add flow list/top-failed/top-slow CLI verbs over the existing L4 list endpoint
- **H-003** [confirmed] (business-key-read-surface): Expose the persisted canonical BusinessKey from L4 session reads and display it verbatim in the CLI
- **H-004** [pending] (scope-integrity): Encode and negatively test the real L4/web ownership boundary while deferring unsupported cross-service projections
- **H-005** [pending] (verification-closeout): Run integrated positive and negative controls plus dual-gates and close v3.16 truthfully

## Cycle ladder

| run | hypothesis | score | decision | verdict |
|---|---|---:|---|---|
| 20260824-081713-h-001 | H-001 | 30 | PUSH | confirmed |
| 20260824-110612-h-002 | H-002 | 55 | PUSH | confirmed |
| 20260825-074220-h-003 | H-003 | 75 | PUSH | confirmed |

## Negative cache

- Do not add fake grid-server RBAC entries for frontend-only routes
- Do not invent optimize/alerts/stats backend endpoints
- Do not duplicate the existing OBSTACK UI into web-platform
- Do not project health into grid-eval or marketplace without a producer contract
