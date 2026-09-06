from __future__ import annotations

import asyncio
import random
from typing import Any

from ..ai import AIOrchestrator, AIProvider
from ..models import CanonicalEvent
from ..session import GameSession, SessionManager, create_game_state
from .architect import UniverseArchitect
from .canon import NarrativeCanon
from .discovery import DiscoveryTracker
from .evidence import NarrativeEvidenceResolver
from .provider import LoreAwareProvider, narrative_provider_from_environment
from .science import GenerativeScienceEngine, ScienceArchitect, ScientificCanon, ScientificRuntime
from .world import OffscreenWorldSimulator


class UniverseGodGameSession(GameSession):
    """GameSession with persistent AI-authored causal lore layered above physics."""

    WORLD_PLAN_TRIGGERS = {
        "narrative_evidence_discovered",
        "scientific_prediction_verified",
        "generated_scientific_capability_installed",
        "encounter_resolved",
        "remote_contact_exchange",
        "signal_reply_transmitted",
        "transmission_sent",
        "weapon_fired",
        "warning_shot_fired",
        "salvage_claimed",
    }

    def __init__(
        self,
        state,
        save_store,
        provider: AIProvider,
        session_id: str | None = None,
        narrative_provider: AIProvider | None = None,
    ):
        super().__init__(state, save_store, provider, session_id=session_id)
        self.narrative_canon = NarrativeCanon(save_store.root, state.universe_id)
        self.scientific_canon = ScientificCanon(save_store.root, state.universe_id)
        self.engine = GenerativeScienceEngine(state, self.scientific_canon)
        self.narrative_provider = narrative_provider or narrative_provider_from_environment(provider)
        self.discovery = DiscoveryTracker(self.narrative_canon)
        self.universe_architect = UniverseArchitect(self.narrative_provider, self.narrative_canon)
        self.science_architect = ScienceArchitect(self.narrative_provider, self.narrative_canon, self.scientific_canon)
        self.science_runtime = ScientificRuntime(self.scientific_canon)
        self.evidence_resolver = NarrativeEvidenceResolver(self.narrative_canon)
        self.offscreen_world = OffscreenWorldSimulator(self.narrative_canon)
        self.scheduled_world_plans: set[str] = set()
        self.ai = AIOrchestrator(LoreAwareProvider(provider, state, self.narrative_canon, self.universe_architect))
        if state.current_encounter and self.narrative_canon.dossier(state.current_encounter.id):
            self.discovery.ensure(state.current_encounter.id)
            self.discovery.sync_activity_board(state, state.current_encounter.id)

    async def _develop_encounter(self, encounter_id: str) -> None:
        encounter = self.state.current_encounter
        established_event: CanonicalEvent | None = None
        if encounter and encounter.id == encounter_id and encounter.status == "active":
            if self.narrative_canon.dossier(encounter_id) is None:
                dossier = await self.universe_architect.create_dossier(self.state, encounter.model_copy(deep=True))
                async with self.lock:
                    current = self.state.current_encounter
                    if current and current.id == encounter_id and current.status == "active":
                        if self.narrative_canon.dossier(encounter_id) is None:
                            self.narrative_canon.commit_dossier(encounter_id, dossier)
                            discovery_state = self.discovery.ensure(encounter_id)
                            self.discovery.sync_activity_board(self.state, encounter_id)
                            current.hidden_truth["narrative_dossier"] = {
                                "committed": True,
                                "entities": len(dossier.entities),
                                "facts": len(dossier.facts),
                                "questions": len(dossier.open_questions),
                                "evidence_routes": len(dossier.evidence),
                                "deep_discovery_shape": {
                                    "surface": bool(dossier.surface_interpretation),
                                    "deeper": bool(dossier.deeper_interpretation),
                                    "contradiction": bool(dossier.central_contradiction),
                                    "choice": bool(dossier.consequential_choice),
                                    "future_hook": bool(dossier.future_hook),
                                },
                            }
                            established_event = self.engine.event(
                                "narrative_situation_established",
                                payload={
                                    "encounter_id": encounter_id,
                                    "phase": discovery_state.phase,
                                    "entities": len(dossier.entities),
                                    "facts": len(dossier.facts),
                                    "claims": len(dossier.claims),
                                    "questions": len(dossier.open_questions),
                                    "evidence_routes": len(dossier.evidence),
                                    "contradiction_routes": sum(item.narrative_role == "contradiction" for item in dossier.evidence),
                                },
                                targets=[encounter_id],
                                source_kind="approved_proposal",
                                source_id="universe_architect",
                                visibility="director",
                            )
                            self._persist([established_event])

            current = self.state.current_encounter
            if (
                current
                and current.id == encounter_id
                and current.status == "active"
                and self.narrative_canon.dossier(encounter_id) is not None
                and self.scientific_canon.blueprint(encounter_id) is None
            ):
                state_snapshot = self.state.model_copy(deep=True)
                encounter_snapshot = current.model_copy(deep=True)
                blueprint = await self.science_architect.create_blueprint(state_snapshot, encounter_snapshot)
                if blueprint is not None:
                    async with self.lock:
                        active = self.state.current_encounter
                        if (
                            active
                            and active.id == encounter_id
                            and active.status == "active"
                            and self.scientific_canon.blueprint(encounter_id) is None
                            and self.scientific_canon.commit_blueprint(blueprint)
                        ):
                            active.hidden_truth["science_phenomenon"] = {
                                "committed": True,
                                "phenomenon_id": blueprint.id,
                                "novelty": blueprint.novelty,
                                "mechanics": [item.primitive for item in blueprint.mechanics],
                                "predictions": len(blueprint.predictions),
                                "generated_capability": blueprint.capability.name if blueprint.capability else None,
                            }
                            director_event = self.engine.event(
                                "scientific_phenomenon_authored",
                                payload={
                                    "phenomenon_id": blueprint.id,
                                    "encounter_id": encounter_id,
                                    "name": blueprint.name,
                                    "novelty": blueprint.novelty,
                                    "mechanics": [item.primitive for item in blueprint.mechanics],
                                    "predictions": len(blueprint.predictions),
                                },
                                targets=[encounter_id],
                                source_kind="approved_proposal",
                                source_id="science_architect",
                                visibility="director",
                            )
                            hook = f"Science anomaly: {blueprint.crew_hook}"
                            if hook not in self.state.crew_knowledge:
                                self.state.crew_knowledge.append(hook)
                            hook_event = self.engine.event(
                                "scientific_anomaly_detected",
                                payload={"phenomenon_id": blueprint.id, "observation": blueprint.crew_hook},
                                targets=[encounter_id, active.target_id],
                                source_kind="simulation",
                                source_id="scientific_runtime",
                                visibility="crew",
                                caused_by=[director_event.id],
                            )
                            self._persist([director_event, hook_event])
        if established_event and self.state.current_encounter:
            self._queue_world_plan(
                self.state.model_copy(deep=True),
                self.state.current_encounter.model_copy(deep=True),
                established_event,
                trigger="new narrative situation established",
            )
        await super()._develop_encounter(encounter_id)

    async def tick_once(self, dt: float) -> list[CanonicalEvent]:
        """Run physics, then deterministically reveal lore, science, and coarse actors."""
        async with self.lock:
            events = self.engine.tick(dt)
            evidence_events = self.evidence_resolver.resolve_scan_events(self.state, self.engine, events)
            events.extend(evidence_events)
            science_events = self.science_runtime.process_events(self.state, self.engine, list(events))
            events.extend(science_events)
            world_events = self.offscreen_world.execute_due(self.state, self.engine)
            events.extend(world_events)
            encounter = self.state.current_encounter
            if encounter and self.narrative_canon.dossier(encounter.id):
                for event in events:
                    self.discovery.mark_event(encounter.id, event.event_type)
                self.discovery.sync_activity_board(self.state, encounter.id)
            if events:
                self._persist(events)
        if events:
            await self.broadcast()
            self._schedule_milestones(events)
            if any(event.event_type == "system_entered" for event in events) and self.state.current_encounter:
                self._schedule_director(self.state.current_encounter.id)
        return events

    def _schedule_milestones(self, events: list[CanonicalEvent]) -> None:
        super()._schedule_milestones(events)
        encounter = self.state.current_encounter
        if not encounter or self.narrative_canon.dossier(encounter.id) is None:
            return
        for event in events:
            self.discovery.mark_event(encounter.id, event.event_type)
        self.discovery.sync_activity_board(self.state, encounter.id)
        for event in events:
            if event.event_type not in self.WORLD_PLAN_TRIGGERS:
                continue
            key = f"world-plan:{event.id}"
            if key in self.scheduled_world_plans:
                continue
            self.scheduled_world_plans.add(key)
            self._queue_world_plan(
                self.state.model_copy(deep=True),
                encounter.model_copy(deep=True),
                event.model_copy(deep=True),
                trigger=f"canonical event {event.event_type}",
                key=key,
            )

    def _queue_world_plan(
        self,
        state_snapshot,
        encounter_snapshot,
        event: CanonicalEvent,
        *,
        trigger: str,
        key: str | None = None,
    ) -> None:
        task = asyncio.create_task(
            self._plan_world_response(state_snapshot, encounter_snapshot, event, trigger=trigger),
            name=f"world-plan-{event.id}",
        )
        self.ai_tasks.add(task)
        task.add_done_callback(self.ai_tasks.discard)
        if key:
            task.add_done_callback(lambda _task, plan_key=key: self.scheduled_world_plans.discard(plan_key))

    async def _plan_world_response(
        self,
        state_snapshot,
        encounter_snapshot,
        event: CanonicalEvent,
        *,
        trigger: str,
    ) -> None:
        intents = await self.universe_architect.plan_world_intentions(
            state_snapshot,
            encounter_snapshot,
            trigger=trigger,
            recent_events=[{
                "event_type": event.event_type,
                "payload": event.payload,
                "universe_time_ms": event.universe_time_ms,
            }],
        )
        if not intents:
            return
        async with self.lock:
            added = self.narrative_canon.schedule_intents(intents)
            if not added:
                return
            scheduled = [intent for intent in intents if intent.id in self.narrative_canon.document.scheduled_intents]
            plan_event = self.engine.event(
                "offscreen_world_intentions_scheduled",
                payload={
                    "trigger_event_id": event.id,
                    "trigger": trigger,
                    "count": added,
                    "intent_ids": [intent.id for intent in scheduled],
                    "execute_at_ms": [intent.execute_at_ms for intent in scheduled],
                },
                targets=[encounter_snapshot.id],
                source_kind="approved_proposal",
                source_id="universe_architect",
                visibility="director",
                caused_by=[event.id],
            )
            self._persist([plan_event])

    def diagnostics(self) -> dict[str, Any]:
        encounter_id = self.state.current_encounter.id if self.state.current_encounter else None
        return {
            **super().diagnostics(),
            "narrative_provider": self.narrative_provider.capabilities().name,
            "narrative_canon": self.narrative_canon.counts(),
            "scientific_canon": self.scientific_canon.counts(),
            "deep_discovery": self.discovery.phase_context(encounter_id) if encounter_id and self.narrative_canon.dossier(encounter_id) else None,
            "discovery_board": self.discovery.crew_board(encounter_id) if encounter_id and self.narrative_canon.dossier(encounter_id) else None,
        }


