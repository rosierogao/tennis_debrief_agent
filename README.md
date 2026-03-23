# Court Debrief

A multi-agent AI system that helps tennis players track match records, identify recurring patterns, and get concrete coaching feedback — backed by persistent match history.

[![Docker MCP](https://img.shields.io/docker/v/rosierogao/tennis-debrief-mcp?label=mcp%20server&logo=docker)](https://hub.docker.com/r/rosierogao/tennis-debrief-mcp)
[![Docker Agent](https://img.shields.io/docker/v/rosierogao/tennis-debrief-agent?label=agent%20ui&logo=docker)](https://hub.docker.com/r/rosierogao/tennis-debrief-agent)
[![Tests](https://img.shields.io/badge/tests-150%20passing-brightgreen)](#running-tests)

---

## Features

### New Debrief tab
- Fill in match date, opponent NTRP rating, scoreline, and six structured fields (what went well, what went poorly, feelings, opponent characteristics, pressure moments, patterns noticed)
- Each field shows previously saved bullets as collapsible pill pickers — select reusable observations from past matches, then add new free-text items
- New items are AI-polished (typos fixed, match-specific numbers removed) and merged into your saved bullet library for future use
- Submits to the 6-agent pipeline and renders the full debrief on the right panel
- Debrief output includes: summary, technique snapshot radar, focus areas, improvement levers, drills, and history comparison

### Technique Snapshot (radar chart)
- AI-inferred scores (1–5) for 10 techniques: 1st Serve %, Double Faults, Forehand, Backhand, Rally Depth, Unforced Errors, Return of Serve, Footwork, Pressure Performance, Momentum
- Only techniques explicitly mentioned in your match notes are scored; unmentioned axes are shown in grey
- Optional opponent-level adjustment: toggle on to scale scores relative to your NTRP baseline, with a 5–30% per NTRP step aggressiveness slider

### Compare tab
- Load past matches and select up to 6 to overlay on a single radar chart
- Each match gets a distinct color (blue, orange, green, red, purple, brown) with a legend
- Optional opponent-level adjustment applies the same NTRP normalization across all overlays

### Progress tab
- 10 technique trend line charts across all past matches, aligned to the same date axis
- **Win/loss coloring:** green line connects wins, red connects losses, blue connects unknown outcomes
- **Rolling baseline:** dashed grey line shows the rolling mean of your last 5 scored matches per technique
- Optional opponent-level adjustment with aggressiveness slider; examples update dynamically based on your saved NTRP

### Match History tab
- View all past matches with full debrief details in expandable cards
- Delete individual matches from history

### Player profile
- One-time NTRP rating setup (shown only until saved) — used as the neutral baseline for all opponent-level adjustments
- Bullet libraries grow automatically with each debrief; accessible across all future sessions

---

## How it works

Six specialized agents run in sequence on each match submission:

| Agent | Role |
|-------|------|
| **Intake** | Structures raw match form input into a typed record |
| **Technical** | Identifies specific stroke/biomechanical issues with evidence |
| **Tactical** | Identifies court strategy and shot selection patterns |
| **Mental** | Identifies emotional and psychological patterns |
| **Pattern Detector** | Synthesizes patterns across current + historical matches |
| **Head Coach** | Produces actionable levers, drills, and history comparison |

Match history is stored in Firestore via a private MCP memory server. Each new debrief cross-references the last 8 matches within the past 6 months.

---

## Deploy your own instance

### Prerequisites

- [Google Cloud account](https://cloud.google.com) with billing enabled
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated:
  ```bash
  gcloud auth login
  gcloud auth application-default login
  ```

### One-command setup

```bash
git clone https://github.com/rosierogao/tennis_debrief_agent.git
cd tennis_debrief_agent
chmod +x setup.sh
./setup.sh
```

The script will:
1. Prompt for your GCP project ID and region
2. Enable all required APIs
3. Create a Firestore database
4. Deploy the MCP memory server (private)
5. Deploy the Streamlit agent UI (public)
6. Wire IAM so the two services can communicate
7. Print your live app URL

By default it pulls pre-built images from Docker Hub — no local Docker build required. You can also choose to build from source when prompted.

> **Estimated time:** ~5 minutes end-to-end

---

## Project structure

```
tennis_debrief_agent/
├── agent/
│   ├── agent.py              # ADK sequential orchestrator
│   ├── agents/               # Individual agent wrappers
│   ├── prompts/              # Prompt templates (one per agent)
│   └── utils/                # JSON parsing, validation, MCP client
├── mcp_memory_server/        # FastAPI memory server (Firestore-backed)
│   └── Dockerfile
├── shared/
│   └── constants.py          # Opponent levels, keywords, priority thresholds
├── tests/                    # Full test suite (150 tests)
├── scripts/
│   └── run_local_mcp.sh      # Start MCP server locally
├── .github/workflows/
│   └── docker-publish.yml    # Auto-publish images to Docker Hub on push to main
├── streamlit_app.py          # Streamlit web UI
├── setup.sh                  # One-command Cloud Run deployment
├── Dockerfile                # Agent UI image
└── .env.example              # Environment variable template
```

---

## Running locally

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=1
MCP_BASE_URL=http://localhost:8080
```

### 2. Install dependencies

```bash
pip install -r agent/requirements.txt
pip install -r mcp_memory_server/requirements.txt
```

### 3. Start the MCP memory server (Terminal 1)

```bash
bash scripts/run_local_mcp.sh
```

Verify: `curl -s http://localhost:8080/health` → `{"ok": true}`

### 4. Start the Streamlit UI (Terminal 2)

```bash
export $(grep -v '^#' .env | xargs)
streamlit run streamlit_app.py
```

Open **http://localhost:8501**

---

## Running tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

150 tests covering all agents, validators, MCP server endpoints, and orchestrator helpers.

---

## Manual Cloud Run deployment

If you prefer to run each step yourself instead of using `setup.sh`:

### Step 1 — Enable required GCP APIs

```bash
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com \
  --project=YOUR_PROJECT_ID
```

### Step 2 — Deploy the MCP memory server

```bash
# Option A: pull pre-built image from Docker Hub
gcloud run deploy tennis-debrief-mcp \
  --image docker.io/rosierogao/tennis-debrief-mcp:latest \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --no-allow-unauthenticated

# Option B: build from source
gcloud run deploy tennis-debrief-mcp \
  --source ./mcp_memory_server \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --no-allow-unauthenticated
```

Note the service URL — you'll need it in the next step.

### Step 3 — Deploy the Streamlit agent UI

```bash
# Option A: pull pre-built image from Docker Hub
gcloud run deploy tennis-debrief-agent \
  --image docker.io/rosierogao/tennis-debrief-agent:latest \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --set-env-vars GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=1,MCP_BASE_URL=https://YOUR_MCP_SERVICE_URL \
  --allow-unauthenticated

# Option B: build from source
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/tennis-debrief-agent .

gcloud run deploy tennis-debrief-agent \
  --image gcr.io/YOUR_PROJECT_ID/tennis-debrief-agent \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --set-env-vars GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=1,MCP_BASE_URL=https://YOUR_MCP_SERVICE_URL \
  --allow-unauthenticated
```

### Step 4 — Grant the agent service access to the MCP server

```bash
SA=$(gcloud run services describe tennis-debrief-agent \
  --region us-central1 --format='value(spec.template.spec.serviceAccountName)')

gcloud run services add-iam-policy-binding tennis-debrief-mcp \
  --region us-central1 \
  --member="serviceAccount:$SA" \
  --role="roles/run.invoker"
```

After this, the MCP server is private (internal calls only) and the agent UI is publicly accessible.

---

## MCP server API reference

```bash
# Health check
curl -s http://localhost:8080/health

# Set player profile
curl -s -X POST http://localhost:8080/tools/profile.upsert \
  -H "Content-Type: application/json" \
  -d '{"patch": {"goal": "Consistency", "tone": "Supportive"}}'

# Retrieve recent matches
curl -s -X POST http://localhost:8080/tools/match.retrieve_recent \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "include_full": false}'

# Delete a match
curl -s -X POST http://localhost:8080/tools/match.delete \
  -H "Content-Type: application/json" \
  -d '{"match_id": "YOUR_MATCH_ID"}'
```

---

## Publishing your own Docker images

If you fork this repo and want to publish your own images to Docker Hub, add two repository secrets in GitHub:

| Secret | Value |
|--------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | A Docker Hub access token |

Images are built and pushed automatically on every push to `main` via `.github/workflows/docker-publish.yml`. Tagged releases (e.g. `v1.0.0`) also publish a versioned image tag.
