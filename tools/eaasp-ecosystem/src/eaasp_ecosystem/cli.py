"""CLI wrapper for the ecosystem backend (Ontology + Marketplace).

v3.14.0 — EAASP Phase 6 — Ontology / Marketplace / Skill ecosystem.

The CLI is intentionally minimal — it delegates to the underlying
``OntologyService`` / ``SkillMarketplace`` via the same JSON-schema
contract exposed by the REST endpoints, so the v3.14.2 SDK
scaffolding can wrap it uniformly.

Subcommands (v3.14.0):

- ``eaasp-ecosystem ontology derive``       — print the taxonomy graph
- ``eaasp-ecosystem ontology tree <path>``  — list nodes under a path
- ``eaasp-ecosystem ontology links``        — print cross-domain links

(Marketplace subcommands land in v3.14.1.)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

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
    p = sub.add_parser("ontology", help="Ontology / taxonomy commands")
    sub2 = p.add_subparsers(dest="ontology_cmd", required=True)

    p_derive = sub2.add_parser("derive", help="Derive full taxonomy graph")
    p_derive.add_argument("--tenant-id", default="default")
    p_derive.add_argument("--l2-db-path", default=os_environ_or("EAASP_L2_DB_PATH", "./data/dev-l2.db"))
    p_derive.add_argument("--l3-db-path", default=os_environ_or("EAASP_L3_DB_PATH", "./data/dev-l3.db"))
    p_derive.add_argument("--l4-db-path", default=os_environ_or("EAASP_L4_DB_PATH", "./data/dev-l4.db"))
    p_derive.add_argument("--l5-db-path", default=os.environ.get("EAASP_L5_DB_PATH"))
    p_derive.add_argument("--root-layer", default="l2_type")
    p_derive.set_defaults(func=cmd_ontology_derive)

    p_tree = sub2.add_parser("tree", help="List taxonomy nodes under path")
    p_tree.add_argument("path", nargs="?", default=None)
    p_tree.add_argument("--tenant-id", default="default")
    p_tree.add_argument("--l2-db-path", default=os_environ_or("EAASP_L2_DB_PATH", "./data/dev-l2.db"))
    p_tree.add_argument("--l3-db-path", default=os_environ_or("EAASP_L3_DB_PATH", "./data/dev-l3.db"))
    p_tree.add_argument("--l4-db-path", default=os_environ_or("EAASP_L4_DB_PATH", "./data/dev-l4.db"))
    p_tree.add_argument("--l5-db-path", default=os.environ.get("EAASP_L5_DB_PATH"))
    p_tree.add_argument("--root-layer", default="l2_type")
    p_tree.set_defaults(func=cmd_ontology_tree)

    p_links = sub2.add_parser("links", help="List cross-domain links")
    p_links.add_argument("--tenant-id", default="default")
    p_links.add_argument("--l2-db-path", default=os_environ_or("EAASP_L2_DB_PATH", "./data/dev-l2.db"))
    p_links.add_argument("--l3-db-path", default=os_environ_or("EAASP_L3_DB_PATH", "./data/dev-l3.db"))
    p_links.add_argument("--l4-db-path", default=os_environ_or("EAASP_L4_DB_PATH", "./data/dev-l4.db"))
    p_links.add_argument("--l5-db-path", default=os.environ.get("EAASP_L5_DB_PATH"))
    p_links.add_argument("--root-layer", default="l2_type")
    p_links.set_defaults(func=cmd_ontology_links)


def os_environ_or(name: str, default: str) -> str:
    import os

    return os.environ.get(name, default)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eaasp-ecosystem",
        description="EAASP ecosystem CLI (Ontology + Marketplace surface).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    _add_ontology_parser(sub)
    # Marketplace subcommands will be added in v3.14.1.

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())