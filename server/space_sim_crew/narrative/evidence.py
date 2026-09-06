from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import CanonicalEvent, GameState, Observation, StationRole
from .canon import NarrativeCanon
from .discovery import DiscoveryTracker
from .models import EvidenceDiscovery

if TYPE_CHECKING:
    from ..simulation import SimulationEngine


class NarrativeEvidenceResolver:
    """Binds AI-authored evidence routes to the existing deterministic scan loop.

    The model is allowed to describe a physically observable clue and compatible
    sensor domains. It never decides whether the clue is observed. Observation is
    gated by the real scan target, selected installed instrument, scan threshold,
    and instrument condition.
    """

    def __init__(self, canon: NarrativeCanon):
        self.canon = canon
        self.discovery = DiscoveryTracker(canon)

    def resolve_scan_events(
        self,
        state: GameState,
        engine: "SimulationEngine",
        events: list[CanonicalEvent],
    ) -> list[CanonicalEvent]:
        encounter = state.current_encounter
        if not encounter:
            return []
        threshold_events = [event for event in events if event.event_type == "scan_threshold_reached"]
        if not threshold_events:
            return []
        if state.ship.active_scan_target != encounter.target_id:
            return []
        instrument = next(
            (capability for capability in state.ship.capabilities if capability.id == state.ship.active_scan_instrument),
            None,
        )
        if instrument is None or instrument.category != "hardware":
            return []
        instrument_domains = set(instrument.input_domains) | set(instrument.output_domains)
        if not instrument_domains:
            return []

        committed: list[CanonicalEvent] = []
        for threshold_event in threshold_events:
            threshold = float(threshold_event.payload.get("threshold", 0))
            for evidence in self.canon.evidence_candidates(encounter.id):
                if threshold + 1e-9 < evidence.minimum_scan_fraction:
                    continue
                required_domains = set(evidence.instrument_domains)
                if not required_domains or not required_domains.intersection(instrument_domains):
                    continue
                confidence = min(
                    0.99,
                    max(0.45, (0.55 + threshold * 0.4) * max(0.35, instrument.condition)),
                )
                discovery = EvidenceDiscovery(
                    evidence_id=evidence.id,
                    encounter_id=encounter.id,
                    target_id=encounter.target_id,
                    instrument_id=instrument.id,
                    instrument_name=instrument.name,
                    observed_at_ms=state.universe_time_ms,
                    scan_fraction=threshold,
                    description=evidence.description,
                    reveals=evidence.reveals,
                    confidence=round(confidence, 3),
                )
                observation = Observation(
                    observed_at_ms=state.universe_time_ms,
                    station=StationRole.SCIENCE,
                    source_capability=instrument.id,
                    target=encounter.target_id,
                    measurement="narrative evidence",
                    value={
                        "observation": evidence.description,
                        "implications": evidence.reveals,
                    },
                    confidence=discovery.confidence,
                    uncertainty=round(1 - discovery.confidence, 3),
                    derived_from_events=[threshold_event.id],
                )
                state.observations.append(observation)
                knowledge = f"Scan evidence ({instrument.name}): {evidence.description}"
                if evidence.reveals:
                    knowledge += " Implications: " + "; ".join(evidence.reveals[:4])
                if knowledge not in state.crew_knowledge:
                    state.crew_knowledge.append(knowledge)
                    state.crew_knowledge = state.crew_knowledge[-300:]
                self.canon.commit_evidence_discovery(discovery)
                discovery_state = self.discovery.record_evidence(encounter.id, evidence.id)
                if evidence.narrative_role == "contradiction" and discovery_state.contradictions:
                    contradiction = f"CONTRADICTION: {discovery_state.contradictions[-1]}"
                    if contradiction not in state.crew_knowledge:
                        state.crew_knowledge.append(contradiction)
                        state.crew_knowledge = state.crew_knowledge[-300:]
                self.discovery.sync_activity_board(state, encounter.id)
                committed.append(engine.event(
                    "narrative_evidence_discovered",
                    payload={
                        "evidence_id": evidence.id,
                        "narrative_role": evidence.narrative_role,
                        "discovery_phase": discovery_state.phase,
                        "instrument_id": instrument.id,
                        "instrument": instrument.name,
                        "scan_fraction": threshold,
                        "observation_id": observation.id,
                        "description": evidence.description,
                        "implications": evidence.reveals,
                        "confidence": discovery.confidence,
                    },
                    targets=[encounter.target_id],
                    source_kind="simulation",
                    visibility="crew",
                    caused_by=[threshold_event.id],
                ))
        return committed