class UniverseGodSessionManager(SessionManager):
    """Drop-in SessionManager that constructs UniverseGodGameSession instances."""

    def __init__(self, saves_root, provider: AIProvider | None = None):
        super().__init__(saves_root, provider=provider)
        self.narrative_provider = narrative_provider_from_environment(self.provider)

    def create_universe(self, **kwargs: Any) -> UniverseGodGameSession:
        if "seed" not in kwargs or kwargs["seed"] is None:
            kwargs["seed"] = random.SystemRandom().randrange(1, 2**63)
        state = create_game_state(**kwargs)
        session = UniverseGodGameSession(state, self.store, self.provider, narrative_provider=self.narrative_provider)
        self.store.initialize(state, session.id)
        initial_events = [
            session.engine.event(
                "universe_created",
                payload={"name": state.universe_name, "seed": state.seed},
                targets=[state.universe_id, state.ship.id],
                source_kind="host_action",
                visibility="public",
            ),
            session.engine.event(
                "encounter_detected",
                payload={"summary": state.current_encounter.public_summary if state.current_encounter else ""},
                targets=[state.current_encounter.id] if state.current_encounter else [],
                source_kind="simulation",
            ),
        ]
        initial_events.extend(session.engine.auto_acquire_detected_signal())
        if state.scenario_preset == "friendly_contact_test" and state.current_encounter and state.signal_analysis:
            initial_events.append(session.engine.event(
                "friendly_contact_test_initialized",
                payload={
                    "frequency_mhz": state.signal_analysis.tuned_frequency_mhz,
                    "opening_translation": state.signal_analysis.interpretation,
                    "contact_window_s": state.current_encounter.deadline_s,
                },
                targets=[state.current_encounter.id],
                source_kind="host_action",
                visibility="crew",
            ))
        self.store.commit(state, initial_events, session.id)
        self.sessions[session.id] = session
        session.start()
        return session

    def load_universe(self, universe_id: str) -> UniverseGodGameSession:
        for session in self.sessions.values():
            if session.state.universe_id == universe_id:
                return session  # type: ignore[return-value]
        state = self.store.load(universe_id)
        session = UniverseGodGameSession(state, self.store, self.provider, narrative_provider=self.narrative_provider)
        migration_events = session.engine.migrate_loaded_state()
        if migration_events:
            self.store.commit(state, migration_events, session.id)
        self.sessions[session.id] = session
        session.start()
        return session
