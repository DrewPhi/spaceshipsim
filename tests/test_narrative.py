from __future__ import annotations

import json

import pytest

from space_sim_crew.ai import AIProvider, ProviderCapabilities
from space_sim_crew.narrative.architect import UniverseArchitect
from space_sim_crew.narrative.canon import NarrativeCanon
from space_sim_crew.narrative.models import DossierFact, SituationDossier
from space_sim_crew.narrative.provider import LoreAwareProvider
from space_sim_crew.session import create_game_state


class NarrativeFakeProvider(AIProvider):
    def __init__(self):
        self.last_task = None

    async def health(self) -> bool:
        return True

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities("narrative-fake", True, 32_000, 1)

    async def generate(self, task):
        self.last_task = task
        request = task.get("narrative_request")
        if request and request.get("purpose", "").startswith("Create the private"):
            payload = {
                "premise": "A memorial transmitter is maintained by two groups who disagree about who may be named.",
                "immediate_stakes": "The transmitter is degrading.",
                "entities": [
                    {"name": "Coordinator Test", "kind": "person", "summary": "A keeper who favors the old naming rule."},
                    {"name": "Memorial Guild", "kind": "institution", "summary": "Caretakers of a public memorial archive."},
                ],
                "facts": [
                    {"subject": "Memorial Guild", "content": "The naming restriction began after an archival loss.", "visibility": "director", "known_by": ["Coordinator Test"]},
                    {"subject": "Memorial Guild", "content": "The transmitter is a public memorial.", "visibility": "crew", "known_by": []},
                    {"subject": "Memorial Guild", "content": "A hidden repair log contradicts the official chronology.", "visibility": "director", "known_by": []},
                ],
                "claims": [],
                "relationships": [],
                "open_questions": [{"question": "Why was the naming rule adopted?", "related_to": ["Memorial Guild"], "why_it_matters": "It explains the disagreement."}],
                "evidence": [{"target": "transmitter", "description": "Layered repairs reveal two construction periods.", "instrument_domains": ["composition", "invented_magic_sensor"], "reveals": ["repair chronology"], "minimum_scan_fraction": 0.75}],
                "possible_developments": ["A younger keeper challenges the old rule."],
                "actor_notes": {"Coordinator Test": "Defends the old rule but is willing to discuss its history."},
            }
            return {"answer": json.dumps(payload)}
        if request and request.get("purpose", "").startswith("Materialize only"):
            payload = {
                "question": request["player_question"],
                "new_entities": [],
                "new_facts": [{"subject": "Memorial Guild", "content": "The archival loss followed a forced evacuation.", "visibility": "director", "known_by": ["Coordinator Test"]}],
                "new_claims": [],
                "new_relationships": [],
                "new_questions": [],
                "new_evidence": [],
                "actor_notes": {"Coordinator Test": "Knows the evacuation caused the archival loss."},
                "summary": "The naming rule is tied to records lost during an evacuation.",
            }
            return {"answer": json.dumps(payload)}
        return {
            "message": "The rule began after an evacuation destroyed part of our archive.",
            "disposition_delta": 0,
            "intention": "explain_history",
            "deadline_delta_s": 0,
            "action": "hold_position",
            "action_summary": "holds position",
            "reason": "The crew asked about history.",
            "request": "",
            "shared_data": "",
            "memory": "The crew asked about the naming rule.",
            "commitment": "",
        }


def _state():
    state = create_game_state(
        universe_name="Narrative Test",
        seed=17,
        ship_name="Lumen",
        crew_capacity=2,
        character_name="Vale",
        backstory="Explorer",
        scenario_preset="friendly_contact_test",
    )
    assert state.current_encounter is not None
    assert state.current_encounter.npc is not None
    state.current_encounter.npc.name = "Coordinator Test"
    return state


@pytest.mark.asyncio
async def test_architect_commits_scoped_canon_and_filters_sensor_domains(tmp_path):
    state = _state()
    encounter = state.current_encounter
    assert encounter is not None
    provider = NarrativeFakeProvider()
    canon = NarrativeCanon(tmp_path, state.universe_id)
    architect = UniverseArchitect(provider, canon)

    dossier = await architect.create_dossier(state, encounter)
    canon.commit_dossier(encounter.id, dossier)

    assert dossier.premise.startswith("A memorial transmitter")
    assert dossier.evidence[0].instrument_domains == ["composition"]
    assert canon.path.exists()

    npc_context = canon.npc_context("Coordinator Test", encounter.id)
    npc_text = json.dumps(npc_context)
    assert "naming restriction" in npc_text
    assert "hidden repair log" not in npc_text

    crew_text = json.dumps(canon.crew_context(encounter.id))
    assert "public memorial" in crew_text
    assert "naming restriction" not in crew_text


@pytest.mark.asyncio
async def test_lore_aware_provider_materializes_question_before_npc_reply(tmp_path):
    state = _state()
    encounter = state.current_encounter
    assert encounter is not None
    assert encounter.npc is not None

    provider = NarrativeFakeProvider()
    canon = NarrativeCanon(tmp_path, state.universe_id)
    canon.commit_dossier(
        encounter.id,
        SituationDossier(
            premise="A memorial dispute surrounds the contact.",
            facts=[DossierFact(subject="Memorial Guild", content="The rule has an unknown origin.", known_by=["Coordinator Test"])],
        ),
    )
    architect = UniverseArchitect(provider, canon)
    wrapped = LoreAwareProvider(provider, state, canon, architect)

    result = await wrapped.generate({
        "task_type": "npc_response",
        "npc": {"name": "Coordinator Test"},
        "player_message": "Why do you follow that naming rule?",
        "public_situation": encounter.public_summary,
    })

    assert result["message"].startswith("The rule began")
    assert canon.document.expansions
    assert "persistent_narrative_context" in provider.last_task
    context_text = json.dumps(provider.last_task["persistent_narrative_context"])
    assert "forced evacuation" in context_text
