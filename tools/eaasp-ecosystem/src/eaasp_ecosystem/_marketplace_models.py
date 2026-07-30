"""Module-scope Pydantic models for marketplace endpoints.

These models are defined at module scope (NOT inside ``create_app``)
because Pydantic 2.13 + FastAPI 0.141 do not auto-resolve forward
references for Pydantic models defined inside a runtime function. When
the model is defined inside ``create_app``, FastAPI's TypeAdapter sees
an unresolved ``ForwardRef('SubmitSkillRequest')`` at request time and
returns HTTP 500 ("TypeAdapter is not fully defined").

Moving the model to module scope (this file) lets FastAPI's import
machinery fully resolve the type at TypeAdapter construction time.

See ``ecosystem.py`` for the route handler references.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class VisibilityScope(str, Enum):
    PRIVATE = "private"
    TENANT = "tenant"
    MARKETPLACE = "marketplace"


class PromotionStage(str, Enum):
    DRAFT = "draft"
    TESTED = "tested"
    REVIEWED = "reviewed"
    PRODUCTION = "production"


class SubmitSkillRequest(BaseModel):
    name: str
    summary: str
    version: str
    manifest: dict
    scope: VisibilityScope = VisibilityScope.PRIVATE
    tags: list[str] = []


class PromoteSkillRequest(BaseModel):
    skill_id: str
    from_stage: PromotionStage
    to_stage: PromotionStage
    rationale: str
