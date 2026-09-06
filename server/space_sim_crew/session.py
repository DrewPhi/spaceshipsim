from __future__ import annotations

import asyncio
import contextlib
import random
import time
from pathlib import Path
from typing import Any

from fastapi import WebSocket

from .ai import AIOrchestrator, AIProvider, provider_from_environment
from .generation import generate_encounter, generate_friendly_contact_encounter, generate_system
from .models import (
    Capability,
    CanonicalEvent,
    CharacterState,
    EncounterState,
    GameState,
    PlayerCommand,
    PlayerConnection,
    SignalAnalysisState,
    ShipState,
    StationRole,
    WorldThread,
    new_id,
)
from .persistence import SaveStore
from .simulation import CommandError, SimulationEngine
from .signal_processing import validate_signal_recipe


def create_game_state(
    *,
    universe_name: str,
    seed: int,
    ship_name: str,
    crew_capacity: int,
    character_name: str,
    backstory: str,
    scenario_preset: str = "random",
) -> GameState:
    origin = generate_system(seed, (0, 0))
    origin.visited = True
    ship = ShipState(
        name=ship_name,
        frame={1: "Autonomous Survey Cutter", 2: "Compact Survey Craft", 3: "Light Expedition Vessel"}.get(
            min(crew_capacity, 3), "Expedition Vessel"
        ),
        crew_capacity=max(1, crew_capacity),
        system_id=origin.id,
        capabilities=[
            Capability(
                id=new_id("cap"),
                name="Composition and Temperature Scan",
                category="hardware",
                power_mw=80,
                input_domains=["electromagnetic", "particle"],
                output_domains=["composition", "temperature", "signal"],
                description="Use on planets, structures, debris, and vessels to identify materials, temperature, and broad electromagnetic emissions.",
            ),
            Capability(
                id=new_id("cap"),
                name="Radiation Hazard Scan",
                category="hardware",
                power_mw=46,
                input_domains=["particle", "radiation"],
                output_domains=["flux", "periodicity", "hazard"],
                description="Use to measure radiation, charged particles, energetic pulses, and whether local conditions threaten the ship.",
            ),
            Capability(
                id=new_id("cap"),
                name="Signal Direction Scan",
                category="hardware",
                power_mw=62,
                input_domains=["field", "gravity"],
                output_domains=["gradient", "coherence", "phase"],
                description="Use on an encounter signal to measure its bearing. Scan again after moving to triangulate the source position.",
            ),
            Capability(
                id=new_id("cap"),
                name="Vessel Systems and Weapons Scan",
                category="hardware",
                power_mw=70,
                input_domains=["electromagnetic", "thermal", "radar"],
                output_domains=["vessel_systems", "weapons", "defenses"],
                description="Use on a detected vessel to estimate propulsion, power generation, defensive systems, and possible weapons.",
            ),
            Capability(
                id=new_id("cap"),
                name="Universal Translator",
                category="software",
                power_mw=18,
                input_domains=["signal", "language"],
                output_domains=["translation", "confidence"],
                description="Converts stable decoded symbols into plain-language interpretations with explicit confidence.",
            ),
            Capability(
                id=new_id("cap"),
                name="Focused Energy Projector",
                category="hardware",
                power_mw=160,
                input_domains=["electrical", "target_track"],
                output_domains=["directed_energy", "damage"],
                description="A rechargeable line-of-sight weapon. Accurate at long range when Sensors provides a strong fire-control track.",
            ),
            Capability(
                id=new_id("cap"),
                name="Kinetic Interceptor",
                category="hardware",
                power_mw=90,
                input_domains=["electrical", "ammunition", "target_track"],
                output_domains=["kinetic_impact", "damage"],
                description="Launches a finite guided interceptor. Higher impact than the energy projector but less effective at long range.",
            ),
        ],
    )
    character = CharacterState(name=character_name, backstory=backstory)
    state = GameState(
        universe_name=universe_name,
        seed=seed,
        ship=ship,
        characters=[character],
        systems={origin.id: origin},
        scenario_preset="friendly_contact_test" if scenario_preset == "friendly_contact_test" else "random",
    )
    state.current_encounter = generate_friendly_contact_encounter(seed, origin) if state.scenario_preset == "friendly_contact_test" else generate_encounter(seed, origin)
    if state.current_encounter.npc:
        state.known_npcs[state.current_encounter.npc.id] = state.current_encounter.npc.model_copy(deep=True)
    state.world_threads.append(_thread_for_encounter(state.current_encounter, origin.id))
    if state.scenario_preset == "friendly_contact_test":
        encounter = state.current_encounter
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), seed, encounter.family)
        frequency = round(float(recipe["center_frequency_mhz"]), 5)
        state.signal_analysis = SignalAnalysisState(
            encounter_id=encounter.id,
            acquired=True,
            tuned_frequency_mhz=frequency,
            structure_result="structured_carrier",
            structure_confidence=.98,
            demodulation_method="amplitude",
            demodulation_confidence=.97,
            symbol_preview="01000111 01110010 01100101 01100101 01110100 01101001 01101110 01100111 01110011",
            interpretation=str(recipe["payload"]),
            interpretation_confidence=.96,
            translation_status="translated",
            translation_protocol="binary framed / amplitude modulation",
            translation_notes="The preset begins with a clean, stable greeting so repeated conversation can be tested immediately.",
            processing_log=[
                {"time_ms": 0, "station": "communications", "operation": "automatic carrier detection and recording", "frequency_mhz": frequency},
                {"time_ms": 0, "station": "communications", "operation": "preset universal translation", "confidence": .96},
            ],
        )
        state.message_log.append({"time_ms": 0, "speaker": "Universal Translator · Contact Liaison", "message": str(recipe["payload"])})
    return state


