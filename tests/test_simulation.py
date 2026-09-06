import math

import pytest

from space_sim_crew.models import PlayerCommand, StationRole
from space_sim_crew.session import create_game_state
from space_sim_crew.simulation import CommandError, SimulationEngine
from space_sim_crew.signal_processing import default_signal_recipe, validate_signal_recipe


def command(state, role: StationRole, command_type: str, **parameters):
    return PlayerCommand(
        session_id="session_test",
        player_id="player_test",
        character_id=state.characters[0].id,
        station=role,
        client_sequence=1,
        command_type=command_type,
        parameters=parameters,
    )


@pytest.fixture
def engine() -> SimulationEngine:
    state = create_game_state(
        universe_name="Test Reach",
        seed=99,
        ship_name="Test Vessel",
        crew_capacity=6,
        character_name="Tester",
        backstory="Test operator.",
    )
    return SimulationEngine(state)


def test_role_authorization_and_power_limit(engine: SimulationEngine) -> None:
    with pytest.raises(CommandError, match="not authorized"):
        engine.apply_command(command(engine.state, StationRole.SCIENCE, "set_power", sensors=.3))
    with pytest.raises(CommandError, match="cannot exceed"):
        engine.apply_command(
            command(
                engine.state,
                StationRole.ENGINEERING,
                "set_power",
                propulsion=.5,
                sensors=.5,
                communications=.5,
            )
        )


def test_flight_power_changes_acceleration(engine: SimulationEngine) -> None:
    engine.apply_command(command(engine.state, StationRole.FLIGHT, "set_flight", heading_deg=90, throttle=1))
    for _ in range(20):
        engine.tick(.05)
    low_power_velocity = engine.state.ship.velocity_km_s

    high = create_game_state(
        universe_name="Test", seed=99, ship_name="Fast", crew_capacity=1, character_name="Tester", backstory=""
    )
    high_engine = SimulationEngine(high)
    high_engine.apply_command(command(high, StationRole.INTEGRATED, "set_power", propulsion=.45, sensors=.05, communications=.05, shields=.1, weapons=.05, cooling=.3))
    high_engine.apply_command(command(high, StationRole.INTEGRATED, "set_flight", heading_deg=90, throttle=1))
    for _ in range(20):
        high_engine.tick(.05)
    assert high.ship.velocity_km_s > low_power_velocity


def test_sensor_power_changes_scan_rate() -> None:
    states = [
        create_game_state(universe_name="Low", seed=88, ship_name="Low", crew_capacity=1, character_name="A", backstory=""),
        create_game_state(universe_name="High", seed=88, ship_name="High", crew_capacity=1, character_name="B", backstory=""),
    ]
    engines = [SimulationEngine(state) for state in states]
    allocations = [
        {"propulsion": .2, "sensors": .05, "communications": .1, "shields": .2, "weapons": .05, "cooling": .2},
        {"propulsion": .1, "sensors": .4, "communications": .05, "shields": .1, "weapons": .05, "cooling": .2},
    ]
    for state, simulation, power in zip(states, engines, allocations, strict=True):
        assert state.current_encounter
        simulation.apply_command(command(state, StationRole.INTEGRATED, "set_power", **power))
        simulation.apply_command(command(state, StationRole.INTEGRATED, "start_scan", target_id=state.current_encounter.target_id))
        for _ in range(100):
            simulation.tick(.05)
    assert states[1].ship.scan_progress > states[0].ship.scan_progress * 4


def test_weapon_power_controls_charge_rate_and_firing_minimum() -> None:
    low = create_game_state(universe_name="Low Weapons", seed=8, ship_name="Low", crew_capacity=1, character_name="A", backstory="", scenario_preset="friendly_contact_test")
    high = low.model_copy(deep=True)
    low_engine = SimulationEngine(low)
    high_engine = SimulationEngine(high)
    low_engine.apply_command(command(low, StationRole.INTEGRATED, "set_power", propulsion=.2, sensors=.2, communications=.1, shields=.2, weapons=.01, cooling=.2))
    high_engine.apply_command(command(high, StationRole.INTEGRATED, "set_power", propulsion=.1, sensors=.15, communications=.05, shields=.1, weapons=.4, cooling=.2))
    for _ in range(200):
        low_engine.tick(.05)
        high_engine.tick(.05)
    assert low.ship.weapon_charge == 0
    assert high.ship.weapon_charge > .9
    with pytest.raises(CommandError, match="at least 4%"):
        low_engine.apply_command(command(low, StationRole.INTEGRATED, "fire_weapon", mode="warning"))


