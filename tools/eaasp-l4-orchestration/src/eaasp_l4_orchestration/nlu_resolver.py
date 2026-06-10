"""Intent→Skill NLU resolver using rapidfuzz fuzzy matching.

D34 / L4-01: Users type natural language → resolver finds best matching skill
from the skill registry via fuzzy string matching against skill names + descriptions.
"""

from __future__ import annotations

import logging
from typing import Any

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

# Default confidence threshold below which the resolver returns ranked
# candidates for user disambiguation instead of auto-selecting (per D-04).
DEFAULT_CONFIDENCE_THRESHOLD = 0.6


class SkillCandidate:
    """A skill matched by the NLU resolver."""

    def __init__(
        self, skill_id: str, name: str, description: str, score: float
    ) -> None:
        self.skill_id = skill_id
        self.name = name
        self.description = description
        self.score = score


class NoSkillMatchError(Exception):
    """Raised when no skill meets the confidence threshold."""

    def __init__(self, intent_text: str, candidates: list[dict[str, Any]]) -> None:
        self.intent_text = intent_text
        self.candidates = candidates
        super().__init__(
            f"No skill matched intent '{intent_text}' above threshold "
            f"(best score: {candidates[0]['score'] if candidates else 'N/A'})"
        )


class IntentResolver:
    """Resolve natural-language intent text to a skill_id via fuzzy matching.

    Queries the skill registry for available skills, builds a name+description
    index, and matches using rapidfuzz token_sort_ratio for typo-tolerant matching.
    """

    def __init__(
        self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    ) -> None:
        self._confidence_threshold = confidence_threshold
        self._skill_index: dict[str, str] = {}  # display_text → skill_id

    async def build_index(self, skill_registry_client: Any) -> None:
        """Fetch all skills from the registry and build a search index.

        The skill_registry_client must have a `list_skills()` method returning
        `[{"skill_id": ..., "name": ..., "description": ...}, ...]`.
        If the registry doesn't expose a list endpoint, callers should pass
        a pre-built list via `build_index_from_list()` instead.
        """
        # SkillRegistryClient currently has read_skill (single) — for MVP,
        # we build the index lazily from the registry. If a list endpoint
        # exists, use it; otherwise, build_from_list is the fallback.
        raise NotImplementedError(
            "Use build_index_from_list() with pre-fetched skill list"
        )

    def build_index_from_list(self, skills: list[dict[str, Any]]) -> None:
        """Build search index from a list of skill metadata dicts.

        Each dict must have: skill_id, name, description (description optional).
        """
        self._skill_index.clear()
        for skill in skills:
            skill_id = skill.get("skill_id", "")
            if not skill_id:
                logger.warning("Skipping skill with empty skill_id: %s", skill)
                continue
            name = skill.get("name", skill_id)
            description = skill.get("description", "")
            # Use name as primary match key; descriptions are often long
            # and dilute token_sort_ratio scores when concatenated.
            # Descriptions are preserved in SkillCandidate for context.
            display_text = name.lower()
            # Handle duplicate names by appending skill_id suffix.
            if display_text in self._skill_index:
                display_text = f"{display_text} ({skill_id})".lower()
            self._skill_index[display_text] = skill_id
        logger.info("NLU index built: %d skills indexed", len(self._skill_index))

    def resolve_intent(
        self, intent_text: str
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Match intent_text against the skill index.

        Returns:
            (skill_id | None, ranked_candidates):
            - If best match exceeds confidence threshold: (skill_id, [top candidates])
            - If no match meets threshold: (None, ranked list for disambiguation)
            - If index is empty: raises NoSkillMatchError with empty candidates
        """
        if not self._skill_index:
            raise NoSkillMatchError(intent_text, [])

        # Normalize to lowercase for case-insensitive matching.
        # token_sort_ratio is typo-tolerant and works well with short skill
        # names (per D-02). WRatio is too permissive with long descriptions.
        query = intent_text.lower()
        ranked = process.extract(
            query,
            list(self._skill_index.keys()),
            scorer=fuzz.token_sort_ratio,
            limit=10,
        )

        candidates: list[dict[str, Any]] = []
        for display_text, score, _ in ranked:
            normalized_score = score / 100.0  # rapidfuzz returns 0-100
            skill_id = self._skill_index[display_text]
            # Parse name from "name: description" format
            name = display_text.split(":")[0].strip()
            candidates.append(
                {
                    "skill_id": skill_id,
                    "name": name,
                    "score": round(normalized_score, 4),
                }
            )

        if not candidates:
            raise NoSkillMatchError(intent_text, [])

        best = candidates[0]
        if best["score"] >= self._confidence_threshold:
            logger.info(
                "NLU match: '%s' → skill=%s score=%.3f",
                intent_text,
                best["skill_id"],
                best["score"],
            )
            return best["skill_id"], candidates
        else:
            logger.info(
                "NLU no match above threshold: '%s' best=%s score=%.3f cutoff=%.2f",
                intent_text,
                best["skill_id"],
                best["score"],
                self._confidence_threshold,
            )
            return None, candidates