def _thread_for_encounter(encounter: EncounterState, system_id: str) -> WorldThread:
    actions = {
        "ordinary_survey": ["Run a close survey", "Collect a documented sample", "Publish the finding"],
        "artificial_signal": ["Localize and decode the signal", "Establish contact", "Trace the source"],
        "damaged_vessel": ["Assess vessel damage", "Offer technical assistance", "Stabilize the vessel"],
        "environmental_hazard": ["Measure the disturbance", "Plot a safe route", "Protect nearby traffic"],
        "disputed_boundary": ["Identify your vessel", "Negotiate passage", "Record the agreement"],
        "ancient_site": ["Map the structure", "Estimate its age", "Recover a documented sample"],
    }[encounter.family]
    kind = {
        "ordinary_survey": "discovery",
        "artificial_signal": "mystery",
        "damaged_vessel": "contact",
        "environmental_hazard": "hazard",
        "disputed_boundary": "contact",
        "ancient_site": "mystery",
    }[encounter.family]
    return WorldThread(
        title=encounter.title,
        kind=kind,  # type: ignore[arg-type]
        summary=encounter.public_summary,
        origin_system_id=system_id,
        npc_id=encounter.npc.id if encounter.npc else None,
        next_actions=actions,
        history=[{"time_ms": 0, "event": "encounter detected", "encounter_id": encounter.id}],
    )


