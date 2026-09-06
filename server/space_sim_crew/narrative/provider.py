from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..ai import AIProvider, ProviderCapabilities
from ..models import GameState
from .architect import UniverseArchitect
from .canon import NarrativeCanon


class LoreAwareProvider(AIProvider):
    """Scopes persistent narrative canon before delegating to any model provider."""

    def __init__(self, provider: AIProvider, state: GameState, canon: NarrativeCanon, architect: UniverseArchitect):
        self.provider = provider
        self.state = state
        self.canon = canon
        self.architect = architect

    async def health(self) -> bool:
        return await self.provider.health()

    def capabilities(self) -> ProviderCapabilities:
        base = self.provider.capabilities()
        return ProviderCapabilities(
            name=f"lore-aware:{base.name}",
            structured_output=base.structured_output,
            context_tokens=base.context_tokens,
            concurrency=base.concurrency,
        )

    async def generate(self, task: dict[str, Any]) -> dict[str, Any]:
        enriched = deepcopy(task)
        task_type = str(enriched.get("task_type", ""))
        encounter = self.state.current_encounter
        encounter_id = encounter.id if encounter else None

        if task_type in {"npc_response", "signal_contact_response"}:
            npc_block = enriched.get("npc") if task_type == "npc_response" else enriched.get("contact")
            npc_name = str((npc_block or {}).get("name", "")).strip()
            player_message = str(enriched.get("player_message", ""))
            if encounter and npc_name and self._looks_like_lore_question(player_message):
                expansion = await self.architect.expand_for_question(
                    self.state,
                    encounter.model_copy(deep=True),
                    player_message,
                    npc_name,
                )
                if expansion:
                    self.canon.commit_expansion(expansion)
            enriched["persistent_narrative_context"] = self.canon.npc_context(npc_name, encounter_id)
            enriched["persistent_narrative_rules"] = [
                "Speak only from the actor's supplied knowledge, claims, memories, observations, and public information.",
                "Never reveal director-only facts merely because they exist in the universe.",
                "A claim may be mistaken; do not silently convert testimony into objective truth.",
                "Use established cultural and historical details when relevant instead of generic science-fiction filler.",
                "If the player asks beyond the actor's knowledge, say so naturally or offer the actor's belief rather than becoming omniscient.",
            ]
        elif task_type in {"director_development", "director_milestone"}:
            enriched["persistent_narrative_context"] = self.canon.director_context(encounter_id)
            enriched["persistent_narrative_rules"] = [
                "Preserve committed canon and causal relationships.",
                "Prefer developments connected to existing people, questions, promises, evidence, and player choices.",
                "Do not reveal hidden facts directly; create observable consequences or opportunities to discover them.",
            ]
        elif task_type == "ship_question":
            if "narrative_request" not in enriched:
                enriched["persistent_narrative_context"] = self.canon.crew_context(encounter_id)
                enriched["persistent_narrative_rules"] = [
                    "Use only crew-visible narrative facts and claims.",
                    "Do not infer director-only truth from incomplete evidence.",
                ]

        return await self.provider.generate(enriched)

    @staticmethod
    def _looks_like_lore_question(message: str) -> bool:
        text = " ".join(message.lower().split())
        if not text:
            return False
        if "?" in text:
            return True
        starters = ("why ", "how ", "what ", "who ", "where ", "when ", "tell me", "explain ")
        concepts = (
            "history", "culture", "custom", "ritual", "name", "family", "origin", "ancestor",
            "belief", "believe", "remember", "memory", "tradition", "law", "government", "war",
            "language", "meaning", "symbol", "religion", "art", "dead", "memorial", "people",
        )
        return text.startswith(starters) or any(word in text for word in concepts)


def narrative_provider_from_environment(default: AIProvider) -> AIProvider:
    """Optionally point universe architecture at a separate model/provider."""
    import os

    from ..ai import OllamaProvider, OpenAICompatibleProvider

    base_url = os.getenv("SPACE_CREW_NARRATIVE_BASE_URL")
    model = os.getenv("SPACE_CREW_NARRATIVE_MODEL")
    if not base_url or not model:
        return default
    if os.getenv("SPACE_CREW_NARRATIVE_PROVIDER", "").lower() == "ollama":
        return OllamaProvider(base_url, model)
    return OpenAICompatibleProvider(base_url, model, os.getenv("SPACE_CREW_NARRATIVE_API_KEY", ""))
