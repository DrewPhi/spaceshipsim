from pathlib import Path

from space_sim_crew.models import PlayerCommand, SignalAnalysisState, StationRole
from space_sim_crew.narrative.science import (
    AnalysisStep,
    GeneratedCapabilityBlueprint,
    GenerativeScienceEngine,
    MechanicSpec,
    PhenomenonBlueprint,
    ScientificCanon,
    ScientificPrediction,
    ScientificRuntime,
    operator_eigenstructure_product,
)
from space_sim_crew.session import create_game_state
from space_sim_crew.signal_processing import default_signal_recipe


def _glyph_points() -> list[list[float]]:
    # An asymmetric three-stroke motif. The runtime treats these as desired
    # nontrivial operator eigenstructure, not pixels to paint on the client.
    return [
        [-.9, .8], [-.5, .8], [-.1, .8], [.3, .8],
        [-.9, .8], [-.9, .35], [-.9, -.1], [-.9, -.55],
        [-.9, .1], [-.5, .1], [-.1, .1], [.25, .1],
        [.25, .1], [.25, -.25], [.25, -.6], [.25, -.85],
        [.25, -.85], [.55, -.85], [.85, -.85],
    ]


def _state(seed: int = 71):
    state = create_game_state(
        universe_name="Science Test",
        seed=seed,
        ship_name="Kepler",
        crew_capacity=3,
        character_name="Tester",
        backstory="Experimental scientist.",
    )
    assert state.current_encounter
    state.current_encounter.family = "artificial_signal"
    state.current_encounter.hidden_truth["signal_recipe"] = default_signal_recipe(seed, "artificial_signal")
    state.signal_analysis = SignalAnalysisState(
        encounter_id=state.current_encounter.id,
        acquired=True,
        shared_with_science=True,
        tuned_frequency_mhz=812.5,
    )
    return state


def _command(state, command_type: str, **parameters) -> PlayerCommand:
    return PlayerCommand(
        session_id="session_science",
        player_id="player_science",
        character_id=state.characters[0].id,
        station=StationRole.SCIENCE,
        client_sequence=1,
        command_type=command_type,
        parameters=parameters,
    )


def test_operator_eigenstructure_recovers_authored_geometry_without_ui_overlay() -> None:
    mechanic = MechanicSpec(
        primitive="operator_eigenstructure",
        parameters={"motif_points": _glyph_points(), "ideal_epsilon": 1.0, "epsilon_tolerance": .45},
    )
    resolved = operator_eigenstructure_product(mechanic, epsilon=1.0, diffusion_time=2, neighbors=5)
    blurred = operator_eigenstructure_product(mechanic, epsilon=3.0, diffusion_time=2, neighbors=5)
    assert resolved is not None and blurred is not None
    assert len(resolved["embedding"]) == len(_glyph_points())
    assert resolved["dominant_dimensions"] == 2
    assert resolved["motif_recovery"] > .9
    assert blurred["motif_recovery"] < resolved["motif_recovery"]


def test_scientific_canon_persists_authored_and_verified_science(tmp_path: Path) -> None:
    canon = ScientificCanon(tmp_path, "universe_science")
    prediction = ScientificPrediction(
        description="The operator should recover a coherent two-dimensional motif.",
        analysis_chain=[AnalysisStep(primitive="diffusion_maps")],
        metric="motif_recovery",
        minimum=.8,
        reveal="The transmission carries deliberate information in its diffusion eigenspace.",
    )
    blueprint = PhenomenonBlueprint(
        encounter_id="encounter_1",
        name="Spectral inscription",
        novelty="exotic",
        crew_hook="The multichannel recording has more state recurrence than its waveform suggests.",
        hidden_mechanism="The transmitter engineered a Markov operator whose first nontrivial eigenspace is information-bearing.",
        mechanics=[MechanicSpec(primitive="operator_eigenstructure", parameters={"motif_points": _glyph_points()})],
        predictions=[prediction],
    )
    assert canon.commit_blueprint(blueprint)
    assert (tmp_path / "universe_science" / "knowledge" / "scientific-canon.md").exists()
    reloaded = ScientificCanon(tmp_path, "universe_science")
    assert reloaded.blueprint("encounter_1") is not None
    assert reloaded.document.novelty_budget < .68


