from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .models import LoreExpansion, NarrativeCanonDocument, SituationDossier


class NarrativeCanon:
    """Persistent narrative truth kept outside the live physics checkpoint.

    The simulation remains authoritative for physical state. This store is the
    canonical home for generated lore, claims, questions, and evidence designs.
    It uses the same human-readable Markdown/YAML convention as the rest of a save.
    """

    def __init__(self, saves_root: Path, universe_id: str):
        self.saves_root = saves_root
        self.universe_id = universe_id
        self.path = saves_root / universe_id / "knowledge" / "narrative-canon.md"
        self.document = self._load()

    def _load(self) -> NarrativeCanonDocument:
        if not self.path.exists():
            return NarrativeCanonDocument(universe_id=self.universe_id)
        text = self.path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            return NarrativeCanonDocument(universe_id=self.universe_id)
        try:
            raw = text.split("---\n", 2)[1]
            data = yaml.safe_load(raw) or {}
            state = data.get("state", {})
            document = NarrativeCanonDocument.model_validate(state)
        except (IndexError, yaml.YAMLError, ValueError, TypeError):
            return NarrativeCanonDocument(universe_id=self.universe_id)
        if document.universe_id != self.universe_id:
            return NarrativeCanonDocument(universe_id=self.universe_id)
        return document

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = self.document.model_dump(mode="json")
        frontmatter = yaml.safe_dump(
            {
                "schema_version": 1,
                "entity_type": "narrative_canon",
                "universe_id": self.universe_id,
                "state": state,
            },
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )
        body = self._readable_body()
        content = f"---\n{frontmatter}---\n\n# Narrative Canon\n\n{body.rstrip()}\n"
        fd, temporary = tempfile.mkstemp(prefix=".narrative-canon.", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _readable_body(self) -> str:
        if not self.document.situations:
            return "No AI-generated narrative situations have been committed yet."
        sections: list[str] = []
        for encounter_id, dossier in self.document.situations.items():
            sections.append(f"## Situation `{encounter_id}`\n\n{dossier.premise}")
            if dossier.immediate_stakes:
                sections.append(f"**Immediate stakes:** {dossier.immediate_stakes}")
            if dossier.entities:
                sections.append("### Entities\n\n" + "\n".join(
                    f"- **{entity.name}** ({entity.kind}): {entity.summary}" for entity in dossier.entities
                ))
            if dossier.facts:
                sections.append("### Director facts\n\n" + "\n".join(
                    f"- [{fact.visibility}] **{fact.subject}:** {fact.content}" for fact in dossier.facts
                ))
            if dossier.claims:
                sections.append("### Claims\n\n" + "\n".join(
                    f"- **{claim.speaker}:** {claim.content}" for claim in dossier.claims
                ))
            if dossier.open_questions:
                sections.append("### Open questions\n\n" + "\n".join(
                    f"- {question.question}" for question in dossier.open_questions
                ))
            if dossier.evidence:
                sections.append("### Evidence routes\n\n" + "\n".join(
                    f"- **{item.target}:** {item.description}" for item in dossier.evidence
                ))
        if self.document.expansions:
            sections.append("## Lazy lore expansions")
            for expansion in self.document.expansions[-30:]:
                sections.append(f"### {expansion.question}\n\n{expansion.summary or 'Additional canon was materialized in response to player curiosity.'}")
        return "\n\n".join(sections)

    def dossier(self, encounter_id: str) -> SituationDossier | None:
        return self.document.situations.get(encounter_id)

    def commit_dossier(self, encounter_id: str, dossier: SituationDossier) -> None:
        if encounter_id in self.document.situations:
            return
        self.document.situations[encounter_id] = dossier
        self.save()

    def commit_expansion(self, expansion: LoreExpansion) -> None:
        normalized = self._normalize(expansion.question)
        if any(self._normalize(item.question) == normalized for item in self.document.expansions):
            return
        self.document.expansions.append(expansion)
        self.document.expansions = self.document.expansions[-200:]
        self.save()

    def question_already_expanded(self, question: str) -> bool:
        normalized = self._normalize(question)
        return any(self._normalize(item.question) == normalized for item in self.document.expansions)

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.lower().split())[:600]

    def director_context(self, encounter_id: str | None = None, *, limit: int = 60) -> list[dict[str, Any]]:
        dossiers = self._selected_dossiers(encounter_id)
        rows: list[dict[str, Any]] = []
        for dossier in dossiers:
            rows.append({"kind": "premise", "content": dossier.premise})
            rows.extend({"kind": "entity", **entity.model_dump(mode="json")} for entity in dossier.entities)
            rows.extend({"kind": "fact", **fact.model_dump(mode="json")} for fact in dossier.facts)
            rows.extend({"kind": "claim", **claim.model_dump(mode="json")} for claim in dossier.claims)
            rows.extend({"kind": "relationship", **item.model_dump(mode="json")} for item in dossier.relationships)
            rows.extend({"kind": "question", **item.model_dump(mode="json")} for item in dossier.open_questions)
            rows.extend({"kind": "evidence", **item.model_dump(mode="json")} for item in dossier.evidence)
        for expansion in self.document.expansions[-20:]:
            rows.append({"kind": "expansion", "question": expansion.question, "summary": expansion.summary})
            rows.extend({"kind": "fact", **fact.model_dump(mode="json")} for fact in expansion.new_facts)
            rows.extend({"kind": "claim", **claim.model_dump(mode="json")} for claim in expansion.new_claims)
        return rows[-limit:]

    def npc_context(self, npc_name: str, encounter_id: str | None = None, *, limit: int = 40) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        names = {npc_name.lower()}
        for dossier in self._selected_dossiers(encounter_id):
            for entity in dossier.entities:
                if entity.name.lower() == npc_name.lower():
                    rows.append({"kind": "self", **entity.model_dump(mode="json")})
            for fact in dossier.facts:
                if fact.visibility in {"public", "crew"} or any(name.lower() in names for name in fact.known_by):
                    rows.append({"kind": "known_fact", "subject": fact.subject, "content": fact.content})
            for claim in dossier.claims:
                if claim.speaker.lower() == npc_name.lower() or claim.visibility in {"public", "crew"}:
                    rows.append({"kind": "claim", **claim.model_dump(mode="json")})
            for relation in dossier.relationships:
                if relation.visibility in {"public", "crew"} or relation.source.lower() == npc_name.lower() or relation.target.lower() == npc_name.lower():
                    rows.append({"kind": "relationship", **relation.model_dump(mode="json")})
            note = dossier.actor_notes.get(npc_name)
            if note:
                rows.append({"kind": "actor_note", "content": note})
        for expansion in self.document.expansions[-20:]:
            for fact in expansion.new_facts:
                if fact.visibility in {"public", "crew"} or any(name.lower() in names for name in fact.known_by):
                    rows.append({"kind": "known_fact", "subject": fact.subject, "content": fact.content})
            for claim in expansion.new_claims:
                if claim.speaker.lower() == npc_name.lower() or claim.visibility in {"public", "crew"}:
                    rows.append({"kind": "claim", **claim.model_dump(mode="json")})
            note = expansion.actor_notes.get(npc_name)
            if note:
                rows.append({"kind": "actor_note", "content": note})
        return rows[-limit:]

    def crew_context(self, encounter_id: str | None = None, *, limit: int = 40) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for dossier in self._selected_dossiers(encounter_id):
            for fact in dossier.facts:
                if fact.visibility in {"crew", "public"}:
                    rows.append({"kind": "known_fact", "subject": fact.subject, "content": fact.content})
            for claim in dossier.claims:
                if claim.visibility in {"crew", "public"}:
                    rows.append({"kind": "claim", "speaker": claim.speaker, "content": claim.content})
        for expansion in self.document.expansions[-20:]:
            for fact in expansion.new_facts:
                if fact.visibility in {"crew", "public"}:
                    rows.append({"kind": "known_fact", "subject": fact.subject, "content": fact.content})
            for claim in expansion.new_claims:
                if claim.visibility in {"crew", "public"}:
                    rows.append({"kind": "claim", "speaker": claim.speaker, "content": claim.content})
        return rows[-limit:]

    def _selected_dossiers(self, encounter_id: str | None) -> list[SituationDossier]:
        if encounter_id and encounter_id in self.document.situations:
            return [self.document.situations[encounter_id]]
        return list(self.document.situations.values())[-6:]

    def counts(self) -> dict[str, int]:
        dossiers = list(self.document.situations.values())
        return {
            "situations": len(dossiers),
            "entities": sum(len(item.entities) for item in dossiers),
            "facts": sum(len(item.facts) for item in dossiers) + sum(len(item.new_facts) for item in self.document.expansions),
            "claims": sum(len(item.claims) for item in dossiers) + sum(len(item.new_claims) for item in self.document.expansions),
            "open_questions": sum(len(item.open_questions) for item in dossiers) + sum(len(item.new_questions) for item in self.document.expansions),
            "expansions": len(self.document.expansions),
        }
