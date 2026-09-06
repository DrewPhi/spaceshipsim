# Space Simulation Crew

An original cooperative deep-space simulation for one or more players. A host runs the authoritative ship and universe simulation; crew members join specialized stations from web browsers on the same local network.

The current implementation targets the endless Minimal Playable Product described in [PROJECT_PLAN.md](PROJECT_PLAN.md).

## What is playable

- Solo integrated command or six specialized stations.
- Live cinematic flight, consequential power routing, heat, hull, shields, sensors, and hidden deadlines.
- Tactical fire control with command authorization, a rechargeable focused-energy weapon, finite kinetic interceptors, sensor-dependent lock, range, charge, cooldown, heat, shield-first damage, and hostile response.
- Endless seeded travel through lazily generated neighboring systems.
- Six encounter families with partial, station-specific observations.
- A multichannel signal-analysis workflow with Communications acquisition/PCA, explicit Science handoff, diffusion maps, spectrograms, provenance, and physical classification.
- A staged artificial-signal loop with visible objectives, structure testing, demodulator choice, failed-frame/nonsense outcomes, symbol interpretation, and reply acknowledgment.
- AI-proposed, server-validated signal recipes rendered into reproducible synthetic data by deterministic code.
- Persistent AI-controlled contacts with private goals, beliefs, fears, memory, relationships, and validated actions that can change range, requests, shared knowledge, and departure state.
- An event-driven AI Director that reacts at encounter and decision milestones without running on physics ticks.
- Persistent multi-stage world threads, cross-system contact follow-ups, consequence activities, and an activity board that explains what can be done next.
- A rebuilt universe-consistency diagnostic at `knowledge/universe-consistency.md` in every save.
- A built-in deterministic AI fallback, so no model or account is required.
- Investigation, diplomacy, departure, tactical escalation, salvage, and permanent upgrades.
- Canonical human-readable Markdown saves.

## Run locally

Requirements: Python 3.12+, `uv`, Node.js 22+, and npm.

```bash
UV_CACHE_DIR=.uv-cache uv sync --extra dev
npm install
npm run build
UV_CACHE_DIR=.uv-cache uv run space-sim-crew
```

Open `http://localhost:8000`. Other people on the local network use `http://<host-ip>:8000`.

Development client with live reload:

```bash
UV_CACHE_DIR=.uv-cache uv run uvicorn space_sim_crew.api:app --reload
npm run dev
```

The browser development server runs at `http://localhost:5173` and proxies the API and WebSocket.

## Run with the local hybrid AI

Ollama is a local model server: prompts and responses stay on this computer. This project keeps its Ollama runtime and model files inside ignored `.tools/` and `.ollama/` directories, so no administrator installation is required.

The local runtime and default `qwen3:4b` model are already installed in this working copy. To reproduce that setup on another Linux x86-64 computer:

```bash
./scripts/setup-local-ai.sh
```

Build the client once, then launch Ollama and the game together:

```bash
npm run build
./scripts/run-local-ai.sh
```

Open `http://localhost:8000`, join the **Integrated** station, and play every panel as one person. Ollama handles routine Ship Computer, NPC, and narrative requests. If the local request fails, the launcher enables a read-only `codex exec` fallback using the Codex CLI's configured account and default model. Disable that fallback with `SPACE_CREW_CODEX_ENABLED=0 ./scripts/run-local-ai.sh`.

For a focused actor playtest, create the **Friendly Contact Test** preset. Reply peacefully to receive a request and shared information, invite the vessel to come closer to see its radar range change, try hostile language to observe withdrawal, or say farewell to end contact. The contact's relationship and observable reason for acting appear above the station panels.

The launcher disables Qwen's extended reasoning for responsive in-game dialogue. Override it with `SPACE_CREW_AI_REASONING_EFFORT=low` if you prefer slower, more deliberative local responses.

The AI can return dialogue and bounded narrative proposals. Physics, sensor truth, installed equipment, damage, permissions, and canonical state remain deterministic and server-validated.

## Connect another AI model

Without configuration, the game uses a deterministic offline provider. Any local or hosted server exposing an OpenAI-compatible chat endpoint can be configured:

```bash
export SPACE_CREW_AI_BASE_URL=http://127.0.0.1:11434/v1
export SPACE_CREW_AI_MODEL=your-model
export SPACE_CREW_AI_API_KEY=optional-key
UV_CACHE_DIR=.uv-cache uv run space-sim-crew
```

The provider affects dialogue and variety. It cannot directly alter canonical state, bypass physics, or see player-inaccessible secrets.

## Test

```bash
UV_CACHE_DIR=.uv-cache uv run pytest
npm run build
npm test
```

## Browser automation for playtests

Playwright is included as a development dependency. With Google Chrome installed,
run `node scripts/browser-check.mjs` to verify browser launch, text entry, clicking,
DOM inspection, and screenshot capture. The check uses a fresh temporary browser
profile and closes it afterward; its screenshot is saved under `/tmp`.
Agents can import `chromium` from `playwright` in Node scripts to operate the game
through its actual browser UI. Restricted environments may require approval to
launch Chrome outside the sandbox. This is terminal-driven browser automation;
it does not register a new MCP tool in an already-running agent session.

Run `node scripts/browser-playtest.mjs` after `npm run build` for the complete
browser regression: friendly exchange, power routing, vessel scan, warp, remote
reply, evidence-backed survey report, finite archive decision, and reload.
It starts its own host on port 8013 with the deterministic AI fallback, saves
screenshots and a disposable universe under `/tmp`, and closes Chrome and the
host afterward. Chrome and local socket access are required.

## Saves

Universes are stored under `saves/<universe-id>/`. Markdown and YAML front matter are canonical. SQLite indexes and generated media are caches and may be rebuilt or removed.

## Project identity

This is an independent work. Contributions must not add protected names, lore, interface reproductions, visual language, or audiovisual assets from existing fictional properties.
