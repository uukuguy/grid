"""eaasp ecosystem — thin wrapper over ``EaaspEcosystemClient``.

Per D-42, this is a **thin CLI**: every subcommand delegates to
``EaaspEcosystemClient`` (the v3.14.2 SDK thin client). No business
logic is re-implemented; the SDK is the single source of truth for
parameter shapes + error mapping.

Three subcommand groups:

- ``eaasp ecosystem ontology {derive,tree,links}`` — read-only taxonomy
  projection over L2 / L3 / L4 / L5 stores.
- ``eaasp ecosystem marketplace {submit,promote,list,stats,audit}`` —
  4-stage promotion lifecycle + ACL-filtered reads.
- ``eaasp ecosystem schema`` — emit the EAASP v2.0 surface as
  machine-readable JSON-schema (SDK-03 pass-through).

Auth is read from environment variables so the CLI does not require
flags for the common case:

- ``EAASP_ECOSYSTEM_API_KEY`` (required for all Bearer-gated calls)
- ``EAASP_ECOSYSTEM_BASE_URL`` (default ``http://127.0.0.1:18087``)
"""

from __future__ import annotations

import json
import os

import click

from eaasp.client.ecosystem_client import (
    EaaspEcosystemACLDenied,
    EaaspEcosystemAuthError,
    EaaspEcosystemClient,
    EaaspEcosystemError,
    EaaspEcosystemPromotionError,
    EaaspEcosystemTenantForbidden,
)


def _build_client_from_ctx(ctx: click.Context) -> EaaspEcosystemClient:
    """Build the SDK client from the Click context + env vars."""
    api_key = ctx.obj.get("api_key") or os.environ.get(
        "EAASP_ECOSYSTEM_API_KEY", ""
    )
    base_url = ctx.obj.get("base_url") or os.environ.get(
        "EAASP_ECOSYSTEM_BASE_URL", "http://127.0.0.1:18087"
    )
    if not api_key:
        click.echo(
            "error: api_key required — pass --api-key or set "
            "EAASP_ECOSYSTEM_API_KEY environment variable",
            err=True,
        )
        ctx.exit(2)
    return EaaspEcosystemClient(base_url=base_url, api_key=api_key)


def _print_json(_ctx: click.Context, data: dict) -> None:  # noqa: ARG001
    """Print a JSON dict to stdout. ``_ctx`` is unused but the function
    is shaped for use as a Click command callback (which always receives
    a Context)."""
    click.echo(json.dumps(data, indent=2, sort_keys=True))


# ─── Click group ───────────────────────────────────────────────────────


@click.group("ecosystem")
@click.option(
    "--api-key",
    default=None,
    envvar="EAASP_ECOSYSTEM_API_KEY",
    help="Bearer credential (or set EAASP_ECOSYSTEM_API_KEY)",
)
@click.option(
    "--base-url",
    default=None,
    envvar="EAASP_ECOSYSTEM_BASE_URL",
    help="Ecosystem backend root URL (default http://127.0.0.1:18087)",
)
@click.pass_context
def ecosystem_cmd(
    ctx: click.Context, api_key: str | None, base_url: str | None
) -> None:
    """EAASP Ecosystem — Ontology / Marketplace / JSON-schema surface."""
    ctx.ensure_object(dict)
    ctx.obj["api_key"] = api_key
    ctx.obj["base_url"] = base_url


# ─── schema (top-level, no nested group) ──────────────────────────────


@ecosystem_cmd.command("schema")
@click.pass_context
def schema_cmd(ctx: click.Context) -> None:
    """Emit the EAASP v2.0 ecosystem surface as JSON-schema (SDK-03)."""
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.get_schema()
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(3)
    _print_json(ctx, data)


# ─── ontology sub-group ────────────────────────────────────────────────


@ecosystem_cmd.group("ontology")
def ontology_group() -> None:
    """Ontology / taxonomy commands (read-only)."""


@ontology_group.command("derive")
@click.pass_context
def ontology_derive(ctx: click.Context) -> None:
    """Derive the full taxonomy graph for the caller's tenant."""
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.derive_taxonomy()
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(3)
    _print_json(ctx, data)


@ontology_group.command("tree")
@click.argument("path", required=False, default=None)
@click.pass_context
def ontology_tree(ctx: click.Context, path: str | None) -> None:
    """List taxonomy nodes under ``PATH`` (omit for root)."""
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.list_taxonomy(path=path)
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(3)
    _print_json(ctx, data)


@ontology_group.command("links")
@click.pass_context
def ontology_links(ctx: click.Context) -> None:
    """List cross-domain links."""
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.list_ontology_links()
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(3)
    _print_json(ctx, data)


# ─── marketplace sub-group ─────────────────────────────────────────────


@ecosystem_cmd.group("marketplace")
def marketplace_group() -> None:
    """Marketplace commands (submit / promote / list / stats / audit)."""