def test_direct_fire_requires_authorization_and_changes_contact_state() -> None:
    state = create_game_state(universe_name="Weapons", seed=18, ship_name="Armed", crew_capacity=1, character_name="A", backstory="", scenario_preset="friendly_contact_test")
    simulation = SimulationEngine(state)
    assert state.current_encounter and state.current_encounter.npc
    state.ship.weapon_charge = 1
    with pytest.raises(CommandError, match="authorize"):
        simulation.apply_command(command(state, StationRole.TACTICAL, "fire_weapon", mode="precision"))
    simulation.apply_command(command(state, StationRole.COMMAND, "set_weapons_authorization", authorized=True))
    before_shields = state.current_encounter.target_shields
    before_heat = state.ship.heat
    events = simulation.apply_command(command(state, StationRole.TACTICAL, "fire_weapon", mode="precision"))
    assert events[0].event_type == "weapon_fired"
    assert events[0].payload["impact_quality"] in {"direct", "glancing"}
    assert state.current_encounter.target_shields < before_shields
    assert state.current_encounter.phase == "hostile"
    assert state.current_encounter.deadline_kind == "patrol_escalates"
    assert state.ship.heat > before_heat
    assert state.ship.weapon_cooldown_s == 3
    assert state.current_encounter.npc.relationship_label == "hostile contact"


def test_weapon_power_changes_damage_and_cooling_changes_recovery() -> None:
    base = create_game_state(universe_name="Power Combat", seed=21, ship_name="Control", crew_capacity=1, character_name="A", backstory="", scenario_preset="friendly_contact_test")
    low = base.model_copy(deep=True)
    high = base.model_copy(deep=True)
    engines = [SimulationEngine(low), SimulationEngine(high)]
    allocations = [
        {"propulsion": .2, "sensors": .3, "communications": .05, "shields": .15, "weapons": .05, "cooling": .2},
        {"propulsion": .1, "sensors": .3, "communications": .05, "shields": .05, "weapons": .3, "cooling": .2},
    ]
    damages = []
    for state, simulation, allocation in zip((low, high), engines, allocations, strict=True):
        simulation.apply_command(command(state, StationRole.INTEGRATED, "set_power", **allocation))
        simulation.apply_command(command(state, StationRole.INTEGRATED, "set_weapons_authorization", authorized=True))
        state.ship.weapon_charge = 1
        event = simulation.apply_command(command(state, StationRole.INTEGRATED, "fire_weapon", mode="full"))[0]
        damages.append(event.payload["damage"])
    assert damages[1] > damages[0]

    low.ship.weapon_cooldown_s = high.ship.weapon_cooldown_s = 5
    low.ship.power.cooling = .05
    high.ship.power.cooling = .35
    low.ship.power.weapons = high.ship.power.weapons = 0
    for simulation in engines:
        simulation.tick(1)
    assert high.ship.weapon_cooldown_s < low.ship.weapon_cooldown_s


def test_kinetic_weapon_consumes_ammunition_and_can_disable_target() -> None:
    state = create_game_state(universe_name="Kinetic", seed=31, ship_name="Interceptor", crew_capacity=1, character_name="A", backstory="", scenario_preset="friendly_contact_test")
    simulation = SimulationEngine(state)
    assert state.current_encounter
    state.current_encounter.hidden_truth["source_position_km"] = [20_000, 0]
    state.current_encounter.target_shields = 0
    state.current_encounter.target_hull = .15
    state.ship.power.weapons = .3
    state.ship.power.sensors = .35
    state.ship.weapon_charge = 1
    simulation.apply_command(command(state, StationRole.INTEGRATED, "configure_weapon", weapon="kinetic_interceptor"))
    simulation.apply_command(command(state, StationRole.INTEGRATED, "set_weapons_authorization", authorized=True))
    ammunition = state.ship.kinetic_ammunition
    event = simulation.apply_command(command(state, StationRole.INTEGRATED, "fire_weapon", mode="full"))[0]
    assert state.ship.kinetic_ammunition == ammunition - 1
    assert event.payload["time_of_flight_s"] > 0
    assert state.current_encounter.status == "resolved"
    assert state.current_encounter.phase == "disabled"


