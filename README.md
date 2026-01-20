# Tennis Debrief Agent

A multi-agent system for analyzing tennis match debriefs using Google ADK and MCP (Model Context Protocol) memory server.

## Description

This project provides an intelligent agent system that helps tennis players analyze their matches, identify patterns, and get personalized improvement recommendations. The system uses Google's Agent Development Kit (ADK) for agent orchestration and an MCP memory server for persistent storage and pattern analysis.

## Local Run

### Prerequisites

- Python 3.11+
- Google Cloud SDK (for Firestore access)
- `gcloud auth application-default login`
- Environment variables configured (see `.env.example`)

### ADK (agent) dev run

From the project root, run one of:

```bash
adk web
```

or

```bash
adk run agent
```

These are ADK’s standard dev UI / CLI entrypoints. See the ADK quickstart for details.  
Source: [ADK Quickstart](https://google.github.io/adk-docs/get-started/quickstart/#run-your-agent)

### Running the MCP Memory Server

```bash
pip install -r mcp_memory_server/requirements.txt
./scripts/run_local_mcp.sh
```

### Testing with curl

```bash
# Health check
curl -s -X POST http://localhost:8080/tools/profile.upsert \
  -H "Content-Type: application/json" \
  -d '{"patch":{"goal":"Consistency","tone":"Supportive"}}'

# profile.get
curl -s -X POST http://localhost:8080/tools/profile.get \
  -H "Content-Type: application/json" \
  -d '{}'

# match.store
curl -s -X POST http://localhost:8080/tools/match.store \
  -H "Content-Type: application/json" \
  -d '{"match_record":{"scoreline":"3-6 4-6"},"debrief_report":{"dummy":true},"themes":["pressure","serve"],"summary":"DFs clustered on big points."}'

# match.retrieve_recent
curl -s -X POST http://localhost:8080/tools/match.retrieve_recent \
  -H "Content-Type: application/json" \
  -d '{"limit":5}'

# health
curl -s http://localhost:8080/health
```

### Optional: Firestore Emulator

If you prefer to run locally without hitting GCP, set the Firestore emulator vars:

```bash
export FIRESTORE_EMULATOR_HOST=localhost:8080
export GOOGLE_CLOUD_PROJECT=local-dev
```

## Deploy to Cloud Run

```bash
# TODO: Replace placeholders with your GCP values
gcloud run deploy tennis-debrief-mcp \
  --source ./mcp_memory_server \
  --region YOUR_REGION \
  --project YOUR_PROJECT_ID \
  --allow-unauthenticated
```

## Project Structure

```
tennis-debrief-agent/
├── mcp_memory_server/    # MCP tool server (deploy to Cloud Run)
├── shared/               # Shared constants and utilities
├── scripts/              # Local development scripts
├── .env.example         # Environment variable template
└── README.md            # This file
```
