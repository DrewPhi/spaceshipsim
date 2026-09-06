from __future__ import annotations

from typing import Any

from .models import GameState


def validate_universe_consistency(state: GameState) -> dict[str, Any]:
    """Build a deterministic, non-authoritative diagnostic from canonical state."""
    issues: list[dict[str, str]] = []
    if state.ship.system_id not in state.systems:
        issues.append({"severity": "critical", "code": "ship_system_missing", "message": "The ship references a system that is not present."})
    encounter = state.current_encounter
    if encounter:
        system = state.systems.get(state.ship.system_id)
        body_ids = {body.id for body in system.bodies} if system else set()
        if encounter.target_id not in body_ids:
            issues.append({"severity": "critical", "code": "encounter_target_missing", "message": "The current encounter target is not present in the current system."})
        if encounter.npc:
            remembered = state.known_npcs.get(encounter.npc.id)
            if not remembered:
                issues.append({"severity": "caution", "code": "npc_registry_missing", "message": "The active contact is absent from the persistent actor registry."})
            elif remembered.name != encounter.npc.name or remembered.vessel_name != encounter.npc.vessel_name:
                issues.append({"severity": "critical", "code": "npc_identity_conflict", "message": "The active contact conflicts with its persistent identity."})
    known_systems = set(state.systems)
    known_npcs = set(state.known_npcs)
    thread_ids: set[str] = set()
    for thread in state.world_threads:
        if thread.id in thread_ids:
            issues.append({"severity": "critical", "code": "duplicate_thread", "message": f"Duplicate world-thread ID {thread.id}."})
        thread_ids.add(thread.id)
        if thread.origin_system_id not in known_systems:
            issues.append({"severity": "critical", "code": "thread_system_missing", "message": f"Thread {thread.title} references a missing origin system."})
        if thread.npc_id and thread.npc_id not in known_npcs:
            issues.append({"severity": "caution", "code": "thread_actor_missing", "message": f"Thread {thread.title} references an unknown actor."})
    return {
        "valid": not any(issue["severity"] == "critical" for issue in issues),
        "checked_at_universe_time_ms": state.universe_time_ms,
        "issues": issues,
        "counts": {
            "systems": len(state.systems),
            "persistent_actors": len(state.known_npcs),
            "world_threads": len(state.world_threads),
            "open_threads": sum(thread.status == "open" for thread in state.world_threads),
            "crew_knowledge": len(state.crew_knowledge),
            "canonical_events": state.event_count,
        },
    }
