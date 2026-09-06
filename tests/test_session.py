from pathlib import Path

import pytest

from typing import Any

from space_sim_crew.ai import AIProvider, DeterministicProvider, ProviderCapabilities
from space_sim_crew.signal_processing import default_signal_recipe, validate_signal_recipe
from space_sim_crew.models import StationRole
from space_sim_crew.persistence import SaveStore
from space_sim_crew.session import GameSession, create_game_state


@pytest.mark.asyncio
async def test_transmission_changes_npc_and_persists(tmp_path: Path) -> None:
    state = None
    for seed in range(200):
        candidate = create_game_state(
            universe_name="Contact Test",
            seed=seed,
            ship_name="Speaker",
            crew_capacity=2,
            character_name="Envoy",
            backstory="",
        )
        if candidate.current_encounter and candidate.current_encounter.npc:
            state = candidate
            break
    assert state is not None
    store = SaveStore(tmp_path)
    session = GameSession(state, store, DeterministicProvider(), "session_contact")
    store.initialize(state, session.id)
    connection = session.join("Envoy", state.characters[0].id, StationRole.COMMUNICATIONS)
    encounter = state.current_encounter
    assert encounter and encounter.npc
    before_disposition = encounter.npc.disposition
    before_deadline = encounter.deadline_s
    frequency = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), state.seed, encounter.family)["center_frequency_mhz"]
    events = await session.command(connection.token, {
        "client_sequence": 1,
        "command_type": "transmit",
        "parameters": {"frequency_mhz": frequency, "message": "We are peaceful explorers and can help repair your vessel."},
    })
    assert [event.event_type for event in events] == ["transmission_sent", "npc_action_committed", "npc_memory_recorded"]
    assert encounter.npc.disposition > before_disposition
    if before_deadline is not None:
        assert encounter.deadline_s and encounter.deadline_s > before_deadline
    assert store.load(state.universe_id).message_log[-1]["speaker"] == encounter.npc.name
    loaded = store.load(state.universe_id)
    assert loaded.current_encounter and loaded.current_encounter.npc
    assert loaded.current_encounter.npc.memories[-1]["summary"]
    assert events[-1].visibility == "entity-private"


@pytest.mark.asyncio
async def test_ship_computer_uses_player_safe_projection(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Computer Test", seed=9, ship_name="Query", crew_capacity=1, character_name="Solo", backstory=""
    )
    secret = "OBJECTIVE_SECRET_DO_NOT_DISCLOSE"
    assert state.current_encounter
    state.current_encounter.hidden_truth["test_secret"] = secret
    store = SaveStore(tmp_path)
    session = GameSession(state, store, DeterministicProvider(), "session_computer")
    store.initialize(state, session.id)
    connection = session.join("Solo", state.characters[0].id, StationRole.INTEGRATED)
    await session.command(connection.token, {
        "client_sequence": 1,
        "command_type": "ask_computer",
        "parameters": {"question": "What is this system?"},
    })
    assert secret not in state.message_log[-1]["message"]


