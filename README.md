# Tennis Debrief Agent

A multi-agent AI system that helps tennis players analyze match performance, identify recurring patterns, and get concrete improvement recommendations — backed by persistent match history.

## How it works

The system runs 6 specialized agents in sequence:

| Agent | Role |
|-------|------|
| **Intake** | Structures raw match form input into a typed record |
| **Technical** | Identifies specific stroke/biomechanical issues with evidence |
| **Tactical** | Identifies court strategy and shot selection patterns |
| **Mental** | Identifies emotional and psychological patterns |
| **Pattern Detector** | Synthesizes patterns across current + historical matches |
| **Head Coach** | Produces actionable levers, drills, and history comparison |

Match history is stored in Firestore via an MCP memory server. Each new debrief cross-references the last 8 matches within the past 6 months.

## Project Structure

```
tennis_debrief_agent/
├── agent/
│   ├── agent.py              # ADK sequential orchestrator
│   ├── agents/               # Individual agent wrappers
│   ├── prompts/              # Prompt templates (one per agent)
│   └── utils/                # JSON parsing, validation, MCP client
├── mcp_memory_server/        # FastAPI memory server (Firestore-backed)
│   └── Dockerfile            # Deploy to Cloud Run
├── shared/
│   └── constants.py          # Opponent levels, keywords, priority thresholds
├── tests/                    # Full test suite (150 tests)
├── scripts/
│   └── run_local_mcp.sh      # Start MCP server locally
├── streamlit_app.py          # Streamlit web UI
├── Dockerfile                # Deploy agent UI to Cloud Run
└── .env.example              # Environment variable template
```

## Running locally

### Prerequisites

- Python 3.11+
- Google Cloud project with Firestore and Vertex AI APIs enabled
- Billing enabled on the project
- `gcloud auth application-default login`

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

### MCP server curl reference

```bash
# Health
curl -s http://localhost:8080/health

# Set player profile
curl -s -X POST http://localhost:8080/tools/profile.upsert \
  -H "Content-Type: application/json" \
  -d '{"patch": {"goal": "Consistency", "tone": "Supportive"}}'

# Retrieve recent matches
curl -s -X POST http://localhost:8080/tools/match.retrieve_recent \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'
```

## Running tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

150 tests covering all agents, validators, MCP server endpoints, and orchestrator helpers.

## Deploying to Cloud Run

There are two services to deploy: the MCP memory server and the Streamlit agent UI.

### Step 1 — Enable required GCP APIs

```bash
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  --project=YOUR_PROJECT_ID
```

### Step 2 — Deploy the MCP memory server

```bash
gcloud run deploy tennis-debrief-mcp \
  --source ./mcp_memory_server \
  --region us-central1 \
  --project YOUR_PROJECT_ID \
  --no-allow-unauthenticated
```

Note the service URL — you'll need it in the next step.

### Step 3 — Deploy the Streamlit agent UI

```bash
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
# Get the agent service account
SA=$(gcloud run services describe tennis-debrief-agent \
  --region us-central1 --format='value(spec.template.spec.serviceAccountName)')

# Allow it to invoke the MCP server
gcloud run services add-iam-policy-binding tennis-debrief-mcp \
  --region us-central1 \
  --member="serviceAccount:$SA" \
  --role="roles/run.invoker"
```

After this, the MCP server is private (internal calls only) and the agent UI is publicly accessible.
