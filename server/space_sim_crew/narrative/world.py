from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import CanonicalEvent, GameState, WorldThread
from .canon import NarrativeCanon
from .models import DossierClaim, DossierFact, LoreExpansion, ScheduledWorldIntent

if TYPE_CHECKING:
    from ..simulation import SimulationEngine


class OffscreenWorldSimulator:
    """Executes due Universe God intentions as bounded canonical consequences.

    This is intentionally a coarse simulation. It may change social state,
    communications, knowledge, and narrative threads. It cannot set coordinates,
    damage, cargo, power, or any other physical simulation field.
    """

    def __init__(self, canon: NarrativeCanon):
        self.canon = canon

    def execute_due(self, state: GameState, engine: "SimulationEngine") -> list[CanonicalEvent]:
        events: list[CanonicalEvent] = []
        for intent in self.canon.due_intents(state.universe_time_ms):
            if intent.requires_departure and state.ship.system_id == intent.origin_system_id:
                continue
            event = self._execute(intent, state, engine)
            if event:
                events.append(event)
        return events

    def _execute(
        self,
        intent: ScheduledWorldIntent,
        state: GameState,
        engine: "SimulationEngine",
    ) -> CanonicalEvent | None:
        npc = next(
            (item for item in state.known_npcs.values() if item.name.lower() == intent.actor.lower()),
            None,
        )
        payload = {
            "intent_id": intent.id,
            "actor": intent.actor,
            "action": intent.action,
            "summary": intent.summary,
            "reason": intent.reason,
        }

        if intent.action == "send_message":
            message = (intent.message or intent.summary).strip()[:1200]
            if not message:
                return self._cancel(intent)
            if npc:
                npc.known_messages.append(f"{npc.name}: {message}")
                npc.known_messages = npc.known_messages[-80:]
                npc.memories.append({
                    "time_ms": state.universe_time_ms,
                    "event": "sent delayed message to crew",
                    "summary": message[:300],
                })
                npc.memories = npc.memories[-50:]
                state.known_npcs[npc.id] = npc
                state.message_log.append({
                    "time_ms": state.universe_time_ms,
                    "speaker": npc.name + " · distant",
                    "message": message,
                })
            else:
                state.message_log.append({
                    "time_ms": state.universe_time_ms,
                    "speaker": intent.actor + " · distant",
                    "message": message,
                })
            payload["message"] = message

        elif intent.action == "create_lead":
            existing = next(
                (
                    thread for thread in state.world_threads
                    if thread.summary == intent.summary and thread.origin_system_id == intent.origin_system_id
                ),
                None,
            )
            if not existing:
                related_thread = next(
                    (thread for thread in state.world_threads if npc and thread.npc_id == npc.id),
                    None,
                )
                lead = WorldThread(
                    title=f"Lead from {intent.actor}",
                    kind="consequence",
                    summary=intent.summary,
                    origin_system_id=intent.origin_system_id,
                    npc_id=npc.id if npc else None,
                    remote_frequency_mhz=related_thread.remote_frequency_mhz if related_thread else None,
                    next_actions=[],
                    history=[{
                        "time_ms": state.universe_time_ms,
                        "event": "off-screen development created lead",
                        "intent_id": intent.id,
                    }],
                )
                state.world_threads.append(lead)
                payload["thread_id"] = lead.id

        elif intent.action == "relationship_shift":
            if not npc:
                return self._cancel(intent)
            npc.disposition = min(1.0, max(-1.0, npc.disposition + intent.relationship_delta))
            npc.visible_reason = (intent.reason or intent.summary)[:300]
            if intent.relationship_delta >= 0.1:
                npc.relationship_label = "increasingly trusting contact"
            elif intent.relationship_delta <= -0.1:
                npc.relationship_label = "increasingly wary contact"
            npc.memories.append({
                "time_ms": state.universe_time_ms,
                "event": "off-screen relationship changed",
                "summary": intent.summary[:300],
            })
            npc.memories = npc.memories[-50:]
            state.known_npcs[npc.id] = npc
            payload["disposition"] = npc.disposition
            payload["relationship_label"] = npc.relationship_label

        elif intent.action == "record_claim":
            content = intent.content.strip()[:800]
            if not content:
                return self._cancel(intent)
            expansion = LoreExpansion(
                encounter_id=intent.encounter_id,
                question=f"World development {intent.id}",
                new_claims=[DossierClaim(
                    speaker=intent.actor,
                    content=content,
                    believes_claim=True,
                    visibility=intent.visibility,
                )],
                summary=intent.summary,
            )
            self.canon.commit_expansion(expansion)
            payload["claim"] = content

        elif intent.action == "record_fact":
            content = intent.content.strip()[:800]
            if not content:
                return self._cancel(intent)
            expansion = LoreExpansion(
                encounter_id=intent.encounter_id,
                question=f"World development {intent.id}",
                new_facts=[DossierFact(
                    subject=(intent.subject or intent.actor)[:120],
                    content=content,
                    visibility="director",
                    known_by=[intent.actor],
                )],
                summary=intent.summary,
            )
            self.canon.commit_expansion(expansion)
            payload["fact_committed"] = True

        elif intent.action == "change_status":
            if not npc:
                return self._cancel(intent)
            npc.visible_activity = (intent.content or intent.summary)[:240]
            npc.visible_reason = (intent.reason or "The actor's circumstances changed while the crew was away.")[:300]
            npc.last_action = "offscreen_status_change"
            npc.memories.append({
                "time_ms": state.universe_time_ms,
                "event": "off-screen status changed",
                "summary": intent.summary[:300],
            })
            npc.memories = npc.memories[-50:]
            state.known_npcs[npc.id] = npc
            payload["visible_activity"] = npc.visible_activity

        else:
            return self._cancel(intent)

        intent.status = "executed"
        intent.executed_at_ms = state.universe_time_ms
        self.canon.update_intent(intent)
        if intent.visibility in {"crew", "public"}:
            knowledge = f"World development — {intent.actor}: {intent.summary}"
            if knowledge not in state.crew_knowledge:
                state.crew_knowledge.append(knowledge)
                state.crew_knowledge = state.crew_knowledge[-300:]
        return engine.event(
            "offscreen_world_intent_executed",
            payload=payload,
            actors=[npc.id] if npc else [],
            targets=[intent.encounter_id],
            source_kind="approved_proposal",
            source_id=intent.id,
            visibility=intent.visibility,
        )

    def _cancel(self, intent: ScheduledWorldIntent) -> None:
        intent.status = "cancelled"
        self.canon.update_intent(intent)
        return None
