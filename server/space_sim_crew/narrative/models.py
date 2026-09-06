from __future__ import annotations

from typing import Literal

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
    question: str = Field(min_length=1, max_length=1000)
    new_entities: list[DossierEntity] = Field(default_factory=list, max_length=4)
    new_facts: list[DossierFact] = Field(default_factory=list, max_length=6)
    new_claims: list[DossierClaim] = Field(default_factory=list, max_length=4)
    new_relationships: list[DossierRelationship] = Field(default_factory=list, max_length=4)
    new_questions: list[DossierQuestion] = Field(default_factory=list, max_length=4)
    new_evidence: list[DossierEvidence] = Field(default_factory=list, max_length=4)
    actor_notes: dict[str, str] = Field(default_factory=dict)
    summary: str = Field(default="", max_length=1200)


class NarrativeCanonDocument(BaseModel):
    schema_version: int = 1
    universe_id: str
    situations: dict[str, SituationDossier] = Field(default_factory=dict)
    expansions: list[LoreExpansion] = Field(default_factory=list)
