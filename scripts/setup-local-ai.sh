#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_DIR/.tools/ollama"
MODEL_DIR="$PROJECT_DIR/.ollama/models"
ARCHIVE_PATH="${TMPDIR:-/tmp}/space-crew-ollama-linux-amd64.tar.zst"
MODEL_NAME="${SPACE_CREW_AI_MODEL:-qwen3:4b}"

mkdir -p "$RUNTIME_DIR" "$MODEL_DIR"
if [[ ! -x "$RUNTIME_DIR/bin/ollama" ]]; then
  echo "Downloading the official Ollama Linux runtime..."
  curl --fail --location --progress-bar "https://ollama.com/download/ollama-linux-amd64.tar.zst" --output "$ARCHIVE_PATH"
  tar --extract --zstd --file "$ARCHIVE_PATH" --directory "$RUNTIME_DIR"
fi

export OLLAMA_MODELS="$MODEL_DIR"
export OLLAMA_HOST="127.0.0.1:11434"
export LD_LIBRARY_PATH="$RUNTIME_DIR/lib/ollama${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

if ! curl --silent --fail "http://127.0.0.1:11434/api/version" >/dev/null; then
  "$RUNTIME_DIR/bin/ollama" serve >"$PROJECT_DIR/.ollama/ollama.log" 2>&1 &
  OLLAMA_PID=$!
  trap 'kill "$OLLAMA_PID" 2>/dev/null || true' EXIT
  for _ in {1..30}; do
    curl --silent --fail "http://127.0.0.1:11434/api/version" >/dev/null && break
    sleep 1
  done
fi

echo "Installing local model $MODEL_NAME..."
"$RUNTIME_DIR/bin/ollama" pull "$MODEL_NAME"
echo "Local AI is ready. Start the game with: ./scripts/run-local-ai.sh"
