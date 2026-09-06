from __future__ import annotations

import random
from typing import Any

from ..ai import AIOrchestrator, AIProvider
from ..session import GameSession, SessionManager, create_game_state
from .architect import UniverseArchitect
from .canon import NarrativeCanon
from .provider import LoreAwareProvider, narrative_provider_from_environment


class UniverseGodGameSession(GameSession):
    """GameSession with persistent AI-authored causal lore layered above physics."""

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
        self.narrative_provider = narrative_provider or narrative_provider_from_environment(provider)
        self.universe_architect = UniverseArchitect(self.narrative_provider, self.narrative_canon)
        self.ai = AIOrchestrator(LoreAwareProvider(provider, state, self.narrative_canon, self.universe_architect))

    async def _develop_encounter(self, encounter_id: str) -> None:
        encounter = self.state.current_encounter
        if encounter and encounter.id == encounter_id and encounter.status == "active":
            if self.narrative_canon.dossier(encounter_id) is None:
                dossier = await self.universe_architect.create_dossier(self.state, encounter.model_copy(deep=True))
                async with self.lock:
                    current = self.state.current_encounter
                    if current and current.id == encounter_id and current.status == "active":
                        if self.narrative_canon.dossier(encounter_id) is None:
                            self.narrative_canon.commit_dossier(encounter_id, dossier)
                            current.hidden_truth["narrative_dossier"] = {
                                "committed": True,
                                "entities": len(dossier.entities),
                                "facts": len(dossier.facts),
                                "questions": len(dossier.open_questions),
                                "evidence_routes": len(dossier.evidence),
                            }
                            event = self.engine.event(
                                "narrative_situation_established",
                                payload={
                                    "encounter_id": encounter_id,
                                    "entities": len(dossier.entities),
                                    "facts": len(dossier.facts),
                                    "claims": len(dossier.claims),
                                    "questions": len(dossier.open_questions),
                                    "evidence_routes": len(dossier.evidence),
                                },
                                targets=[encounter_id],
                                source_kind="approved_proposal",
                                source_id="universe_architect",
                                visibility="director",
                            )
                            self._persist([event])
        await super()._develop_encounter(encounter_id)

    def diagnostics(self) -> dict[str, Any]:
        return {
            **super().diagnostics(),
            "narrative_provider": self.narrative_provider.capabilities().name,
            "narrative_canon": self.narrative_canon.counts(),
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
