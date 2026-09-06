from pathlib import Path

import pytest

from space_sim_crew.ai import DeterministicProvider
from space_sim_crew.models import PlayerCommand, StationRole
from space_sim_crew.persistence import SaveStore
from space_sim_crew.session import GameSession, create_game_state
from space_sim_crew.simulation import CommandError, SimulationEngine


class OfflineProvider(DeterministicProvider):
    async def generate(self, task):
        raise ValueError("offline during playtest")


def state():
    return create_game_state(universe_name="Regression", seed=55, ship_name="Test", crew_capacity=1, character_name="Solo", backstory="", scenario_preset="friendly_contact_test")


def command(s, kind, **parameters):
    return PlayerCommand(session_id="test", player_id="solo", character_id=s.characters[0].id, station=StationRole.INTEGRATED, client_sequence=1, command_type=kind, parameters=parameters)


def travel(s, engine, kind="begin_transit"):
    parameters = {"coordinate": [1, 0]} if kind == "begin_transit" else {}
    engine.apply_command(command(s, kind, **parameters))
    for _ in range(60):
        engine.tick(.25)
        if not s.ship.transit_target:
            break


@pytest.mark.parametrize("kind", ["begin_transit", "emergency_warp"])
def test_departure_clears_scan_and_cannot_complete_new_target(kind):
    s = state()
    e = SimulationEngine(s)
    e.apply_command(command(s, "start_scan", target_id=s.current_encounter.target_id))
    for _ in range(240):
        e.tick(.25)
    assert s.ship.scan_progress > .75
    travel(s, e, kind)
    assert s.ship.scan_progress == 0
    assert s.ship.active_scan_target is None
    assert s.ship.active_scan_instrument is None
    thread = s.world_threads[-1]
    assert not e.station_projection(StationRole.INTEGRATED)["objectives"]["primary"]["ready"]
    with pytest.raises(CommandError, match="75%"):
        e.apply_command(command(s, "pursue_thread", thread_id=thread.id, action=thread.next_actions[0]))


def test_investigation_needs_local_observations_and_finite_consequence():
    s = state()
    e = SimulationEngine(s)
    travel(s, e)
    thread = s.world_threads[-1]
    target = s.current_encounter.target_id
    other = next(body.id for body in s.systems[s.ship.system_id].bodies if body.id != target)
    e.apply_command(command(s, "start_scan", target_id=other))
    s.ship.scan_progress = 1
    with pytest.raises(CommandError, match="75%"):
        e.apply_command(command(s, "pursue_thread", thread_id=thread.id, action=thread.next_actions[0]))
    e.apply_command(command(s, "start_scan", target_id=target))
    for _ in range(250):
        e.tick(.25)
    assert thread.stage == 2
    with pytest.raises(CommandError, match="describe"):
        e.apply_command(command(s, "pursue_thread", thread_id=thread.id, action=thread.next_actions[0]))
    with pytest.raises(CommandError, match="select Science"):
        e.apply_command(command(s, "pursue_thread", thread_id=thread.id, action=thread.next_actions[0], note="Unsupported claim", observation_ids=["invented"]))
    evidence = [obs.id for obs in s.observations if obs.target == target and obs.station == StationRole.SCIENCE]
    events = e.apply_command(command(s, "pursue_thread", thread_id=thread.id, action=thread.next_actions[0], note="Material observations recorded; origin uncertain.", observation_ids=evidence))
    assert s.current_encounter.status == "resolved"
    assert "Material observations" in events[0].payload["evidence"]
    consequence = s.world_threads[-1]
    count = len(s.world_threads)
    events = e.apply_command(command(s, "choose_consequence", thread_id=consequence.id, choice="archive"))
    assert events[0].visibility == "crew"
    assert consequence.status == "resolved"
    assert len(s.world_threads) == count
    with pytest.raises(CommandError):
        e.apply_command(command(s, "choose_consequence", thread_id=consequence.id, choice="publish"))


def test_legacy_scan_cleanup_and_hostile_contact_cannot_claim_accord():
    s = state()
    e = SimulationEngine(s)
    s.ship.active_scan_target = "target-from-a-previous-system"
    s.ship.scan_progress = 1
    assert any(event.event_type == "stale_scan_cleared" for event in e.migrate_loaded_state())
    assert s.ship.scan_progress == 0
    s.current_encounter.npc.known_messages.append("Crew: We identify our vessel.")
    s.current_encounter.phase = "hostile"
    with pytest.raises(CommandError, match="not ready"):
        e.apply_command(command(s, "resolve_encounter", method="diplomacy"))
    thread = s.world_threads[0]
    with pytest.raises(CommandError, match="Communications"):
        e.apply_command(command(s, "pursue_thread", thread_id=thread.id, action=thread.next_actions[0]))


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_type", [DeterministicProvider, OfflineProvider])
async def test_contact_objectives_and_remote_reply_persist(tmp_path: Path, provider_type):
    s = state()
    store = SaveStore(tmp_path)
    session = GameSession(s, store, provider_type())
    store.initialize(s, session.id)
    conn = session.join("Solo", s.characters[0].id, StationRole.INTEGRATED)
    thread = s.world_threads[0]
    frequency = session.engine.station_projection(StationRole.INTEGRATED)["ship"]["detected_signal_frequency_mhz"]
    await session.command(conn.token, {"client_sequence": 1, "command_type": "send_signal_reply", "parameters": {"message": "We are peaceful explorers.", "frequency_mhz": frequency}})
    assert thread.stage == 1
    assert "Identify your vessel" not in thread.next_actions
    with pytest.raises(CommandError, match="Communications"):
        session.engine.apply_command(command(s, "pursue_thread", thread_id=thread.id, action=thread.next_actions[0]))
    travel(s, session.engine)
    channels = session.engine.station_projection(StationRole.COMMUNICATIONS)["remote_channels"]
    assert channels[0]["frequency_mhz"] == frequency
    assert session.engine.station_projection(StationRole.SCIENCE)["remote_channels"] == []
    before = s.current_encounter.model_dump()
    await session.command(conn.token, {"client_sequence": 2, "command_type": "reply_remote_contact", "parameters": {"thread_id": thread.id, "frequency_mhz": frequency, "message": "Please come closer. We have reached the next system safely."}})
    assert s.current_encounter.model_dump() == before
    loaded = store.load(s.universe_id)
    assert loaded.world_threads[0].status == "resolved"
    assert "remote" in loaded.message_log[-1]["speaker"]
    assert loaded.known_npcs[thread.npc_id].known_messages[-1]
    with pytest.raises(CommandError, match="frequency"):
        await session.command(conn.token, {"client_sequence": 3, "command_type": "reply_remote_contact", "parameters": {"thread_id": thread.id, "frequency_mhz": float("nan"), "message": "Test"}})
    await session.stop()
