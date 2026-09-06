from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class StationRole(StrEnum):
    INTEGRATED = "integrated"
    COMMAND = "command"
    FLIGHT = "flight"
    ENGINEERING = "engineering"
    SCIENCE = "science"
    COMMUNICATIONS = "communications"
    TACTICAL = "tactical"


class PowerAllocation(BaseModel):
    propulsion: float = 0.24
    sensors: float = 0.20
    communications: float = 0.12
    shields: float = 0.20
    weapons: float = 0.08
    cooling: float = 0.16

    @field_validator("propulsion", "sensors", "communications", "shields", "weapons", "cooling")
    @classmethod
    def valid_fraction(cls, value: float) -> float:
        if not 0 <= value <= 1:
            raise ValueError("power allocations must be between 0 and 1")
        return value

    @property
    def total(self) -> float:
        return sum(self.model_dump().values())


class Capability(BaseModel):
    id: str
    name: str
    category: Literal["hardware", "software", "technique", "configuration"]
    condition: float = 1.0
    power_mw: float = 0
    input_domains: list[str] = Field(default_factory=list)
    output_domains: list[str] = Field(default_factory=list)
    description: str = ""
    origin_event: str | None = None


class CargoItem(BaseModel):
    id: str
    name: str
    quantity: int = 1
    description: str = ""
    installable_capability: Capability | None = None


class ShipState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ship"))
    name: str = "Wayfinder"
    frame: str = "Survey Vessel"
    crew_capacity: int = 6
    system_id: str = ""
    x_km: float = 0
    y_km: float = 0
    heading_deg: float = 0
    target_heading_deg: float = 0
    throttle: float = 0
    velocity_km_s: float = 0
    baseline_origin_x_km: float | None = None
    baseline_origin_y_km: float | None = None
    baseline_target_km: float = 0
    baseline_autobraking: bool = False
    hull: float = 1
    shields: float = 1
    defensive_posture: bool = False
    weapons_authorized: bool = False
    selected_weapon: Literal["focused_energy", "kinetic_interceptor"] = "focused_energy"
    weapon_charge: float = 0
    weapon_cooldown_s: float = 0
    kinetic_ammunition: int = 8
    last_weapon_result: str = "No weapon fired."
    heat: float = 0.25
    reactor_output_mw: float = 600
    reactor_capacity_mw: float = 800
    power: PowerAllocation = Field(default_factory=PowerAllocation)
    capabilities: list[Capability] = Field(default_factory=list)
    cargo: list[CargoItem] = Field(default_factory=list)
    active_scan_target: str | None = None
    active_scan_instrument: str | None = None
    scan_progress: float = 0
    transit_target: str | None = None
    transit_remaining_s: float = 0
    transit_mode: Literal["normal", "emergency_warp"] | None = None


class CelestialBody(BaseModel):
    id: str
    name: str
    kind: Literal["star", "planet", "moon", "belt", "station", "anomaly"]
    orbit_index: int = 0
    summary: str
    properties: dict[str, Any] = Field(default_factory=dict)


class SystemState(BaseModel):
    id: str
    name: str
    coordinate: tuple[int, int]
    star_class: str
    bodies: list[CelestialBody]
    neighbor_coordinates: list[tuple[int, int]]
    visited: bool = False
    surveyed: bool = False
    generated_depth: int = 1


class Observation(BaseModel):
    id: str = Field(default_factory=lambda: new_id("obs"))
    observed_at_ms: int
    station: StationRole
    source_capability: str
    target: str
    measurement: str
    value: Any = None
    unit: str | None = None
    uncertainty: float | None = None
    confidence: float = 0
    derived_from_events: list[str] = Field(default_factory=list)


class BearingMeasurement(BaseModel):
    id: str = Field(default_factory=lambda: new_id("bearing"))
    target: str
    observed_at_ms: int
    instrument_id: str
    origin_x_km: float
    origin_y_km: float
    bearing_deg: float
    angular_uncertainty_deg: float
    confidence: float
    derived_from_event: str


class SignalAnalysisState(BaseModel):
    encounter_id: str
    acquired: bool = False
    recording_retained: bool = True
    workspace_open: bool = True
    tuned_frequency_mhz: float | None = None
    shared_with_science: bool = False
    pca_cutoff: int = 1
    pca_selected_side: Literal["high_variance", "low_variance"] = "low_variance"
    pca_configured: bool = False
    structure_result: Literal["noise_like", "structured_but_contaminated", "structured_carrier", "inconclusive"] | None = None
    structure_confidence: float = 0
    demodulation_method: Literal["amplitude", "frequency", "phase_shift", "pulse"] | None = None
    demodulation_confidence: float = 0
    symbol_preview: str = ""
    interpretation: str = ""
    interpretation_confidence: float = 0
    translation_status: Literal["idle", "rejected", "translated"] = "idle"
    translation_protocol: str = ""
    translation_notes: str = ""
    reply_sent: bool = False
    reply_acknowledgment: str = ""
    dmaps_epsilon: float = 1.0
    dmaps_diffusion_time: int = 1
    dmaps_neighbors: int = 5
    science_classification: Literal["natural_contamination", "instrument_artifact", "structured_residual", "inconclusive"] | None = None
    science_note: str = ""
    processing_log: list[dict[str, Any]] = Field(default_factory=list)
    version: int = 0