def test_engineering_projection_explains_cross_system_power_effects() -> None:
    state = create_game_state(universe_name="Power Readout", seed=3, ship_name="Grid", crew_capacity=1, character_name="A", backstory="")
    simulation = SimulationEngine(state)
    projection = simulation.station_projection(StationRole.ENGINEERING)
    effects = projection["engineering_effects"]
    assert effects["communications"]["transmitter_ready"]
    assert effects["weapons"]["charge_rate_pct_s"] > 0
    assert effects["shields"]["target_strength"] == 1
    assert effects["cooling"]["weapon_cooldown_rate"] > 0
    assert projection["weapon_control"] is not None


def test_one_cause_creates_three_station_observations(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    engine.apply_command(command(engine.state, StationRole.SCIENCE, "start_scan", target_id=encounter.target_id))
    for _ in range(2_000):
        engine.tick(.05)
        if engine.state.ship.scan_progress >= .5:
            break
    stations = {observation.station for observation in engine.state.observations}
    assert StationRole.SCIENCE in stations
    assert StationRole.ENGINEERING in stations
    assert StationRole.FLIGHT in stations
    science = engine.station_projection(StationRole.SCIENCE)
    engineering = engine.station_projection(StationRole.ENGINEERING)
    assert science["observations"]
    assert engineering["observations"]
    assert "hidden_truth" not in str(science)


def test_science_instruments_are_selectable_and_produce_distinct_readings(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    instruments = {capability.name: capability for capability in engine.state.ship.capabilities}
    particle = instruments["Radiation Hazard Scan"]
    engine.apply_command(
        command(
            engine.state,
            StationRole.SCIENCE,
            "start_scan",
            target_id=encounter.target_id,
            instrument_id=particle.id,
        )
    )
    for _ in range(1_000):
        engine.tick(.05)
        if engine.state.ship.scan_progress >= .21:
            break
    science = [observation for observation in engine.state.observations if observation.station == StationRole.SCIENCE]
    assert engine.state.ship.active_scan_instrument == particle.id
    assert any(observation.measurement == "radiation variation" for observation in science)


def test_vessel_systems_scan_requires_vessel_and_reports_weapon_likelihood() -> None:
    state = None
    for seed in range(200):
        candidate = create_game_state(universe_name="Vessel Scan", seed=seed, ship_name="Observer", crew_capacity=1, character_name="A", backstory="")
        if candidate.current_encounter and candidate.current_encounter.npc:
            state = candidate
            break
    assert state is not None and state.current_encounter is not None
    simulation = SimulationEngine(state)
    instrument = next(capability for capability in state.ship.capabilities if capability.name == "Vessel Systems and Weapons Scan")
    simulation.apply_command(command(state, StationRole.SCIENCE, "start_scan", target_id=state.current_encounter.target_id, instrument_id=instrument.id))
    for _ in range(3_000):
        simulation.tick(.05)
        if state.ship.scan_progress >= .76:
            break
    readings = [observation.measurement for observation in state.observations if observation.station == StationRole.SCIENCE]
    assert "vessel radar profile confidence" in readings
    assert "active power and propulsion confidence" in readings
    assert "weapon system likelihood" in readings

    non_vessel = next(body for body in state.systems[state.ship.system_id].bodies if body.id != state.current_encounter.target_id)
    with pytest.raises(CommandError, match="detected vessel"):
        simulation.apply_command(command(state, StationRole.SCIENCE, "start_scan", target_id=non_vessel.id, instrument_id=instrument.id))


def test_scan_rejects_uninstalled_instrument(engine: SimulationEngine) -> None:
    assert engine.state.current_encounter
    with pytest.raises(CommandError, match="not installed"):
        engine.apply_command(
            command(
                engine.state,
                StationRole.SCIENCE,
                "start_scan",
                target_id=engine.state.current_encounter.target_id,
                instrument_id="cap_not_installed",
            )
        )


def test_ship_movement_creates_localization_baseline_without_revealing_truth(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    instrument = next(capability for capability in engine.state.ship.capabilities if capability.name == "Signal Direction Scan")
    engine.apply_command(command(engine.state, StationRole.SCIENCE, "start_scan", target_id=encounter.target_id, instrument_id=instrument.id))
    for _ in range(1_000):
        engine.tick(.05)
        if len(engine.state.bearing_measurements) == 1:
            break
    first = engine.state.bearing_measurements[0]
    perpendicular = math.radians(first.bearing_deg + 90)
    engine.state.ship.x_km += math.cos(perpendicular) * 6_000
    engine.state.ship.y_km += math.sin(perpendicular) * 6_000
    engine.apply_command(command(engine.state, StationRole.SCIENCE, "start_scan", target_id=encounter.target_id, instrument_id=instrument.id))
    for _ in range(1_000):
        engine.tick(.05)
        if len(engine.state.bearing_measurements) == 2:
            break
    projection = engine.station_projection(StationRole.SCIENCE)
    localization = projection["localization"]
    assert localization["baseline_km"] >= 5_999
    assert localization["estimated_x_km"] is not None
    assert localization["intercept_heading_deg"] is not None
    assert "source_position_km" not in str(projection)


def test_signal_dataset_requires_communications_science_handoff(engine: SimulationEngine) -> None:
    state = engine.state
    assert state.current_encounter
    state.current_encounter.family = "artificial_signal"
    state.current_encounter.hidden_truth["signal_recipe"] = default_signal_recipe(state.seed, "artificial_signal")
    frequency = validate_signal_recipe(state.current_encounter.hidden_truth.get("signal_recipe"), state.seed, "artificial_signal")["center_frequency_mhz"]
    events = engine.apply_command(command(state, StationRole.COMMUNICATIONS, "acquire_signal"))
    assert events[0].event_type == "signal_acquired"
    assert state.signal_analysis and state.signal_analysis.tuned_frequency_mhz == frequency
    communications = engine.station_projection(StationRole.COMMUNICATIONS)["signal_lab"]
    science = engine.station_projection(StationRole.SCIENCE)["signal_lab"]
    assert communications["access"] == "granted"
    assert communications["spectrogram"]["frames"]
    assert len(communications["pca"]["eigenvalues"]) == 4
    assert science["access"] == "awaiting_share"
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "test_signal_structure"))
    assert state.signal_analysis and state.signal_analysis.structure_result == "structured_but_contaminated"
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "configure_pca", cutoff=1, selected_side="high_variance"))
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "test_signal_structure"))
    assert state.signal_analysis.structure_result == "inconclusive"
    with pytest.raises(CommandError, match="route the dataset"):
        engine.apply_command(command(state, StationRole.SCIENCE, "configure_dmaps", epsilon=1.2))
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "configure_pca", cutoff=1, selected_side="low_variance"))
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "test_signal_structure"))
    assert state.signal_analysis.structure_result == "structured_carrier"
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "share_signal_with_science"))
    engine.apply_command(command(state, StationRole.SCIENCE, "configure_dmaps", epsilon=.8, diffusion_time=2, neighbors=6))
    engine.apply_command(command(state, StationRole.SCIENCE, "classify_signal", classification="natural_contamination", note="A curved low-frequency component dominates."))
    science = engine.station_projection(StationRole.SCIENCE)["signal_lab"]
    communications = engine.station_projection(StationRole.COMMUNICATIONS)["signal_lab"]
    assert science["dmaps"]["embedding"]
    assert science["analysis"]["dmaps_diffusion_time"] == 2
    assert communications["analysis"]["science_classification"] == "natural_contamination"
    assert "signal_recipe" not in str(communications)


