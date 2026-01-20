#!/bin/bash
# Script to run the MCP memory server locally

set -e

cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  . .env
  set +a
fi

if [ -n "${GOOGLE_CLOUD_PROJECT}" ]; then
  export GOOGLE_CLOUD_PROJECT
fi

echo "Starting MCP Memory Server locally..."
uvicorn mcp_memory_server.app:app --reload --port 8080
