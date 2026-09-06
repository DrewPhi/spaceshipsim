from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..ai import AIProvider, ProviderCapabilities
from ..models import GameState
from .architect import UniverseArchitect
from .canon import NarrativeCanon
from .discovery import DiscoveryTracker


class LoreAwareProvider(AIProvider):
    """Scopes persistent narrative canon before delegating to any model provider."""

    def __init__(self, provider: AIProvider, state: GameState, canon: NarrativeCanon, architect: UniverseArchitect):
        self.provider = provider
        self.state = state
        self.canon = canon
        self.architect = architect
        self.discovery = DiscoveryTracker(canon)

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
            confrontation = False
            if encounter and npc_name:
                confrontation = self.discovery.is_evidence_confrontation(player_message, encounter.id)
                self.discovery.record_player_message(encounter.id, player_message, npc_name)
                if self._looks_like_lore_question(player_message):
                    expansion = await self.architect.expand_for_question(
                        self.state,
                        encounter.model_copy(deep=True),
                        player_message,
                        npc_name,
                    )
                    if expansion:
                        self.canon.commit_expansion(expansion)
                enriched["discovery_state"] = self.discovery.phase_context(encounter.id)
                enriched["crew_discovered_evidence"] = self.discovery.discovered_evidence_context(encounter.id)
                enriched["conversation_mode"] = "evidence_confrontation" if confrontation else "ordinary_contact"
            enriched["persistent_narrative_context"] = self.canon.npc_context(npc_name, encounter_id)
            enriched["persistent_narrative_rules"] = [
                "Speak only from the actor's supplied knowledge, claims, memories, observations, and public information.",
                "Never reveal director-only facts merely because they exist in the universe.",
                "A claim may be mistaken; do not silently convert testimony into objective truth.",
                "Use established cultural, historical, and personal details when relevant instead of generic science-fiction filler.",
                "Keep this actor psychologically distinct: use their worldview, role, stake, uncertainty, and relationships rather than sounding like an encyclopedia.",
                "If the player asks beyond the actor's knowledge, say so naturally or offer the actor's belief rather than becoming omniscient.",
                "If conversation_mode is evidence_confrontation, respond specifically to the crew's supplied observed evidence. Do not ignore, erase, or magically invalidate a high-confidence physical observation.",
                "When evidence conflicts with this actor's beliefs or prior account, react according to character: reconsider, explain, distinguish, become defensive, admit uncertainty, reveal a personal stake, or knowingly deceive only when canon supports it.",
                "Do not make every contradiction a lie. Bias, inherited accounts, institutional narratives, incomplete records, and honest error are often more interesting.",
            ]
        elif task_type in {"director_development", "director_milestone"}:
            phase = self.discovery.phase_context(encounter_id) if encounter_id else None
            enriched["persistent_narrative_context"] = self.canon.director_context(encounter_id)
            enriched["discovery_state"] = phase
            enriched["persistent_narrative_rules"] = [
                "Preserve committed canon and causal relationships.",
                "Prefer developments connected to existing people, questions, promises, evidence, player interests, and player choices.",
                "Do not reveal hidden facts directly; create observable consequences or opportunities to discover them.",
                *self._phase_rules(str((phase or {}).get("phase", "hook"))),
            ]
        elif task_type == "ship_question":
            if "narrative_request" not in enriched:
                enriched["persistent_narrative_context"] = self.canon.crew_context(encounter_id)
                if encounter_id:
                    enriched["discovery_board"] = self.discovery.crew_board(encounter_id)
                enriched["persistent_narrative_rules"] = [
                    "Use only crew-visible narrative facts, observed evidence, and claims.",
                    "Distinguish observation from testimony and hypothesis.",
                    "Call out an established contradiction when two crew-visible pieces of information do not fit, but do not infer director-only truth from it.",
                    "Treat open questions as unresolved; do not fill them with guesses presented as facts.",
                ]

        return await self.provider.generate(enriched)

    @staticmethod
    def _phase_rules(phase: str) -> list[str]:
        return {
            "hook": [
                "The crew is at the hook. Preserve curiosity; do not dump the explanation. One concrete anomaly is better than exposition.",
            ],
            "investigation": [
                "The crew is investigating. Offer connected avenues, testimony, or observable effects; do not hand them the central contradiction for free.",
            ],
            "contradiction": [
                "The crew has found something that does not fit. Let people and systems react to the contradiction while preserving uncertainty about the deeper explanation.",
            ],
            "reinterpretation": [
                "The crew now has enough evidence to reinterpret the situation. Allow old statements to gain new meaning and let important actors respond specifically.",
            ],
            "decision": [
                "The crew understands enough for a consequential choice. Surface stakes and actor interests without reducing the situation to a simplistic good/evil binary.",
            ],
            "aftermath": [
                "The local decision has been made. Prefer remembered consequences, relationship changes, and a causal future lead over a new unrelated emergency.",
            ],
        }.get(phase, [])

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
            "record", "archive", "built", "repair", "evidence", "scan", "chronology", "date",
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