def test_pca_can_return_to_raw_recording_and_invalidates_derived_results(engine: SimulationEngine) -> None:
    state = engine.state
    assert state.current_encounter
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "acquire_signal"))
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "configure_pca", cutoff=1, selected_side="low_variance"))
    engine.apply_command(command(state, StationRole.COMMUNICATIONS, "test_signal_structure"))
    assert state.signal_analysis and state.signal_analysis.pca_configured
    events = engine.apply_command(command(state, StationRole.COMMUNICATIONS, "reset_pca"))
    assert events[0].event_type == "signal_processing_reset_to_raw"
    assert state.signal_analysis.pca_configured is False
    assert state.signal_analysis.structure_result is None
    assert state.signal_analysis.demodulation_method is None
    assert state.signal_analysis.acquired is True
    assert state.signal_analysis.processing_log[-1]["operation"] == "returned to raw recording"


def test_signal_processing_controls_are_role_restricted(engine: SimulationEngine) -> None:
    with pytest.raises(CommandError, match="not authorized"):
        engine.apply_command(command(engine.state, StationRole.SCIENCE, "acquire_signal"))
    assert engine.state.current_encounter
    frequency = validate_signal_recipe(engine.state.current_encounter.hidden_truth.get("signal_recipe"), engine.state.seed, engine.state.current_encounter.family)["center_frequency_mhz"]
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "acquire_signal", frequency_mhz=frequency))
    with pytest.raises(CommandError, match="not authorized"):
        engine.apply_command(command(engine.state, StationRole.SCIENCE, "configure_pca", cutoff=1, selected_side="low_variance"))


