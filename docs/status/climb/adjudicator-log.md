# Climb adjudicator log

Append-only record of architecture and push decisions.

- 2026-08-23 H-001 route-ownership calibration: L4 owns OBSTACK APIs; grid-server has no proxy. Use authenticated frontend routes and direct L4 client; keep Rust catalog at 134 unless real server routes are added.
- 2026-08-24 architecture adjudication: `web/` already owns the OBSTACK dashboard. Complete it in place; do not duplicate it into `web-platform` or invent grid-server routes.
- 2026-08-24 ecosystem adjudication: grid-eval and marketplace have no OBSTACK producer contract. Register explicit deferrals and score boundary integrity instead of synthetic health fields.
