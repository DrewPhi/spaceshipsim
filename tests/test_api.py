import asyncio
import socket

import httpx
import pytest
import uvicorn
import websockets

from space_sim_crew.api import create_app


@pytest.mark.asyncio
async def test_create_join_and_real_websocket_command(tmp_path) -> None:
    app = create_app(tmp_path / "saves")
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    server_task = asyncio.create_task(server.serve(sockets=[listener]))
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(.01)
    assert server.started

    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            home = await client.get("/")
            assert home.status_code == 200
            assert "Space Simulation Crew" in home.text
            response = await client.post("/api/v1/universes", json={
                "universe_name": "API Reach",
                "seed": 77,
                "ship_name": "Relay",
                "crew_capacity": 4,
                "character_name": "Operator",
                "backstory": "Network test character.",
            })
            assert response.status_code == 200
            session = response.json()
            join = await client.post(f"/api/v1/sessions/{session['session_id']}/join", json={
                "display_name": "Operator",
                "character_id": session["characters"][0]["id"],
                "station": "integrated",
            })
            assert join.status_code == 200
            joined = join.json()

            async with websockets.connect(f"ws://127.0.0.1:{port}{joined['websocket_path']}") as websocket:
                snapshot = await asyncio.wait_for(websocket.recv(), timeout=2)
                import json

                decoded = json.loads(snapshot)
                assert decoded["type"] == "snapshot"
                assert decoded["data"]["station"] == "integrated"
                await websocket.send(json.dumps({
                    "type": "command",
                    "client_sequence": 1,
                    "command_type": "set_flight",
                    "parameters": {"heading_deg": 45, "throttle": .5},
                }))
                seen_result = False
                for _ in range(5):
                    message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
                    if message["type"] == "command_result":
                        seen_result = True
                        break
                assert seen_result

            # The same station token reconnects and receives a fresh authorized snapshot.
            async with websockets.connect(f"ws://127.0.0.1:{port}{joined['websocket_path']}") as websocket:
                reconnected = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
                assert reconnected["type"] == "snapshot"
                assert reconnected["data"]["ship"]["target_heading_deg"] == 45

            diagnostics = await client.get(f"/api/v1/sessions/{session['session_id']}/diagnostics")
            assert diagnostics.status_code == 200
            assert diagnostics.json()["save"]["valid"] is True
    finally:
        server.should_exit = True
        await asyncio.wait_for(server_task, timeout=5)
