from __future__ import annotations

import json

import pytest

from space_sim_crew.ai import AIProvider, ProviderCapabilities
from space_sim_crew.narrative.architect import UniverseArchitect
from space_sim_crew.narrative.canon import NarrativeCanon
from space_sim_crew.narrative.discovery import DiscoveryTracker
from space_sim_crew.narrative.models import (
    DossierClaim,
    DossierEvidence,
    DossierFact,
    DossierQuestion,
    EvidenceDiscovery,
    SituationDossier,
)
from space_sim_crew.narrative.provider import LoreAwareProvider
from space_sim_crew.session import create_game_state


class DeepDiscoveryProvider(AIProvider):
    def __init__(self):
        self.last_task = None
        self.architect_calls = 0

    async def health(self) -> bool:
        return True

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities("deep-discovery-fake", True, 32_000, 1)

    async def generate(self, task):
        self.last_task = task
        request = task.get("narrative_request")
        if request and str(request.get("purpose", "")).startswith("Create the private"):
            self.architect_calls += 1
            return {"answer": json.dumps({
                "premise": "A memorial archive transmits a chronology that seems internally consistent until physical dating is performed.",
                "immediate_stakes": "Publishing the discrepancy could reopen a long-settled civic dispute.",
                "surface_interpretation": "The transmitter appears to be a memorial built after an evacuation.",
                "deeper_interpretation": "The memorial incorporated an older censored archive that survived the evacuation.",
                "central_contradiction": "The substrate is older than the official date of the memorial.",
                "consequential_choice": "The crew can share the dating evidence privately, publish it, or withhold it while investigating further.",
                "future_hook": "A distant archive keeper may contact the crew after comparing an older register.",
                "entities": [
                    {"name": "Coordinator Test", "kind": "person", "summary": "A sincere keeper raised on the official chronology."},
                    {"name": "Memorial Guild", "kind": "institution", "summary": "Caretakers of the archive transmitter."},
                ],
                "facts": [
                    {"subject": "Memorial transmitter", "content": "The underlying archive predates the evacuation.", "visibility": "director", "known_by": []},
                ],
                "claims": [
                    {"speaker": "Coordinator Test", "content": "The memorial was built only after the evacuation.", "believes_claim": True, "visibility": "crew"},
                ],
                "relationships": [],
                "open_questions": [
                    {"question": "Why does the physical substrate predate the official memorial?", "related_to": ["Memorial transmitter"], "why_it_matters": "It distinguishes repair from inherited material."},
                    {"question": "Who had access to the older archive?", "related_to": ["Memorial Guild"], "why_it_matters": "It could explain how the chronology changed."},
                ],
                "evidence": [
                    {"target": "transmitter", "description": "Outer repair layers use a modern alloy family.", "instrument_domains": ["composition"], "reveals": ["The visible shell was rebuilt after the evacuation."], "minimum_scan_fraction": 0.45, "narrative_role": "clue"},
                    {"target": "transmitter", "description": "The inner lattice has an older isotopic signature than the official construction date permits.", "instrument_domains": ["composition"], "reveals": ["The transmitter substrate predates the official memorial chronology."], "minimum_scan_fraction": 0.75, "narrative_role": "contradiction"},
                ],
                "possible_developments": ["The coordinator asks an older keeper to check a restricted register."],
                "actor_notes": {"Coordinator Test": "Earnest, precise, institutionally loyal, personally afraid that the memorial story may be incomplete."},
            })}
        if request:
            return {"answer": "{}"}
        return {
            "message": "That dating result does not fit what I was taught. Give me a moment to distinguish the shell from the archive lattice.",
            "disposition_delta": 0,
            "intention": "reconsider_chronology",
            "deadline_delta_s": 0,
            "action": "hold_position",
            "action_summary": "reviews the crew evidence",
            "reason": "The crew presented physical evidence that conflicts with the inherited chronology.",
            "request": "Share the isotopic confidence interval.",
            "shared_data": "",
            "memory": "The crew confronted the official chronology with physical dating evidence.",
            "commitment": "I will check the older register.",
        }