class GameSession:
    def __init__(
        self,
        state: GameState,
        save_store: SaveStore,
        provider: AIProvider,
        session_id: str | None = None,
    ):
        self.id = session_id or new_id("session")
        self.state = state
        self.engine = SimulationEngine(state)
        self.store = save_store
        self.ai = AIOrchestrator(provider)
        self.connections: dict[str, PlayerConnection] = {}
        self.sockets: dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()
        self.task: asyncio.Task[None] | None = None
        self.started_at = time.monotonic()
        self.last_checkpoint = time.monotonic()
        self.last_tick = time.monotonic()
        self.last_events: list[CanonicalEvent] = []
        self.last_broadcast = time.monotonic()
        self.ai_tasks: set[asyncio.Task[None]] = set()
        self.scheduled_director_milestones: set[str] = set()
        self.send_lock = asyncio.Lock()

    def start(self) -> None:
        if not self.task or self.task.done():
            self.last_tick = time.monotonic()
            self.task = asyncio.create_task(self._run(), name=f"simulation-{self.id}")
            if self.state.current_encounter and self.state.current_encounter.hidden_truth.get("preset") != "friendly_contact_test" and "director_detail" not in self.state.current_encounter.hidden_truth:
                self._schedule_director(self.state.current_encounter.id)

    async def stop(self) -> None:
        for ai_task in self.ai_tasks:
            ai_task.cancel()
        if self.ai_tasks:
            await asyncio.gather(*self.ai_tasks, return_exceptions=True)
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        async with self.lock:
            self.store.commit(self.state, [], self.id)

    def join(self, display_name: str, character_id: str, station: StationRole) -> PlayerConnection:
        if not any(char.id == character_id for char in self.state.characters):
            raise CommandError("character does not exist in this universe")
        connection = PlayerConnection(display_name=display_name, character_id=character_id, station=station)
        self.connections[connection.token] = connection
        return connection

    async def attach(self, token: str, websocket: WebSocket) -> PlayerConnection:
        connection = self.connection(token)
        connection.connected = True
        connection.disconnected_at_monotonic = None
        self.sockets[token] = websocket
        await self.send_to(token, {"type": "snapshot", "sequence": self.state.event_count, "data": self.engine.station_projection(connection.station)})
        return connection

    async def send_to(self, token: str, payload: dict[str, Any]) -> None:
        socket = self.sockets[token]
        async with self.send_lock:
            await socket.send_json(payload)

    def detach(self, token: str) -> None:
        if token in self.connections:
            self.connections[token].connected = False
            self.connections[token].disconnected_at_monotonic = time.monotonic()
        self.sockets.pop(token, None)

    def connection(self, token: str) -> PlayerConnection:
        try:
            connection = self.connections[token]
        except KeyError as exc:
            raise CommandError("invalid session token") from exc
        if connection.disconnected_at_monotonic is not None and time.monotonic() - connection.disconnected_at_monotonic > 120:
            self.connections.pop(token, None)
            raise CommandError("session token reconnect grace period expired")
        return connection

    async def command(self, token: str, payload: dict[str, Any]) -> list[CanonicalEvent]:
        connection = self.connection(token)
        sequence = int(payload.get("client_sequence", 0))
        if sequence <= connection.last_client_sequence:
            raise CommandError("stale or duplicate client sequence")
        connection.last_client_sequence = sequence
        command_type = str(payload.get("command_type", ""))
        parameters = payload.get("parameters") or {}
        if not isinstance(parameters, dict):
            raise CommandError("parameters must be an object")
        command = PlayerCommand(
            session_id=self.id,
            player_id=connection.player_id,
            character_id=connection.character_id,
            station=connection.station,
            client_sequence=sequence,
            command_type=command_type,
            parameters=parameters,
        )
        async with self.lock:
            if command_type == "transmit":
                events = await self._transmit(command)
            elif command_type == "send_signal_reply":
                events = await self._signal_reply(command)
            elif command_type == "reply_remote_contact":
                events = await self._reply_remote_contact(command)
            elif command_type == "ask_computer":
                events = await self._ask_computer(command)
            else:
                events = self.engine.apply_command(command)
            self._persist(events)
        await self.broadcast()
        self._schedule_milestones(events)
        return events

    async def _signal_reply(self, command: PlayerCommand) -> list[CanonicalEvent]:
        encounter, analysis, player_message, _ = self.engine._validate_signal_reply(command)
        incoming, proposal = await self.ai.signal_contact_response(encounter, analysis.interpretation, player_message)
        return self.engine.commit_signal_reply(
            command,
            incoming,
            proposal_id=proposal.id,
            tone=str(proposal.parameters.get("tone", "unclear")),
            proposal_parameters=proposal.parameters,
        )

    async def _reply_remote_contact(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self.engine._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS, StationRole.COMMAND})
        if self.state.ship.power.communications < .03:
            raise CommandError("allocate at least 3% power to Communications")
        thread = next((t for t in self.state.world_threads if t.id == command.parameters.get("thread_id")), None)
        if not thread or thread.remote_frequency_mhz is None or thread.origin_system_id == self.state.ship.system_id or thread.npc_id not in self.state.known_npcs:
            raise CommandError("this remote channel is unavailable")
        message = str(command.parameters.get("message", "")).strip()[:2000]
        try:
            frequency = float(command.parameters.get("frequency_mhz", 0))
        except (TypeError, ValueError):
            raise CommandError("enter the remote channel frequency") from None
        import math
        if not message or not math.isfinite(frequency) or abs(frequency - thread.remote_frequency_mhz) > .05:
            raise CommandError("enter a message and the displayed remote channel frequency")
        npc = self.state.known_npcs[thread.npc_id]
        # A detached conversation context prevents remote dialogue from moving or damaging local vessels.
        context = EncounterState(family="disputed_boundary", title=thread.title, target_id=npc.id, public_summary="Remote radio conversation across different systems. Acknowledge and discuss messages only; no local approach, weapons, or physical actions can occur over this channel.", npc=npc.model_copy(deep=True))
        incoming, proposal = await self.ai.npc_response(context, message, remote=True)
        incoming = incoming.strip()[:4000]
        npc.known_messages.extend([f"Crew: {message}", f"{npc.name}: {incoming}"])
        self.state.message_log.extend([{"time_ms": self.state.universe_time_ms, "speaker": "crew · remote", "message": message}, {"time_ms": self.state.universe_time_ms, "speaker": npc.name + " · remote", "message": incoming}])
        thread.status = "resolved"
        thread.next_actions = []
        thread.history.append({"time_ms": self.state.universe_time_ms, "event": "remote reply received", "proposal_id": proposal.id})
        return [self.engine.event("remote_contact_exchange", payload={"thread_id": thread.id, "frequency_mhz": frequency, "message": message, "response": incoming}, actors=[command.character_id, npc.id], targets=[thread.id], source_kind="approved_proposal", source_id=proposal.id)]

    async def _transmit(self, command: PlayerCommand) -> list[CanonicalEvent]:
        if command.station not in {StationRole.INTEGRATED, StationRole.COMMUNICATIONS, StationRole.COMMAND}:
            raise CommandError("station is not authorized to transmit")
        if self.state.ship.power.communications < .03:
            raise CommandError("Engineering must allocate at least 3% power to Communications before transmitting")
        encounter = self.state.current_encounter
        if not encounter or encounter.status != "active" or not encounter.npc:
            raise CommandError("there is no responsive contact")
        player_message = str(command.parameters.get("message", "")).strip()
        if not player_message:
            raise CommandError("message cannot be empty")
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        center_frequency = float(recipe["center_frequency_mhz"])
        try:
            transmit_frequency = float(command.parameters["frequency_mhz"])
        except (KeyError, TypeError, ValueError):
            raise CommandError("enter the displayed carrier frequency in MHz before transmitting") from None
        if abs(transmit_frequency - center_frequency) > .05:
            raise CommandError(f"transmitter is off-frequency at {transmit_frequency:.3f} MHz — the vessel did not receive the message")
        player_message = player_message[:2_000]
        encounter.npc.known_messages.append(f"Crew: {player_message}")
        self.state.message_log.append({"time_ms": self.state.universe_time_ms, "speaker": "crew", "message": player_message})
        incoming, proposal = await self.ai.npc_response(encounter, player_message)
        encounter.npc.known_messages.append(f"{encounter.npc.name}: {incoming}")
        self.state.message_log.append({"time_ms": self.state.universe_time_ms, "speaker": encounter.npc.name, "message": incoming})
        preset_contact_established = encounter.hidden_truth.get("preset") == "friendly_contact_test"
        if preset_contact_established:
            encounter.phase = "contact_established"
            encounter.deadline_s = None
        sent_event = self.engine.event(
            "transmission_sent",
            payload={"frequency_mhz": round(transmit_frequency, 5), "message": player_message, "contact_established": preset_contact_established},
            actors=[command.character_id],
            targets=[encounter.npc.id],
            source_kind="player_command",
            source_id=command.id,
        )
        actor_parameters = {**proposal.parameters, "message": incoming}
        events = [sent_event, *self.engine.commit_npc_decision(
            encounter,
            actor_parameters,
            proposal.id,
            player_message,
            caused_by_command=sent_event.id,
        )]
        return events

    async def _ask_computer(self, command: PlayerCommand) -> list[CanonicalEvent]:
        question = str(command.parameters.get("question", "")).strip()
        if not question:
            raise CommandError("question cannot be empty")
        # Only the normal player projection is supplied. Hidden encounter truth cannot enter this call.
        projection = self.engine.station_projection(command.station)
        accessible_context = {
            **projection["ship"],
            "current_encounter": projection["encounter"],
            "detected_contacts": projection["contacts"],
            "signal_receiver": {
                "frequency_mhz": projection["ship"].get("detected_signal_frequency_mhz"),
                "status": projection.get("signal_lab", {}).get("access") if projection.get("signal_lab") else None,
                "guidance": projection.get("signal_lab", {}).get("guidance") if projection.get("signal_lab") else None,
            },
        }
        answer = await self.ai.ship_answer(question, accessible_context, self.state.crew_knowledge)
        self.state.message_log.append({"time_ms": self.state.universe_time_ms, "speaker": "Ship Computer", "message": answer})
        return [
            self.engine.event(
                "ship_computer_answered",
                payload={"question": question[:2_000], "answer": answer},
                actors=[command.character_id],
                source_kind="player_command",
                source_id=command.id,
            )
        ]

    async def tick_once(self, dt: float) -> list[CanonicalEvent]:
        async with self.lock:
            events = self.engine.tick(dt)
            if events:
                self._persist(events)
        if events:
            await self.broadcast()
            self._schedule_milestones(events)
            if any(event.event_type == "system_entered" for event in events) and self.state.current_encounter:
                self._schedule_director(self.state.current_encounter.id)
        return events

    def _persist(self, events: list[CanonicalEvent]) -> None:
        self.last_events = events[-20:]
        self.store.commit(self.state, events, self.id)
        self.last_checkpoint = time.monotonic()

    async def broadcast(self) -> None:
        stale: list[str] = []
        for token, socket in list(self.sockets.items()):
            connection = self.connections[token]
            try:
                await self.send_to(token, {
                    "type": "snapshot",
                    "sequence": self.state.event_count,
                    "data": self.engine.station_projection(connection.station),
                })
            except RuntimeError:
                stale.append(token)
        for token in stale:
            self.detach(token)

    async def _run(self) -> None:
        interval = 1 / self.engine.tick_hz
        while True:
            now = time.monotonic()
            dt = now - self.last_tick
            self.last_tick = now
            await self.tick_once(dt)
            if now - self.last_broadcast >= .1:
                await self.broadcast()
                self.last_broadcast = now
            if now - self.last_checkpoint >= 30:
                async with self.lock:
                    self.store.commit(self.state, [], self.id)
                    self.last_checkpoint = now
            elapsed = time.monotonic() - now
            await asyncio.sleep(max(0, interval - elapsed))

    def _schedule_director(self, encounter_id: str) -> None:
        task = asyncio.create_task(self._develop_encounter(encounter_id), name=f"director-{encounter_id}")
        self.ai_tasks.add(task)
        task.add_done_callback(self.ai_tasks.discard)

    def _schedule_milestones(self, events: list[CanonicalEvent]) -> None:
        encounter = self.state.current_encounter
        if not encounter or encounter.status != "active":
            return
        meaningful = {"storm_arrived", "patrol_fired", "vessel_became_critical", "signal_reply_transmitted", "weapon_fired", "warning_shot_fired"}
        for event in events:
            if event.event_type == "scan_threshold_reached" and float(event.payload.get("threshold", 0)) < 1:
                continue
            if event.event_type not in meaningful and event.event_type != "scan_threshold_reached":
                continue
            milestone_key = f"{encounter.id}:{event.event_type}"
            if milestone_key in self.scheduled_director_milestones or milestone_key in self.state.director.recent_milestones:
                continue
            self.scheduled_director_milestones.add(milestone_key)
            task = asyncio.create_task(
                self._develop_milestone(encounter.id, event.model_copy(deep=True), milestone_key),
                name=f"director-milestone-{event.id}",
            )
            self.ai_tasks.add(task)
            task.add_done_callback(self.ai_tasks.discard)

    async def _develop_milestone(self, encounter_id: str, milestone: CanonicalEvent, milestone_key: str) -> None:
        encounter = self.state.current_encounter
        if not encounter or encounter.id != encounter_id or encounter.status != "active":
            return
        proposal = await self.ai.director_milestone(
            encounter.model_copy(deep=True),
            milestone.event_type,
            milestone.payload,
            self.state.director.model_dump(mode="json"),
            list(self.state.crew_knowledge),
        )
        async with self.lock:
            current = self.state.current_encounter
            if not current or current.id != encounter_id or current.status != "active":
                return
            self.state.director.recent_milestones.append(milestone_key)
            self.state.director.recent_milestones = self.state.director.recent_milestones[-30:]
            if proposal.action == "no_event":
                return
            event = self.engine.commit_director_beat(current, proposal.parameters, proposal.id, milestone.id)
            if event:
                self._persist([event])
        await self.broadcast()

    async def _develop_encounter(self, encounter_id: str) -> None:
        encounter = self.state.current_encounter
        if not encounter or encounter.id != encounter_id or encounter.status != "active":
            return
        proposal = await self.ai.develop_encounter(encounter.model_copy(deep=True), list(self.state.crew_knowledge))
        if proposal.action == "no_event":
            return
        async with self.lock:
            current = self.state.current_encounter
            if not current or current.id != encounter_id or current.status != "active":
                return
            public_detail = str(proposal.parameters.get("public_detail", "")).strip()
            hidden_detail = str(proposal.parameters.get("hidden_detail", "")).strip()
            # Bounded continuity rules: details may extend but never replace established fields.
            if public_detail and public_detail not in current.public_summary:
                current.public_summary = f"{current.public_summary} {public_detail}"
            if hidden_detail:
                current.hidden_truth.setdefault("director_detail", hidden_detail)
            if not self.state.signal_analysis or self.state.signal_analysis.encounter_id != current.id:
                current.hidden_truth["signal_recipe"] = validate_signal_recipe(
                    proposal.parameters.get("signal_recipe"), self.state.seed, current.family
                )
            if current.deadline_s is not None:
                current.deadline_s = max(10, current.deadline_s + float(proposal.parameters.get("deadline_adjustment_s", 0)))
            event = self.engine.event(
                "director_scenario_configured",
                payload={"public_detail": public_detail, "deadline_adjustment_s": proposal.parameters.get("deadline_adjustment_s", 0)},
                targets=[current.id],
                source_kind="approved_proposal",
                source_id=proposal.id,
            )
            self._persist([event])
        await self.broadcast()

    def diagnostics(self) -> dict[str, Any]:
        return {
            "session_id": self.id,
            "universe_id": self.state.universe_id,
            "simulation_hz": self.engine.tick_hz,
            "universe_time_ms": self.state.universe_time_ms,
            "time_scale": self.state.time_scale,
            "players": len(self.connections),
            "connected_players": sum(connection.connected for connection in self.connections.values()),
            "ai_provider": self.ai.provider.capabilities().name,
            "ai_failures": self.ai.failures,
            "ai_queue_depth": len(self.ai_tasks),
            "systems_generated": len(self.state.systems),
            "event_count": self.state.event_count,
            "uptime_s": round(time.monotonic() - self.started_at, 1),
        }


class SessionManager:
    def __init__(self, saves_root: Path, provider: AIProvider | None = None):
        self.store = SaveStore(saves_root)
        self.provider = provider or provider_from_environment()
        self.sessions: dict[str, GameSession] = {}

    def create_universe(self, **kwargs: Any) -> GameSession:
        if "seed" not in kwargs or kwargs["seed"] is None:
            kwargs["seed"] = random.SystemRandom().randrange(1, 2**63)
        state = create_game_state(**kwargs)
        session = GameSession(state, self.store, self.provider)
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

    def load_universe(self, universe_id: str) -> GameSession:
        for session in self.sessions.values():
            if session.state.universe_id == universe_id:
                return session
        state = self.store.load(universe_id)
        session = GameSession(state, self.store, self.provider)
        migration_events = session.engine.migrate_loaded_state()
        if migration_events:
            self.store.commit(state, migration_events, session.id)
        self.sessions[session.id] = session
        session.start()
        return session

    def get(self, session_id: str) -> GameSession:
        try:
            return self.sessions[session_id]
        except KeyError as exc:
            raise CommandError("session not found") from exc

    async def shutdown(self) -> None:
        await asyncio.gather(*(session.stop() for session in self.sessions.values()), return_exceptions=True)