def test_artificial_signal_cannot_bypass_analysis_or_reveal_hidden_source(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    encounter.family = "artificial_signal"
    encounter.hidden_truth["source"] = "SECRET ANSWER THAT MUST NOT BE REVEALED"
    encounter.hidden_truth["source_position_km"] = [80_000.0, 0.0]
    frequency = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), engine.state.seed, encounter.family)["center_frequency_mhz"]
    instrument = next(capability for capability in engine.state.ship.capabilities if capability.name == "Signal Direction Scan")
    engine.apply_command(command(engine.state, StationRole.SCIENCE, "start_scan", target_id=encounter.target_id, instrument_id=instrument.id))
    for _ in range(1_000):
        engine.tick(.05)
        if len(engine.state.bearing_measurements) == 1:
            break
    engine.state.ship.y_km = 6_000
    engine.apply_command(command(engine.state, StationRole.SCIENCE, "start_scan", target_id=encounter.target_id, instrument_id=instrument.id))
    for _ in range(1_000):
        engine.tick(.05)
        if len(engine.state.bearing_measurements) == 2:
            break
    engine.state.ship.scan_progress = .8
    with pytest.raises(CommandError, match="requires Communications acquisition"):
        engine.apply_command(command(engine.state, StationRole.SCIENCE, "resolve_encounter", method="investigation"))
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "acquire_signal", frequency_mhz=frequency))
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "test_signal_structure"))
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "configure_pca", cutoff=1, selected_side="low_variance"))
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "test_signal_structure"))
    recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), engine.state.seed, encounter.family)
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "attempt_demodulation", method=recipe["modulation"]))
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "interpret_signal"))
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "send_signal_reply", frequency_mhz=frequency, message="Translation received. Peaceful contact requested."))
    events = engine.apply_command(command(engine.state, StationRole.SCIENCE, "resolve_encounter", method="investigation"))
    assert events[0].payload["finding"]
    assert "SECRET ANSWER" not in events[0].payload["finding"]
    assert "ultimate origin remain unresolved" in events[0].payload["finding"]


def test_signal_deadline_records_failed_contact_and_retains_recording(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    encounter.family = "artificial_signal"
    encounter.deadline_kind = "signal_fades"
    encounter.deadline_s = .01
    encounter.hidden_truth["signal_recipe"] = default_signal_recipe(engine.state.seed, "artificial_signal")
    frequency = encounter.hidden_truth["signal_recipe"]["center_frequency_mhz"]
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "acquire_signal", frequency_mhz=frequency))

    events = engine.tick(.05)

    assert events[-1].event_type == "signal_faded"
    assert events[-1].payload["reason"] == "carrier faded before a translated reply established contact"
    assert events[-1].payload["signal_recorded"] is True
    assert encounter.status == "departed"
    assert encounter.phase == "signal_lost"
    assert "contact failed" in (encounter.outcome or "")
    projection = engine.station_projection(StationRole.INTEGRATED)
    assert projection["signal_lab"]["live"] is False
    assert projection["workflow"]["result"].startswith("SIGNAL LOST")
    assert any("no contact was established" in message["message"].lower() for message in projection["messages"])
    assert any("CONTACT LOST" in alert["message"] for alert in projection["alerts"])
    assert projection["signal_lab"]["access"] == "archived"
    assert "channels" not in projection["signal_lab"]

    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "open_signal_recording"))
    assert engine.station_projection(StationRole.COMMUNICATIONS)["signal_lab"]["access"] == "granted"
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "clear_signal_workspace"))
    cleared = engine.station_projection(StationRole.COMMUNICATIONS)["signal_lab"]
    assert cleared["access"] == "archived"
    assert "pca" not in cleared

    # The recorded data remains analyzable, but no live reply can be sent.
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "test_signal_structure"))
    with pytest.raises(CommandError, match="not active"):
        engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "send_signal_reply", frequency_mhz=frequency, message="Too late"))


