from __future__ import annotations

import re
from typing import Any

from ..models import GameState
from .canon import NarrativeCanon
from .models import DiscoveryState, DossierEvidence


_PHASE_ORDER = {
    "hook": 0,
    "investigation": 1,
    "contradiction": 2,
    "reinterpretation": 3,
    "decision": 4,
    "aftermath": 5,
}

_STOPWORDS = {
    "about", "after", "again", "also", "because", "before", "being", "could", "does", "from",
    "have", "into", "just", "more", "much", "only", "other", "should", "some", "than", "that",
    "their", "them", "then", "there", "these", "they", "this", "those", "through", "what", "when",
    "where", "which", "while", "with", "would", "your", "you", "ours", "were", "been", "tell",
    "explain", "please", "really", "said", "says", "saying", "know", "think", "want", "why", "how",
}

_CONFRONTATION_MARKERS = (
    "our scan", "our scans", "the scan", "evidence", "we found", "we detected", "we measured",
    "you said", "you told", "doesn't match", "does not match", "contradict", "conflict", "but you",
    "that can't be", "that cannot be", "wrong about", "lied", "lying", "proof", "records show",
)


class DiscoveryTracker:
    """Deterministic narrative pacing and player-interest state.

    The model authors the hidden situation. This tracker decides only what the
    crew has actually reached in the discovery arc based on conversations,
    observations, and canonical events. It never invents facts.
    """

    def __init__(self, canon: NarrativeCanon):
        self.canon = canon

    def ensure(self, encounter_id: str) -> DiscoveryState:
        existing = self.canon.document.discovery_states.get(encounter_id)
        if existing:
            return existing
        dossier = self.canon.dossier(encounter_id)
        state = DiscoveryState(
            encounter_id=encounter_id,
            surface_interpretation=dossier.surface_interpretation if dossier else "",
            deeper_interpretation=dossier.deeper_interpretation if dossier else "",
            central_contradiction=dossier.central_contradiction if dossier else "",
            consequential_choice=dossier.consequential_choice if dossier else "",
            future_hook=dossier.future_hook if dossier else "",
        )
        self.canon.document.discovery_states[encounter_id] = state
        self.canon.save()
        return state

    def record_player_message(self, encounter_id: str, message: str, npc_name: str | None = None) -> DiscoveryState:
        state = self.ensure(encounter_id)
        text = " ".join(message.split())[:1200]
        if npc_name and npc_name not in state.contacted_actors:
            state.contacted_actors.append(npc_name)
            state.contacted_actors = state.contacted_actors[-24:]
        if text:
            if "?" in text or self._looks_inquisitive(text):
                state.recent_questions.append(text[:400])
                state.recent_questions = state.recent_questions[-20:]
            for topic in self._topics(text):
                state.interest_topics[topic] = min(99, state.interest_topics.get(topic, 0) + 1)
            state.interest_topics = dict(
                sorted(state.interest_topics.items(), key=lambda item: (-item[1], item[0]))[:24]
            )
        if state.phase == "hook":
            state.phase = "investigation"
        if self.is_evidence_confrontation(text, encounter_id):
            state.confrontation_count += 1
            if state.contradictions:
                state.phase = "reinterpretation"
                if len(state.discovered_evidence_ids) >= 2:
                    state.phase = "decision"
                    state.decision_available = True
        self.canon.document.discovery_states[encounter_id] = state
        self.canon.save()
        return state

    def record_evidence(self, encounter_id: str, evidence_id: str) -> DiscoveryState:
        state = self.ensure(encounter_id)
        evidence = self._evidence_by_id(encounter_id, evidence_id)
        if evidence_id not in state.discovered_evidence_ids:
            state.discovered_evidence_ids.append(evidence_id)
            state.discovered_evidence_ids = state.discovered_evidence_ids[-24:]
        if evidence and evidence.narrative_role == "contradiction":
            contradiction = evidence.reveals[0] if evidence.reveals else evidence.description
            if contradiction not in state.contradictions:
                state.contradictions.append(contradiction[:700])
                state.contradictions = state.contradictions[-12:]
            state.phase = "contradiction"
        elif state.phase == "hook":
            state.phase = "investigation"
        if len(state.discovered_evidence_ids) >= 2 and state.contradictions:
            state.phase = "reinterpretation"
            if state.confrontation_count > 0:
                state.phase = "decision"
                state.decision_available = True
        self.canon.document.discovery_states[encounter_id] = state
        self.canon.save()
        return state

    def mark_event(self, encounter_id: str, event_type: str) -> DiscoveryState:
        state = self.ensure(encounter_id)
        if event_type in {"encounter_resolved", "consequence_chosen"}:
            state.phase = "aftermath"
            state.decision_available = False
        self.canon.document.discovery_states[encounter_id] = state
        self.canon.save()
        return state

    def phase_context(self, encounter_id: str) -> dict[str, Any]:
        state = self.ensure(encounter_id)
        return {
            "phase": state.phase,
            "evidence_count": len(state.discovered_evidence_ids),
            "contradictions_found": len(state.contradictions),
            "contacted_actors": state.contacted_actors[-8:],
            "recent_questions": state.recent_questions[-6:],
            "top_interests": self.top_interests(encounter_id),
            "decision_available": state.decision_available,
        }

    def top_interests(self, encounter_id: str, limit: int = 6) -> list[str]:
        state = self.ensure(encounter_id)
        return [topic for topic, _ in sorted(state.interest_topics.items(), key=lambda item: (-item[1], item[0]))[:limit]]

    def discovered_evidence_context(self, encounter_id: str) -> list[dict[str, Any]]:
        return [
            {
                "evidence_id": item.evidence_id,
                "instrument": item.instrument_name,
                "description": item.description,
                "reveals": item.reveals,
                "confidence": item.confidence,
            }
            for item in self.canon.document.evidence_discoveries.values()
            if item.encounter_id == encounter_id
        ][-12:]

    def is_evidence_confrontation(self, message: str, encounter_id: str) -> bool:
        text = " ".join(message.lower().split())
        if not text:
            return False
        if any(marker in text for marker in _CONFRONTATION_MARKERS):
            return bool(self.discovered_evidence_context(encounter_id))
        discoveries = self.discovered_evidence_context(encounter_id)
        evidence_terms: set[str] = set()
        for item in discoveries:
            evidence_terms.update(self._topics(item["description"]))
            for reveal in item["reveals"]:
                evidence_terms.update(self._topics(str(reveal)))
        mentioned = sum(1 for term in evidence_terms if term in text)
        return mentioned >= 2 and bool(discoveries)

    def crew_board(self, encounter_id: str) -> dict[str, Any]:
        state = self.ensure(encounter_id)
        dossier = self.canon.dossier(encounter_id)
        known: list[str] = []
        claims: list[str] = []
        questions: list[str] = []
        if dossier:
            if state.surface_interpretation:
                known.append(state.surface_interpretation)
            known.extend(f"{fact.subject}: {fact.content}" for fact in dossier.facts if fact.visibility in {"crew", "public"})
            claims.extend(f"{claim.speaker}: {claim.content}" for claim in dossier.claims if claim.visibility in {"crew", "public"})
            if state.phase != "hook":
                questions.extend(question.question for question in dossier.open_questions)
        for expansion in self.canon.document.expansions:
            if expansion.encounter_id != encounter_id:
                continue
            known.extend(f"{fact.subject}: {fact.content}" for fact in expansion.new_facts if fact.visibility in {"crew", "public"})
            claims.extend(f"{claim.speaker}: {claim.content}" for claim in expansion.new_claims if claim.visibility in {"crew", "public"})
            if state.phase != "hook":
                questions.extend(question.question for question in expansion.new_questions)
        for item in self.canon.document.evidence_discoveries.values():
            if item.encounter_id != encounter_id:
                continue
            known.append(item.description)
            known.extend(str(reveal) for reveal in item.reveals)
        known = self._unique(known)
        claims = self._unique(claims)
        questions = self._unique(questions)
        contradictions = self._unique(state.contradictions)
        stakes = ""
        if state.decision_available and state.consequential_choice:
            stakes = state.consequential_choice
        elif dossier and dossier.immediate_stakes and state.phase in {"reinterpretation", "decision", "aftermath"}:
            stakes = dossier.immediate_stakes
        return {
            "phase": state.phase,
            "known": known[-8:],
            "claims": claims[-6:],
            "contradictions": contradictions[-6:],
            "open_questions": questions[-8:],
            "stakes": stakes,
            "top_interests": self.top_interests(encounter_id),
            "decision_available": state.decision_available,
        }

    def sync_activity_board(self, game_state: GameState, encounter_id: str) -> None:
        board = self.crew_board(encounter_id)
        thread = next(
            (
                item for item in game_state.world_threads
                if any(entry.get("encounter_id") == encounter_id for entry in item.history)
            ),
            None,
        )
        if not thread:
            return
        known = board["known"][-1] if board["known"] else "No evidence-backed fact established yet."
        claim = board["claims"][-1] if board["claims"] else "No explicit testimony recorded as crew-visible canon."
        contradiction = board["contradictions"][-1] if board["contradictions"] else "None established."
        unanswered = board["open_questions"][0] if board["open_questions"] else "Continue investigating what does not yet fit."
        stakes = board["stakes"] or "The consequences are not yet understood."
        thread.summary = (
            f"DISCOVERY PHASE: {str(board['phase']).upper()} · "
            f"KNOWN: {known} · CLAIM: {claim} · CONTRADICTION: {contradiction} · "
            f"UNANSWERED: {unanswered} · STAKES: {stakes}"
        )[:1800]

    @staticmethod
    def _looks_inquisitive(text: str) -> bool:
        lowered = text.lower().lstrip()
        return lowered.startswith(("why ", "how ", "what ", "who ", "where ", "when ", "tell me", "explain "))

    @staticmethod
    def _topics(text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z'-]{3,}", text.lower())
        return [word for word in words if word not in _STOPWORDS][:16]

    def _evidence_by_id(self, encounter_id: str, evidence_id: str) -> DossierEvidence | None:
        dossier = self.canon.dossier(encounter_id)
        if dossier:
            found = next((item for item in dossier.evidence if item.id == evidence_id), None)
            if found:
                return found
        for expansion in self.canon.document.expansions:
            if expansion.encounter_id != encounter_id:
                continue
            found = next((item for item in expansion.new_evidence if item.id == evidence_id), None)
            if found:
                return found
        return None

    @staticmethod
    def _unique(items: list[str]) -> list[str]:
        seen: set[str] = set()
        rows: list[str] = []
        for item in items:
            normalized = " ".join(item.lower().split())
            if not item.strip() or normalized in seen:
                continue
            seen.add(normalized)
            rows.append(" ".join(item.split())[:800])
        return rows