def _state():
    state = create_game_state(
        universe_name="Deep Discovery Test",
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
async def test_architect_requires_complete_deep_discovery_shape(tmp_path):
    state = _state()
    encounter = state.current_encounter
    assert encounter is not None
    provider = DeepDiscoveryProvider()
    canon = NarrativeCanon(tmp_path, state.universe_id)
    architect = UniverseArchitect(provider, canon)

    dossier = await architect.create_dossier(state, encounter)

    assert dossier.surface_interpretation.startswith("The transmitter")
    assert dossier.deeper_interpretation.startswith("The memorial")
    assert dossier.central_contradiction
    assert dossier.consequential_choice
    assert dossier.future_hook
    assert len(dossier.evidence) >= 2
    assert any(item.narrative_role == "contradiction" for item in dossier.evidence)
    assert provider.architect_calls == 1


def test_discovery_tracker_advances_only_from_earned_information(tmp_path):
    state = _state()
    encounter = state.current_encounter
    assert encounter is not None
    canon = NarrativeCanon(tmp_path, state.universe_id)
    clue = DossierEvidence(
        target="transmitter",
        description="Outer repair layers use a modern alloy family.",
        instrument_domains=["composition"],
        reveals=["The visible shell was rebuilt after the evacuation."],
        minimum_scan_fraction=0.45,
        narrative_role="clue",
    )
    contradiction = DossierEvidence(
        target="transmitter",
        description="The inner lattice has an older isotopic signature.",
        instrument_domains=["composition"],
        reveals=["The substrate predates the official memorial chronology."],
        minimum_scan_fraction=0.75,
        narrative_role="contradiction",
    )
    canon.commit_dossier(encounter.id, SituationDossier(
        premise="A disputed memorial chronology.",
        surface_interpretation="The transmitter appears to have been built after an evacuation.",
        deeper_interpretation="An older archive was incorporated into the later memorial.",
        central_contradiction="Physical dating conflicts with the official construction date.",
        consequential_choice="Decide whether and how to share the dating evidence.",
        future_hook="An older register exists elsewhere.",
        facts=[DossierFact(subject="Memorial", content="A crew-visible plaque gives a post-evacuation date.", visibility="crew")],
        claims=[DossierClaim(speaker="Coordinator Test", content="The memorial was built after the evacuation.", visibility="crew")],
        open_questions=[DossierQuestion(question="Why does the substrate predate the plaque?")],
        evidence=[clue, contradiction],
    ))
    tracker = DiscoveryTracker(canon)

    assert tracker.ensure(encounter.id).phase == "hook"
    tracker.record_player_message(encounter.id, "Why was this memorial built?", "Coordinator Test")
    assert tracker.ensure(encounter.id).phase == "investigation"

    for evidence in (clue, contradiction):
        canon.commit_evidence_discovery(EvidenceDiscovery(
            evidence_id=evidence.id,
            encounter_id=encounter.id,
            target_id=encounter.target_id,
            instrument_id="scan",
            instrument_name="Composition and Temperature Scan",
            observed_at_ms=state.universe_time_ms,
            scan_fraction=evidence.minimum_scan_fraction,
            description=evidence.description,
            reveals=evidence.reveals,
            confidence=0.9,
        ))
        tracker.record_evidence(encounter.id, evidence.id)

    assert tracker.ensure(encounter.id).phase == "reinterpretation"
    assert tracker.ensure(encounter.id).decision_available is False

    tracker.record_player_message(
        encounter.id,
        "You said it was built after the evacuation, but our scan shows the inner lattice is older.",
        "Coordinator Test",
    )
    progress = tracker.ensure(encounter.id)
    assert progress.phase == "decision"
    assert progress.decision_available is True
    assert "memorial" in tracker.top_interests(encounter.id)

    tracker.sync_activity_board(state, encounter.id)
    thread = next(item for item in state.world_threads if any(row.get("encounter_id") == encounter.id for row in item.history))
    assert "KNOWN:" in thread.summary
    assert "CLAIM:" in thread.summary
    assert "CONTRADICTION:" in thread.summary
    assert "UNANSWERED:" in thread.summary
    assert "STAKES:" in thread.summary

    tracker.mark_event(encounter.id, "encounter_resolved")
    assert tracker.ensure(encounter.id).phase == "aftermath"


@pytest.mark.asyncio
async def test_npc_confrontation_receives_only_earned_evidence_and_phase(tmp_path):
    state = _state()
    encounter = state.current_encounter
    assert encounter is not None
    provider = DeepDiscoveryProvider()
    canon = NarrativeCanon(tmp_path, state.universe_id)
    contradiction = DossierEvidence(
        target="transmitter",
        description="The inner lattice has an older isotopic signature.",
        instrument_domains=["composition"],
        reveals=["The substrate predates the official memorial chronology."],
        narrative_role="contradiction",
    )
    clue = DossierEvidence(
        target="transmitter",
        description="Outer repairs use modern alloy.",
        instrument_domains=["composition"],
        reveals=["The shell is newer than the lattice."],
        narrative_role="clue",
    )
    canon.commit_dossier(encounter.id, SituationDossier(
        premise="A disputed memorial chronology.",
        surface_interpretation="A post-evacuation memorial.",
        deeper_interpretation="An older archive survived inside it.",
        central_contradiction="The lattice is too old.",
        consequential_choice="Choose how to disclose the evidence.",
        future_hook="An older register may survive.",
        evidence=[clue, contradiction],
        actor_notes={"Coordinator Test": "Sincere but institutionally loyal."},
    ))
    tracker = DiscoveryTracker(canon)
    for evidence in (clue, contradiction):
        canon.commit_evidence_discovery(EvidenceDiscovery(
            evidence_id=evidence.id,
            encounter_id=encounter.id,
            target_id=encounter.target_id,
            instrument_id="scan",
            instrument_name="Composition and Temperature Scan",
            observed_at_ms=0,
            scan_fraction=0.75,
            description=evidence.description,
            reveals=evidence.reveals,
            confidence=0.95,
        ))
        tracker.record_evidence(encounter.id, evidence.id)

    architect = UniverseArchitect(provider, canon)
    wrapped = LoreAwareProvider(provider, state, canon, architect)
    result = await wrapped.generate({
        "task_type": "npc_response",
        "npc": {"name": "Coordinator Test"},
        "player_message": "You said it was built later, but our scan shows the inner lattice is older.",
    })

    assert result["message"].startswith("That dating result")
    assert provider.last_task["conversation_mode"] == "evidence_confrontation"
    assert len(provider.last_task["crew_discovered_evidence"]) == 2
    assert provider.last_task["discovery_state"]["phase"] == "decision"
    evidence_text = json.dumps(provider.last_task["crew_discovered_evidence"])
    assert "older isotopic" in evidence_text
    assert "director-only" not in evidence_text
