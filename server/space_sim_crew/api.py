from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .models import StationRole
from .narrative.session import UniverseGodSessionManager as SessionManager
from .simulation import CommandError


class CreateUniverseRequest(BaseModel):
    universe_name: str = Field(min_length=1, max_length=80)
    seed: int | None = None
    ship_name: str = Field(min_length=1, max_length=80)
    crew_capacity: int = Field(default=6, ge=1, le=100)
    character_name: str = Field(min_length=1, max_length=80)
    backstory: str = Field(default="Independent deep-space explorer.", max_length=8_000)
    scenario_preset: Literal["random", "friendly_contact_test"] = "random"


class LoadUniverseRequest(BaseModel):
    universe_id: str


class JoinRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    character_id: str
    station: StationRole


class CreateCharacterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    backstory: str = Field(default="Independent deep-space explorer.", max_length=8_000)
    expertise: list[str] = Field(default_factory=list, max_length=20)


def create_app(saves_root: Path | None = None) -> FastAPI:
    root = saves_root or Path(os.getenv("SPACE_CREW_SAVES", "saves"))
    manager = SessionManager(root)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await manager.shutdown()

    app = FastAPI(title="Space Simulation Crew", version="0.1.0", lifespan=lifespan)
    app.state.sessions = manager

    @app.get("/api/v1/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "provider": manager.provider.capabilities().name,
            "provider_healthy": await manager.provider.health(),
            "active_sessions": len(manager.sessions),
        }

    @app.get("/api/v1/universes")
    async def universes() -> list[dict[str, Any]]:
        return manager.store.list_universes()

    @app.post("/api/v1/universes")
    async def create_universe(request: CreateUniverseRequest) -> dict[str, Any]:
        session = manager.create_universe(**request.model_dump())
        return session_summary(session)

    @app.post("/api/v1/sessions")
    async def load_universe(request: LoadUniverseRequest) -> dict[str, Any]:
        try:
            session = manager.load_universe(request.universe_id)
            return session_summary(session)
        except (ValueError, OSError) as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/v1/sessions/{session_id}")
    async def session_status(session_id: str) -> dict[str, Any]:
        try:
            return session_summary(manager.get(session_id))
        except CommandError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/v1/sessions/{session_id}/join")
    async def join(session_id: str, request: JoinRequest) -> dict[str, Any]:
        try:
            session = manager.get(session_id)
            connection = session.join(request.display_name, request.character_id, request.station)
            return {
                "player_id": connection.player_id,
                "token": connection.token,
                "station": connection.station,
                "websocket_path": f"/ws/v1/sessions/{session_id}?token={connection.token}",
            }
        except CommandError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/v1/sessions/{session_id}/characters")
    async def create_character(session_id: str, request: CreateCharacterRequest) -> dict[str, Any]:
        try:
            session = manager.get(session_id)
            from .models import CharacterState

            character = CharacterState(**request.model_dump())
            async with session.lock:
                session.state.characters.append(character)
                event = session.engine.event(
                    "character_created",
                    payload={"character": character.model_dump(mode="json")},
                    targets=[character.id],
                    source_kind="host_action",
                    visibility="public",
                )
                session.store.commit(session.state, [event], session.id)
            return character.model_dump(mode="json")
        except CommandError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/v1/sessions/{session_id}/diagnostics")
    async def diagnostics(session_id: str) -> dict[str, Any]:
        try:
            session = manager.get(session_id)
            return {**session.diagnostics(), "save": manager.store.verify(session.state.universe_id)}
        except (CommandError, ValueError, OSError) as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.websocket("/ws/v1/sessions/{session_id}")
    async def websocket_session(websocket: WebSocket, session_id: str, token: str) -> None:
        try:
            session = manager.get(session_id)
            session.connection(token)
        except CommandError:
            await websocket.close(code=4401, reason="invalid session or token")
            return
        await websocket.accept()
        await session.attach(token, websocket)
        try:
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "command":
                    try:
                        events = await session.command(token, message)
                        await session.send_to(token, {
                            "type": "command_result",
                            "client_sequence": message.get("client_sequence"),
                            "events": [event.model_dump(mode="json") for event in events],
                        })
                    except CommandError as exc:
                        await session.send_to(token, {
                            "type": "command_error",
                            "client_sequence": message.get("client_sequence"),
                            "error": str(exc),
                        })
                elif message.get("type") == "ping":
                    await session.send_to(token, {"type": "pong"})
        except WebSocketDisconnect:
            session.detach(token)

    dist = Path(__file__).resolve().parents[2] / "dist"
    if dist.exists():
        assets = dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}")
        async def client_app(path: str):
            candidate = dist / path
            if path and candidate.is_file() and candidate.resolve().is_relative_to(dist.resolve()):
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")
    else:
        @app.get("/")
        async def unbuilt_client() -> HTMLResponse:
            return HTMLResponse(
                "<!doctype html><html><head><title>Space Simulation Crew</title></head>"
                "<body><main><h1>Space Simulation Crew</h1><p>Client assets are not built yet.</p></main></body></html>"
            )

    return app


def session_summary(session: Any) -> dict[str, Any]:
    return {
        "session_id": session.id,
        "universe_id": session.state.universe_id,
        "universe_name": session.state.universe_name,
        "characters": [character.model_dump(mode="json") for character in session.state.characters],
        "ship": {"id": session.state.ship.id, "name": session.state.ship.name, "frame": session.state.ship.frame},
        "provider": session.ai.provider.capabilities().name,
    }


app = create_app()
