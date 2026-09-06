from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


LoreVisibility = Literal["director", "entity-private", "crew", "public"]
LoreEntityKind = Literal[
    "person",
    "civilization",
    "faction",
    "institution",
    "place",
    "artifact",
    "historical_event",
    "custom",
    "phenomenon",
    "document",
    "technology",
]
WorldIntentAction = Literal[
    "send_message",
    "create_lead",
    "relationship_shift",
    "record_claim",
    "record_fact",
    "change_status",
]


def _lore_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class DossierEntity(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: LoreEntityKind
    summary: str = Field(min_length=1, max_length=800)


class DossierFact(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=800)
    visibility: LoreVisibility = "director"
    known_by: list[str] = Field(default_factory=list, max_length=12)


class DossierClaim(BaseModel):
    speaker: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=800)
    believes_claim: bool = True
    visibility: LoreVisibility = "entity-private"


class DossierRelationship(BaseModel):
    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    kind: str = Field(min_length=1, max_length=80)
    state: str = Field(min_length=1, max_length=500)
    visibility: LoreVisibility = "director"


class DossierQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    related_to: list[str] = Field(default_factory=list, max_length=8)
    why_it_matters: str = Field(default="", max_length=500)


class DossierEvidence(BaseModel):
    id: str = Field(default_factory=lambda: _lore_id("evidence"))
    target: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=700)
    instrument_domains: list[str] = Field(default_factory=list, max_length=8)
    reveals: list[str] = Field(default_factory=list, max_length=8)
    minimum_scan_fraction: float = 0.75

    @field_validator("minimum_scan_fraction")
    @classmethod
    def valid_scan_fraction(cls, value: float) -> float:
        return min(1.0, max(0.0, value))


class SituationDossier(BaseModel):
    schema_version: int = 1
    premise: str = Field(min_length=1, max_length=1200)
    immediate_stakes: str = Field(default="", max_length=800)
    entities: list[DossierEntity] = Field(default_factory=list, max_length=8)
    facts: list[DossierFact] = Field(default_factory=list, max_length=12)
    claims: list[DossierClaim] = Field(default_factory=list, max_length=8)
    relationships: list[DossierRelationship] = Field(default_factory=list, max_length=8)
    open_questions: list[DossierQuestion] = Field(default_factory=list, max_length=8)
    evidence: list[DossierEvidence] = Field(default_factory=list, max_length=8)
    possible_developments: list[str] = Field(default_factory=list, max_length=8)
    actor_notes: dict[str, str] = Field(default_factory=dict)


class LoreExpansion(BaseModel):
    schema_version: int = 1
    encounter_id: str = ""
    question: str = Field(min_length=1, max_length=1000)
    new_entities: list[DossierEntity] = Field(default_factory=list, max_length=4)
    new_facts: list[DossierFact] = Field(default_factory=list, max_length=6)
    new_claims: list[DossierClaim] = Field(default_factory=list, max_length=4)
    new_relationships: list[DossierRelationship] = Field(default_factory=list, max_length=4)
    new_questions: list[DossierQuestion] = Field(default_factory=list, max_length=4)
    new_evidence: list[DossierEvidence] = Field(default_factory=list, max_length=4)
    actor_notes: dict[str, str] = Field(default_factory=dict)
    summary: str = Field(default="", max_length=1200)


class EvidenceDiscovery(BaseModel):
    evidence_id: str
    encounter_id: str
    target_id: str
    instrument_id: str
    instrument_name: str
    observed_at_ms: int
    scan_fraction: float
    description: str
    reveals: list[str] = Field(default_factory=list)
    confidence: float = 0.8


class WorldIntentDraft(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    action: WorldIntentAction
    summary: str = Field(min_length=1, max_length=500)
    reason: str = Field(default="", max_length=500)
    delay_s: float = 90
    requires_departure: bool = True
    message: str = Field(default="", max_length=1200)
    relationship_delta: float = 0
    subject: str = Field(default="", max_length=120)
    content: str = Field(default="", max_length=800)
    visibility: LoreVisibility = "director"

    @field_validator("delay_s")
    @classmethod
    def valid_delay(cls, value: float) -> float:
        return min(86_400.0, max(15.0, value))

    @field_validator("relationship_delta")
    @classmethod
    def valid_relationship_delta(cls, value: float) -> float:
        return min(0.25, max(-0.25, value))


class WorldPlan(BaseModel):
    intents: list[WorldIntentDraft] = Field(default_factory=list, max_length=4)


class ScheduledWorldIntent(WorldIntentDraft):
    id: str = Field(default_factory=lambda: _lore_id("intent"))
    encounter_id: str
    origin_system_id: str
    created_at_ms: int
    execute_at_ms: int
    status: Literal["scheduled", "executed", "cancelled"] = "scheduled"
    executed_at_ms: int | None = None


class NarrativeCanonDocument(BaseModel):
    schema_version: int = 2
    universe_id: str
    situations: dict[str, SituationDossier] = Field(default_factory=dict)
    expansions: list[LoreExpansion] = Field(default_factory=list)
    evidence_discoveries: dict[str, EvidenceDiscovery] = Field(default_factory=dict)
    scheduled_intents: dict[str, ScheduledWorldIntent] = Field(default_factory=dict)