def test_legacy_active_signal_loss_is_migrated_once(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    encounter.family = "artificial_signal"
    encounter.phase = "signal_lost"
    encounter.status = "active"
    encounter.deadline_s = None

    events = engine.migrate_loaded_state()

    assert [event.event_type for event in events] == ["legacy_signal_loss_outcome_repaired"]
    assert encounter.status == "departed"
    assert engine.migrate_loaded_state() == []


def test_legacy_instrument_names_are_migrated_to_scan_purposes(engine: SimulationEngine) -> None:
    replacements = {
        "Composition and Temperature Scan": "Multispectral Array",
        "Radiation Hazard Scan": "Particle Flux Detector",
        "Signal Direction Scan": "Field Interferometer",
        "Universal Translator": "Adaptive Interpretation Array",
    }
    engine.state.ship.capabilities = [
        capability for capability in engine.state.ship.capabilities if capability.name != "Vessel Systems and Weapons Scan"
    ]
    for capability in engine.state.ship.capabilities:
        capability.name = replacements.get(capability.name, capability.name)

    events = engine.migrate_loaded_state()

    names = {capability.name for capability in engine.state.ship.capabilities}
    assert {"Composition and Temperature Scan", "Radiation Hazard Scan", "Signal Direction Scan", "Universal Translator", "Vessel Systems and Weapons Scan"} <= names
    assert any(event.event_type == "science_scan_labels_migrated" for event in events)


def test_translated_reply_establishes_contact_and_stops_signal_deadline(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    encounter.family = "artificial_signal"
    encounter.deadline_kind = "signal_fades"
    encounter.deadline_s = 1
    encounter.hidden_truth["signal_recipe"] = default_signal_recipe(engine.state.seed, "artificial_signal")
    frequency = encounter.hidden_truth["signal_recipe"]["center_frequency_mhz"]
    engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "acquire_signal", frequency_mhz=frequency))
    assert engine.state.signal_analysis is not None
    engine.state.signal_analysis.demodulation_method = "phase_shift"
    engine.state.signal_analysis.demodulation_confidence = .9
    engine.state.signal_analysis.interpretation = "A translated test message"
    engine.state.signal_analysis.interpretation_confidence = .9

    events = engine.apply_command(command(engine.state, StationRole.COMMUNICATIONS, "send_signal_reply", frequency_mhz=frequency, message="We receive you."))

    assert events[0].payload["contact_established"] is True
    assert encounter.phase == "contact_established"
    assert encounter.deadline_s is None
    assert not any(event.event_type == "signal_faded" for event in engine.tick(.25))