def test_science_projection_uses_raw_diffusion_maps_not_pca_selection(tmp_path: Path) -> None:
    state = _state()
    canon = ScientificCanon(tmp_path, state.universe_id)
    engine = GenerativeScienceEngine(state, canon)
    first = engine.station_projection(StationRole.SCIENCE)["signal_lab"]["dmaps"]["embedding"]
    assert state.signal_analysis
    state.signal_analysis.pca_configured = True
    state.signal_analysis.pca_cutoff = 3
    state.signal_analysis.pca_selected_side = "high_variance"
    state.signal_analysis.version += 1
    second = engine.station_projection(StationRole.SCIENCE)["signal_lab"]["dmaps"]["embedding"]
    assert first == second


def test_verified_ai_authored_prediction_can_install_persistent_capability(tmp_path: Path) -> None:
    state = _state(91)
    assert state.current_encounter and state.signal_analysis
    canon = ScientificCanon(tmp_path, state.universe_id)
    prerequisite = state.ship.capabilities[0].name
    prediction = ScientificPrediction(
        description="At the correct kernel scale, the recovered operator contains deliberate geometric structure.",
        analysis_chain=[AnalysisStep(primitive="diffusion_maps")],
        metric="motif_recovery",
        minimum=.82,
        epsilon_range=(.8, 1.2),
        diffusion_time_range=(1, 4),
        reveal="The carrier's state-transition geometry is deliberately information-bearing.",
    )
    capability = GeneratedCapabilityBlueprint(
        name="Reciprocal Geometry Decoder",
        description="A field modification that preserves and compares recurring operator geometry across later recordings.",
        acquisition="field_modification",
        category="configuration",
        power_mw=24,
        input_domains=["signal"],
        output_domains=["operator_geometry", "motif_similarity"],
        operations=["diffusion_maps", "recurrence"],
        prerequisites=[prerequisite],
        unlock_after_prediction_ids=[prediction.id],
    )
    blueprint = PhenomenonBlueprint(
        encounter_id=state.current_encounter.id,
        name="Engineered state-space message",
        novelty="exotic",
        crew_hook="The same states recur, but ordinary temporal plots do not explain the ordering.",
        hidden_mechanism="Information is encoded in the nontrivial eigenspace of an engineered transition operator.",
        observable_domains=["signal"],
        mechanics=[MechanicSpec(
            primitive="operator_eigenstructure",
            parameters={"motif_points": _glyph_points(), "ideal_epsilon": 1.0, "epsilon_tolerance": .5},
        )],
        predictions=[prediction],
        capability=capability,
    )
    assert canon.commit_blueprint(blueprint)
    engine = GenerativeScienceEngine(state, canon)
    runtime = ScientificRuntime(canon)
    event = engine.apply_command(_command(state, "configure_dmaps", epsilon=1.0, diffusion_time=2, neighbors=5))[0]
    produced = runtime.process_events(state, engine, [event])
    assert any(item.event_type == "scientific_prediction_verified" for item in produced)
    assert any(item.event_type == "generated_scientific_capability_installed" for item in produced)
    assert any(item.name == "Reciprocal Geometry Decoder" for item in state.ship.capabilities)
    assert capability.id in canon.document.installed_capabilities
    reloaded = ScientificCanon(tmp_path, state.universe_id)
    assert reloaded.document.installed_capabilities[capability.id].name == "Reciprocal Geometry Decoder"


def test_pca_is_no_longer_required_for_correct_signal_demodulation(tmp_path: Path) -> None:
    state = _state(103)
    assert state.current_encounter and state.signal_analysis
    recipe = default_signal_recipe(state.seed, "artificial_signal")
    state.current_encounter.hidden_truth["signal_recipe"] = recipe
    canon = ScientificCanon(tmp_path, state.universe_id)
    engine = GenerativeScienceEngine(state, canon)
    structure = engine._test_signal_structure(PlayerCommand(
        session_id="s",
        player_id="p",
        character_id=state.characters[0].id,
        station=StationRole.COMMUNICATIONS,
        client_sequence=1,
        command_type="test_signal_structure",
        parameters={},
    ))[0]
    assert structure.payload["pca_required"] is False
    assert state.signal_analysis.pca_configured is False
    demod = engine._attempt_demodulation(PlayerCommand(
        session_id="s",
        player_id="p",
        character_id=state.characters[0].id,
        station=StationRole.COMMUNICATIONS,
        client_sequence=2,
        command_type="attempt_demodulation",
        parameters={"method": recipe["modulation"]},
    ))[0]
    assert demod.payload["stable_frame"] is True
    assert state.signal_analysis.demodulation_confidence >= .55
