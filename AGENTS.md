# Repository instructions

Read `PROJECT_PLAN.md` before changing architecture or feature scope.

## Non-negotiable rules

- AI proposes. The deterministic simulation validates and commits.
- Every consequential persistent change creates an immutable canonical event.
- Sensors expose authorized observations, never objective hidden truth.
- Retrieve only information the receiving model role is authorized to know.
- Model failure must not stop simulation, controls, or persistence.
- Markdown/YAML is canonical save state; indexes and media are disposable.
- Generated code never receives unrestricted shell, filesystem, network, process, cookie, or credential access.
- Preserve original terminology, lore, interface design, and audiovisual identity.
- Add deterministic tests for simulation changes and fake-provider tests for AI changes.
- Do not mark a checklist item complete until its acceptance test passes.

## Commands

- Python tests: `UV_CACHE_DIR=.uv-cache uv run pytest`
- Client build: `npm run build`
- Client tests: `npm test`
- Run host: `UV_CACHE_DIR=.uv-cache uv run space-sim-crew`