def test_detected_contact_signal_is_acquired_automatically(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    encounter.family = "artificial_signal"
    encounter.hidden_truth["signal_recipe"] = default_signal_recipe(engine.state.seed, "artificial_signal")
    engine.state.signal_analysis = None

    events = engine.auto_acquire_detected_signal()

    assert [event.event_type for event in events] == ["signal_automatically_acquired"]
    assert engine.state.signal_analysis and engine.state.signal_analysis.acquired
    projection = engine.station_projection(StationRole.COMMUNICATIONS)
    assert projection["signal_lab"]["access"] == "granted"
    assert projection["ship"]["detected_signal_frequency_mhz"] == events[0].payload["center_frequency_mhz"]
    assert engine.auto_acquire_detected_signal() == []


def test_radar_projects_vessel_contact_on_map() -> None:
    state = None
    for seed in range(200):
        candidate = create_game_state(universe_name="Radar", seed=seed, ship_name="Tracker", crew_capacity=1, character_name="A", backstory="")
        if candidate.current_encounter and candidate.current_encounter.npc:
            state = candidate
            break
    assert state is not None
    projection = SimulationEngine(state).station_projection(StationRole.INTEGRATED)
    assert len(projection["contacts"]) == 1
    assert projection["contacts"][0]["kind"] == "vessel"
    assert projection["contacts"][0]["range_km"] > 0
    assert 0 <= projection["contacts"][0]["bearing_deg"] < 360


def test_emergency_warp_closes_encounter_and_adds_heat(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    start_heat = engine.state.ship.heat
    engine.state.ship.defensive_posture = True

    events = engine.apply_command(command(engine.state, StationRole.FLIGHT, "emergency_warp"))

    assert events[0].event_type == "emergency_warp_initiated"
    assert encounter.status == "departed"
    assert encounter.outcome == "crew escaped by emergency warp"
    assert engine.state.ship.transit_mode == "emergency_warp"
    assert engine.state.ship.transit_remaining_s == 3
    assert engine.state.ship.heat == pytest.approx(start_heat + .18)
    assert engine.state.ship.defensive_posture is False


def test_friendly_contact_preset_starts_ready_for_conversation() -> None:
    state = create_game_state(
        universe_name="Conversation Test",
        seed=404,
        ship_name="Greeter",
        crew_capacity=1,
        character_name="Operator",
        backstory="",
        scenario_preset="friendly_contact_test",
    )
    encounter = state.current_encounter
    assert encounter is not None and encounter.npc is not None
    assert encounter.title == "Friendly Contact Test"
    assert encounter.npc.disposition > .5
    assert encounter.deadline_s == 7_200
    assert state.signal_analysis and state.signal_analysis.acquired
    assert state.signal_analysis.translation_status == "translated"
    assert state.signal_analysis.interpretation_confidence >= .9
    projection = SimulationEngine(state).station_projection(StationRole.INTEGRATED)
    assert projection["contacts"][0]["label"] == "Independent Survey Vessel"
    assert projection["workflow"]["title"] == "Friendly contact conversation test"
    assert projection["ship"]["detected_signal_frequency_mhz"] is not None


def test_transit_generates_neighbor_and_endless_route(engine: SimulationEngine) -> None:
    for hop in range(10):
        current = engine.state.systems[engine.state.ship.system_id]
        target = current.neighbor_coordinates[0]
        engine.apply_command(command(engine.state, StationRole.FLIGHT, "begin_transit", coordinate=list(target)))
        for _ in range(60):
            engine.tick(.25)
            if engine.state.ship.transit_target is None:
                break
        assert engine.state.systems[engine.state.ship.system_id].coordinate == target
    assert len(engine.state.systems) == 11


def test_time_acceleration_is_denied_during_deadline(engine: SimulationEngine) -> None:
    encounter = engine.state.current_encounter
    assert encounter is not None
    encounter.deadline_s = 30
    with pytest.raises(CommandError, match="unsafe"):
        engine.apply_command(command(engine.state, StationRole.COMMAND, "set_time_scale", scale=100))


def test_default_power_is_thermally_stable(engine: SimulationEngine) -> None:
    starting_hull = engine.state.ship.hull
    starting_heat = engine.state.ship.heat
    for _ in range(12_000):
        engine.tick(.05)
    assert engine.state.ship.hull == starting_hull
    assert engine.state.ship.heat <= starting_heat + .01


def test_thermal_and_sensor_hazards_produce_authorized_alerts(engine: SimulationEngine) -> None:
    engine.state.ship.heat = .82
    assert engine.state.current_encounter
    engine.state.ship.scan_progress = .25
    engine.state.current_encounter.environmental_effects["power_induction"] = .2
    projection = engine.station_projection(StationRole.ENGINEERING)
    messages = {alert["message"] for alert in projection["alerts"]}
    assert any("Thermal index elevated" in message for message in messages)
    assert any("External energy coupling" in message for message in messages)


def test_defensive_posture_routes_incoming_damage_to_shields() -> None:
    unprotected = create_game_state(
        universe_name="Open", seed=12, ship_name="Open", crew_capacity=1, character_name="A", backstory=""
    )
    protected = unprotected.model_copy(deep=True)
    open_engine = SimulationEngine(unprotected)
    protected_engine = SimulationEngine(protected)
    for state in (unprotected, protected):
        assert state.current_encounter
        state.current_encounter.deadline_kind = "patrol_escalates"
        state.current_encounter.deadline_s = .01
    protected_engine.apply_command(command(protected, StationRole.INTEGRATED, "raise_shields", level=1))
    open_engine.tick(.05)
    protected_engine.tick(.05)
    assert unprotected.ship.hull < 1
    assert unprotected.ship.shields == 1
    assert protected.ship.hull == 1
    assert protected.ship.shields < 1
    assert any(alert["message"] == "Defensive field active" for alert in protected_engine.station_projection(StationRole.TACTICAL)["alerts"])


def test_engineering_can_repair_preserved_demo_damage(engine: SimulationEngine) -> None:
    engine.state.ship.hull = .72
    engine.state.ship.heat = .4
    events = engine.apply_command(command(engine.state, StationRole.ENGINEERING, "field_repair"))
    assert engine.state.ship.hull == pytest.approx(.82)
    assert events[0].event_type == "field_repair_completed"
    engine.state.ship.throttle = .2
    with pytest.raises(CommandError, match="stationary"):
        engine.apply_command(command(engine.state, StationRole.ENGINEERING, "field_repair"))


def test_cooling_projection_reports_signed_heat_flow_and_eta(engine: SimulationEngine) -> None:
    ship = engine.state.ship
    ship.heat = .9
    ship.power.propulsion = .1
    ship.power.sensors = .1
    ship.power.communications = .05
    ship.power.shields = .1
    ship.power.weapons = .05
    ship.power.cooling = .35
    cooling = engine.station_projection(StationRole.ENGINEERING)["engineering_effects"]["cooling"]
    assert cooling["trend"] == "cooling"
    assert cooling["net_heat_pct_s"] < 0
    assert cooling["eta_safe_s"] > 0


def test_threads_persist_across_warp_and_known_contact_sends_follow_up() -> None:
    state = create_game_state(universe_name="Threads", seed=55, ship_name="Traveler", crew_capacity=1, character_name="A", backstory="", scenario_preset="friendly_contact_test")
    engine = SimulationEngine(state)
    original_thread = state.world_threads[0]
    destination = list(state.systems[state.ship.system_id].neighbor_coordinates[0])
    engine.apply_command(command(state, StationRole.INTEGRATED, "begin_transit", coordinate=destination))
    events = []
    for _ in range(60):
        events.extend(engine.tick(.25))
        if state.ship.transit_target is None:
            break
    assert state.ship.transit_target is None
    assert original_thread in state.world_threads and original_thread.status == "open"
    assert len([thread for thread in state.world_threads if thread.status == "open"]) >= 2
    assert original_thread.next_actions[0].startswith("Respond to")
    assert any(event.event_type == "persistent_contact_follow_up_received" for event in events)
    assert any("Delayed follow-up" in entry["message"] for entry in state.message_log)


def test_multistage_world_thread_creates_persistent_follow_up() -> None:
    state = None
    for seed in range(100):
        candidate = create_game_state(universe_name="Stages", seed=seed, ship_name="Surveyor", crew_capacity=1, character_name="A", backstory="")
        if candidate.current_encounter and candidate.current_encounter.family not in {"artificial_signal", "disputed_boundary", "damaged_vessel"}:
            state = candidate
            break
    assert state and state.current_encounter
    engine = SimulationEngine(state)
    engine.apply_command(command(state, StationRole.INTEGRATED, "start_scan", target_id=state.current_encounter.target_id))
    for _ in range(650):
        engine.tick(.25)
        if state.ship.scan_progress >= .8:
            break
    thread = state.world_threads[0]
    while thread.status == "open":
        engine.apply_command(command(state, StationRole.INTEGRATED, "pursue_thread", thread_id=thread.id, action=thread.next_actions[0], note="Observed measurements support further study; origin is uncertain.", observation_ids=[obs.id for obs in state.observations if obs.station == StationRole.SCIENCE]))
    assert state.current_encounter.status == "resolved"
    follow_up = state.world_threads[-1]
    assert follow_up.kind == "consequence"
    assert follow_up.status == "open"
    projection = engine.station_projection(StationRole.INTEGRATED)
    assert projection["objectives"]["open_threads"]


def test_eight_simulated_hour_soak(engine: SimulationEngine) -> None:
    # Large time scale advances eight universe hours in under two thousand deterministic ticks.
    engine.state.current_encounter = None
    engine.state.time_scale = 100
    start = engine.state.universe_time_ms
    for _ in range(1_152):
        engine.tick(.25)
    assert engine.state.universe_time_ms - start == 8 * 60 * 60 * 1_000
    assert 0 <= engine.state.ship.hull <= 1
    assert 0 <= engine.state.ship.shields <= 1
