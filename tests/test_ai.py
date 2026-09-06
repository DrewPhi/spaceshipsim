import json
from typing import Any

import pytest

from space_sim_crew.ai import AIOrchestrator, AIProvider, DeterministicProvider, HybridProvider, OllamaProvider, ProviderCapabilities, provider_from_environment
from space_sim_crew.generation import generate_encounter, generate_system


class SpyProvider(AIProvider):
    def __init__(self):
        self.tasks: list[dict[str, Any]] = []

    async def health(self) -> bool:
        return True

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities("spy", True, 1_000, 1)

    async def generate(self, task: dict[str, Any]) -> dict[str, Any]:
        self.tasks.append(task)
        if task["task_type"] == "director_development":
            return {"action": "configure_scenario", "public_detail": "A new public detail.", "hidden_detail": "A private extension.", "deadline_adjustment_s": 0}
        return {"message": "We acknowledge your signal.", "disposition_delta": .1, "intention": "cooperate", "deadline_delta_s": 30}


class FailingProvider(SpyProvider):
    async def generate(self, task: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("provider unavailable")


@pytest.mark.asyncio
async def test_npc_prompt_excludes_hidden_truth() -> None:
    provider = SpyProvider()
    orchestrator = AIOrchestrator(provider)
    # Find a generated encounter with an NPC.
    encounter = None
    for x in range(100):
        system = generate_system(42, (x, 0))
        candidate = generate_encounter(42, system)
        if candidate.npc:
            encounter = candidate
            break
    assert encounter is not None
    encounter.hidden_truth["secret_marker"] = "DO_NOT_LEAK_7B3"
    message, proposal = await orchestrator.npc_response(encounter, "We are peaceful explorers.")
    assert message
    assert proposal.action == "npc_decision"
    assert proposal.parameters["actor_action"] in {"hold_position", "approach", "withdraw", "share_data", "request_action", "change_course", "depart"}
    assert "DO_NOT_LEAK_7B3" not in json.dumps(provider.tasks)
    assert "hidden_truth" not in json.dumps(provider.tasks)
    assert encounter.npc.memories == []


@pytest.mark.asyncio
async def test_deterministic_provider_changes_response_to_player_intent() -> None:
    provider = DeterministicProvider()
    helpful = await provider.generate({"task_type": "npc_response", "player_message": "We can help repair you", "npc": {}})
    hostile = await provider.generate({"task_type": "npc_response", "player_message": "Surrender or we attack", "npc": {}})
    assert helpful["disposition_delta"] > 0
    assert hostile["disposition_delta"] < 0


@pytest.mark.asyncio
async def test_director_proposes_bounded_scenario_configuration() -> None:
    system = generate_system(7, (0, 0))
    encounter = generate_encounter(7, system)
    encounter.hidden_truth["secret_marker"] = "DIRECTOR_SECRET_9F2"
    provider = SpyProvider()
    orchestrator = AIOrchestrator(provider)
    proposal = await orchestrator.develop_encounter(encounter, [])
    assert proposal.action == "configure_scenario"
    assert len(proposal.parameters["public_detail"]) <= 500
    assert -60 <= proposal.parameters["deadline_adjustment_s"] <= 60
    assert "DIRECTOR_SECRET_9F2" not in json.dumps(provider.tasks)


@pytest.mark.asyncio
async def test_hybrid_provider_escalates_only_after_local_failure() -> None:
    escalation = SpyProvider()
    hybrid = HybridProvider(FailingProvider(), escalation)
    result = await hybrid.generate({"task_type": "npc_response"})
    assert result["message"]
    assert len(escalation.tasks) == 1


def test_environment_builds_hybrid_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPACE_CREW_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("SPACE_CREW_AI_MODEL", "qwen3:4b")
    monkeypatch.setenv("SPACE_CREW_CODEX_ENABLED", "1")
    assert isinstance(provider_from_environment(), HybridProvider)


def test_environment_selects_native_ollama_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPACE_CREW_AI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("SPACE_CREW_AI_MODEL", "qwen3:4b")
    monkeypatch.setenv("SPACE_CREW_AI_PROVIDER", "ollama")
    monkeypatch.delenv("SPACE_CREW_CODEX_ENABLED", raising=False)
    assert isinstance(provider_from_environment(), OllamaProvider)
