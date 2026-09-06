from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from .generation import generate_encounter, generate_system, system_id
from .models import (
    BearingMeasurement,
    Capability,
    CanonicalEvent,
    GameState,
    Observation,
    PlayerCommand,
    SignalAnalysisState,
    StationRole,
    WorldThread,
)
from .signal_processing import diffusion_maps, pca_analysis, spectrogram, synthesize_signal, validate_signal_recipe


class CommandError(ValueError):
    """A player command is invalid for the current state."""


class SimulationEngine:
    tick_hz = 20

    def __init__(self, state: GameState):
        self.state = state
        self._processed_commands: dict[str, list[CanonicalEvent]] = {}
        self._signal_cache: tuple[tuple[Any, ...], dict[str, Any]] | None = None

    def event(
        self,
        event_type: str,
        *,
        payload: dict[str, Any] | None = None,
        actors: Iterable[str] = (),
        targets: Iterable[str] = (),
        source_kind: str = "simulation",
        source_id: str | None = None,
        visibility: str = "crew",
        caused_by: Iterable[str] = (),
    ) -> CanonicalEvent:
        event = CanonicalEvent(
            universe_id=self.state.universe_id,
            universe_time_ms=self.state.universe_time_ms,
            event_type=event_type,
            actor_ids=list(actors),
            target_ids=list(targets),
            payload=payload or {},
            source_kind=source_kind,  # type: ignore[arg-type]
            source_id=source_id,
            visibility=visibility,  # type: ignore[arg-type]
            caused_by=list(caused_by),
        )
        self.state.event_count += 1
        return event

    def apply_command(self, command: PlayerCommand) -> list[CanonicalEvent]:
        if command.id in self._processed_commands:
            return self._processed_commands[command.id]

        handlers = {
            "set_flight": self._set_flight,
            "set_power": self._set_power,
            "start_scan": self._start_scan,
            "set_time_scale": self._set_time_scale,
            "begin_transit": self._begin_transit,
            "emergency_warp": self._emergency_warp,
            "raise_shields": self._raise_shields,
            "set_weapons_authorization": self._set_weapons_authorization,
            "configure_weapon": self._configure_weapon,
            "fire_weapon": self._fire_weapon,
            "fire_warning": self._fire_warning,
            "claim_salvage": self._claim_salvage,
            "install_cargo": self._install_cargo,
            "field_repair": self._field_repair,
            "resolve_encounter": self._resolve_encounter,
            "pursue_thread": self._pursue_thread,
            "choose_consequence": self._choose_consequence,
            "acquire_signal": self._acquire_signal,
            "share_signal_with_science": self._share_signal_with_science,
            "configure_pca": self._configure_pca,
            "reset_pca": self._reset_pca,
            "open_signal_recording": self._open_signal_recording,
            "clear_signal_workspace": self._clear_signal_workspace,
            "configure_dmaps": self._configure_dmaps,
            "classify_signal": self._classify_signal,
            "test_signal_structure": self._test_signal_structure,
            "attempt_demodulation": self._attempt_demodulation,
            "interpret_signal": self._interpret_signal,
            "run_universal_translator": self._interpret_signal,
            "send_signal_reply": self._send_signal_reply,
        }
        try:
            handler = handlers[command.command_type]
        except KeyError as exc:
            raise CommandError(f"unknown command: {command.command_type}") from exc
        events = handler(command)
        self._processed_commands[command.id] = events
        if len(self._processed_commands) > 2_000:
            self._processed_commands.pop(next(iter(self._processed_commands)))
        return events

    def migrate_loaded_state(self) -> list[CanonicalEvent]:
        """Repair legacy checkpoints whose deadline fired without closing the contact attempt."""
        encounter = self.state.current_encounter
        events: list[CanonicalEvent] = []
        valid_targets = {body.id for body in self.state.systems[self.state.ship.system_id].bodies}
        if encounter:
            valid_targets.add(encounter.target_id)
        ship = self.state.ship
        if ship.active_scan_target and (ship.transit_target or ship.active_scan_target not in valid_targets):
            ship.active_scan_target = None
            ship.active_scan_instrument = None
            ship.scan_progress = 0
            events.append(self.event("stale_scan_cleared", targets=[ship.id], payload={"reason": "scan target no longer in current system"}))
        instrument_updates = {
            "Multispectral Array": ("Composition and Temperature Scan", "Use on planets, structures, debris, and vessels to identify materials, temperature, and broad electromagnetic emissions."),
            "Particle Flux Detector": ("Radiation Hazard Scan", "Use to measure radiation, charged particles, energetic pulses, and whether local conditions threaten the ship."),
            "Field Interferometer": ("Signal Direction Scan", "Use on an encounter signal to measure its bearing. Scan again after moving to triangulate the source position."),
            "Adaptive Interpretation Array": ("Universal Translator", "Converts stable decoded symbols into plain-language interpretations with explicit confidence."),
        }
        renamed: list[dict[str, str]] = []
        for capability in self.state.ship.capabilities:
            if capability.name in instrument_updates:
                previous = capability.name
                capability.name, capability.description = instrument_updates[previous]
                renamed.append({"from": previous, "to": capability.name})
        added_vessel_scan = False
        if not any(capability.name == "Vessel Systems and Weapons Scan" for capability in self.state.ship.capabilities):
            self.state.ship.capabilities.append(Capability(
                id=f"cap_vessel_scan_{self.state.ship.id.removeprefix('ship_')}",
                name="Vessel Systems and Weapons Scan",
                category="hardware",
                power_mw=70,
                input_domains=["electromagnetic", "thermal", "radar"],
                output_domains=["vessel_systems", "weapons", "defenses"],
                description="Use on a detected vessel to estimate propulsion, power generation, defensive systems, and possible weapons.",
            ))
            added_vessel_scan = True
        added_weapons: list[str] = []
        weapon_capabilities = (
            ("Focused Energy Projector", 160, ["electrical", "target_track"], ["directed_energy", "damage"], "A rechargeable line-of-sight weapon. Accurate at long range when Sensors provides a strong fire-control track."),
            ("Kinetic Interceptor", 90, ["electrical", "ammunition", "target_track"], ["kinetic_impact", "damage"], "Launches a finite guided interceptor. Higher impact than the energy projector but less effective at long range."),
        )
        for name, power_mw, input_domains, output_domains, description in weapon_capabilities:
            if any(capability.name == name for capability in self.state.ship.capabilities):
                continue
            self.state.ship.capabilities.append(Capability(
                id=f"cap_{name.lower().replace(' ', '_')}_{self.state.ship.id.removeprefix('ship_')}",
                name=name,
                category="hardware",
                power_mw=power_mw,
                input_domains=input_domains,
                output_domains=output_domains,
                description=description,
            ))
            added_weapons.append(name)
        if renamed or added_vessel_scan or added_weapons:
            events.append(self.event(
                "science_scan_labels_migrated",
                payload={"renamed": renamed, "vessel_systems_scan_added": added_vessel_scan, "weapons_added": added_weapons},
                targets=[self.state.ship.id],
                source_kind="simulation",
            ))
        if encounter and encounter.npc and not encounter.npc.goals:
            npc = encounter.npc
            npc.personality = ["observant", "self-protective"]
            npc.goals = ["understand the crew's intent", "protect the vessel and its occupants"]
            npc.beliefs = ["actions provide stronger evidence than assurances"]
            npc.fears = ["misunderstanding escalating into avoidable harm"]
            npc.relationship_label = "unfamiliar contact"
            npc.visible_activity = "holding position and monitoring the crew vessel"
            npc.visible_reason = "The contact has not yet established the crew's intentions."
            npc.current_request = "State your identity and purpose."
            events.append(self.event(
                "npc_actor_state_migrated",
                payload={"actor_id": npc.id, "memory_limit": 50},
                actors=[npc.id],
                source_kind="simulation",
                visibility="entity-private",
            ))
        if encounter and encounter.npc:
            remembered = self.state.known_npcs.get(encounter.npc.id)
            if remembered and remembered.memories and not encounter.npc.memories:
                encounter.npc = remembered.model_copy(deep=True)
            self.state.known_npcs[encounter.npc.id] = encounter.npc.model_copy(deep=True)
        if encounter and not self.state.world_threads:
            thread = self._new_thread(encounter)
            self.state.world_threads.append(thread)
            events.append(self.event("legacy_world_thread_created", payload={"thread_id": thread.id, "title": thread.title}, targets=[thread.id]))
        if encounter and encounter.family == "artificial_signal" and encounter.phase == "signal_lost" and encounter.status == "active":
            analysis = self.state.signal_analysis if self.state.signal_analysis and self.state.signal_analysis.encounter_id == encounter.id else None
            encounter.status = "departed"
            encounter.outcome = "contact failed — signal lost before a translated reply"
            message = "CONTACT LOST. The carrier faded before a translated reply was transmitted. No contact was established."
            if not any(entry.get("speaker") == "Communications" and entry.get("message") == message for entry in self.state.message_log):
                self.state.message_log.append({"time_ms": self.state.universe_time_ms, "speaker": "Communications", "message": message})
            knowledge = "A patterned carrier was lost before a translated reply could establish contact; any acquired recording remains available for post-incident analysis."
            if knowledge not in self.state.crew_knowledge:
                self.state.crew_knowledge.append(knowledge)
            events.append(self.event(
                "legacy_signal_loss_outcome_repaired",
                payload={"reason": "older simulation left a faded carrier marked active", "new_status": encounter.status, "outcome": encounter.outcome, "signal_recorded": bool(analysis and analysis.acquired)},
                targets=[encounter.id, encounter.target_id],
                source_kind="simulation",
            ))
        events.extend(self.auto_acquire_detected_signal())
        return events

    def auto_acquire_detected_signal(self) -> list[CanonicalEvent]:
        encounter = self.state.current_encounter
        if not encounter or encounter.status != "active" or (encounter.family != "artificial_signal" and not encounter.npc):
            return []
        if self.state.signal_analysis and self.state.signal_analysis.encounter_id == encounter.id and self.state.signal_analysis.acquired:
            return []
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        frequency = round(float(recipe["center_frequency_mhz"]), 5)
        analysis = SignalAnalysisState(encounter_id=encounter.id, acquired=True, tuned_frequency_mhz=frequency)
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "automatic carrier detection and recording", "frequency_mhz": frequency})
        self.state.signal_analysis = analysis
        self._signal_cache = None
        source = encounter.npc.vessel_name if encounter.npc else "unidentified source"
        self.state.message_log.append({"time_ms": self.state.universe_time_ms, "speaker": "Communications", "message": f"Incoming signal automatically acquired from {source} at {frequency:.3f} MHz."})
        return [self.event(
            "signal_automatically_acquired",
            payload={"center_frequency_mhz": frequency, "source": source, "channels": 4, "samples": 192},
            targets=[encounter.target_id],
            source_kind="simulation",
        )]

    def _set_flight(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.FLIGHT, StationRole.COMMAND})
        heading = float(command.parameters.get("heading_deg", self.state.ship.target_heading_deg)) % 360
        throttle = min(1.0, max(0.0, float(command.parameters.get("throttle", self.state.ship.throttle))))
        self.state.ship.target_heading_deg = heading
        self.state.ship.throttle = throttle
        baseline_distance = float(command.parameters.get("baseline_distance_km", 0))
        if baseline_distance:
            if not 1_000 <= baseline_distance <= 20_000:
                raise CommandError("measurement baseline must be between 1,000 and 20,000 km")
            self.state.ship.baseline_origin_x_km = self.state.ship.x_km
            self.state.ship.baseline_origin_y_km = self.state.ship.y_km
            self.state.ship.baseline_target_km = baseline_distance
            self.state.ship.baseline_autobraking = False
        return [
            self.event(
                "flight_ordered",
                payload={"heading_deg": heading, "throttle": throttle, "baseline_distance_km": baseline_distance or None},
                actors=[command.character_id],
                targets=[self.state.ship.id],
                source_kind="player_command",
                source_id=command.id,
            )
        ]

    def _set_power(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.ENGINEERING})
        allocations = self.state.ship.power.model_dump()
        for key, value in command.parameters.items():
            if key in allocations:
                allocations[key] = min(1.0, max(0.0, float(value)))
        if sum(allocations.values()) > 1.00001:
            raise CommandError("total power allocation cannot exceed 100%")
        self.state.ship.power = self.state.ship.power.model_validate(allocations)
        return [
            self.event(
                "power_reallocated",
                payload=allocations,
                actors=[command.character_id],
                targets=[self.state.ship.id],
                source_kind="player_command",
                source_id=command.id,
            )
        ]

    def _start_scan(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.SCIENCE})
        if self.state.ship.transit_target:
            raise CommandError("wait until transit ends before scanning")
        target = str(command.parameters.get("target_id", ""))
        current_system = self.state.systems[self.state.ship.system_id]
        valid = {body.id for body in current_system.bodies}
        if self.state.current_encounter:
            valid.add(self.state.current_encounter.target_id)
        if target not in valid:
            raise CommandError("scan target is not present in the current system")
        requested_instrument = str(command.parameters.get("instrument_id", ""))
        science_instruments = [
            capability
            for capability in self.state.ship.capabilities
            if capability.category == "hardware"
            and any(domain in {"composition", "temperature", "signal", "flux", "periodicity", "hazard", "gradient", "coherence", "phase", "vessel_systems", "weapons", "defenses"} for domain in capability.output_domains)
        ]
        if not requested_instrument:
            requested_instrument = next(
                (capability.id for capability in science_instruments if capability.name in {"Composition and Temperature Scan", "Multispectral Array"}),
                science_instruments[0].id if science_instruments else "",
            )
        instrument = next((capability for capability in science_instruments if capability.id == requested_instrument), None)
        if instrument is None:
            raise CommandError("selected science instrument is not installed")
        if instrument.name in {"Signal Direction Scan", "Field Interferometer"} and (not self.state.current_encounter or target != self.state.current_encounter.target_id):
            raise CommandError("Signal Direction Scan requires the focused encounter signal as its target")
        if instrument.name == "Vessel Systems and Weapons Scan" and (not self.state.current_encounter or not self.state.current_encounter.npc or target != self.state.current_encounter.target_id):
            raise CommandError("Vessel Systems and Weapons Scan requires a detected vessel as its target")
        self.state.ship.active_scan_target = target
        self.state.ship.active_scan_instrument = instrument.id
        self.state.ship.scan_progress = 0
        return [
            self.event(
                "scan_started",
                payload={"target_id": target, "instrument_id": instrument.id, "scan_purpose": instrument.name, "instrument": instrument.name},
                actors=[command.character_id],
                targets=[target],
                source_kind="player_command",
                source_id=command.id,
            )
        ]

    def _set_time_scale(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMAND})
        scale = int(command.parameters.get("scale", 1))
        if scale not in {1, 5, 20, 100}:
            raise CommandError("time scale must be 1, 5, 20, or 100")
        if scale > 1 and self._time_critical():
            raise CommandError("time acceleration is unsafe during the current situation")
        self.state.time_scale = scale
        return [
            self.event(
                "time_scale_changed",
                payload={"scale": scale},
                actors=[command.character_id],
                source_kind="player_command",
                source_id=command.id,
            )
        ]

    def _begin_transit(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.FLIGHT, StationRole.COMMAND})
        if self.state.ship.transit_target:
            raise CommandError("the ship is already in transit")
        coordinate = command.parameters.get("coordinate")
        if not isinstance(coordinate, list) or len(coordinate) != 2:
            raise CommandError("coordinate must be a two-number list")
        target_coordinate = (int(coordinate[0]), int(coordinate[1]))
        current = self.state.systems[self.state.ship.system_id]
        if target_coordinate not in current.neighbor_coordinates:
            raise CommandError("target must be a neighboring system")
        if self.state.current_encounter and self.state.current_encounter.status == "active":
            self.state.current_encounter.status = "departed"
            self.state.current_encounter.outcome = "crew departed before resolution"
        if self.state.current_encounter and self.state.current_encounter.npc:
            npc = self.state.current_encounter.npc
            self.state.known_npcs[npc.id] = npc.model_copy(deep=True)
        self.state.ship.transit_target = system_id(self.state.seed, target_coordinate)
        self.state.ship.transit_remaining_s = 12
        self.state.ship.transit_mode = "normal"
        self._clear_scan_for_departure()
        if self.state.ship.transit_target not in self.state.systems:
            generated = generate_system(self.state.seed, target_coordinate)
            self.state.systems[generated.id] = generated
        self.state.time_scale = 1
        return [
            self.event(
                "transit_started",
                payload={"coordinate": list(target_coordinate), "eta_s": 12},
                actors=[command.character_id],
                targets=[self.state.ship.transit_target],
                source_kind="player_command",
                source_id=command.id,
            )
        ]

    def _emergency_warp(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.FLIGHT, StationRole.COMMAND})
        ship = self.state.ship
        if ship.transit_target:
            raise CommandError("the ship is already in intersystem transit")
        if ship.heat >= 1.15:
            raise CommandError("emergency warp is locked out above 115% thermal index")
        if ship.power.propulsion < .12:
            raise CommandError("emergency warp requires at least 12% propulsion power")
        current = self.state.systems[ship.system_id]
        requested = command.parameters.get("coordinate")
        target_coordinate = tuple(int(value) for value in requested) if isinstance(requested, list) and len(requested) == 2 else current.neighbor_coordinates[0]
        if target_coordinate not in current.neighbor_coordinates:
            raise CommandError("emergency warp destination must be a neighboring system")
        encounter = self.state.current_encounter
        escaped_encounter = encounter.id if encounter and encounter.status == "active" else None
        if encounter and encounter.status == "active":
            encounter.status = "departed"
            encounter.outcome = "crew escaped by emergency warp"
            encounter.deadline_s = None
        if encounter and encounter.npc:
            self.state.known_npcs[encounter.npc.id] = encounter.npc.model_copy(deep=True)
        ship.transit_target = system_id(self.state.seed, target_coordinate)
        ship.transit_remaining_s = 3
        ship.transit_mode = "emergency_warp"
        self._clear_scan_for_departure()
        ship.throttle = 0
        ship.baseline_target_km = 0
        ship.baseline_origin_x_km = None
        ship.baseline_origin_y_km = None
        ship.baseline_autobraking = False
        heat_added = .18
        ship.heat = min(1.5, ship.heat + heat_added)
        ship.defensive_posture = False
        if ship.transit_target not in self.state.systems:
            generated = generate_system(self.state.seed, target_coordinate)
            self.state.systems[generated.id] = generated
        self.state.time_scale = 1
        return [self.event(
            "emergency_warp_initiated",
            payload={"coordinate": list(target_coordinate), "eta_s": 3, "heat_added": heat_added, "defensive_field_dropped": True, "escaped_encounter": escaped_encounter},
            actors=[command.character_id],
            targets=[ship.transit_target],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _raise_shields(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.TACTICAL})
        amount = min(1.0, max(0.0, float(command.parameters.get("level", 1))))
        self.state.ship.defensive_posture = amount > 0
        return [self.event(
            "shield_posture_changed",
            payload={"active": self.state.ship.defensive_posture},
            actors=[command.character_id],
            targets=[self.state.ship.id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _fire_warning(self, command: PlayerCommand) -> list[CanonicalEvent]:
        command.parameters["mode"] = "warning"
        return self._fire_weapon(command)

    def _set_weapons_authorization(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMAND})
        authorized = bool(command.parameters.get("authorized", False))
        self.state.ship.weapons_authorized = authorized
        return [self.event(
            "weapons_authorization_changed",
            payload={"authorized": authorized},
            actors=[command.character_id],
            targets=[self.state.ship.id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _configure_weapon(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.TACTICAL})
        weapon = str(command.parameters.get("weapon", ""))
        if weapon not in {"focused_energy", "kinetic_interceptor"}:
            raise CommandError("select an installed weapon")
        installed_name = "Focused Energy Projector" if weapon == "focused_energy" else "Kinetic Interceptor"
        if not any(capability.name == installed_name and capability.condition > .2 for capability in self.state.ship.capabilities):
            raise CommandError(f"{installed_name} is not operational")
        self.state.ship.selected_weapon = weapon  # type: ignore[assignment]
        return [self.event(
            "weapon_selected",
            payload={"weapon": weapon, "display_name": installed_name},
            actors=[command.character_id],
            targets=[self.state.ship.id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _weapon_solution(self, encounter: Any) -> dict[str, Any]:
        ship = self.state.ship
        contacts = self._contact_projection(encounter)
        range_km = float(contacts[0]["range_km"]) if contacts else math.inf
        weapon = ship.selected_weapon
        max_range_km = 125_000 if weapon == "focused_energy" else 70_000
        sensor_noise = encounter.environmental_effects.get("sensor_noise", 0)
        lock = .18 + ship.power.sensors * 1.7 + min(.25, ship.scan_progress * .25) - sensor_noise * .2
        lock -= max(0, range_km - 30_000) / (max_range_km * 2.4)
        if weapon == "kinetic_interceptor":
            lock -= max(0, range_km - 35_000) / 180_000
        lock = min(.98, max(.05, lock))
        return {
            "weapon": weapon,
            "display_name": "Focused Energy Projector" if weapon == "focused_energy" else "Kinetic Interceptor",
            "range_km": range_km,
            "max_range_km": max_range_km,
            "lock_quality": lock,
            "in_range": range_km <= max_range_km,
            "time_of_flight_s": 0 if weapon == "focused_energy" else range_km / 60,
        }

    def _fire_weapon(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.TACTICAL, StationRole.COMMAND})
        encounter = self._active_encounter()
        if not encounter.npc:
            raise CommandError("there is no tracked vessel to target")
        mode = str(command.parameters.get("mode", "precision"))
        if mode not in {"warning", "precision", "full"}:
            raise CommandError("firing mode must be warning, precision, or full")
        ship = self.state.ship
        solution = self._weapon_solution(encounter)
        required_charge = {"warning": .15, "precision": .45, "full": .8}[mode]
        if mode != "warning" and not ship.weapons_authorized:
            raise CommandError("Command must authorize weapons release")
        if ship.weapon_cooldown_s > 0:
            raise CommandError(f"weapon cooling cycle has {ship.weapon_cooldown_s:.1f} seconds remaining")
        if ship.power.weapons < .04:
            raise CommandError("Engineering must allocate at least 4% power to weapons")
        if ship.weapon_charge + 1e-6 < required_charge:
            raise CommandError(f"weapon charge is {ship.weapon_charge:.0%}; {mode} fire requires {required_charge:.0%}")
        if not solution["in_range"]:
            raise CommandError(f"target is beyond {solution['max_range_km']:,.0f} km weapon range")
        if mode != "warning" and solution["lock_quality"] < .25:
            raise CommandError("fire-control lock is below 25%; allocate sensor power, scan the vessel, or close range")
        if ship.selected_weapon == "kinetic_interceptor" and mode != "warning" and ship.kinetic_ammunition <= 0:
            raise CommandError("kinetic interceptor ammunition is depleted")

        ship.weapon_charge = max(0, ship.weapon_charge - required_charge)
        ship.weapon_cooldown_s = {"warning": 1.5, "precision": 3.0, "full": 5.0}[mode]
        heat_added = {"warning": .012, "precision": .035, "full": .075}[mode] * (1.15 - min(.6, ship.power.cooling))
        ship.heat = min(1.5, ship.heat + heat_added)
        if ship.selected_weapon == "kinetic_interceptor" and mode != "warning":
            ship.kinetic_ammunition -= 1

        damage = 0.0
        damage_target = "none"
        quality = "warning"
        if mode != "warning":
            quality = "direct" if solution["lock_quality"] >= .62 else "glancing" if solution["lock_quality"] >= .38 else "miss"
            base_damage = {
                ("focused_energy", "precision"): .10,
                ("focused_energy", "full"): .22,
                ("kinetic_interceptor", "precision"): .15,
                ("kinetic_interceptor", "full"): .29,
            }[(ship.selected_weapon, mode)]
            power_factor = .65 + min(1, ship.power.weapons / .30) * .35
            accuracy_factor = 1 if quality == "direct" else .45 if quality == "glancing" else 0
            damage = round(base_damage * power_factor * accuracy_factor, 4)
            if encounter.target_shields > 0:
                absorbed = min(encounter.target_shields, damage)
                encounter.target_shields = max(0, encounter.target_shields - absorbed)
                remainder = damage - absorbed
                if remainder > 0:
                    encounter.target_hull = max(0, encounter.target_hull - remainder)
                    damage_target = "shields and hull"
                else:
                    damage_target = "shields"
            elif damage > 0:
                encounter.target_hull = max(0, encounter.target_hull - damage)
                damage_target = "hull"

        npc = encounter.npc
        npc.disposition = max(-1, npc.disposition - (.2 if mode == "warning" else .65))
        npc.intention = "defensive" if mode == "warning" else "disable_intruder"
        npc.relationship_label = "hostile contact"
        npc.visible_activity = "turning to present defensive systems" if mode == "warning" else "executing hostile defensive maneuvers"
        npc.visible_reason = "The crew vessel discharged a weapon nearby." if mode == "warning" else "The crew vessel fired directly on the contact."
        npc.current_request = "Cease fire and withdraw."
        self.state.known_npcs[npc.id] = npc.model_copy(deep=True)
        if encounter.target_hull <= 0:
            encounter.phase = "disabled"
            encounter.status = "resolved"
            encounter.deadline_s = None
            encounter.outcome = "target vessel disabled by weapons fire"
        else:
            encounter.phase = "hostile"
            encounter.deadline_kind = "patrol_escalates"
            encounter.deadline_s = min(encounter.deadline_s or 8, 8)
        ship.last_weapon_result = (
            f"{solution['display_name']} {mode} discharge: {quality}; "
            f"{damage:.1%} effect to {damage_target}."
        )
        return [self.event(
            "warning_shot_fired" if mode == "warning" else "weapon_fired",
            payload={
                **solution,
                "mode": mode,
                "impact_quality": quality,
                "damage": damage,
                "damage_target": damage_target,
                "target_shields_remaining": round(encounter.target_shields, 4),
                "target_hull_remaining": round(encounter.target_hull, 4),
                "charge_spent": required_charge,
                "heat_added": round(heat_added, 4),
                "ammunition_remaining": ship.kinetic_ammunition,
            },
            actors=[command.character_id],
            targets=[npc.id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _claim_salvage(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.ENGINEERING, StationRole.COMMAND})
        encounter = self._active_encounter(require_resolved=True)
        if not encounter.salvage:
            raise CommandError("no recoverable component is available")
        self.state.ship.cargo.append(encounter.salvage)
        item = encounter.salvage
        encounter.salvage = None
        return [
            self.event(
                "salvage_recovered",
                payload={"cargo": item.model_dump(mode="json")},
                actors=[command.character_id],
                targets=[self.state.ship.id],
                source_kind="player_command",
                source_id=command.id,
            )
        ]

    def _install_cargo(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.ENGINEERING})
        cargo_id = str(command.parameters.get("cargo_id", ""))
        item = next((item for item in self.state.ship.cargo if item.id == cargo_id), None)
        if not item or not item.installable_capability:
            raise CommandError("cargo item is not an installable capability")
        capability = item.installable_capability.model_copy(deep=True)
        self.state.ship.capabilities.append(capability)
        self.state.ship.cargo.remove(item)
        event = self.event(
            "capability_installed",
            payload={"capability": capability.model_dump(mode="json")},
            actors=[command.character_id],
            targets=[self.state.ship.id],
            source_kind="player_command",
            source_id=command.id,
        )
        capability.origin_event = event.id
        return [event]

    def _field_repair(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.ENGINEERING})
        ship = self.state.ship
        if ship.velocity_km_s > 1 or ship.throttle > 0:
            raise CommandError("field repair requires the ship to be stationary")
        if ship.heat >= .75:
            raise CommandError("field repair is unsafe while the thermal index is elevated")
        if ship.hull >= .999:
            raise CommandError("hull integrity does not require field repair")
        restored = min(.10, 1 - ship.hull)
        ship.hull += restored
        ship.heat = min(1.5, ship.heat + .05)
        return [self.event(
            "field_repair_completed",
            payload={"hull_restored": restored, "heat_added": .05},
            actors=[command.character_id],
            targets=[ship.id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _resolve_encounter(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMAND, StationRole.SCIENCE, StationRole.COMMUNICATIONS})
        encounter = self._active_encounter()
        method = str(command.parameters.get("method", "investigation"))
        if method not in {"investigation", "diplomacy"}:
            raise CommandError("choose investigation or diplomacy")
        if method == "investigation" and not encounter.npc and encounter.family != "artificial_signal":
            raise CommandError("record a conclusion with supporting Science observations in the Activity Board")
        if method == "investigation" and self._encounter_evidence_depth() < 0.75:
            raise CommandError("insufficient scan evidence to resolve by investigation")
        if method == "investigation" and encounter.family == "artificial_signal":
            analysis = self.state.signal_analysis
            localization = self._localization_projection(encounter.target_id)
            if localization["estimated_x_km"] is None:
                raise CommandError("signal investigation requires two direction-finding scans from a useful movement baseline")
            if not analysis or analysis.encounter_id != encounter.id or analysis.interpretation_confidence < .55:
                raise CommandError("signal investigation requires Communications acquisition, structure testing, stable demodulation, and universal translation")
            if not analysis.reply_sent:
                raise CommandError("establish contact by replying on the translated channel before concluding the investigation")
        if method == "diplomacy" and (not encounter.npc or encounter.npc.disposition < 0.15 or encounter.phase == "hostile" or not any(m.startswith("Crew:") for m in encounter.npc.known_messages)):
            raise CommandError("the contact is not ready to accept a diplomatic resolution")
        encounter.status = "resolved"
        encounter.outcome = method
        encounter.deadline_s = None
        if encounter.family == "artificial_signal" and self.state.signal_analysis:
            finding = f"Recovered transmission: {self.state.signal_analysis.interpretation} Source identity and ultimate origin remain unresolved."
        else:
            finding = encounter.hidden_truth.get("known_fact") or encounter.hidden_truth.get("finding") or encounter.hidden_truth.get("source")
        if finding:
            self.state.crew_knowledge.append(str(finding))
        for thread in self.state.world_threads:
            if thread.status == "open" and any(item.get("encounter_id") == encounter.id for item in thread.history):
                thread.status = "resolved"
                thread.stage = max(thread.stage, 3)
                thread.next_actions = []
                thread.evidence.append(str(finding or encounter.outcome or method))
                thread.history.append({"time_ms": self.state.universe_time_ms, "event": "encounter resolved", "method": method})
        return [
            self.event(
                "encounter_resolved",
                payload={"method": method, "finding": finding},
                actors=[command.character_id],
                targets=[encounter.id],
                source_kind="player_command",
                source_id=command.id,
                visibility="public",
            )
        ]

    def _new_thread(self, encounter: Any) -> WorldThread:
        actions = {
            "ordinary_survey": ["Run a close survey", "Collect a documented sample", "Publish the finding"],
            "artificial_signal": ["Localize and decode the signal", "Establish contact", "Trace the source"],
            "damaged_vessel": ["Assess vessel damage", "Offer technical assistance", "Stabilize the vessel"],
            "environmental_hazard": ["Measure the disturbance", "Plot a safe route", "Protect nearby traffic"],
            "disputed_boundary": ["Identify your vessel", "Negotiate passage", "Record the agreement"],
            "ancient_site": ["Map the structure", "Estimate its age", "Recover a documented sample"],
        }[encounter.family]
        kind = {"ordinary_survey": "discovery", "artificial_signal": "mystery", "damaged_vessel": "contact", "environmental_hazard": "hazard", "disputed_boundary": "contact", "ancient_site": "mystery"}[encounter.family]
        return WorldThread(
            title=encounter.title,
            kind=kind,  # type: ignore[arg-type]
            summary=encounter.public_summary,
            origin_system_id=self.state.ship.system_id,
            npc_id=encounter.npc.id if encounter.npc else None,
            next_actions=actions,
            history=[{"time_ms": self.state.universe_time_ms, "event": "encounter detected", "encounter_id": encounter.id}],
        )

    def _pursue_thread(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMAND, StationRole.SCIENCE})
        thread_id = str(command.parameters.get("thread_id", ""))
        action = str(command.parameters.get("action", ""))
        thread = next((item for item in self.state.world_threads if item.id == thread_id), None)
        if not thread or thread.status != "open":
            raise CommandError("the selected world thread is not open")
        if thread.kind == "consequence":
            raise CommandError("choose whether to archive privately or publish the findings")
        if not thread.next_actions or action != thread.next_actions[0]:
            raise CommandError("complete the current thread action before advancing")
        encounter = self.state.current_encounter
        is_current = bool(encounter and any(item.get("encounter_id") == encounter.id for item in thread.history))
        if not is_current or not encounter or encounter.status != "active":
            raise CommandError("return to this investigation's system, or reply through Communications")
        if encounter.npc:
            raise CommandError("use Communications to advance this contact; Command can accept an accord after an exchange")
        if encounter.family == "artificial_signal":
            raise CommandError("localize and decode the signal through Science and Communications")
        if self._encounter_evidence_depth() < .75:
            raise CommandError("scan this encounter target to at least 75% before recording a finding")
        if not str(command.parameters.get("note", "")).strip():
            raise CommandError("describe your conclusion and select supporting observations")
        selected = command.parameters.get("observation_ids", [])
        if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
            raise CommandError("select Science observation IDs as a list")
        observations = [obs for obs in self.state.observations if obs.id in selected and obs.target == encounter.target_id and obs.station == StationRole.SCIENCE and (command.station != StationRole.COMMAND or obs.confidence >= .75)]
        if not observations or len(observations) != len(set(selected)):
            raise CommandError("select Science observations from this encounter as evidence")
        thread.stage = 2
        thread.next_actions = [action]
        evidence = f"Crew conclusion: {str(command.parameters['note']).strip()[:2000]} Supporting measurements: {'; '.join(f'{obs.measurement}: {obs.value} ({obs.confidence:.0%} confidence)' for obs in observations)}."
        thread.evidence.append(evidence)
        thread.history.append({"time_ms": self.state.universe_time_ms, "event": "thread advanced", "action": action, "system_id": self.state.ship.system_id})
        thread.stage += 1
        thread.next_actions = thread.next_actions[1:]
        if is_current and encounter:
            encounter.phase = f"investigation_stage_{thread.stage}"
        events = [self.event(
            "world_thread_advanced",
            payload={"thread_id": thread.id, "title": thread.title, "action": action, "stage": thread.stage, "evidence": evidence, "observation_ids": [obs.id for obs in observations]},
            actors=[command.character_id],
            targets=[thread.id],
            source_kind="player_command",
            source_id=command.id,
        )]
        if not thread.next_actions:
            thread.status = "resolved"
            finding = f"Recorded finding: {thread.title}. {evidence}"
            if finding not in self.state.crew_knowledge:
                self.state.crew_knowledge.append(finding)
            if is_current and encounter and encounter.status == "active":
                encounter.status = "resolved"
                encounter.outcome = "world thread completed"
                encounter.deadline_s = None
            follow_up = WorldThread(
                title=f"Follow-up: {thread.title}",
                kind="consequence",
                summary=f"The crew must decide how to use, share, or revisit what was learned from {thread.title}.",
                origin_system_id=thread.origin_system_id,
                npc_id=thread.npc_id,
                next_actions=["Choose how to use the findings"],
                history=[{"time_ms": self.state.universe_time_ms, "event": "created by resolved thread", "source_thread_id": thread.id}],
            )
            self.state.world_threads.append(follow_up)
            events.append(self.event("follow_up_thread_created", payload={"thread_id": follow_up.id, "title": follow_up.title}, targets=[follow_up.id], caused_by=[events[0].id]))
        return events

    def _clear_scan_for_departure(self) -> None:
        ship = self.state.ship
        ship.scan_progress = 0
        ship.active_scan_target = None
        ship.active_scan_instrument = None
        encounter = self.state.current_encounter
        if encounter and encounter.npc:
            frequency = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)["center_frequency_mhz"]
            for thread in self.state.world_threads:
                if thread.npc_id == encounter.npc.id:
                    thread.remote_frequency_mhz = float(frequency)

    def _encounter_evidence_depth(self) -> float:
        encounter = self.state.current_encounter
        ship = self.state.ship
        if ship.transit_target or not encounter or ship.active_scan_target != encounter.target_id:
            return 0
        return ship.scan_progress

    def _choose_consequence(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMAND, StationRole.SCIENCE})
        thread = next((t for t in self.state.world_threads if t.id == command.parameters.get("thread_id")), None)
        choice = command.parameters.get("choice")
        if not thread or thread.kind != "consequence" or thread.status != "open" or choice not in {"archive", "publish"}:
            raise CommandError("choose archive or publish for an open consequence")
        thread.status = "resolved"
        thread.next_actions = []
        thread.history.append({"time_ms": self.state.universe_time_ms, "event": "consequence decided", "choice": choice})
        record = f"{'Published' if choice == 'publish' else 'Privately archived'}: {thread.title}"
        self.state.crew_knowledge.append(record)
        return [self.event("consequence_decided", payload={"thread_id": thread.id, "choice": choice, "record": record}, actors=[command.character_id], targets=[thread.id], source_kind="player_command", source_id=command.id, visibility="public" if choice == "publish" else "crew")]

    def _acquire_signal(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS})
        encounter = self._active_encounter()
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        center_frequency = float(recipe["center_frequency_mhz"])
        analysis = SignalAnalysisState(encounter_id=encounter.id, acquired=True, tuned_frequency_mhz=round(center_frequency, 5))
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "automatic carrier detection and recording", "frequency_mhz": round(center_frequency, 5)})
        self.state.signal_analysis = analysis
        self._signal_cache = None
        return [self.event(
            "signal_acquired",
            payload={"center_frequency_mhz": center_frequency, "automatic_lock": True, "sample_rate_hz": 64, "channels": 4, "samples": 192},
            actors=[command.character_id],
            targets=[encounter.target_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _share_signal_with_science(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS})
        analysis = self._require_signal_analysis()
        analysis.shared_with_science = True
        analysis.version += 1
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "dataset routed to science"})
        return [self.event(
            "signal_dataset_shared",
            payload={"destination": "science", "analysis_version": analysis.version},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _configure_pca(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS})
        analysis = self._require_signal_analysis()
        cutoff = int(command.parameters.get("cutoff", analysis.pca_cutoff))
        selected_side = str(command.parameters.get("selected_side", analysis.pca_selected_side))
        if cutoff not in {1, 2, 3}:
            raise CommandError("PCA cutoff must be between adjacent components 1–2, 2–3, or 3–4")
        if selected_side not in {"high_variance", "low_variance"}:
            raise CommandError("select either the high-variance or low-variance side of the PCA cutoff")
        analysis.pca_cutoff = cutoff
        analysis.pca_selected_side = selected_side  # type: ignore[assignment]
        analysis.pca_configured = True
        analysis.structure_result = None
        analysis.structure_confidence = 0
        analysis.demodulation_method = None
        analysis.demodulation_confidence = 0
        analysis.symbol_preview = ""
        analysis.interpretation = ""
        analysis.interpretation_confidence = 0
        analysis.translation_status = "idle"
        analysis.translation_protocol = ""
        analysis.translation_notes = ""
        analysis.version += 1
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "PCA partition reconstruction", "cutoff": cutoff, "selected_side": selected_side})
        self._signal_cache = None
        return [self.event(
            "pca_configuration_changed",
            payload={"cutoff": cutoff, "selected_side": selected_side, "analysis_version": analysis.version},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _reset_pca(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS})
        analysis = self._require_signal_analysis()
        analysis.pca_configured = False
        analysis.pca_cutoff = 1
        analysis.pca_selected_side = "low_variance"
        analysis.shared_with_science = False
        analysis.structure_result = None
        analysis.structure_confidence = 0
        analysis.demodulation_method = None
        analysis.demodulation_confidence = 0
        analysis.symbol_preview = ""
        analysis.interpretation = ""
        analysis.interpretation_confidence = 0
        analysis.translation_status = "idle"
        analysis.translation_protocol = ""
        analysis.translation_notes = ""
        analysis.science_classification = None
        analysis.science_note = ""
        analysis.version += 1
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "returned to raw recording"})
        return [self.event(
            "signal_processing_reset_to_raw",
            payload={"analysis_version": analysis.version, "raw_recording_preserved": True},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _open_signal_recording(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS, StationRole.SCIENCE})
        analysis = self._require_signal_analysis()
        if not analysis.recording_retained:
            raise CommandError("no retained signal recording is available")
        analysis.workspace_open = True
        return [self.event(
            "retained_signal_recording_opened",
            payload={"analysis_version": analysis.version},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _clear_signal_workspace(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS})
        analysis = self._require_signal_analysis()
        analysis.workspace_open = False
        analysis.pca_configured = False
        analysis.shared_with_science = False
        analysis.structure_result = None
        analysis.structure_confidence = 0
        analysis.demodulation_method = None
        analysis.demodulation_confidence = 0
        analysis.symbol_preview = ""
        analysis.interpretation = ""
        analysis.interpretation_confidence = 0
        analysis.translation_status = "idle"
        analysis.translation_protocol = ""
        analysis.translation_notes = ""
        analysis.science_classification = None
        analysis.science_note = ""
        analysis.version += 1
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "workspace cleared; raw recording retained"})
        return [self.event(
            "signal_workspace_cleared",
            payload={"analysis_version": analysis.version, "raw_recording_retained": True},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _configure_dmaps(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.SCIENCE})
        analysis = self._require_signal_analysis(require_science_share=True)
        analysis.dmaps_epsilon = min(4.0, max(0.1, float(command.parameters.get("epsilon", analysis.dmaps_epsilon))))
        analysis.dmaps_diffusion_time = min(8, max(1, int(command.parameters.get("diffusion_time", analysis.dmaps_diffusion_time))))
        analysis.dmaps_neighbors = min(12, max(2, int(command.parameters.get("neighbors", analysis.dmaps_neighbors))))
        analysis.version += 1
        analysis.processing_log.append({
            "time_ms": self.state.universe_time_ms,
            "station": "science",
            "operation": "diffusion-map embedding",
            "epsilon": analysis.dmaps_epsilon,
            "diffusion_time": analysis.dmaps_diffusion_time,
            "neighbors": analysis.dmaps_neighbors,
        })
        self._signal_cache = None
        return [self.event(
            "diffusion_map_configuration_changed",
            payload={
                "epsilon": analysis.dmaps_epsilon,
                "diffusion_time": analysis.dmaps_diffusion_time,
                "neighbors": analysis.dmaps_neighbors,
                "analysis_version": analysis.version,
            },
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _classify_signal(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.SCIENCE})
        analysis = self._require_signal_analysis(require_science_share=True)
        classification = str(command.parameters.get("classification", ""))
        allowed = {"natural_contamination", "instrument_artifact", "structured_residual", "inconclusive"}
        if classification not in allowed:
            raise CommandError("unknown signal classification")
        analysis.science_classification = classification  # type: ignore[assignment]
        analysis.science_note = str(command.parameters.get("note", ""))[:500]
        analysis.version += 1
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "science", "operation": "physical classification", "classification": classification})
        return [self.event(
            "signal_component_classified",
            payload={"classification": classification, "note": analysis.science_note, "analysis_version": analysis.version},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _test_signal_structure(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS})
        analysis = self._require_signal_analysis()
        encounter = self.state.current_encounter
        assert encounter is not None
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        if recipe["signal_kind"] == "noise_like":
            result, confidence = "noise_like", .86
        elif not analysis.pca_configured and float(recipe["correlated_noise"]) >= .65:
            result, confidence = "structured_but_contaminated", .58
        elif analysis.pca_configured and analysis.pca_selected_side == "high_variance":
            result, confidence = "inconclusive", .42
        else:
            result, confidence = "structured_carrier", .9
        analysis.structure_result = result  # type: ignore[assignment]
        analysis.structure_confidence = confidence
        analysis.demodulation_method = None
        analysis.demodulation_confidence = 0
        analysis.symbol_preview = ""
        analysis.interpretation = ""
        analysis.interpretation_confidence = 0
        analysis.translation_status = "idle"
        analysis.translation_protocol = ""
        analysis.translation_notes = ""
        analysis.version += 1
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "cyclostationary structure test", "result": result, "confidence": confidence})
        return [self.event(
            "signal_structure_tested",
            payload={"result": result, "confidence": confidence},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _attempt_demodulation(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS})
        analysis = self._require_signal_analysis()
        if not analysis.structure_result:
            raise CommandError("run the signal structure test before choosing a demodulator")
        method = str(command.parameters.get("method", ""))
        if method not in {"amplitude", "frequency", "phase_shift", "pulse"}:
            raise CommandError("unknown demodulation method")
        encounter = self.state.current_encounter
        assert encounter is not None
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        correct = recipe["signal_kind"] == "structured" and method == recipe["modulation"]
        if correct:
            if analysis.structure_result == "structured_but_contaminated" and not analysis.pca_configured:
                confidence = .34
            elif analysis.pca_configured and analysis.pca_selected_side == "high_variance":
                confidence = .24
            else:
                confidence = .91 if analysis.pca_configured else .64
            payload_bytes = str(recipe["payload"]).encode("utf-8")[:10]
            bits = "".join(f"{byte:08b}" for byte in payload_bytes)
            preview = " ".join(bits[index:index + 8] for index in range(0, len(bits), 8))
        else:
            confidence = .07 if recipe["signal_kind"] == "structured" else .03
            preview = "?10? 0??1 ???? 11?0 — FRAME LOCK LOST"
        analysis.demodulation_method = method  # type: ignore[assignment]
        analysis.demodulation_confidence = confidence
        analysis.symbol_preview = preview
        analysis.interpretation = ""
        analysis.interpretation_confidence = 0
        analysis.translation_status = "idle"
        analysis.translation_protocol = ""
        analysis.translation_notes = ""
        analysis.version += 1
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "demodulation attempt", "method": method, "confidence": confidence})
        return [self.event(
            "signal_demodulation_attempted",
            payload={"method": method, "confidence": confidence, "stable_frame": confidence >= .55},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _interpret_signal(self, command: PlayerCommand) -> list[CanonicalEvent]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS})
        analysis = self._require_signal_analysis()
        if not analysis.demodulation_method:
            raise CommandError("choose a demodulation method before attempting interpretation")
        encounter = self.state.current_encounter
        assert encounter is not None
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        if analysis.demodulation_confidence < .55:
            interpretation = "NONSENSE / UNTRANSLATABLE: no stable symbol framing or repeatable token boundaries were recovered."
            confidence = .04
            status = "rejected"
            protocol = "unresolved — unstable input"
            notes = "The Universal Translator rejected the input rather than inventing a meaning. Recover a stable symbol frame and try again."
        else:
            interpretation = str(recipe["payload"])
            confidence = min(.96, analysis.demodulation_confidence + .04)
            status = "translated"
            protocol = f"binary framed / {str(analysis.demodulation_method).replace('_', '-')} modulation"
            notes = "Token boundaries, repetition, and encounter context agree. The displayed text is a plain-language semantic rendering, not a word-for-word transcript."
        analysis.interpretation = interpretation
        analysis.interpretation_confidence = confidence
        analysis.translation_status = status  # type: ignore[assignment]
        analysis.translation_protocol = protocol
        analysis.translation_notes = notes
        analysis.version += 1
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "universal translation", "status": status, "protocol": protocol, "confidence": confidence})
        return [self.event(
            "universal_translation_attempted",
            payload={"status": status, "protocol": protocol, "interpretation": interpretation, "confidence": confidence, "notes": notes},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        )]

    def _send_signal_reply(self, command: PlayerCommand) -> list[CanonicalEvent]:
        return self.commit_signal_reply(command, "A short translated response returns on the recovered carrier.")

    def _validate_signal_reply(self, command: PlayerCommand) -> tuple[Any, SignalAnalysisState, str, float]:
        self._require_role(command, {StationRole.INTEGRATED, StationRole.COMMUNICATIONS, StationRole.COMMAND})
        if self.state.ship.power.communications < .03:
            raise CommandError("Engineering must allocate at least 3% power to Communications before transmitting")
        encounter = self._active_encounter()
        analysis = self._require_signal_analysis()
        if analysis.interpretation_confidence < .55:
            raise CommandError("a stable interpreted channel is required before transmitting a reply")
        message = str(command.parameters.get("message", "")).strip()[:1_000]
        if not message:
            raise CommandError("reply message cannot be empty")
        try:
            transmit_frequency = float(command.parameters["frequency_mhz"])
        except (KeyError, TypeError, ValueError):
            raise CommandError("enter the recovered carrier frequency in MHz before transmitting") from None
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        center_frequency = float(recipe["center_frequency_mhz"])
        if abs(transmit_frequency - center_frequency) > .05:
            raise CommandError(f"transmitter is off-frequency at {transmit_frequency:.3f} MHz — no contact established")
        return encounter, analysis, message, transmit_frequency

    def commit_signal_reply(
        self,
        command: PlayerCommand,
        incoming: str,
        proposal_id: str | None = None,
        tone: str = "unclear",
        proposal_parameters: dict[str, Any] | None = None,
    ) -> list[CanonicalEvent]:
        encounter, analysis, message, transmit_frequency = self._validate_signal_reply(command)
        incoming = incoming.strip()[:4_000] or "A stable acknowledgment frame returns, but its meaning remains unclear."
        acknowledgment = f"Reply received at {transmit_frequency:.3f} MHz. Universal Translator rendering: {incoming}"
        analysis.reply_sent = True
        analysis.reply_acknowledgment = acknowledgment
        analysis.version += 1
        encounter.phase = "contact_established"
        encounter.deadline_s = None
        self.state.message_log.append({"time_ms": self.state.universe_time_ms, "speaker": "crew", "message": message})
        self.state.message_log.append({"time_ms": self.state.universe_time_ms, "speaker": "signal channel", "message": acknowledgment})
        actor_events: list[CanonicalEvent] = []
        if encounter.npc:
            encounter.npc.known_messages.append(f"Crew: {message}")
            encounter.npc.known_messages.append(f"{encounter.npc.name}: {incoming}")
            if proposal_id and proposal_parameters is not None:
                actor_events = self.commit_npc_decision(
                    encounter,
                    proposal_parameters,
                    proposal_id,
                    message,
                    caused_by_command=command.id,
                )
        analysis.processing_log.append({"time_ms": self.state.universe_time_ms, "station": "communications", "operation": "reply transmitted", "message": message})
        return [self.event(
            "signal_reply_transmitted",
            payload={"frequency_mhz": round(transmit_frequency, 5), "message": message, "contact_established": True},
            actors=[command.character_id],
            source_kind="player_command",
            source_id=command.id,
        ), self.event(
            "signal_contact_response_received",
            payload={"frequency_mhz": round(transmit_frequency, 5), "translated_response": incoming, "tone": tone, "acknowledgment": acknowledgment},
            targets=[self.state.ship.id],
            source_kind="approved_proposal" if proposal_id else "simulation",
            source_id=proposal_id,
        ), *actor_events]

    def commit_npc_decision(
        self,
        encounter: Any,
        parameters: dict[str, Any],
        proposal_id: str,
        player_message: str,
        *,
        caused_by_command: str | None = None,
    ) -> list[CanonicalEvent]:
        """Validate and commit one bounded actor proposal; generated text never mutates state directly."""
        npc = encounter.npc
        if npc is None or encounter.status != "active":
            raise CommandError("NPC proposal target is no longer active")
        allowed = {"hold_position", "approach", "withdraw", "share_data", "request_action", "change_course", "depart"}
        requested_action = str(parameters.get("actor_action", "hold_position"))
        action = requested_action
        constrained_reason = ""
        if action not in allowed:
            action = "hold_position"
            constrained_reason = "unknown actor action"
        delta = min(.5, max(-.5, float(parameters.get("disposition_delta", 0))))
        npc.disposition = min(1, max(-1, npc.disposition + delta))
        if action == "approach" and npc.disposition < .15:
            action = "hold_position"
            constrained_reason = "approach requires a cooperative relationship"
        elif action == "share_data" and npc.disposition < 0:
            action = "request_action"
            constrained_reason = "data sharing requires non-hostile relations"
        npc.intention = str(parameters.get("intention", npc.intention))[:80] or npc.intention
        npc.last_action = action
        npc.visible_activity = str(parameters.get("action_summary", "holds position and monitors the channel"))[:240]
        npc.visible_reason = str(parameters.get("reason", "The latest exchange did not justify a larger maneuver."))[:300]
        npc.current_request = str(parameters.get("request", ""))[:300]
        if npc.disposition >= .7:
            npc.relationship_label = "trusted contact"
        elif npc.disposition >= .3:
            npc.relationship_label = "cooperative contact"
        elif npc.disposition <= -.6:
            npc.relationship_label = "hostile contact"
        elif npc.disposition <= -.2:
            npc.relationship_label = "wary contact"
        else:
            npc.relationship_label = "uncertain contact"
        if encounter.deadline_s is not None:
            encounter.deadline_s = max(5, encounter.deadline_s + min(180, max(-90, float(parameters.get("deadline_delta_s", 0)))))

        position = encounter.hidden_truth.get("source_position_km")
        range_change_km = 0.0
        if isinstance(position, list) and len(position) == 2 and action in {"approach", "withdraw", "change_course"}:
            dx = float(position[0]) - self.state.ship.x_km
            dy = float(position[1]) - self.state.ship.y_km
            old_range = math.hypot(dx, dy)
            if action == "approach":
                factor = .82
            elif action == "withdraw":
                factor = 1.22
            else:
                angle = math.radians(18)
                dx, dy = dx * math.cos(angle) - dy * math.sin(angle), dx * math.sin(angle) + dy * math.cos(angle)
                factor = 1.0
            encounter.hidden_truth["source_position_km"] = [
                round(self.state.ship.x_km + dx * factor, 3),
                round(self.state.ship.y_km + dy * factor, 3),
            ]
            range_change_km = round(math.hypot(dx * factor, dy * factor) - old_range, 1)

        shared_data = str(parameters.get("shared_data", ""))[:500] if action == "share_data" else ""
        if shared_data and shared_data not in self.state.crew_knowledge:
            self.state.crew_knowledge.append(shared_data)
        commitment = str(parameters.get("commitment", "")).strip()[:300]
        if commitment and commitment not in npc.commitments:
            npc.commitments.append(commitment)
            npc.commitments = npc.commitments[-20:]
        memory = str(parameters.get("memory", ""))[:300] or f"The crew transmitted: {player_message[:180]}"
        npc.memories.append({
            "time_ms": self.state.universe_time_ms,
            "summary": memory,
            "action": action,
            "disposition_after": round(npc.disposition, 3),
        })
        npc.memories = npc.memories[-50:]
        if action == "depart":
            encounter.status = "departed"
            encounter.deadline_s = None
            encounter.outcome = "contact departed after the communications exchange"
        self.state.known_npcs[npc.id] = npc.model_copy(deep=True)

        public_payload = {
            "message": str(parameters.get("message", ""))[:4_000],
            "actor_action": action,
            "activity": npc.visible_activity,
            "reason": npc.visible_reason,
            "request": npc.current_request,
            "shared_data": shared_data,
            "commitment": commitment,
            "disposition_delta": delta,
            "relationship": npc.relationship_label,
            "range_change_km": range_change_km,
        }
        constrained_events: list[CanonicalEvent] = []
        if constrained_reason:
            constrained_events.append(self.event(
                "npc_proposal_constrained",
                payload={"requested_action": requested_action, "committed_action": action, "reason": constrained_reason},
                actors=[npc.id],
                source_kind="approved_proposal",
                source_id=proposal_id,
                visibility="entity-private",
            ))
        accepted = self.event(
            "npc_action_committed",
            payload=public_payload,
            actors=[npc.id],
            targets=[self.state.ship.id],
            source_kind="approved_proposal",
            source_id=proposal_id,
            caused_by=[caused_by_command] if caused_by_command else [],
        )
        private_memory = self.event(
            "npc_memory_recorded",
            payload={"summary": memory, "action": action, "disposition_after": round(npc.disposition, 3)},
            actors=[npc.id],
            source_kind="approved_proposal",
            source_id=proposal_id,
            visibility="entity-private",
            caused_by=[accepted.id],
        )
        for thread in self.state.world_threads:
            if thread.status == "open" and any(item.get("encounter_id") == encounter.id for item in thread.history):
                thread.stage = max(1, thread.stage)
                thread.next_actions = ["Respond in Communications or accept an accord in Command" if encounter.phase != "hostile" else "De-escalate in Communications or withdraw"]
                thread.evidence.append(f"Contact exchange: {player_message[:2000]}")
                thread.history.append({"time_ms": self.state.universe_time_ms, "event": "contact exchange", "event_id": accepted.id})
        return [*constrained_events, accepted, private_memory]

    def _require_signal_analysis(self, require_science_share: bool = False) -> SignalAnalysisState:
        encounter = self.state.current_encounter
        if not encounter or (encounter.status != "active" and encounter.phase != "signal_lost"):
            raise CommandError("there is no live signal or retained signal recording to analyze")
        analysis = self.state.signal_analysis
        if not analysis or analysis.encounter_id != encounter.id or not analysis.acquired:
            raise CommandError("Communications must acquire a signal dataset first")
        if require_science_share and not analysis.shared_with_science:
            raise CommandError("Communications must route the dataset to Science first")
        return analysis

    def tick(self, wall_dt_s: float) -> list[CanonicalEvent]:
        dt = min(0.25, max(0, wall_dt_s)) * self.state.time_scale
        self.state.universe_time_ms += int(dt * 1000)
        events: list[CanonicalEvent] = []
        ship = self.state.ship

        turn_rate = 16 * max(0.15, ship.power.propulsion)
        delta = (ship.target_heading_deg - ship.heading_deg + 540) % 360 - 180
        ship.heading_deg = (ship.heading_deg + max(-turn_rate * dt, min(turn_rate * dt, delta))) % 360
        desired_velocity = ship.throttle * 250 * min(1.25, ship.power.propulsion / 0.24)
        acceleration = 22 * max(0.1, ship.power.propulsion)
        ship.velocity_km_s += max(-acceleration * dt, min(acceleration * dt, desired_velocity - ship.velocity_km_s))
        radians = math.radians(ship.heading_deg)
        ship.x_km += math.cos(radians) * ship.velocity_km_s * dt
        ship.y_km += math.sin(radians) * ship.velocity_km_s * dt

        if ship.baseline_origin_x_km is not None and ship.baseline_origin_y_km is not None:
            traveled = math.hypot(ship.x_km - ship.baseline_origin_x_km, ship.y_km - ship.baseline_origin_y_km)
            deceleration = 22 * max(0.1, ship.power.propulsion)
            braking_distance = ship.velocity_km_s**2 / (2 * deceleration)
            if not ship.baseline_autobraking and traveled + braking_distance >= ship.baseline_target_km:
                ship.throttle = 0
                ship.baseline_autobraking = True
                events.append(self.event("baseline_autobrake_started", payload={"distance_km": round(traveled, 1), "braking_distance_km": round(braking_distance, 1)}))
            if ship.baseline_autobraking and ship.velocity_km_s < .5:
                events.append(self.event("measurement_baseline_completed", payload={"distance_km": round(traveled, 1)}))
                ship.baseline_origin_x_km = None
                ship.baseline_origin_y_km = None
                ship.baseline_target_km = 0
                ship.baseline_autobraking = False

        load = ship.power.total
        cooling = ship.power.cooling
        ship.weapon_cooldown_s = max(0, ship.weapon_cooldown_s - dt * (.5 + cooling * 3))
        if ship.power.weapons >= .02 and ship.weapon_cooldown_s <= 0 and ship.heat < 1.1:
            charge_rate = .015 + ship.power.weapons * .42
            ship.weapon_charge = min(1, ship.weapon_charge + charge_rate * dt)
        elif ship.power.weapons < .02:
            ship.weapon_charge = max(0, ship.weapon_charge - .01 * dt)
        propulsion_heat = ship.throttle * ship.power.propulsion * 0.014
        weapon_heat = ship.power.weapons * 0.004 if ship.weapon_charge < 1 else 0
        heat_change = load * 0.012 + propulsion_heat + weapon_heat - cooling * 0.075
        ship.heat = min(1.5, max(0.12, ship.heat + heat_change * dt))
        if ship.heat > 1:
            damage = (ship.heat - 1) * 0.004 * dt
            ship.hull = max(0, ship.hull - damage)
        shield_target = min(1.0, ship.power.shields / 0.20)
        ship.shields += max(-0.03 * dt, min(0.025 * dt, shield_target - ship.shields))

        if ship.active_scan_target and not ship.transit_target:
            noise = self.state.current_encounter.environmental_effects.get("sensor_noise", 0) if self.state.current_encounter else 0
            instrument = next((cap for cap in ship.capabilities if cap.id == ship.active_scan_instrument), None)
            condition = instrument.condition if instrument else 0.5
            scan_rate = max(0.005, ship.power.sensors * condition * (1 - noise) * 0.10)
            before = ship.scan_progress
            ship.scan_progress = min(1, ship.scan_progress + scan_rate * dt)
            events.extend(self._scan_thresholds(before, ship.scan_progress))

        if ship.transit_target:
            ship.transit_remaining_s -= dt
            if ship.transit_remaining_s <= 0:
                previous = self.state.current_encounter
                if previous and previous.npc:
                    self.state.known_npcs[previous.npc.id] = previous.npc.model_copy(deep=True)
                ship.system_id = ship.transit_target
                ship.transit_target = None
                ship.transit_remaining_s = 0
                ship.transit_mode = None
                ship.x_km = ship.y_km = ship.velocity_km_s = ship.throttle = 0
                ship.scan_progress = 0
                ship.active_scan_target = None
                ship.active_scan_instrument = None
                destination = self.state.systems[ship.system_id]
                destination.visited = True
                self.state.current_encounter = generate_encounter(self.state.seed, destination)
                if self.state.current_encounter.npc:
                    generated_npc = self.state.current_encounter.npc
                    self.state.current_encounter.npc = self.state.known_npcs.get(generated_npc.id, generated_npc).model_copy(deep=True)
                    self.state.known_npcs[generated_npc.id] = self.state.current_encounter.npc.model_copy(deep=True)
                new_thread = self._new_thread(self.state.current_encounter)
                self.state.world_threads.append(new_thread)
                remote_follow_ups: list[dict[str, str]] = []
                for thread in self.state.world_threads:
                    if thread is new_thread or thread.status != "open" or not thread.npc_id or thread.origin_system_id == destination.id:
                        continue
                    if any(item.get("event") == "remote follow-up received" and item.get("system_id") == destination.id for item in thread.history):
                        continue
                    npc = self.state.known_npcs.get(thread.npc_id)
                    if not npc:
                        continue
                    action = f"Respond to {npc.name}'s follow-up"
                    if action not in thread.next_actions:
                        thread.next_actions.insert(0, action)
                    thread.history.append({"time_ms": self.state.universe_time_ms, "event": "remote follow-up received", "system_id": destination.id})
                    message = f"Delayed follow-up from {npc.vessel_name}: We recorded your departure. Please confirm your status over this remote channel."
                    self.state.message_log.append({"time_ms": self.state.universe_time_ms, "speaker": "Communications", "message": message})
                    remote_follow_ups.append({"thread_id": thread.id, "npc_id": npc.id, "message": message})
                self.state.observations = []
                self.state.bearing_measurements = []
                self.state.signal_analysis = None
                self._signal_cache = None
                events.append(self.event("system_entered", targets=[destination.id], payload={"name": destination.name, "coordinate": destination.coordinate}, visibility="public"))
                events.append(self.event("encounter_detected", targets=[self.state.current_encounter.id], payload={"summary": self.state.current_encounter.public_summary}))
                events.append(self.event("world_thread_opened", targets=[new_thread.id], payload={"title": new_thread.title, "kind": new_thread.kind, "next_action": new_thread.next_actions[0]}))
                for follow_up in remote_follow_ups:
                    events.append(self.event("persistent_contact_follow_up_received", targets=[follow_up["thread_id"]], payload=follow_up))
                events.extend(self.auto_acquire_detected_signal())

        encounter = self.state.current_encounter
        if encounter and encounter.status == "active" and encounter.deadline_s is not None:
            encounter.deadline_s -= dt
            if encounter.npc:
                encounter.npc.patience_s = max(0, encounter.deadline_s)
            if encounter.deadline_s <= 0:
                events.extend(self._fire_deadline(encounter.deadline_kind or "deadline"))
        return events

    def _scan_thresholds(self, before: float, after: float) -> list[CanonicalEvent]:
        encounter = self.state.current_encounter
        if not encounter or self.state.ship.active_scan_target != encounter.target_id:
            return []
        events: list[CanonicalEvent] = []
        thresholds = (0.20, 0.45, 0.75, 1.0)
        for threshold in thresholds:
            if before < threshold <= after:
                event = self.event("scan_threshold_reached", payload={"threshold": threshold}, targets=[encounter.target_id])
                events.append(event)
                if threshold == 0.20:
                    events.append(self._record_bearing(encounter, event.id))
                self._add_cross_station_observations(encounter, threshold, event.id)
                if threshold == .75 and not encounter.npc and encounter.family != "artificial_signal":
                    for thread in self.state.world_threads:
                        if thread.status == "open" and thread.stage < 2 and any(item.get("encounter_id") == encounter.id for item in thread.history):
                            thread.stage = 2
                            thread.next_actions = ["Record an evidence-backed conclusion"]
                            thread.history.append({"time_ms": self.state.universe_time_ms, "event": "scan evidence collected", "event_id": event.id})
                            events.append(self.event("investigation_evidence_ready", payload={"thread_id": thread.id}, targets=[thread.id], caused_by=[event.id]))
        return events

    def _record_bearing(self, encounter: Any, caused_by: str) -> CanonicalEvent:
        ship = self.state.ship
        position = encounter.hidden_truth.get("source_position_km")
        if not isinstance(position, list) or len(position) != 2:
            position = [80_000.0, 0.0]
        true_bearing = math.degrees(math.atan2(float(position[1]) - ship.y_km, float(position[0]) - ship.x_km)) % 360
        instrument = next((cap for cap in ship.capabilities if cap.id == ship.active_scan_instrument), None)
        base_uncertainty = {
            "Signal Direction Scan": 0.24,
            "Field Interferometer": 0.24,
            "Composition and Temperature Scan": 0.58,
            "Multispectral Array": 0.58,
            "Radiation Hazard Scan": 1.15,
            "Particle Flux Detector": 1.15,
        }.get(instrument.name if instrument else "", 0.8)
        stability = self._sensor_stability()
        uncertainty = min(8.0, base_uncertainty / max(0.18, stability))
        phase = self.state.seed * 0.731 + len(self.state.bearing_measurements) * 2.173
        measured_bearing = (true_bearing + math.sin(phase) * uncertainty * 0.38) % 360
        measurement = BearingMeasurement(
            target=encounter.target_id,
            observed_at_ms=self.state.universe_time_ms,
            instrument_id=instrument.id if instrument else "unknown",
            origin_x_km=round(ship.x_km, 3),
            origin_y_km=round(ship.y_km, 3),
            bearing_deg=round(measured_bearing, 4),
            angular_uncertainty_deg=round(uncertainty, 4),
            confidence=round(max(0.05, min(0.98, stability * (1 - uncertainty / 12))), 3),
            derived_from_event=caused_by,
        )
        self.state.bearing_measurements.append(measurement)
        self.state.bearing_measurements = self.state.bearing_measurements[-24:]
        return self.event(
            "bearing_recorded",
            payload=measurement.model_dump(mode="json"),
            targets=[encounter.target_id],
            caused_by=[caused_by],
        )

    def _sensor_stability(self) -> float:
        ship = self.state.ship
        encounter = self.state.current_encounter
        noise = encounter.environmental_effects.get("sensor_noise", 0) if encounter and encounter.status == "active" else 0
        return max(0.05, min(1.0, 0.45 + ship.power.sensors * 2.2 - noise * 0.75 - max(0, ship.heat - 0.7) * 0.8))

    def _localization_projection(self, target: str) -> dict[str, Any]:
        measurements = [item for item in self.state.bearing_measurements if item.target == target]
        result: dict[str, Any] = {
            "measurements": [item.model_dump(mode="json") for item in measurements],
            "estimated_x_km": None,
            "estimated_y_km": None,
            "uncertainty_radius_km": None,
            "confidence": 0.0,
            "baseline_km": 0.0,
            "intercept_heading_deg": None,
            "guidance": "RUN A DIRECTION-FINDING SCAN TO ESTABLISH THE FIRST BEARING.",
        }
        if not measurements:
            return result
        if len(measurements) == 1:
            first = measurements[0]
            bearing = first.bearing_deg
            baseline = math.hypot(self.state.ship.x_km - first.origin_x_km, self.state.ship.y_km - first.origin_y_km)
            result["baseline_km"] = round(baseline, 1)
            if self.state.ship.baseline_target_km:
                remaining = max(0, self.state.ship.baseline_target_km - baseline)
                phase = "AUTOMATIC BRAKING" if self.state.ship.baseline_autobraking else "BASELINE MANEUVER"
                result["guidance"] = f"{phase} ACTIVE. {remaining:,.0f} KM TO PLANNED STOP; HOLD CONTROLS."
            elif baseline >= 2_000:
                result["guidance"] = "MEASUREMENT BASELINE ESTABLISHED. SET THROTTLE TO ZERO AND RUN THE DIRECTION-FINDING SCAN AGAIN."
            else:
                remaining = max(0, 2_000 - baseline)
                result["guidance"] = f"MOVE {remaining:,.0f} KM MORE NEAR HEADING {(bearing + 90) % 360:.0f}° OR {(bearing - 90) % 360:.0f}°, THEN SCAN AGAIN."
            return result
        pairs = [
            (first, second, math.hypot(second.origin_x_km - first.origin_x_km, second.origin_y_km - first.origin_y_km))
            for index, first in enumerate(measurements)
            for second in measurements[index + 1:]
        ]
        first, second, baseline = max(pairs, key=lambda pair: pair[2])
        result["baseline_km"] = round(baseline, 1)
        a1 = math.radians(first.bearing_deg)
        a2 = math.radians(second.bearing_deg)
        d1 = (math.cos(a1), math.sin(a1))
        d2 = (math.cos(a2), math.sin(a2))
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        if baseline < 1_000 or abs(cross) < 0.003:
            result["guidance"] = "BASELINE OR CROSSING ANGLE TOO SMALL. MOVE PERPENDICULAR TO THE BEARING AND SCAN AGAIN."
            return result
        delta = (second.origin_x_km - first.origin_x_km, second.origin_y_km - first.origin_y_km)
        distance_along_first = (delta[0] * d2[1] - delta[1] * d2[0]) / cross
        estimate_x = first.origin_x_km + distance_along_first * d1[0]
        estimate_y = first.origin_y_km + distance_along_first * d1[1]
        range_km = math.hypot(estimate_x - self.state.ship.x_km, estimate_y - self.state.ship.y_km)
        mean_uncertainty = math.radians((first.angular_uncertainty_deg + second.angular_uncertainty_deg) / 2)
        uncertainty_radius = max(350.0, range_km * math.tan(mean_uncertainty) / max(abs(cross), 0.02))
        confidence = max(0.05, min(0.97, 1 - uncertainty_radius / max(5_000, range_km)))
        intercept = math.degrees(math.atan2(estimate_y - self.state.ship.y_km, estimate_x - self.state.ship.x_km)) % 360
        result.update({
            "estimated_x_km": round(estimate_x, 1),
            "estimated_y_km": round(estimate_y, 1),
            "uncertainty_radius_km": round(uncertainty_radius, 1),
            "confidence": round(confidence, 3),
            "intercept_heading_deg": round(intercept, 2),
            "guidance": "INTERCEPT SOLUTION AVAILABLE." if confidence >= 0.7 else "POSITION REMAINS UNCERTAIN. EXTEND THE BASELINE AND SCAN AGAIN.",
        })
        return result

    def _add_cross_station_observations(self, encounter: Any, threshold: float, event_id: str) -> None:
        now = self.state.universe_time_ms
        effects = encounter.environmental_effects
        instrument = next(
            (capability for capability in self.state.ship.capabilities if capability.id == self.state.ship.active_scan_instrument),
            None,
        )
        instrument_name = instrument.name if instrument else "Composition and Temperature Scan"
        source = instrument.id if instrument else "composition_temperature_scan"
        period = encounter.hidden_truth.get("period_s", 31.4)
        science_readings = {
            "Composition and Temperature Scan": {
                0.20: ("material emission variation", effects.get("sensor_noise", 0), 0.30),
                0.45: ("repeating spectral feature period", period, 0.57),
                0.75: ("non-natural material or emission confidence", 0.82, 0.82),
                1.0: ("composition and temperature scan completeness", 1.0, 0.96),
            },
            "Multispectral Array": {
                0.20: ("broadband emission variance", effects.get("sensor_noise", 0), 0.30),
                0.45: ("spectral repetition period", period, 0.57),
                0.75: ("artificial-origin confidence", 0.82, 0.82),
                1.0: ("multispectral survey completeness", 1.0, 0.96),
            },
            "Radiation Hazard Scan": {
                0.20: ("radiation variation", effects.get("sensor_noise", 0) * 1.7, 0.34),
                0.45: ("radiation pulse period", period, 0.61),
                0.75: ("radiation hazard confidence", min(1.0, effects.get("power_induction", 0) * 3.5), 0.78),
                1.0: ("radiation hazard scan completeness", 1.0, 0.96),
            },
            "Particle Flux Detector": {
                0.20: ("charged-particle flux variance", effects.get("sensor_noise", 0) * 1.7, 0.34),
                0.45: ("particle pulse period", period, 0.61),
                0.75: ("energetic-particle hazard confidence", min(1.0, effects.get("power_induction", 0) * 3.5), 0.78),
                1.0: ("particle survey completeness", 1.0, 0.96),
            },
            "Signal Direction Scan": {
                0.20: ("signal bearing measurement", self._localization_projection(encounter.target_id)["measurements"][-1]["bearing_deg"] if self.state.bearing_measurements else 0, 0.36),
                0.45: ("signal phase repetition period", period, 0.64),
                0.75: ("signal direction stability", max(0.1, 1 - effects.get("sensor_noise", 0)), 0.84),
                1.0: ("signal direction scan completeness", 1.0, 0.97),
            },
            "Field Interferometer": {
                0.20: ("local field gradient", effects.get("power_induction", 0), 0.36),
                0.45: ("field phase period", period, 0.64),
                0.75: ("field coherence", max(0.1, 1 - effects.get("sensor_noise", 0)), 0.84),
                1.0: ("field survey completeness", 1.0, 0.97),
            },
            "Vessel Systems and Weapons Scan": {
                0.20: ("vessel radar profile confidence", 0.91, 0.48),
                0.45: ("active power and propulsion confidence", 0.78, 0.66),
                0.75: ("weapon system likelihood", 0.88 if encounter.phase == "hostile" else 0.56, 0.82),
                1.0: ("vessel systems and weapons scan completeness", 1.0, 0.96),
            },
        }
        measurement, science_value, science_confidence = science_readings.get(
            instrument_name, science_readings["Composition and Temperature Scan"]
        )[threshold]
        if threshold == 0.20:
            values = [
                (StationRole.SCIENCE, source, measurement, science_value, science_confidence),
                (StationRole.ENGINEERING, "power_bus", "external power induction", effects.get("power_induction", 0), 0.32),
                (StationRole.FLIGHT, "navigation_array", "position drift", effects.get("navigation_drift", 0), 0.30),
            ]
        elif threshold == 0.45:
            values = [
                (StationRole.SCIENCE, source, measurement, science_value, science_confidence),
                (StationRole.ENGINEERING, "power_bus", "induction period", period, 0.55),
                (StationRole.COMMUNICATIONS, "signal_array", "carrier period", period, 0.51),
            ]
        elif threshold == 0.75:
            values = [
                (StationRole.SCIENCE, source, measurement, science_value, science_confidence),
                (StationRole.TACTICAL, "contact_tracker", "hazard confidence", 0.36, 0.63),
            ]
        else:
            values = [(StationRole.SCIENCE, source, measurement, science_value, science_confidence)]
        for station, source, measurement, value, confidence in values:
            self.state.observations.append(
                Observation(
                    observed_at_ms=now,
                    station=station,
                    source_capability=source,
                    target=encounter.target_id,
                    measurement=measurement,
                    value=value,
                    uncertainty=round(1 - confidence, 3),
                    confidence=confidence,
                    derived_from_events=[event_id],
                )
            )

    def _fire_deadline(self, kind: str) -> list[CanonicalEvent]:
        encounter = self._active_encounter()
        encounter.deadline_s = None
        if kind == "storm_arrives":
            damage = max(0.02, 0.15 * (1 - self.state.ship.power.shields))
            if self.state.ship.defensive_posture and self.state.ship.shields > 0:
                self.state.ship.shields = max(0, self.state.ship.shields - damage)
                damage_target = "shields"
            else:
                self.state.ship.hull = max(0, self.state.ship.hull - damage)
                damage_target = "hull"
            encounter.phase = "storm_active"
            return [self.event("storm_arrived", payload={"damage": damage, "damage_target": damage_target}, targets=[self.state.ship.id])]
        if kind == "life_support_failure":
            encounter.phase = "critical"
            return [self.event("vessel_became_critical", targets=[encounter.target_id])]
        if kind == "patrol_escalates":
            encounter.phase = "hostile"
            if encounter.npc:
                encounter.npc.intention = "disable_intruder"
            if self.state.ship.defensive_posture and self.state.ship.shields > 0:
                self.state.ship.shields = max(0, self.state.ship.shields - 0.18)
                damage_target = "shields"
            else:
                self.state.ship.hull = max(0, self.state.ship.hull - 0.18)
                damage_target = "hull"
            return [self.event("patrol_fired", payload={"damage": 0.18, "damage_target": damage_target}, targets=[self.state.ship.id])]
        analysis = self.state.signal_analysis if self.state.signal_analysis and self.state.signal_analysis.encounter_id == encounter.id else None
        if analysis:
            analysis.workspace_open = False
            analysis.recording_retained = bool(analysis.acquired)
        failure = {
            "reason": "carrier faded before a translated reply established contact",
            "signal_recorded": bool(analysis and analysis.acquired),
            "structure_result": analysis.structure_result if analysis else None,
            "stable_frame_recovered": bool(analysis and analysis.demodulation_confidence >= .55),
            "translation_completed": bool(analysis and analysis.interpretation_confidence >= .55),
            "reply_transmitted": bool(analysis and analysis.reply_sent),
        }
        encounter.phase = "signal_lost"
        encounter.status = "departed"
        encounter.outcome = "contact failed — signal lost before a translated reply"
        self.state.message_log.append({
            "time_ms": self.state.universe_time_ms,
            "speaker": "Communications",
            "message": "CONTACT LOST. The carrier faded before a translated reply was transmitted. No contact was established.",
        })
        self.state.crew_knowledge.append("A patterned carrier was lost before a translated reply could establish contact; any acquired recording remains available for post-incident analysis.")
        return [self.event("signal_faded", payload=failure, targets=[encounter.target_id])]

    def station_projection(self, station: StationRole) -> dict[str, Any]:
        ship = self.state.ship
        integrated = station == StationRole.INTEGRATED
        observations = [
            obs.model_dump(mode="json")
            for obs in self.state.observations
            if integrated or obs.station == station or station == StationRole.COMMAND and obs.confidence >= 0.75
        ]
        system = self.state.systems[ship.system_id]
        encounter = self.state.current_encounter
        sensor_stability = self._sensor_stability()
        alerts = self._authorized_alerts(station, sensor_stability)
        projection: dict[str, Any] = {
            "schema_version": 1,
            "universe_time_ms": self.state.universe_time_ms,
            "time_scale": self.state.time_scale,
            "station": station,
            "ship": {
                "id": ship.id,
                "name": ship.name,
                "frame": ship.frame,
                "system_id": ship.system_id,
                "x_km": round(ship.x_km, 3),
                "y_km": round(ship.y_km, 3),
                "heading_deg": round(ship.heading_deg, 2),
                "target_heading_deg": ship.target_heading_deg,
                "throttle": round(ship.throttle, 3),
                "velocity_km_s": round(ship.velocity_km_s, 3),
                "baseline_target_km": ship.baseline_target_km,
                "baseline_autobraking": ship.baseline_autobraking,
                "hull": round(ship.hull, 4),
                "shields": round(ship.shields, 4),
                "defensive_posture": ship.defensive_posture,
                "weapons_authorized": ship.weapons_authorized,
                "selected_weapon": ship.selected_weapon,
                "weapon_charge": round(ship.weapon_charge, 4),
                "weapon_cooldown_s": round(ship.weapon_cooldown_s, 2),
                "kinetic_ammunition": ship.kinetic_ammunition,
                "last_weapon_result": ship.last_weapon_result,
                "heat": round(ship.heat, 4),
                "power": ship.power.model_dump(),
                "scan_progress": round(ship.scan_progress, 4),
                "active_scan_target": ship.active_scan_target,
                "active_scan_instrument": ship.active_scan_instrument,
                "transit_remaining_s": round(ship.transit_remaining_s, 2),
                "transit_mode": ship.transit_mode,
                "detected_signal_frequency_mhz": self._detected_signal_frequency(encounter) if encounter and (encounter.family == "artificial_signal" or encounter.npc) else None,
                "capabilities": [cap.model_dump(mode="json") for cap in ship.capabilities],
                "cargo": [item.model_dump(mode="json") for item in ship.cargo],
            },
            "system": {
                "id": system.id,
                "name": system.name,
                "coordinate": system.coordinate,
                "star_class": system.star_class,
                "bodies": [body.model_dump(mode="json") for body in system.bodies],
                "neighbors": [
                    {"coordinate": coordinate, "id": system_id(self.state.seed, coordinate)}
                    for coordinate in system.neighbor_coordinates
                ],
            },
            "encounter": None,
            "observations": observations,
            "sensor_stability": round(sensor_stability, 3),
            "alerts": alerts,
            "crew_knowledge": self.state.crew_knowledge,
            "messages": self.state.message_log[-50:],
            "event_count": self.state.event_count,
            "localization": self._localization_projection(encounter.target_id) if encounter else None,
            "signal_lab": self._signal_lab_projection(station),
            "workflow": self._workflow_projection(encounter),
            "contacts": self._contact_projection(encounter),
            "narrative": {
                "pressure": round(self.state.director.narrative_pressure, 2),
                "danger": round(self.state.director.danger_level, 2),
                "next_decision": self.state.director.unresolved_threads[-1] if self.state.director.unresolved_threads else "",
            },
            "weapon_control": self._weapon_control_projection(station, encounter),
            "engineering_effects": self._engineering_effects_projection() if station in {StationRole.INTEGRATED, StationRole.ENGINEERING, StationRole.COMMAND} else None,
            "objectives": self._objectives_projection(),
            "remote_channels": [{"thread_id": t.id, "name": self.state.known_npcs[t.npc_id].vessel_name, "frequency_mhz": t.remote_frequency_mhz, "messages": self.state.known_npcs[t.npc_id].known_messages[-20:]} for t in self.state.world_threads if t.remote_frequency_mhz is not None and t.npc_id in self.state.known_npcs and t.origin_system_id != ship.system_id] if station in {StationRole.INTEGRATED, StationRole.COMMUNICATIONS, StationRole.COMMAND} else [],
            "continuity": self.state.continuity_report,
        }
        if encounter:
            projection["encounter"] = {
                "id": encounter.id,
                "family": encounter.family,
                "title": encounter.title,
                "target_id": encounter.target_id,
                "status": encounter.status,
                "phase": encounter.phase,
                "public_summary": encounter.public_summary,
                "deadline_s": round(encounter.deadline_s, 1) if encounter.deadline_s is not None else None,
                "outcome": encounter.outcome,
                "salvage_available": bool(encounter.salvage and encounter.status == "resolved"),
                "requires_signal_analysis": encounter.family == "artificial_signal",
                "signal_analysis_complete": bool(
                    self.state.signal_analysis
                    and self.state.signal_analysis.encounter_id == encounter.id
                    and self.state.signal_analysis.interpretation_confidence >= .55
                    and self.state.signal_analysis.reply_sent
                    and self._localization_projection(encounter.target_id)["estimated_x_km"] is not None
                ),
                "npc": {
                    "name": encounter.npc.name,
                    "vessel_name": encounter.npc.vessel_name,
                    "disposition": round(encounter.npc.disposition, 2),
                    "intention_observed": self._observed_intention(encounter.npc.intention),
                    "relationship": encounter.npc.relationship_label,
                    "activity": encounter.npc.visible_activity,
                    "activity_reason": encounter.npc.visible_reason,
                    "current_request": encounter.npc.current_request,
                    "commitments": encounter.npc.commitments[-3:],
                } if encounter.npc else None,
            }
        return projection

    def _objectives_projection(self) -> dict[str, Any]:
        encounter = self.state.current_encounter
        open_threads = [thread for thread in self.state.world_threads if thread.status == "open"]
        threads: list[dict[str, Any]] = []
        for thread in open_threads[-8:]:
            action = thread.next_actions[0] if thread.next_actions else "Review completed record"
            is_current = bool(encounter and any(item.get("encounter_id") == encounter.id for item in thread.history))
            ready = True
            reason = "Ready"
            station_hint = "SCI"
            if thread.kind == "consequence":
                station_hint = "CMD"
            elif thread.npc_id:
                station_hint = "COM"
                ready, reason = False, "Use Communications to exchange messages; Command records an accord"
                if is_current and encounter and encounter.phase == "hostile":
                    action = "De-escalate in Communications or withdraw"
                    reason = "Contact is hostile; an accord cannot be recorded now"
            elif not is_current or not encounter or encounter.status != "active":
                ready, reason = False, "Return to the origin system to continue"
                station_hint = "FLT"
            elif encounter.family == "artificial_signal":
                ready, reason = False, "Use Science and Communications to localize and decode"
            elif self._encounter_evidence_depth() < .75:
                ready, reason = False, "Scan this encounter target to 75%"
            threads.append({
                "id": thread.id,
                "title": thread.title,
                "kind": thread.kind,
                "stage": thread.stage,
                "summary": thread.summary,
                "origin_system_id": thread.origin_system_id,
                "next_action": action,
                "ready": ready,
                "reason": reason,
                "evidence_count": len(thread.evidence),
                "current_system": thread.origin_system_id == self.state.ship.system_id,
                "station_hint": station_hint,
            })
        system = self.state.systems[self.state.ship.system_id]
        activities = [{"id": f"body:{body.id}", "label": f"Survey {body.name}", "detail": body.summary, "kind": "survey"} for body in system.bodies[:4]]
        activities.extend({"id": thread["id"], "label": thread["next_action"], "detail": thread["title"], "kind": "thread"} for thread in threads)
        return {
            "open_threads": threads,
            "activities": activities,
            "primary": threads[-1] if threads else None,
        }

    def _engineering_effects_projection(self) -> dict[str, Any]:
        ship = self.state.ship
        encounter = self.state.current_encounter
        noise = encounter.environmental_effects.get("sensor_noise", 0) if encounter and encounter.status == "active" else 0
        propulsion_heat = ship.throttle * ship.power.propulsion * .014
        weapon_heat = ship.power.weapons * .004 if ship.weapon_charge < 1 else 0
        net_heat_per_s = ship.power.total * .012 + propulsion_heat + weapon_heat - ship.power.cooling * .075
        eta_safe_s = (ship.heat - .75) / -net_heat_per_s if ship.heat > .75 and net_heat_per_s < 0 else 0 if ship.heat <= .75 else None
        return {
            "propulsion": {
                "maximum_speed_km_s": round(250 * min(1.25, ship.power.propulsion / .24), 1),
                "turn_rate_deg_s": round(16 * max(.15, ship.power.propulsion), 2),
            },
            "sensors": {
                "stability": round(self._sensor_stability(), 3),
                "nominal_scan_rate_pct_s": round(max(.005, ship.power.sensors * (1 - noise) * .10) * 100, 2),
            },
            "communications": {
                "transmitter_ready": ship.power.communications >= .03,
                "allocated_mw": round(ship.reactor_output_mw * ship.power.communications, 1),
            },
            "shields": {
                "target_strength": round(min(1, ship.power.shields / .20), 3),
                "recharge_pct_s": round(min(.025, ship.power.shields * .125) * 100, 2),
            },
            "weapons": {
                "firing_bus_ready": ship.power.weapons >= .04,
                "charge_rate_pct_s": round((.015 + ship.power.weapons * .42) * 100, 2) if ship.power.weapons >= .02 else 0,
            },
            "cooling": {
                "heat_removal_pct_s": round(ship.power.cooling * 7.5, 2),
                "weapon_cooldown_rate": round(.5 + ship.power.cooling * 3, 2),
                "net_heat_pct_s": round(net_heat_per_s * 100, 3),
                "trend": "cooling" if net_heat_per_s < -.0001 else "heating" if net_heat_per_s > .0001 else "stable",
                "eta_safe_s": round(eta_safe_s, 1) if eta_safe_s is not None else None,
            },
        }

    def _weapon_control_projection(self, station: StationRole, encounter: Any | None) -> dict[str, Any] | None:
        if station not in {StationRole.INTEGRATED, StationRole.COMMAND, StationRole.ENGINEERING, StationRole.TACTICAL}:
            return None
        ship = self.state.ship
        solution = self._weapon_solution(encounter) if encounter and encounter.status == "active" and encounter.npc else None
        required = {"warning": .15, "precision": .45, "full": .8}
        blockers: list[str] = []
        if not solution:
            blockers.append("No active tracked vessel")
        else:
            if not solution["in_range"]:
                blockers.append("Target beyond selected weapon range")
            if solution["lock_quality"] < .25:
                blockers.append("Fire-control lock below 25%")
        if ship.power.weapons < .04:
            blockers.append("Weapons power below 4%")
        if ship.weapon_charge < required["warning"]:
            blockers.append(f"Charge {ship.weapon_charge:.0%}; warning discharge requires 15%")
        elif ship.weapon_charge < required["precision"]:
            blockers.append(f"Charge {ship.weapon_charge:.0%}; precision fire requires 45%")
        elif ship.weapon_charge < required["full"]:
            blockers.append(f"Charge {ship.weapon_charge:.0%}; full discharge requires 80%")
        if not ship.weapons_authorized:
            blockers.append("Command release not authorized for direct fire")
        if ship.selected_weapon == "kinetic_interceptor" and ship.kinetic_ammunition <= 0:
            blockers.append("Kinetic ammunition depleted")
        if ship.weapon_cooldown_s > 0:
            blockers.append(f"Cooling cycle {ship.weapon_cooldown_s:.1f}s")
        if ship.heat >= 1.1:
            blockers.append("Charging suspended above 110% heat")
        return {
            "authorized": ship.weapons_authorized,
            "selected_weapon": ship.selected_weapon,
            "display_name": "Focused Energy Projector" if ship.selected_weapon == "focused_energy" else "Kinetic Interceptor",
            "charge": round(ship.weapon_charge, 4),
            "cooldown_s": round(ship.weapon_cooldown_s, 2),
            "kinetic_ammunition": ship.kinetic_ammunition,
            "required_charge": required,
            "solution": solution,
            "blockers": blockers,
            "last_result": ship.last_weapon_result,
            "target_damage": ({
                "estimated_shields": round(encounter.target_shields, 1),
                "estimated_hull": round(encounter.target_hull, 1),
                "confidence": round(min(.95, .55 + ship.power.sensors), 2),
            } if solution and ship.scan_progress >= .75 else None),
        }

    def _contact_projection(self, encounter: Any | None) -> list[dict[str, Any]]:
        if not encounter or not encounter.npc or encounter.status == "departed":
            return []
        position = encounter.hidden_truth.get("source_position_km")
        if isinstance(position, list) and len(position) == 2:
            x_km, y_km = float(position[0]), float(position[1])
        else:
            identity = sum((index + 1) * ord(character) for index, character in enumerate(encounter.id))
            angle = math.radians(float(identity % 360))
            range_km = float(28_000 + identity % 58_000)
            x_km, y_km = math.cos(angle) * range_km, math.sin(angle) * range_km
        return [{
            "id": encounter.npc.id,
            "label": encounter.npc.vessel_name,
            "kind": "vessel",
            "x_km": round(x_km, 1),
            "y_km": round(y_km, 1),
            "range_km": round(math.hypot(x_km - self.state.ship.x_km, y_km - self.state.ship.y_km), 1),
            "bearing_deg": round(math.degrees(math.atan2(y_km - self.state.ship.y_km, x_km - self.state.ship.x_km)) % 360, 1),
            "confidence": .94,
            "status": "hostile" if encounter.phase == "hostile" or encounter.npc.intention in {"disable_intruder", "defensive"} else "tracked",
        }]

    def commit_director_beat(self, encounter: Any, parameters: dict[str, Any], proposal_id: str, milestone_event_id: str) -> CanonicalEvent | None:
        cue = str(parameters.get("public_cue", "")).strip()[:500]
        decision = str(parameters.get("next_decision", "")).strip()[:300]
        if not cue and not decision:
            return None
        pressure_delta = min(.25, max(-.25, float(parameters.get("pressure_delta", 0))))
        novelty_cost = min(.25, max(0, float(parameters.get("novelty_cost", 0))))
        director = self.state.director
        director.narrative_pressure = min(1, max(0, director.narrative_pressure + pressure_delta))
        director.novelty_budget = min(1, max(0, director.novelty_budget - novelty_cost))
        if decision:
            director.unresolved_threads.append(decision)
            director.unresolved_threads = director.unresolved_threads[-12:]
        if cue and cue not in encounter.public_summary:
            encounter.public_summary = f"{encounter.public_summary} {cue}"
        deadline_delta = min(60, max(-60, float(parameters.get("deadline_delta_s", 0))))
        if encounter.deadline_s is not None:
            encounter.deadline_s = max(5, encounter.deadline_s + deadline_delta)
        return self.event(
            "director_beat_committed",
            payload={
                "beat_type": str(parameters.get("beat_type", "cue"))[:40],
                "public_cue": cue,
                "next_decision": decision,
                "pressure": round(director.narrative_pressure, 3),
                "deadline_delta_s": deadline_delta,
            },
            targets=[encounter.id],
            source_kind="approved_proposal",
            source_id=proposal_id,
            caused_by=[milestone_event_id],
        )

    def _workflow_projection(self, encounter: Any | None) -> dict[str, Any] | None:
        if not encounter:
            return None
        if encounter.hidden_truth.get("preset") == "friendly_contact_test":
            analysis = self.state.signal_analysis
            replied = bool((analysis and analysis.reply_sent) or (encounter.npc and any(message.startswith("Crew:") for message in encounter.npc.known_messages)))
            npc = encounter.npc
            data_shared = bool(npc and any(memory.get("action") == "share_data" for memory in npc.memories))
            maneuvered = bool(npc and npc.last_action in {"approach", "withdraw", "change_course", "depart"})
            contact_departed = encounter.status == "departed"
            return {
                "title": "Friendly contact conversation test",
                "steps": [
                    {"id": "receive", "label": "Automatically receive the carrier and frequency", "complete": bool(analysis and analysis.acquired)},
                    {"id": "translate", "label": "Translate the opening greeting", "complete": bool(analysis and analysis.interpretation_confidence >= .55)},
                    {"id": "reply", "label": "Enter the displayed frequency and send a reply", "complete": replied},
                    {"id": "request", "label": "Receive and answer a concrete request", "complete": bool(npc and npc.current_request and len(npc.memories) >= 1)},
                    {"id": "exchange", "label": "Build trust and receive shared information", "complete": data_shared},
                    {"id": "maneuver", "label": "Invite an approach, provoke withdrawal, or end contact", "complete": maneuvered, "optional": True},
                ],
                "next_action": "Select another destination; this contact has departed." if contact_departed else ("Enter the displayed carrier frequency and send any reply from Communications." if not replied else (npc.current_request if npc and npc.current_request else "Ask a question, invite the vessel closer, say farewell, or warp away.")),
                "result": "CONTACT ENDED — THE OTHER VESSEL HAS DEPARTED." if contact_departed else ("LOW-PRESSURE TEST PRESET — CONTACT WINDOW IS TWO HOURS." if not replied else "CONTACT ESTABLISHED — CONVERSATION CHANNEL REMAINS OPEN."),
                "result_severity": "status",
            }
        if encounter.family != "artificial_signal":
            thread = next((item for item in self.state.world_threads if any(entry.get("encounter_id") == encounter.id for entry in item.history)), None)
            if not encounter.npc:
                return {
                    "title": encounter.title,
                    "steps": [
                        {"id": "detect", "label": "Detect the investigation target", "complete": True},
                        {"id": "scan", "label": "Collect target scan evidence (75% or more)", "complete": self._encounter_evidence_depth() >= .75},
                        {"id": "report", "label": "Select observations and record a conclusion", "complete": encounter.status == "resolved"},
                    ],
                    "next_action": "Choose how to use the findings, or select another destination." if encounter.status == "resolved" else "Review the observations and record an evidence-backed conclusion in the Activity Board." if self._encounter_evidence_depth() >= .75 else "Open Science, select this encounter target, and collect scan evidence.",
                }
            return {
                "title": thread.title if thread else "Encounter investigation",
                "steps": [
                    {"id": "initial", "label": thread.history[0].get("event", "Detect the situation") if thread else "Detect the situation", "complete": True},
                    *([{"id": f"stage-{index}", "label": action, "complete": bool(thread and thread.stage > index)} for index, action in enumerate({
                        "ordinary_survey": ["Run a close survey", "Collect a documented sample", "Publish the finding"],
                        "damaged_vessel": ["Assess vessel damage", "Offer technical assistance", "Stabilize the vessel"],
                        "environmental_hazard": ["Measure the disturbance", "Plot a safe route", "Protect nearby traffic"],
                        "disputed_boundary": ["Identify your vessel", "Negotiate passage", "Record the agreement"],
                        "ancient_site": ["Map the structure", "Estimate its age", "Recover a documented sample"],
                    }[encounter.family])]),
                    {"id": "resolve", "label": "Choose an outcome", "complete": encounter.status == "resolved"},
                ],
                "next_action": thread.next_actions[0] if thread and thread.next_actions else ("Select a follow-up activity or another destination." if encounter.status == "resolved" else "Review evidence and choose an outcome."),
            }
        localization = self._localization_projection(encounter.target_id)
        analysis = self.state.signal_analysis
        acquired = bool(analysis and analysis.encounter_id == encounter.id and analysis.acquired)
        structured = bool(acquired and analysis and analysis.structure_result)
        demodulated = bool(acquired and analysis and analysis.demodulation_confidence >= .55)
        interpreted = bool(acquired and analysis and analysis.interpretation_confidence >= .55)
        replied = bool(acquired and analysis and analysis.reply_sent)
        steps = [
            {"id": "bearing", "label": "Record first direction-finding bearing", "complete": len(localization["measurements"]) >= 1},
            {"id": "localize", "label": "Move and cross a second bearing", "complete": localization["estimated_x_km"] is not None},
            {"id": "acquire", "label": "Acquire the carrier in Communications", "complete": acquired},
            {"id": "classify", "label": "Test whether the carrier contains repeatable structure", "complete": structured},
            {"id": "separate", "label": "Separate contamination and confirm preserved structure", "complete": bool(analysis and analysis.structure_result == "structured_carrier")},
            {"id": "demodulate", "label": "Recover a stable symbol frame", "complete": demodulated},
            {"id": "interpret", "label": "Run the Universal Translator", "complete": interpreted},
            {"id": "reply", "label": "Transmit a translated reply and establish contact", "complete": replied},
            {"id": "conclude", "label": "Record the investigation outcome", "complete": encounter.status == "resolved"},
        ]
        if encounter.phase == "signal_lost":
            for step in steps:
                if not step["complete"]:
                    step["failed"] = True
            return {
                "title": "Contact attempt failed",
                "steps": steps,
                "next_action": "The live carrier is gone. Review the retained recording or select another destination.",
                "result": "SIGNAL LOST — NO CONTACT ESTABLISHED. The deadline expired before a translated reply reached the source.",
                "result_severity": "critical",
            }
        next_action = next((step["label"] for step in steps if not step["complete"] and not step.get("optional")), "Investigation complete.")
        return {"title": "Artificial-signal investigation", "steps": steps, "next_action": next_action}

    def _signal_lab_projection(self, station: StationRole) -> dict[str, Any] | None:
        if station not in {StationRole.INTEGRATED, StationRole.COMMUNICATIONS, StationRole.SCIENCE}:
            return None
        encounter = self.state.current_encounter
        analysis = self.state.signal_analysis
        if encounter and encounter.phase == "signal_lost" and (not analysis or analysis.encounter_id != encounter.id or not analysis.acquired):
            return {"access": "lost", "live": False, "detected_frequency_mhz": self._detected_signal_frequency(encounter), "tuning_tolerance_khz": 50, "guidance": "CARRIER LOST. NO SIGNAL RECORDING WAS ACQUIRED BEFORE THE DEADLINE."}
        if not encounter or not analysis or analysis.encounter_id != encounter.id or not analysis.acquired:
            return {
                "access": "available" if station in {StationRole.INTEGRATED, StationRole.COMMUNICATIONS} else "awaiting_acquisition",
                "live": True,
                "detected_frequency_mhz": self._detected_signal_frequency(encounter) if encounter and encounter.family == "artificial_signal" else None,
                "tuning_tolerance_khz": 50,
                "guidance": "ACQUIRE A FOUR-CHANNEL WIDEBAND DATASET." if station in {StationRole.INTEGRATED, StationRole.COMMUNICATIONS} else "WAITING FOR COMMUNICATIONS TO ACQUIRE AND ROUTE A DATASET.",
            }
        if not analysis.workspace_open:
            return {
                "access": "archived",
                "live": False,
                "detected_frequency_mhz": self._detected_signal_frequency(encounter),
                "tuned_frequency_mhz": analysis.tuned_frequency_mhz,
                "recording_retained": analysis.recording_retained,
                "guidance": "LIVE CARRIER LOST. DATA PANELS RESET. OPEN THE RETAINED RECORDING FOR POST-INCIDENT ANALYSIS OR LEAVE THE WORKSPACE CLEARED.",
                "analysis_summary": {
                    "structure_result": analysis.structure_result,
                    "translation_status": analysis.translation_status,
                    "reply_sent": analysis.reply_sent,
                    "processing_steps": len(analysis.processing_log),
                },
            }
        if station == StationRole.SCIENCE and not analysis.shared_with_science:
            return {"access": "awaiting_share", "guidance": "DATASET EXISTS. WAITING FOR COMMUNICATIONS TO ROUTE IT TO SCIENCE."}
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        key = (
            encounter.id,
            analysis.version,
            tuple(sorted(recipe.items())),
            analysis.pca_cutoff,
            analysis.pca_selected_side,
            analysis.dmaps_epsilon,
            analysis.dmaps_diffusion_time,
            analysis.dmaps_neighbors,
        )
        if not self._signal_cache or self._signal_cache[0] != key:
            signal = synthesize_signal(recipe, self.state.seed)
            pca = pca_analysis(signal, analysis.pca_cutoff, analysis.pca_selected_side)
            dmaps = diffusion_maps(signal, pca, analysis.dmaps_epsilon, analysis.dmaps_diffusion_time, analysis.dmaps_neighbors)
            public_pca = {name: value for name, value in pca.items() if name != "reconstructed_channels"}
            self._signal_cache = (key, {
                "sample_rate_hz": signal["sample_rate_hz"],
                "times": signal["times"],
                "channels": signal["channels"],
                "spectrogram": spectrogram(signal),
                "pca": public_pca,
                "dmaps": dmaps,
            })
        products = self._signal_cache[1]
        if station in {StationRole.INTEGRATED, StationRole.COMMUNICATIONS}:
            if not analysis.structure_result:
                guidance = "RUN THE STRUCTURE TEST. PCA IS OPTIONAL UNLESS THE TEST REPORTS CORRELATED CONTAMINATION."
            elif analysis.structure_result == "structured_but_contaminated" and not analysis.pca_configured:
                guidance = "REPEATABLE STRUCTURE IS PRESENT BUT CONTAMINATED. USE THE PCA PARTITION, RECONSTRUCT A SIDE, THEN RUN THE STRUCTURE TEST AGAIN."
            elif analysis.structure_result == "inconclusive":
                guidance = "THE SELECTED PCA SIDE DID NOT PRESERVE STABLE STRUCTURE. RECONSTRUCT THE OTHER SIDE AND RERUN THE STRUCTURE TEST."
            elif not analysis.demodulation_method or analysis.demodulation_confidence < .55:
                guidance = "TRY A DEMODULATOR. A WRONG METHOD WILL FAIL TO PRODUCE STABLE SYMBOL FRAMES; COMPARE THE CONFIDENCE RESULT."
            elif not analysis.interpretation:
                guidance = "STABLE SYMBOL FRAMES RECOVERED. RUN SYMBOL INTERPRETATION."
            elif analysis.interpretation_confidence < .55:
                guidance = "INTERPRETATION IS NONSENSE BECAUSE THE SYMBOL FRAME IS UNSTABLE. TRY ANOTHER DEMODULATOR."
            elif not analysis.reply_sent:
                guidance = "MESSAGE RECOVERED. YOU MAY REPLY ON THE RECOVERED CHANNEL OR CONCLUDE THE INVESTIGATION."
            else:
                guidance = "REPLY ACKNOWLEDGED. THE INVESTIGATION MAY BE CONCLUDED."
        else:
            guidance = "OPTIONAL ADVANCED ANALYSIS: USE DIFFUSION MAPS ONLY TO TEST WHETHER RESIDUAL SAMPLES FORM A PHYSICAL OR INSTRUMENTAL MANIFOLD."
        return {
            "access": "granted",
            "live": encounter.status == "active" and encounter.phase != "signal_lost",
            "detected_frequency_mhz": self._detected_signal_frequency(encounter),
            "tuned_frequency_mhz": analysis.tuned_frequency_mhz,
            "tuning_tolerance_khz": 50,
            "guidance": guidance,
            "analysis": analysis.model_dump(mode="json"),
            **products,
        }

    def _detected_signal_frequency(self, encounter: Any) -> float:
        recipe = validate_signal_recipe(encounter.hidden_truth.get("signal_recipe"), self.state.seed, encounter.family)
        return round(float(recipe["center_frequency_mhz"]), 3)

    def _authorized_alerts(self, station: StationRole, sensor_stability: float) -> list[dict[str, str]]:
        ship = self.state.ship
        encounter = self.state.current_encounter
        alerts: list[dict[str, str]] = []
        if ship.heat >= 1:
            alerts.append({"severity": "critical", "source": "ENGINEERING", "message": "Thermal limit exceeded — hull integrity is degrading"})
        elif ship.heat >= .75:
            alerts.append({"severity": "caution", "source": "ENGINEERING", "message": "Thermal index elevated — increase cooling or reduce load"})
        if ship.hull < .75:
            alerts.append({"severity": "critical" if ship.hull < .4 else "caution", "source": "DAMAGE CONTROL", "message": f"Hull integrity at {ship.hull:.0%}"})
        if encounter and encounter.status == "active":
            if encounter.deadline_s is not None and encounter.deadline_s <= 30:
                alerts.append({"severity": "critical", "source": "COMMAND", "message": f"Time-critical development estimated in {encounter.deadline_s:.0f} seconds"})
            if encounter.phase in {"hostile", "storm_active", "critical"}:
                alerts.append({"severity": "critical", "source": "TACTICAL", "message": f"Active hazard: {encounter.phase.replace('_', ' ')}"})
            induction = encounter.environmental_effects.get("power_induction", 0)
            if ship.scan_progress >= .2 and induction >= .12 and station in {StationRole.INTEGRATED, StationRole.COMMAND, StationRole.ENGINEERING, StationRole.SCIENCE}:
                alerts.append({"severity": "caution", "source": "SENSORS", "message": "External energy coupling detected on ship power systems"})
        if encounter and encounter.phase == "signal_lost":
            alerts.append({"severity": "critical", "source": "COMMUNICATIONS", "message": "CONTACT LOST — carrier faded before a translated reply; no contact established"})
        if sensor_stability < .35 and station in {StationRole.INTEGRATED, StationRole.COMMAND, StationRole.SCIENCE}:
            alerts.append({"severity": "caution", "source": "SENSORS", "message": "Low sensor stability — displayed readings have increased variation"})
        if ship.defensive_posture:
            alerts.append({"severity": "status", "source": "TACTICAL", "message": "Defensive field active"})
        if ship.weapons_authorized and station in {StationRole.INTEGRATED, StationRole.COMMAND, StationRole.TACTICAL}:
            alerts.append({"severity": "caution", "source": "TACTICAL", "message": "Weapons release authorized"})
        if ship.power.weapons < .04 and station in {StationRole.INTEGRATED, StationRole.ENGINEERING, StationRole.TACTICAL}:
            alerts.append({"severity": "status", "source": "WEAPONS", "message": "Weapons bus below firing minimum — allocate at least 4% power"})
        return alerts

    def _time_critical(self) -> bool:
        encounter = self.state.current_encounter
        return bool(encounter and encounter.status == "active" and encounter.deadline_s is not None)

    def _active_encounter(self, require_resolved: bool = False):
        encounter = self.state.current_encounter
        if not encounter:
            raise CommandError("there is no current encounter")
        if require_resolved and encounter.status != "resolved":
            raise CommandError("the encounter must be resolved first")
        if not require_resolved and encounter.status != "active":
            raise CommandError("the encounter is not active")
        return encounter

    @staticmethod
    def _require_role(command: PlayerCommand, allowed: set[StationRole]) -> None:
        if command.station not in allowed:
            raise CommandError(f"{command.station} is not authorized for this command")

    @staticmethod
    def _observed_intention(intention: str) -> str:
        return {
            "observe": "holding position",
            "request_assistance": "seeking assistance",
            "demand_identification": "awaiting identification",
            "defensive": "defensive posture",
            "disable_intruder": "weapons active",
            "cooperate": "cooperative posture",
            "investigate_claim": "evaluating message",
        }.get(intention, "uncertain")