class NPCState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("npc"))
    name: str
    vessel_name: str
    culture: str
    disposition: float = 0
    intention: str = "observe"
    patience_s: float = 120
    known_messages: list[str] = Field(default_factory=list)
    personality: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    beliefs: list[str] = Field(default_factory=list)
    fears: list[str] = Field(default_factory=list)
    memories: list[dict[str, Any]] = Field(default_factory=list)
    commitments: list[str] = Field(default_factory=list)
    relationship_label: str = "unfamiliar contact"
    visible_activity: str = "holding position"
    visible_reason: str = "No motive has been established."
    current_request: str = ""
    last_action: str = "hold_position"


class DirectorState(BaseModel):
    narrative_pressure: float = 0.25
    novelty_budget: float = 0.75
    danger_level: float = 0.15
    mystery_density: float = 0.5
    recent_milestones: list[str] = Field(default_factory=list)
    unresolved_threads: list[str] = Field(default_factory=list)


class WorldThread(BaseModel):
    id: str = Field(default_factory=lambda: new_id("thread"))
    title: str
    kind: Literal["contact", "discovery", "hazard", "mystery", "promise", "consequence"]
    status: Literal["open", "resolved", "failed"] = "open"
    stage: int = 0
    summary: str
    origin_system_id: str
    npc_id: str | None = None
    remote_frequency_mhz: float | None = None
    evidence: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)


class EncounterState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("encounter"))
    family: Literal[
        "ordinary_survey",
        "artificial_signal",
        "damaged_vessel",
        "environmental_hazard",
        "disputed_boundary",
        "ancient_site",
    ]
    title: str
    target_id: str
    status: Literal["active", "resolved", "departed"] = "active"
    phase: str = "detected"
    public_summary: str
    environmental_effects: dict[str, float] = Field(default_factory=dict)
    hidden_truth: dict[str, Any] = Field(default_factory=dict)
    npc: NPCState | None = None
    deadline_s: float | None = None
    deadline_kind: str | None = None
    outcome: str | None = None
    salvage: CargoItem | None = None
    target_hull: float = 1
    target_shields: float = 0.65


class CharacterState(BaseModel):
    id: str = Field(default_factory=lambda: new_id("character"))
    name: str
    backstory: str = "Independent deep-space explorer."
    expertise: list[str] = Field(default_factory=list)
    personal_knowledge: list[str] = Field(default_factory=list)
    status: Literal["active", "injured", "deceased", "retired"] = "active"


class CanonicalEvent(BaseModel):
    schema_version: int = 1
    id: str = Field(default_factory=lambda: new_id("event"))
    universe_id: str
    universe_time_ms: int
    event_type: str
    actor_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    source_kind: Literal["player_command", "simulation", "approved_proposal", "host_action"]
    source_id: str | None = None
    visibility: Literal["director", "entity-private", "crew", "public"] = "crew"
    caused_by: list[str] = Field(default_factory=list)


class GameState(BaseModel):
    schema_version: int = 1
    universe_id: str = Field(default_factory=lambda: new_id("universe"))
    universe_name: str = "Uncharted Expanse"
    seed: int
    universe_time_ms: int = 0
    time_scale: int = 1
    consequence_mode: Literal["forgiving", "serious", "unforgiving"] = "forgiving"
    scenario_preset: Literal["random", "friendly_contact_test"] = "random"
    ship: ShipState
    characters: list[CharacterState] = Field(default_factory=list)
    systems: dict[str, SystemState] = Field(default_factory=dict)
    current_encounter: EncounterState | None = None
    known_npcs: dict[str, NPCState] = Field(default_factory=dict)
    observations: list[Observation] = Field(default_factory=list)
    bearing_measurements: list[BearingMeasurement] = Field(default_factory=list)
    signal_analysis: SignalAnalysisState | None = None
    crew_knowledge: list[str] = Field(default_factory=list)
    message_log: list[dict[str, Any]] = Field(default_factory=list)
    director: DirectorState = Field(default_factory=DirectorState)
    world_threads: list[WorldThread] = Field(default_factory=list)
    continuity_report: dict[str, Any] = Field(default_factory=dict)
    event_count: int = 0


class PlayerCommand(BaseModel):
    schema_version: int = 1
    id: str = Field(default_factory=lambda: new_id("command"))
    session_id: str
    player_id: str
    character_id: str
    station: StationRole
    client_sequence: int
    command_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class WorldProposal(BaseModel):
    schema_version: int = 1
    id: str = Field(default_factory=lambda: new_id("proposal"))
    proposed_by: str
    action: Literal[
        "change_intention",
        "npc_decision",
        "director_beat",
        "schedule_event",
        "propose_fact",
        "configure_scenario",
        "send_message",
        "no_event",
    ]
    targets: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_universe_time_ms: int = 0
    rationale: str = ""


class PlayerConnection(BaseModel):
    player_id: str = Field(default_factory=lambda: new_id("player"))
    token: str = Field(default_factory=lambda: uuid4().hex)
    display_name: str
    character_id: str
    station: StationRole
    connected: bool = True
    last_client_sequence: int = 0
    disconnected_at_monotonic: float | None = None
