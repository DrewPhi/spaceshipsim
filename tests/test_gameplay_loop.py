import math

from space_sim_crew.models import PlayerCommand, StationRole
from space_sim_crew.session import create_game_state
from space_sim_crew.simulation import SimulationEngine
from space_sim_crew.signal_processing import validate_signal_recipe


def _command(state, command_type: str, **parameters):
    return PlayerCommand(
        session_id="playthrough",
        player_id="solo",
        character_id=state.characters[0].id,
        station=StationRole.INTEGRATED,
        client_sequence=1,
        command_type=command_type,
        parameters=parameters,
    )


def test_complete_artificial_signal_playthrough() -> None:
    state = None
    for seed in range(300):
        candidate = create_game_state(
            universe_name="Playthrough", seed=seed, ship_name="Test Ship", crew_capacity=1, character_name="Solo", backstory=""
        )
        if candidate.current_encounter and candidate.current_encounter.family == "artificial_signal":
            state = candidate
            break
    assert state and state.current_encounter
    engine = SimulationEngine(state)
    encounter = state.current_encounter
    recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), state.seed, encounter.family)
    instrument = next(capability for capability in state.ship.capabilities if capability.name == "Signal Direction Scan")

    engine.apply_command(_command(state, "start_scan", target_id=encounter.target_id, instrument_id=instrument.id))
    elapsed = 0.0
    while len(state.bearing_measurements) < 1 and elapsed < 120:
        engine.tick(.25)
        elapsed += .25
    assert len(state.bearing_measurements) == 1
    first_bearing_time = elapsed
    first = state.bearing_measurements[0]

    baseline_heading = (first.bearing_deg + 90) % 360
    engine.apply_command(_command(state, "set_flight", heading_deg=baseline_heading, throttle=1, baseline_distance_km=2_000))
    while state.ship.baseline_target_km > 0 and elapsed < 180:
        engine.tick(.25)
        elapsed += .25
    baseline_time = elapsed - first_bearing_time
    assert math.hypot(state.ship.x_km - first.origin_x_km, state.ship.y_km - first.origin_y_km) >= 1_900
    assert state.ship.velocity_km_s <= .5

    engine.apply_command(_command(state, "start_scan", target_id=encounter.target_id, instrument_id=instrument.id))
    while len(state.bearing_measurements) < 2 and elapsed < 300:
        engine.tick(.25)
        elapsed += .25
    localization = engine.station_projection(StationRole.INTEGRATED)["localization"]
    assert localization["estimated_x_km"] is not None
    assert localization["intercept_heading_deg"] is not None

    while state.ship.scan_progress < .75 and elapsed < 360:
        engine.tick(.25)
        elapsed += .25
    engine.apply_command(_command(state, "acquire_signal", frequency_mhz=recipe["center_frequency_mhz"]))
    assert "repeatable structure" in engine.station_projection(StationRole.INTEGRATED)["workflow"]["next_action"]
    engine.apply_command(_command(state, "test_signal_structure"))
    assert "Separate contamination" in engine.station_projection(StationRole.INTEGRATED)["workflow"]["next_action"]
    engine.apply_command(_command(state, "configure_pca", cutoff=1, selected_side="low_variance"))
    engine.apply_command(_command(state, "test_signal_structure"))
    assert "stable symbol frame" in engine.station_projection(StationRole.INTEGRATED)["workflow"]["next_action"]
    wrong_method = next(method for method in ("amplitude", "frequency", "phase_shift", "pulse") if method != recipe["modulation"])
    engine.apply_command(_command(state, "attempt_demodulation", method=wrong_method))
    engine.apply_command(_command(state, "interpret_signal"))
    assert state.signal_analysis and state.signal_analysis.interpretation.startswith("NONSENSE")
    engine.apply_command(_command(state, "attempt_demodulation", method=recipe["modulation"]))
    assert state.signal_analysis and state.signal_analysis.demodulation_confidence >= .55
    engine.apply_command(_command(state, "interpret_signal"))
    assert state.signal_analysis.interpretation_confidence >= .55
    engine.apply_command(_command(state, "send_signal_reply", frequency_mhz=recipe["center_frequency_mhz"], message="Reception confirmed. We are conducting a peaceful survey."))
    assert state.signal_analysis.reply_acknowledgment
    assert "outcome" in engine.station_projection(StationRole.INTEGRATED)["workflow"]["next_action"]
    engine.apply_command(_command(state, "share_signal_with_science"))
    engine.apply_command(_command(state, "configure_dmaps", epsilon=1.0, diffusion_time=2, neighbors=5))
    engine.apply_command(_command(state, "classify_signal", classification="structured_residual", note="A repeatable residual remains after correlated contamination is separated."))
    events = engine.apply_command(_command(state, "resolve_encounter", method="investigation"))

    assert encounter.status == "resolved"
    assert "ultimate origin remain unresolved" in events[0].payload["finding"]
    assert elapsed < 360
    print(f"first bearing {first_bearing_time:.1f}s; automatic baseline and braking {baseline_time:.1f}s; complete {elapsed:.1f}s")