@marketplace_group.command("submit")
@click.option("--name", required=True)
@click.option("--summary", required=True)
@click.option("--version", required=True)
@click.option(
    "--manifest",
    required=True,
    help="JSON manifest string, e.g. '{\"entrypoints\":[\"calibrate\"]}'",
)
@click.option(
    "--scope",
    type=click.Choice(["private", "tenant", "marketplace"]),
    default="private",
)
@click.option(
    "--tags",
    default="",
    help="Comma-separated tag list, e.g. 'eaasp,llm'",
)
@click.option("--author-principal", required=True)
@click.pass_context
def marketplace_submit(
    ctx: click.Context,
    name: str,
    summary: str,
    version: str,
    manifest: str,
    scope: str,
    tags: str,
    author_principal: str,
) -> None:
    """Submit a 3rd-party skill (POST /v1/ecosystem/marketplace/skills/submit)."""
    body_tags = [t for t in tags.split(",") if t] if tags else []
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.submit_skill(
                name=name,
                summary=summary,
                version=version,
                manifest=json.loads(manifest),
                scope=scope,
                tags=tuple(body_tags),
                author_principal=author_principal,
            )
        except EaaspEcosystemACLDenied as exc:
            click.echo(f"error: ACL denied — {exc}", err=True)
            ctx.exit(3)
        except EaaspEcosystemTenantForbidden as exc:
            click.echo(f"error: cross-tenant — {exc}", err=True)
            ctx.exit(3)
        except EaaspEcosystemAuthError as exc:
            click.echo(f"error: auth — {exc}", err=True)
            ctx.exit(3)
        except EaaspEcosystemPromotionError as exc:
            click.echo(f"error: promotion — {exc}", err=True)
            ctx.exit(2)
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(4)
    _print_json(ctx, data)


@marketplace_group.command("promote")
@click.option("--skill-id", required=True)
@click.option(
    "--from-stage",
    type=click.Choice(["draft", "review", "certified", "published"]),
    required=True,
)
@click.option(
    "--to-stage",
    type=click.Choice(["draft", "review", "certified", "published"]),
    required=True,
)
@click.option("--rationale", required=True)
@click.option(
    "--actor-principal",
    default=None,
    help="Override actor_principal (default: derived from API key server-side)",
)
@click.option(
    "--actor-role",
    type=click.Choice(["author", "reviewer", "admin", "public"]),
    default=None,
    help="Override actor_role (default: derived from API key server-side)",
)
@click.pass_context
def marketplace_promote(
    ctx: click.Context,
    skill_id: str,
    from_stage: str,
    to_stage: str,
    rationale: str,
    actor_principal: str | None,
    actor_role: str | None,
) -> None:
    """Promote a skill (POST /v1/ecosystem/marketplace/skills/promote).

    The server's ``_require_principal`` resolves actor_principal +
    actor_role from the API key by default. Pass ``--actor-principal``
    or ``--actor-role`` to override (useful for testing / cross-tenant
    workflows).
    """
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.promote_skill(
                skill_id=skill_id,
                from_stage=from_stage,
                to_stage=to_stage,
                rationale=rationale,
                actor_principal=actor_principal or "apikey:server-resolved",
                actor_role=actor_role or "author",
            )
        except EaaspEcosystemACLDenied as exc:
            click.echo(f"error: ACL denied — {exc}", err=True)
            ctx.exit(3)
        except EaaspEcosystemPromotionError as exc:
            click.echo(f"error: promotion — {exc}", err=True)
            ctx.exit(2)
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(4)
    _print_json(ctx, data)


@marketplace_group.command("list")
@click.option("--tag", default=None)
@click.pass_context
def marketplace_list(ctx: click.Context, tag: str | None) -> None:
    """List ACL-filtered marketplace skills."""
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.list_skills(tag=tag)
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(3)
    _print_json(ctx, data)


@marketplace_group.command("stats")
@click.option("--skill-id", required=True)
@click.pass_context
def marketplace_stats(ctx: click.Context, skill_id: str) -> None:
    """Per-skill analytics."""
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.skill_stats(skill_id=skill_id)
        except EaaspEcosystemPromotionError as exc:
            click.echo(f"error: not found — {exc}", err=True)
            ctx.exit(2)
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(3)
    _print_json(ctx, data)


@marketplace_group.command("audit")
@click.option("--skill-id", required=True)
@click.pass_context
def marketplace_audit(ctx: click.Context, skill_id: str) -> None:
    """Submission audit trail."""
    with _build_client_from_ctx(ctx) as client:
        data: dict = {}
        try:
            data = client.submission_audit(skill_id=skill_id)
        except EaaspEcosystemError as exc:
            click.echo(f"error: {exc}", err=True)
            ctx.exit(3)
    _print_json(ctx, data)
