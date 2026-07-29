"""CLI wrapper for the ecosystem backend (Ontology + Marketplace).

v3.14.0 + v3.14.2 — EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem.

The CLI is intentionally minimal:

- **Ontology** subcommands (``derive`` / ``tree`` / ``links``) are
  in-process: they instantiate ``OntologyService`` directly from CLI
  args, since the projection is purely a SQL derivation against local
  L2 / L3 / L4 / L5 SQLite stores.
- **Marketplace** subcommands (``submit`` / ``promote`` / ``list`` /
  ``stats`` / ``audit``) are **HTTP-only** (v3.14.2 MARKETPLACE-03):
  they forward to the live ``L4 /v1/ecosystem/marketplace/*`` endpoints
  via ``httpx.Client(trust_env=False)``. The in-process
  ``SkillMarketplace`` surface is covered by 66 backend tests in
  ``tests/test_marketplace.py``; the CLI does not duplicate that
  surface. Per the v3.14.0 round-1 security review, this avoids a
  guard-bypass class that a CLI in-process write would create.

Auth: ``--api-key`` flag (or ``EAASP_ECOSYSTEM_API_KEY`` env var) +
``--tenant-id`` flag (or ``EAASP_ECOSYSTEM_TENANT``). The server's
``_require_principal`` (``ecosystem.py:151``) maps the API key to a
tenant; the client never sets ``X-Tenant-Id`` or ``?tenant_id=`` (both
explicitly rejected by the round-1 audit lock).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

from .ecosystem import EcosystemConfig
from .ontology import CrossTenantForbidden, OntologyService


def _build_service_from_args(args: argparse.Namespace) -> OntologyService:
    cfg = EcosystemConfig(
        l2_db_path=args.l2_db_path,
        l3_db_path=args.l3_db_path,
        l4_db_path=args.l4_db_path,
        l5_db_path=args.l5_db_path,
        default_tenant=args.tenant_id,
        root_layer=args.root_layer,
    )
    return OntologyService(
        l2_db_path=cfg.l2_db_path,
        l3_db_path=cfg.l3_db_path,
        l4_db_path=cfg.l4_db_path,
        l5_db_path=cfg.l5_db_path,
        default_tenant=cfg.default_tenant,
        root_layer=cfg.root_layer,
    )


# ─── Ontology subcommands (in-process) ────────────────────────────────


def cmd_ontology_derive(args: argparse.Namespace) -> int:
    svc = _build_service_from_args(args)
    try:
        graph = svc.derive_taxonomy(tenant_id=args.tenant_id)
    except CrossTenantForbidden as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    json.dump(graph.to_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def cmd_ontology_tree(args: argparse.Namespace) -> int:
    svc = _build_service_from_args(args)
    try:
        nodes = svc.list_taxonomy(path=args.path, tenant_id=args.tenant_id)
    except CrossTenantForbidden as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    payload: dict[str, Any] = {
        "tenant_id": args.tenant_id,
        "path": args.path or "",
        "nodes": [n.to_dict() for n in nodes],
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def cmd_ontology_links(args: argparse.Namespace) -> int:
    svc = _build_service_from_args(args)
    try:
        graph = svc.derive_taxonomy(tenant_id=args.tenant_id)
    except CrossTenantForbidden as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    payload: dict[str, Any] = {
        "tenant_id": args.tenant_id,
        "links": [l.to_dict() for l in graph.links],
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def _add_ontology_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("ontology", help="Ontology / taxonomy commands (in-process)")
    sub2 = p.add_subparsers(dest="ontology_cmd", required=True)

    p_derive = sub2.add_parser("derive", help="Derive full taxonomy graph")
    p_derive.add_argument("--tenant-id", default="default")
    p_derive.add_argument("--l2-db-path", default=os_environ_or("EAASP_L2_DB_PATH", "./data/dev-l2.db"))
    p_derive.add_argument("--l3-db-path", default=os_environ_or("EAASP_L3_DB_PATH", "./data/dev-l3.db"))
    p_derive.add_argument("--l4-db-path", default=os_environ_or("EAASP_L4_DB_PATH", "./data/dev-l4.db"))
    p_derive.add_argument("--l5-db-path", default=os_environ_or("EAASP_L5_DB_PATH", ""))
    p_derive.add_argument("--root-layer", default="l2_type")
    p_derive.set_defaults(func=cmd_ontology_derive)

    p_tree = sub2.add_parser("tree", help="List taxonomy nodes under path")
    p_tree.add_argument("path", nargs="?", default=None)
    p_tree.add_argument("--tenant-id", default="default")
    p_tree.add_argument("--l2-db-path", default=os_environ_or("EAASP_L2_DB_PATH", "./data/dev-l2.db"))
    p_tree.add_argument("--l3-db-path", default=os_environ_or("EAASP_L3_DB_PATH", "./data/dev-l3.db"))
    p_tree.add_argument("--l4-db-path", default=os_environ_or("EAASP_L4_DB_PATH", "./data/dev-l4.db"))
    p_tree.add_argument("--l5-db-path", default=os_environ_or("EAASP_L5_DB_PATH", ""))
    p_tree.add_argument("--root-layer", default="l2_type")
    p_tree.set_defaults(func=cmd_ontology_tree)

    p_links = sub2.add_parser("links", help="List cross-domain links")
    p_links.add_argument("--tenant-id", default="default")
    p_links.add_argument("--l2-db-path", default=os_environ_or("EAASP_L2_DB_PATH", "./data/dev-l2.db"))
    p_links.add_argument("--l3-db-path", default=os_environ_or("EAASP_L3_DB_PATH", "./data/dev-l3.db"))
    p_links.add_argument("--l4-db-path", default=os_environ_or("EAASP_L4_DB_PATH", "./data/dev-l4.db"))
    p_links.add_argument("--l5-db-path", default=os_environ_or("EAASP_L5_DB_PATH", ""))
    p_links.add_argument("--root-layer", default="l2_type")
    p_links.set_defaults(func=cmd_ontology_links)


# ─── Marketplace subcommands (HTTP only, v3.14.2 MARKETPLACE-03) ─────


def _http_client_from_args(args: argparse.Namespace) -> httpx.Client:
    """Build an ``httpx.Client`` for marketplace subcommands.

    ``trust_env=False`` avoids the macOS Clash proxy (per the project-wide
    ``feedback_env_var_conventions`` gotcha). The Bearer credential is
    forwarded via the ``Authorization`` header; the server's
    ``_require_principal`` resolves it to a tenant.
    """
    return httpx.Client(
        base_url=args.base_url.rstrip("/"),
        trust_env=False,
        timeout=args.timeout,
        headers={
            "Authorization": f"Bearer {args.api_key}",
            # The tenant header is NOT sent — the server's _require_principal
            # maps the API key to a tenant; explicit X-Tenant-Id headers are
            # rejected (per v3.14.0 round-1 audit lock).
        },
    )


def _http_status_to_exit_code(status_code: int) -> int:
    """Translate HTTP status code to a CLI exit code.

    0  — 2xx success.
    2  — 4xx client error (bad request, not-found, ACL denied).
    3  — 401/403 (auth/ACL — distinct from generic 4xx so callers can
          branch on auth failure in CI / scripts).
    4  — 5xx server error (upstream registry unreachable, etc).
    """
    if 200 <= status_code < 300:
        return 0
    if status_code in (401, 403):
        return 3
    if 400 <= status_code < 500:
        return 2
    return 4


def cmd_marketplace_submit(args: argparse.Namespace) -> int:
    """POST /v1/ecosystem/marketplace/skills/submit."""
    body = {
        "name": args.name,
        "summary": args.summary,
        "version": args.version,
        "manifest": json.loads(args.manifest),
        "scope": args.scope,
        "tags": [t for t in args.tags.split(",") if t] if args.tags else [],
        "author_principal": args.author_principal,
    }
    with _http_client_from_args(args) as client:
        resp = client.post("/v1/ecosystem/marketplace/skills/submit", json=body)
    if resp.status_code in (200, 201):
        json.dump(resp.json(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    print(
        f"error: HTTP {resp.status_code}: {resp.text}",
        file=sys.stderr,
    )
    return _http_status_to_exit_code(resp.status_code)


def cmd_marketplace_promote(args: argparse.Namespace) -> int:
    """POST /v1/ecosystem/marketplace/skills/promote."""
    body = {
        "skill_id": args.skill_id,
        "from_stage": args.from_stage,
        "to_stage": args.to_stage,
        "rationale": args.rationale,
    }
    with _http_client_from_args(args) as client:
        resp = client.post("/v1/ecosystem/marketplace/skills/promote", json=body)
    if resp.status_code == 200:
        json.dump(resp.json(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    print(
        f"error: HTTP {resp.status_code}: {resp.text}",
        file=sys.stderr,
    )
    return _http_status_to_exit_code(resp.status_code)


def cmd_marketplace_list(args: argparse.Namespace) -> int:
    """GET /v1/ecosystem/marketplace/skills/list?tag=<tag>."""
    params: dict[str, str] = {}
    if args.tag:
        params["tag"] = args.tag
    with _http_client_from_args(args) as client:
        resp = client.get(
            "/v1/ecosystem/marketplace/skills/list", params=params
        )
    if resp.status_code == 200:
        json.dump(resp.json(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    print(
        f"error: HTTP {resp.status_code}: {resp.text}",
        file=sys.stderr,
    )
    return _http_status_to_exit_code(resp.status_code)


def cmd_marketplace_stats(args: argparse.Namespace) -> int:
    """GET /v1/ecosystem/marketplace/skills/stats?skill_id=<id>."""
    with _http_client_from_args(args) as client:
        resp = client.get(
            "/v1/ecosystem/marketplace/skills/stats",
            params={"skill_id": args.skill_id},
        )
    if resp.status_code == 200:
        json.dump(resp.json(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    print(
        f"error: HTTP {resp.status_code}: {resp.text}",
        file=sys.stderr,
    )
    return _http_status_to_exit_code(resp.status_code)


def cmd_marketplace_audit(args: argparse.Namespace) -> int:
    """GET /v1/ecosystem/marketplace/skills/audit?skill_id=<id>."""
    with _http_client_from_args(args) as client:
        resp = client.get(
            "/v1/ecosystem/marketplace/skills/audit",
            params={"skill_id": args.skill_id},
        )
    if resp.status_code == 200:
        json.dump(resp.json(), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0
    print(
        f"error: HTTP {resp.status_code}: {resp.text}",
        file=sys.stderr,
    )
    return _http_status_to_exit_code(resp.status_code)


def _add_marketplace_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "marketplace",
        help="Marketplace commands (HTTP only — talks to L4 /v1/ecosystem/marketplace/*)",
    )
    sub2 = p.add_subparsers(dest="marketplace_cmd", required=True)

    # Shared flags for every subcommand.
    def _add_shared(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--api-key",
            default=os_environ_or("EAASP_ECOSYSTEM_API_KEY", ""),
            help="Bearer credential (or set EAASP_ECOSYSTEM_API_KEY)",
        )
        p.add_argument(
            "--base-url",
            default=os_environ_or(
                "EAASP_ECOSYSTEM_BASE_URL", "http://127.0.0.1:18087"
            ),
            help="Ecosystem backend root URL",
        )
        p.add_argument(
            "--timeout",
            type=float,
            default=10.0,
            help="Per-request timeout in seconds",
        )

    # submit
    p_submit = sub2.add_parser("submit", help="Submit a 3rd-party skill")
    _add_shared(p_submit)
    p_submit.add_argument("--name", required=True)
    p_submit.add_argument("--summary", required=True)
    p_submit.add_argument("--version", required=True)
    p_submit.add_argument(
        "--manifest",
        required=True,
        help='JSON manifest string, e.g. \'{"entrypoints": ["calibrate"]}\'',
    )
    p_submit.add_argument(
        "--scope",
        choices=["private", "tenant", "marketplace"],
        default="private",
    )
    p_submit.add_argument(
        "--tags",
        default="",
        help="Comma-separated tag list, e.g. 'eaasp,llm'",
    )
    p_submit.add_argument("--author-principal", required=True)
    p_submit.set_defaults(func=cmd_marketplace_submit)

    # promote
    p_promote = sub2.add_parser(
        "promote", help="Promote a skill along the 4-stage lifecycle"
    )
    _add_shared(p_promote)
    p_promote.add_argument("--skill-id", required=True)
    p_promote.add_argument(
        "--from-stage",
        choices=["draft", "review", "certified", "published"],
        required=True,
    )
    p_promote.add_argument(
        "--to-stage",
        choices=["draft", "review", "certified", "published"],
        required=True,
    )
    p_promote.add_argument("--rationale", required=True)
    p_promote.set_defaults(func=cmd_marketplace_promote)

    # list
    p_list = sub2.add_parser("list", help="List marketplace skills")
    _add_shared(p_list)
    p_list.add_argument("--tag", default=None)
    p_list.set_defaults(func=cmd_marketplace_list)

    # stats
    p_stats = sub2.add_parser("stats", help="Per-skill analytics")
    _add_shared(p_stats)
    p_stats.add_argument("--skill-id", required=True)
    p_stats.set_defaults(func=cmd_marketplace_stats)

    # audit
    p_audit = sub2.add_parser("audit", help="Submission audit trail")
    _add_shared(p_audit)
    p_audit.add_argument("--skill-id", required=True)
    p_audit.set_defaults(func=cmd_marketplace_audit)


# ─── argparse bootstrap ────────────────────────────────────────────────


def os_environ_or(name: str, default: str) -> str:
    import os

    return os.environ.get(name, default)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eaasp-ecosystem",
        description="EAASP ecosystem CLI (Ontology in-process + Marketplace HTTP).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    _add_ontology_parser(sub)
    _add_marketplace_parser(sub)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())