class FailingProvider(AIProvider):
    async def health(self) -> bool:
        return False

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities("offline", True, 100, 1)

    async def generate(self, task: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("provider unavailable")


class SignalResponseProvider(AIProvider):
    def __init__(self) -> None:
        self.tasks: list[dict[str, Any]] = []

    async def health(self) -> bool:
        return True

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities("signal-response-spy", True, 1_000, 1)

    async def generate(self, task: dict[str, Any]) -> dict[str, Any]:
        self.tasks.append(task)
        return {"message": "Your peaceful survey declaration is understood. Provide your point of origin.", "tone": "curious"}


class DirectorBeatProvider(AIProvider):
    async def health(self) -> bool:
        return True

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities("director-beat-spy", True, 1_000, 1)

    async def generate(self, task: dict[str, Any]) -> dict[str, Any]:
        if task["task_type"] == "director_milestone":
            assert "hidden_truth" not in str(task["encounter"])
            return {
                "action": "director_beat",
                "beat_type": "opportunity",
                "public_cue": "The completed scan leaves several viable responses.",
                "pressure_delta": -.1,
                "novelty_cost": .1,
                "deadline_delta_s": 15,
                "next_decision": "Communicate, approach, investigate further, or leave.",
            }
        return {"answer": "No response."}


@pytest.mark.asyncio
async def test_tuned_signal_reply_uses_ai_provider_and_persists_response(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Frequency Contact", seed=17, ship_name="Receiver", crew_capacity=1, character_name="Operator", backstory="", scenario_preset="friendly_contact_test"
    )
    encounter = state.current_encounter
    assert encounter is not None
    frequency = encounter.hidden_truth["signal_recipe"]["center_frequency_mhz"]
    provider = SignalResponseProvider()
    store = SaveStore(tmp_path)
    session = GameSession(state, store, provider, "session_frequency_contact")
    store.initialize(state, session.id)
    connection = session.join("Operator", state.characters[0].id, StationRole.INTEGRATED)
    await session.command(connection.token, {
        "client_sequence": 1,
        "command_type": "acquire_signal",
        "parameters": {"frequency_mhz": frequency},
    })
    assert state.signal_analysis is not None
    state.signal_analysis.demodulation_method = "amplitude"
    state.signal_analysis.demodulation_confidence = .9
    state.signal_analysis.interpretation = "Identify yourself and state your purpose."
    state.signal_analysis.interpretation_confidence = .9

    events = await session.command(connection.token, {
        "client_sequence": 2,
        "command_type": "send_signal_reply",
        "parameters": {"frequency_mhz": frequency, "message": "We are peaceful surveyors from an independent vessel."},
    })

    assert provider.tasks[0]["task_type"] == "signal_contact_response"
    assert "hidden_truth" not in str(provider.tasks[0])
    assert events[1].event_type == "signal_contact_response_received"
    assert events[1].source_kind == "approved_proposal"
    assert events[1].payload["translated_response"].startswith("Your peaceful survey")
    loaded = store.load(state.universe_id)
    assert loaded.signal_analysis and "point of origin" in loaded.signal_analysis.reply_acknowledgment

    second_events = await session.command(connection.token, {
        "client_sequence": 3,
        "command_type": "send_signal_reply",
        "parameters": {"frequency_mhz": frequency, "message": "Our point of origin is the neighboring surveyed system."},
    })
    assert second_events[1].event_type == "signal_contact_response_received"
    assert len(provider.tasks) == 2
    assert any("peaceful survey declaration" in item for item in provider.tasks[1]["contact"]["known_messages"])


@pytest.mark.asyncio
async def test_communications_power_is_required_to_transmit(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Power Gate", seed=19, ship_name="Quiet", crew_capacity=1,
        character_name="Operator", backstory="", scenario_preset="friendly_contact_test",
    )
    assert state.current_encounter
    frequency = state.current_encounter.hidden_truth["signal_recipe"]["center_frequency_mhz"]
    state.ship.power.communications = .01
    store = SaveStore(tmp_path)
    session = GameSession(state, store, DeterministicProvider(), "session_power_gate")
    store.initialize(state, session.id)
    connection = session.join("Operator", state.characters[0].id, StationRole.INTEGRATED)
    with pytest.raises(ValueError, match="at least 3%"):
        await session.command(connection.token, {
            "client_sequence": 1,
            "command_type": "send_signal_reply",
            "parameters": {"frequency_mhz": frequency, "message": "Can you hear us?"},
        })


@pytest.mark.asyncio
async def test_provider_outage_uses_fallback_without_stopping_simulation(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Fallback Test", seed=3, ship_name="Resilient", crew_capacity=1, character_name="Solo", backstory=""
    )
    store = SaveStore(tmp_path)
    session = GameSession(state, store, FailingProvider(), "session_fallback")
    store.initialize(state, session.id)
    connection = session.join("Solo", state.characters[0].id, StationRole.INTEGRATED)
    before = state.universe_time_ms
    await session.command(connection.token, {
        "client_sequence": 1,
        "command_type": "ask_computer",
        "parameters": {"question": "What is our heat state?"},
    })
    await session.tick_once(.25)
    assert state.universe_time_ms > before
    assert state.message_log[-1]["speaker"] == "Ship Computer"
    assert session.ai.failures >= 2


@pytest.mark.asyncio
async def test_friendly_contact_actor_remembers_shares_moves_and_departs(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Actor Test", seed=44, ship_name="Listener", crew_capacity=1,
        character_name="Envoy", backstory="", scenario_preset="friendly_contact_test",
    )
    encounter = state.current_encounter
    assert encounter and encounter.npc and state.signal_analysis
    frequency = float(encounter.hidden_truth["signal_recipe"]["center_frequency_mhz"])
    store = SaveStore(tmp_path)
    session = GameSession(state, store, DeterministicProvider(), "session_actor_test")
    store.initialize(state, session.id)
    connection = session.join("Envoy", state.characters[0].id, StationRole.INTEGRATED)

    await session.command(connection.token, {
        "client_sequence": 1,
        "command_type": "send_signal_reply",
        "parameters": {"frequency_mhz": frequency, "message": "We are peaceful explorers and wish to exchange science."},
    })
    assert encounter.npc.last_action == "share_data"
    assert encounter.npc.memories
    assert encounter.npc.commitments[-1].startswith("We will maintain")
    assert any("independent survey" in item.lower() for item in state.crew_knowledge)
    projection = session.engine.station_projection(StationRole.COMMUNICATIONS)
    serialized = str(projection)
    assert "personality" not in serialized and "memories" not in serialized and "fears" not in serialized
    assert projection["encounter"]["npc"]["commitments"]

    before = session.engine._contact_projection(encounter)[0]["range_km"]
    await session.command(connection.token, {
        "client_sequence": 2,
        "command_type": "send_signal_reply",
        "parameters": {"frequency_mhz": frequency, "message": "Please come closer and meet us."},
    })
    after = session.engine._contact_projection(encounter)[0]["range_km"]
    assert encounter.npc.last_action == "approach"
    assert after < before

    await session.command(connection.token, {
        "client_sequence": 3,
        "command_type": "send_signal_reply",
        "parameters": {"frequency_mhz": frequency, "message": "Farewell. We are ending contact."},
    })
    assert encounter.status == "departed"
    assert session.engine._contact_projection(encounter) == []
    loaded = store.load(state.universe_id)
    assert loaded.current_encounter and loaded.current_encounter.npc
    assert len(loaded.current_encounter.npc.memories) == 3
    assert len(loaded.known_npcs[encounter.npc.id].memories) == 3
    assert (tmp_path / state.universe_id / "npcs" / f"{encounter.npc.id}.md").exists()


@pytest.mark.asyncio
async def test_director_reacts_once_to_meaningful_milestone(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Director Test", seed=12, ship_name="Surveyor", crew_capacity=1,
        character_name="Solo", backstory="",
    )
    assert state.current_encounter
    store = SaveStore(tmp_path)
    session = GameSession(state, store, DirectorBeatProvider(), "session_director_test")
    store.initialize(state, session.id)
    milestone = session.engine.event("scan_threshold_reached", payload={"threshold": 1.0}, targets=[state.current_encounter.target_id])
    before_pressure = state.director.narrative_pressure
    await session._develop_milestone(state.current_encounter.id, milestone, f"{state.current_encounter.id}:scan_threshold_reached")
    assert state.director.narrative_pressure < before_pressure
    assert state.director.unresolved_threads[-1].startswith("Communicate")
    assert session.last_events[-1].event_type == "director_beat_committed"
    assert session.last_events[-1].caused_by == [milestone.id]


def test_simulation_constrains_physically_unsafe_npc_proposal(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Validation Test", seed=45, ship_name="Observer", crew_capacity=1,
        character_name="Solo", backstory="", scenario_preset="friendly_contact_test",
    )
    encounter = state.current_encounter
    assert encounter and encounter.npc
    encounter.npc.disposition = -.9
    session = GameSession(state, SaveStore(tmp_path), DeterministicProvider(), "session_validation")
    events = session.engine.commit_npc_decision(
        encounter,
        {"actor_action": "approach", "disposition_delta": 0, "action_summary": "approaches", "reason": "generated", "memory": "attempt"},
        "proposal_invalid_approach",
        "come closer",
    )
    assert encounter.npc.last_action == "hold_position"
    assert events[0].event_type == "npc_proposal_constrained"
    assert events[1].payload["actor_action"] == "hold_position"


def test_six_players_can_hold_distinct_station_projections(tmp_path: Path) -> None:
    state = create_game_state(
        universe_name="Crew Test", seed=1, ship_name="Many Hands", crew_capacity=6, character_name="First", backstory=""
    )
    store = SaveStore(tmp_path)
    session = GameSession(state, store, DeterministicProvider(), "session_crew")
    store.initialize(state, session.id)
    roles = [StationRole.COMMAND, StationRole.FLIGHT, StationRole.ENGINEERING, StationRole.SCIENCE, StationRole.COMMUNICATIONS, StationRole.TACTICAL]
    connections = [session.join(f"Crew {index}", state.characters[0].id, role) for index, role in enumerate(roles)]
    assert len({connection.token for connection in connections}) == 6
    assert {session.engine.station_projection(connection.station)["station"] for connection in connections} == set(roles)


@pytest.mark.asyncio
async def test_salvage_installation_survives_reload(tmp_path: Path) -> None:
    state = None
    for seed in range(100):
        candidate = create_game_state(
            universe_name="Salvage Test", seed=seed, ship_name="Builder", crew_capacity=1, character_name="Engineer", backstory=""
        )
        if candidate.current_encounter and candidate.current_encounter.salvage:
            state = candidate
            break
    assert state and state.current_encounter and state.current_encounter.salvage
    state.current_encounter.status = "resolved"
    store = SaveStore(tmp_path)
    session = GameSession(state, store, DeterministicProvider(), "session_salvage")
    store.initialize(state, session.id)
    connection = session.join("Engineer", state.characters[0].id, StationRole.INTEGRATED)
    await session.command(connection.token, {"client_sequence": 1, "command_type": "claim_salvage", "parameters": {}})
    cargo_id = state.ship.cargo[0].id
    await session.command(connection.token, {"client_sequence": 2, "command_type": "install_cargo", "parameters": {"cargo_id": cargo_id}})
    loaded = store.load(state.universe_id)
    assert any(capability.name == "Coherent Field Sampler" for capability in loaded.ship.capabilities)
