from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .models import CanonicalEvent, GameState
from .continuity import validate_universe_consistency


class SaveIntegrityError(RuntimeError):
    pass


def _markdown(frontmatter: dict[str, Any], title: str, body: str) -> str:
    rendered = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True, width=100)
    return f"---\n{rendered}---\n\n# {title}\n\n{body.rstrip()}\n"


def _read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SaveIntegrityError(f"missing YAML front matter: {path}")
    try:
        raw = text.split("---\n", 2)[1]
        value = yaml.safe_load(raw)
    except (IndexError, yaml.YAMLError) as exc:
        raise SaveIntegrityError(f"invalid YAML front matter: {path}") from exc
    if not isinstance(value, dict):
        raise SaveIntegrityError(f"front matter is not a mapping: {path}")
    return value


class SaveStore:
    """Canonical Markdown persistence with atomic replacement and replayable event chunks."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def universe_path(self, universe_id: str) -> Path:
        if not universe_id.startswith("universe_") or not universe_id.replace("_", "").isalnum():
            raise ValueError("invalid universe ID")
        return self.root / universe_id

    def list_universes(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("universe_*/universe.md")):
            try:
                data = _read_frontmatter(path)
                result.append({
                    "id": data["id"],
                    "name": data["name"],
                    "seed": data["seed"],
                    "universe_time_ms": data.get("universe_time_ms", 0),
                })
            except (KeyError, SaveIntegrityError):
                continue
        return result

    def initialize(self, state: GameState, session_id: str) -> None:
        base = self.universe_path(state.universe_id)
        for directory in (
            "rules", "events", "systems", "objects", "civilizations", "factions", "artifacts",
            "mysteries", "ships", "characters", "npcs", "technologies", "languages", "knowledge",
            "generated_mechanics", "checkpoints",
        ):
            (base / directory).mkdir(parents=True, exist_ok=True)
        self._write_rules(base)
        self.commit(state, [], session_id)

    def commit(self, state: GameState, events: list[CanonicalEvent], session_id: str) -> None:
        base = self.universe_path(state.universe_id)
        base.mkdir(parents=True, exist_ok=True)
        self._write_universe(base, state)
        self._write_ship(base, state)
        self._write_characters(base, state)
        self._write_npcs(base, state)
        self._write_systems(base, state)
        self._write_world_threads(base, state)
        state.continuity_report = validate_universe_consistency(state)
        self._write_continuity_report(base, state)
        if events:
            self._append_events(base, events, session_id)
        self._write_checkpoint(base, state)
        self.rebuild_index(state.universe_id)

    def load(self, universe_id: str) -> GameState:
        checkpoint = self.universe_path(universe_id) / "checkpoints" / "current.md"
        data = _read_frontmatter(checkpoint)
        state_data = data.get("state")
        if not isinstance(state_data, dict):
            raise SaveIntegrityError("checkpoint has no state mapping")
        state = GameState.model_validate(state_data)
        if state.universe_id != universe_id:
            raise SaveIntegrityError("checkpoint universe ID mismatch")
        return state

    def verify(self, universe_id: str) -> dict[str, Any]:
        base = self.universe_path(universe_id)
        state = self.load(universe_id)
        problems: list[str] = []
        if not (base / "ships" / f"{state.ship.id}.md").exists():
            problems.append("ship entity document missing")
        for sid in state.systems:
            if not (base / "systems" / f"{sid}.md").exists():
                problems.append(f"system entity document missing: {sid}")
        event_files = sorted((base / "events").glob("*.md"))
        return {
            "valid": not problems,
            "problems": problems,
            "universe_id": universe_id,
            "event_count": state.event_count,
            "event_chunks": len(event_files),
            "systems": len(state.systems),
            "index_present": (base / "cache.sqlite3").exists(),
        }

    def rebuild_index(self, universe_id: str) -> Path:
        base = self.universe_path(universe_id)
        index_path = base / "cache.sqlite3"
        connection = sqlite3.connect(index_path)
        try:
            connection.execute("DROP TABLE IF EXISTS documents")
            connection.execute("CREATE VIRTUAL TABLE documents USING fts5(path, entity_type, title, content)")
            for path in base.rglob("*.md"):
                relative = path.relative_to(base).as_posix()
                if relative.startswith("events/") or relative.startswith("checkpoints/"):
                    continue
                text = path.read_text(encoding="utf-8")
                try:
                    frontmatter = _read_frontmatter(path)
                except SaveIntegrityError:
                    continue
                title = next((line.removeprefix("# ") for line in text.splitlines() if line.startswith("# ")), path.stem)
                connection.execute(
                    "INSERT INTO documents(path, entity_type, title, content) VALUES (?, ?, ?, ?)",
                    (relative, str(frontmatter.get("entity_type", "unknown")), title, text),
                )
            connection.commit()
        finally:
            connection.close()
        return index_path

    def search(self, universe_id: str, query: str, limit: int = 20) -> list[dict[str, str]]:
        if not query.strip():
            return []
        index_path = self.universe_path(universe_id) / "cache.sqlite3"
        if not index_path.exists():
            self.rebuild_index(universe_id)
        connection = sqlite3.connect(index_path)
        try:
            rows = connection.execute(
                "SELECT path, entity_type, title FROM documents WHERE documents MATCH ? LIMIT ?",
                (query, max(1, min(limit, 100))),
            ).fetchall()
            return [{"path": row[0], "entity_type": row[1], "title": row[2]} for row in rows]
        finally:
            connection.close()

    def _write_universe(self, base: Path, state: GameState) -> None:
        data = {
            "schema_version": state.schema_version,
            "id": state.universe_id,
            "name": state.universe_name,
            "seed": state.seed,
            "universe_time_ms": state.universe_time_ms,
            "consequence_mode": state.consequence_mode,
            "ship_id": state.ship.id,
            "event_count": state.event_count,
        }
        body = (
            "This universe is generated lazily from its seed. Structured event records are authoritative "
            "for changes; this document is its current high-level summary."
        )
        self._atomic_write(base / "universe.md", _markdown(data, state.universe_name, body))

    def _write_ship(self, base: Path, state: GameState) -> None:
        ship = state.ship
        data = {"schema_version": 1, "entity_type": "ship", "state": ship.model_dump(mode="json")}
        capabilities = "\n".join(f"- {cap.name} ({cap.category}, condition {cap.condition:.0%})" for cap in ship.capabilities) or "- None"
        body = f"## Installed capabilities\n\n{capabilities}\n\n## Current location\n\nSystem `{ship.system_id}`."
        self._atomic_write(base / "ships" / f"{ship.id}.md", _markdown(data, ship.name, body))

    def _write_characters(self, base: Path, state: GameState) -> None:
        for character in state.characters:
            data = {"schema_version": 1, "entity_type": "character", "state": character.model_dump(mode="json")}
            body = f"## Backstory\n\n{character.backstory}\n\n## Expertise\n\n" + ("\n".join(f"- {item}" for item in character.expertise) or "- Unspecified")
            self._atomic_write(base / "characters" / f"{character.id}.md", _markdown(data, character.name, body))

    def _write_npcs(self, base: Path, state: GameState) -> None:
        encounter = state.current_encounter
        actors = dict(state.known_npcs)
        if encounter and encounter.npc:
            actors[encounter.npc.id] = encounter.npc
        for npc in actors.values():
            data = {
                "schema_version": 1,
                "entity_type": "npc",
                "visibility": "entity-private",
                "state": npc.model_dump(mode="json"),
            }
            body = (
                f"## Current intention\n\n{npc.intention}\n\n"
                f"## Relationship\n\n{npc.relationship_label} (disposition {npc.disposition:.2f})\n\n"
                "This actor record contains private beliefs and memory. Player stations receive only validated observable projections."
            )
            self._atomic_write(base / "npcs" / f"{npc.id}.md", _markdown(data, npc.name, body))

    def _write_systems(self, base: Path, state: GameState) -> None:
        for system in state.systems.values():
            data = {"schema_version": 1, "entity_type": "system", "state": system.model_dump(mode="json")}
            body = "## Known bodies\n\n" + "\n".join(f"- **{body.name}:** {body.summary}" for body in system.bodies)
            self._atomic_write(base / "systems" / f"{system.id}.md", _markdown(data, system.name, body))

    def _write_world_threads(self, base: Path, state: GameState) -> None:
        for thread in state.world_threads:
            data = {"schema_version": 1, "entity_type": "world_thread", "state": thread.model_dump(mode="json")}
            actions = "\n".join(f"- {action}" for action in thread.next_actions) or "- No pending actions."
            evidence = "\n".join(f"- {item}" for item in thread.evidence) or "- No recorded evidence."
            body = f"## Status\n\n{thread.status}, stage {thread.stage}\n\n## Next actions\n\n{actions}\n\n## Evidence\n\n{evidence}"
            self._atomic_write(base / "knowledge" / f"{thread.id}.md", _markdown(data, thread.title, body))

    def _append_events(self, base: Path, events: list[CanonicalEvent], session_id: str) -> None:
        safe_session = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")
        if not safe_session:
            raise ValueError("invalid session ID")
        path = base / "events" / f"{safe_session}.md"
        if path.exists():
            current = path.read_text(encoding="utf-8").rstrip() + "\n\n"
        else:
            current = _markdown(
                {"schema_version": 1, "session_id": safe_session, "sealed": False},
                f"Event Log — {safe_session}",
                "Append-only canonical events for this play session.",
            ).rstrip() + "\n\n"
        additions: list[str] = []
        for event in events:
            payload = yaml.safe_dump(event.model_dump(mode="json"), sort_keys=False, allow_unicode=True)
            additions.append(f"## {event.universe_time_ms} — {event.event_type}\n\n```yaml\n{payload}```")
        self._atomic_write(path, current + "\n\n".join(additions) + "\n")

    def _write_checkpoint(self, base: Path, state: GameState) -> None:
        serialized = state.model_dump(mode="json")
        canonical = yaml.safe_dump(serialized, sort_keys=True, allow_unicode=True)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        data = {
            "schema_version": 1,
            "universe_id": state.universe_id,
            "universe_time_ms": state.universe_time_ms,
            "event_count": state.event_count,
            "state_sha256": digest,
            "state": serialized,
        }
        self._atomic_write(base / "checkpoints" / "current.md", _markdown(data, "Current Checkpoint", "Atomic resumable state."))

    def _write_rules(self, base: Path) -> None:
        path = base / "rules" / "foundational-laws.md"
        if path.exists():
            return
        body = (
            "1. AI proposes; the simulation validates and commits.\n"
            "2. Sensors reveal partial observations, not hidden truth.\n"
            "3. Canonical events are immutable.\n"
            "4. Unknown facts may remain unresolved.\n"
            "5. Model failure never stops the physical simulation."
        )
        self._atomic_write(path, _markdown({"schema_version": 1, "entity_type": "universe_rules"}, "Foundational Laws", body))

    def _write_continuity_report(self, base: Path, state: GameState) -> None:
        report = state.continuity_report
        issues = report.get("issues", [])
        issue_text = "\n".join(f"- **{item['severity'].upper()} · {item['code']}:** {item['message']}" for item in issues) or "- No consistency issues detected."
        body = (
            "This is a derived diagnostic report, not a second source of canonical truth. It is rebuilt from the checkpoint and entity state on every commit.\n\n"
            f"## Status\n\n{'VALID' if report.get('valid') else 'INVALID'}\n\n"
            f"## Issues\n\n{issue_text}\n"
        )
        self._atomic_write(base / "knowledge" / "universe-consistency.md", _markdown(
            {"schema_version": 1, "entity_type": "continuity_report", **report},
            "Universe Consistency Report",
            body,
        ))

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
