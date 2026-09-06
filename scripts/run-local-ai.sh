#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_DIR/.tools/ollama"
MODEL_DIR="$PROJECT_DIR/.ollama/models"
MODEL_NAME="${SPACE_CREW_AI_MODEL:-qwen3:4b}"

if [[ ! -x "$RUNTIME_DIR/bin/ollama" ]]; then
  echo "Ollama is not installed for this project. Run ./scripts/setup-local-ai.sh first." >&2
  exit 1
fi

export OLLAMA_MODELS="$MODEL_DIR"
export OLLAMA_HOST="127.0.0.1:11434"
export LD_LIBRARY_PATH="$RUNTIME_DIR/lib/ollama${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export SPACE_CREW_AI_BASE_URL="http://127.0.0.1:11434/v1"
export SPACE_CREW_AI_MODEL="$MODEL_NAME"
export SPACE_CREW_AI_PROVIDER="ollama"
export SPACE_CREW_AI_REASONING_EFFORT="${SPACE_CREW_AI_REASONING_EFFORT:-none}"
export SPACE_CREW_CODEX_ENABLED="${SPACE_CREW_CODEX_ENABLED:-1}"

STARTED_OLLAMA=0
if ! curl --silent --fail "http://127.0.0.1:11434/api/version" >/dev/null; then
  "$RUNTIME_DIR/bin/ollama" serve >"$PROJECT_DIR/.ollama/ollama.log" 2>&1 &
  OLLAMA_PID=$!
  STARTED_OLLAMA=1
  for _ in {1..30}; do
    curl --silent --fail "http://127.0.0.1:11434/api/version" >/dev/null && break
    sleep 1
  done
fi

cleanup() {
  if [[ "$STARTED_OLLAMA" == "1" ]]; then
    kill "$OLLAMA_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if ! "$RUNTIME_DIR/bin/ollama" show "$MODEL_NAME" >/dev/null 2>&1; then
  echo "Model $MODEL_NAME is missing. Run ./scripts/setup-local-ai.sh first." >&2
  exit 1
fi

cd "$PROJECT_DIR"
UV_CACHE_DIR=.uv-cache uv run space-sim-crew
