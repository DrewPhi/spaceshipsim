from __future__ import annotations

import hashlib
import math
import random
import uuid

from .models import (
    Capability,
    CargoItem,
    CelestialBody,
    EncounterState,
    NPCState,
    SystemState,
)
from .signal_processing import default_signal_recipe


STAR_CLASSES = ("amber dwarf", "white main-sequence", "red dwarf", "blue-white star", "orange giant")
NAME_START = ("Aru", "Bel", "Cyr", "Dema", "Eli", "Fara", "Ione", "Kest", "Mora", "Naru", "Ossa", "Pela", "Rhy", "Sola", "Tavi", "Vey")
NAME_END = ("dan", "eth", "ia", "ion", "ora", "os", "une", "ara", "esh", "uum", "yr")
FAMILIES = (
    "ordinary_survey",
    "artificial_signal",
    "damaged_vessel",
    "environmental_hazard",
    "disputed_boundary",
    "ancient_site",
)


def _seeded_int(seed: int, namespace: str) -> int:
    digest = hashlib.sha256(f"{seed}:{namespace}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _stable_id(seed: int, namespace: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"space-sim-crew:{seed}:{namespace}").hex


def system_id(seed: int, coordinate: tuple[int, int]) -> str:
    return f"system_{_stable_id(seed, f'system:{coordinate[0]}:{coordinate[1]}')}"


def generate_system(seed: int, coordinate: tuple[int, int]) -> SystemState:
    rng = random.Random(_seeded_int(seed, f"system:{coordinate}"))
    name = f"{rng.choice(NAME_START)}{rng.choice(NAME_END)} {abs(coordinate[0]) + abs(coordinate[1]) + 1}"
    sid = system_id(seed, coordinate)
    bodies: list[CelestialBody] = [
        CelestialBody(
            id=f"body_{_stable_id(seed, f'{sid}:star')}",
            name=name,
            kind="star",
            summary=f"A {rng.choice(STAR_CLASSES)} with stable long-range navigation references.",
            properties={"activity": round(rng.uniform(0.05, 0.95), 3), "x_km": 0, "y_km": 0},
        )
    ]
    for orbit in range(1, rng.randint(3, 8)):
        kind = rng.choice(("planet", "planet", "planet", "belt"))
        body_name = f"{name}-{orbit}"
        orbital_radius_km = 35_000_000 * orbit * rng.uniform(0.82, 1.18)
        orbital_angle = rng.uniform(0, 360)
        bodies.append(
            CelestialBody(
                id=f"body_{_stable_id(seed, f'{sid}:{orbit}')}",
                name=body_name,
                kind=kind,
                orbit_index=orbit,
                summary="Long-range survey incomplete.",
                properties={
                    "temperature_k": rng.randint(45, 850),
                    "radius_km": rng.randint(300, 75_000) if kind == "planet" else rng.randint(50_000, 400_000),
                    "orbital_radius_km": round(orbital_radius_km),
                    "orbital_angle_deg": round(orbital_angle, 3),
                    "x_km": round(math.cos(math.radians(orbital_angle)) * orbital_radius_km),
                    "y_km": round(math.sin(math.radians(orbital_angle)) * orbital_radius_km),
                },
            )
        )
    x, y = coordinate
    neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
    return SystemState(
        id=sid,
        name=name,
        coordinate=coordinate,
        star_class=bodies[0].summary.split(" with", 1)[0].removeprefix("A "),
        bodies=bodies,
        neighbor_coordinates=neighbors,
    )


def generate_encounter(seed: int, system: SystemState) -> EncounterState:
    rng = random.Random(_seeded_int(seed, f"encounter:{system.coordinate}"))
    family = FAMILIES[rng.randrange(len(FAMILIES))]
    target = rng.choice(system.bodies[1:] or system.bodies)
    source_angle = rng.uniform(0, 360)
    source_range_km = rng.uniform(65_000, 115_000)
    source_position = [
        round(math.cos(math.radians(source_angle)) * source_range_km, 3),
        round(math.sin(math.radians(source_angle)) * source_range_km, 3),
    ]

    def truth(values: dict[str, object]) -> dict[str, object]:
        return {
            **values,
            "source_position_km": source_position,
            "signal_recipe": default_signal_recipe(_seeded_int(seed, f"signal:{system.id}"), family),
        }
    shared = {
        "target_id": target.id,
        "environmental_effects": {
            "sensor_noise": round(rng.uniform(0.05, 0.55), 3),
            "power_induction": round(rng.uniform(0, 0.22), 3),
            "navigation_drift": round(rng.uniform(0.01, 0.25), 3),
        },
    }
    salvage = CargoItem(
        id=f"cargo_{_stable_id(seed, f'salvage:{system.id}')}",
        name="Coherent Field Sampler",
        description="A compact instrument recovered from the encounter; its interfaces are unfamiliar but adaptable.",
        installable_capability=Capability(
            id=f"cap_{_stable_id(seed, f'capability:{system.id}')}",
            name="Coherent Field Sampler",
            category="hardware",
            power_mw=22,
            input_domains=["field", "particle"],
            output_domains=["coherence", "phase"],
            description="Reveals phase relationships that standard field instruments cannot resolve.",
        ),
    )

    if family == "ordinary_survey":
        return EncounterState(
            family=family,
            title="Quiet Survey Opportunity",
            public_summary=f"{target.name} has not been surveyed at close range.",
            hidden_truth=truth({"finding": "A rare but natural lattice has formed below the surface."}),
            salvage=None,
            **shared,
        )
    if family == "artificial_signal":
        return EncounterState(
            family=family,
            title="Patterned Narrow-Band Signal",
            public_summary=f"A weak repeating signal appears to originate near {target.name}.",
            hidden_truth=truth({"source": "An automated archive seeking compatible listeners.", "period_s": 31.4}),
            deadline_s=240,
            deadline_kind="signal_fades",
            salvage=salvage,
            **shared,
        )
    if family == "damaged_vessel":
        npc = NPCState(
            id=f"npc_{_stable_id(seed, f'npc:damaged:{system.id}')}",
            name=f"Coordinator {rng.choice(NAME_START)}{rng.choice(NAME_END)}",
            vessel_name=f"{rng.choice(NAME_START)}{rng.choice(NAME_END)}",
            culture="A cautious convoy society that values practical aid and precise promises.",
            disposition=-0.1,
            intention="request_assistance",
            patience_s=180,
            personality=["practical", "guarded", "duty-bound"],
            goals=["stabilize the vessel", "protect the crew", "obtain aid without exposing avoidable secrets"],
            beliefs=["precise promises are more reliable than reassurance"],
            fears=["life-support failure", "being blamed for the drive test"],
            relationship_label="cautious stranger",
            visible_activity="drifting with intermittent attitude control",
            visible_reason="The vessel is damaged and conserving power.",
            current_request="Offer a specific form of assistance before life support fails.",
        )
        return EncounterState(
            family=family,
            title="Disabled Vessel",
            public_summary="A vessel broadcasts an intermittent low-power emergency carrier.",
            hidden_truth=truth({"damage_cause": "A failed experimental drive test", "fear": "being blamed"}),
            npc=npc,
            deadline_s=180,
            deadline_kind="life_support_failure",
            salvage=salvage,
            **shared,
        )
    if family == "environmental_hazard":
        return EncounterState(
            family=family,
            title="Advancing Particle Front",
            public_summary="Long-range instruments show a fast-moving disturbance crossing the system.",
            hidden_truth=truth({"cause": "A natural stellar magnetic reconnection", "safe_vector_deg": rng.randrange(360)}),
            deadline_s=150,
            deadline_kind="storm_arrives",
            salvage=None,
            **shared,
        )
    if family == "disputed_boundary":
        npc = NPCState(
            id=f"npc_{_stable_id(seed, f'npc:boundary:{system.id}')}",
            name=f"Warden {rng.choice(NAME_START)}{rng.choice(NAME_END)}",
            vessel_name=f"Boundary Vessel {rng.randint(10, 99)}",
            culture="A territorial coalition whose law treats clear identification as a sign of respect.",
            disposition=-0.35,
            intention="demand_identification",
            patience_s=120,
            personality=["formal", "territorial", "procedural"],
            goals=["identify the intruder", "enforce the boundary without unnecessary violence"],
            beliefs=["clear identification demonstrates respect for local law"],
            fears=["a disguised hostile incursion", "appearing weak to nearby traffic"],
            relationship_label="suspicious authority",
            visible_activity="matching the crew vessel's course",
            visible_reason="The patrol is waiting for verifiable identification.",
            current_request="State your identity, origin, and purpose.",
        )
        return EncounterState(
            family=family,
            title="Boundary Challenge",
            public_summary="An unknown patrol vessel is matching course and transmitting a structured challenge.",
            hidden_truth=truth({"reinforcements_available": True, "prefers_nonviolence": True}),
            npc=npc,
            deadline_s=120,
            deadline_kind="patrol_escalates",
            salvage=salvage,
            **shared,
        )
    return EncounterState(
        family="ancient_site",
        title="Buried Geometric Structure",
        public_summary=f"Low-resolution mapping of {target.name} shows a formation unlikely to be natural.",
        hidden_truth=truth({
            "origin": "unresolved",
            "known_fact": "The structure predates all nearby settlements.",
            "period_s": 31.4,
        }),
        deadline_s=None,
        salvage=salvage,
        **shared,
    )


def generate_friendly_contact_encounter(seed: int, system: SystemState) -> EncounterState:
    """Deterministic low-pressure contact used to exercise the full communications loop."""
    rng = random.Random(_seeded_int(seed, f"friendly-contact:{system.id}"))
    target = system.bodies[1] if len(system.bodies) > 1 else system.bodies[0]
    angle = rng.uniform(0, 360)
    distance = rng.uniform(38_000, 62_000)
    recipe = default_signal_recipe(_seeded_int(seed, f"friendly-contact-signal:{system.id}"), "artificial_signal")
    recipe.update({
        "center_frequency_mhz": round(rng.uniform(700, 1800), 3),
        "correlated_noise": .3,
        "nonlinear_noise": .12,
        "impulse_rate_hz": .1,
        "signal_kind": "structured",
        "modulation": "amplitude",
        "payload": "Greetings. We detected your vessel and invite a peaceful exchange of names, origins, science, and culture.",
    })
    npc = NPCState(
        id=f"npc_{_stable_id(seed, f'npc:friendly:{system.id}')}",
        name="Contact Liaison",
        vessel_name="Independent Survey Vessel",
        culture="A cooperative exploratory society that values patient questions, reciprocal scientific exchange, and clear statements of uncertainty.",
        disposition=.7,
        intention="open_exchange",
        patience_s=7_200,
        known_messages=["Contact Liaison: Greetings. We detected your vessel and invite a peaceful exchange."],
        personality=["curious", "patient", "reciprocal", "careful about uncertainty"],
        goals=["learn the crew's identity and origin", "exchange a useful scientific observation", "establish a durable peaceful relationship"],
        beliefs=["trust grows through reciprocal disclosure", "uncertainty should be stated plainly"],
        fears=["accidental escalation", "one-sided extraction of information"],
        relationship_label="welcoming new contact",
        visible_activity="holding position with communications open",
        visible_reason="The vessel is inviting a reciprocal cultural and scientific exchange.",
        current_request="Introduce your vessel and share one question or observation.",
    )
    return EncounterState(
        family="disputed_boundary",
        title="Friendly Contact Test",
        target_id=target.id,
        status="active",
        phase="open_channel",
        public_summary="A friendly exploratory vessel is holding position with an open communications channel for an extended conversation test.",
        environmental_effects={"sensor_noise": .08, "power_induction": 0, "navigation_drift": .01},
        hidden_truth={
            "preset": "friendly_contact_test",
            "source_position_km": [round(math.cos(math.radians(angle)) * distance, 3), round(math.sin(math.radians(angle)) * distance, 3)],
            "signal_recipe": recipe,
        },
        npc=npc,
        deadline_s=7_200,
        deadline_kind="contact_window_closes",
        salvage=None,
    )
