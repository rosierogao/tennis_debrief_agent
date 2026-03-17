#!/usr/bin/env bash
# Tennis Debrief Agent — one-command Cloud Run deployment
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}▶ $*${NC}"; }
ok()   { echo -e "${GREEN}✔ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
die()  { echo -e "${RED}✖ $*${NC}"; exit 1; }

echo ""
echo -e "${CYAN}🎾 Tennis Debrief Agent — Cloud Run Setup${NC}"
echo "==========================================="
echo ""

# ── Prerequisites ─────────────────────────────────────────────────────────────

command -v gcloud >/dev/null 2>&1 || die "gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install"

# ── Collect config ─────────────────────────────────────────────────────────────

read -rp "GCP Project ID: " PROJECT_ID
[[ -z "$PROJECT_ID" ]] && die "Project ID is required."

read -rp "Region [us-central1]: " REGION
REGION="${REGION:-us-central1}"

echo ""
echo "Deploy using pre-built Docker Hub images (faster) or build from source?"
echo "  1) Docker Hub images  (recommended)"
echo "  2) Build from source"
read -rp "Choice [1]: " BUILD_CHOICE
BUILD_CHOICE="${BUILD_CHOICE:-1}"

if [[ "$BUILD_CHOICE" == "1" ]]; then
  read -rp "Docker Hub username [rosierogao]: " DOCKERHUB_USER
  DOCKERHUB_USER="${DOCKERHUB_USER:-rosierogao}"
  MCP_IMAGE="docker.io/${DOCKERHUB_USER}/tennis-debrief-mcp:latest"
  AGENT_IMAGE="docker.io/${DOCKERHUB_USER}/tennis-debrief-agent:latest"
fi

echo ""
log "Using project: $PROJECT_ID  |  region: $REGION"
echo ""

# ── Set active project ─────────────────────────────────────────────────────────

gcloud config set project "$PROJECT_ID" --quiet

# ── Enable APIs ────────────────────────────────────────────────────────────────

log "Enabling required GCP APIs (this may take a minute)..."
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project="$PROJECT_ID" --quiet
ok "APIs enabled."

# ── Firestore ─────────────────────────────────────────────────────────────────

log "Setting up Firestore..."
if gcloud firestore databases describe --project="$PROJECT_ID" --quiet >/dev/null 2>&1; then
  warn "Firestore database already exists, skipping creation."
else
  gcloud firestore databases create \
    --location="$REGION" \
    --project="$PROJECT_ID" --quiet
  ok "Firestore database created."
fi

# ── Deploy MCP memory server ──────────────────────────────────────────────────

log "Deploying MCP memory server..."
if [[ "$BUILD_CHOICE" == "1" ]]; then
  gcloud run deploy tennis-debrief-mcp \
    --image "$MCP_IMAGE" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --no-allow-unauthenticated \
    --quiet
else
  gcloud run deploy tennis-debrief-mcp \
    --source ./mcp_memory_server \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --no-allow-unauthenticated \
    --quiet
fi

MCP_URL=$(gcloud run services describe tennis-debrief-mcp \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format="value(status.url)")
ok "MCP server deployed: $MCP_URL"

# ── Deploy Streamlit agent UI ─────────────────────────────────────────────────

log "Deploying Streamlit agent UI..."
if [[ "$BUILD_CHOICE" == "1" ]]; then
  gcloud run deploy tennis-debrief-agent \
    --image "$AGENT_IMAGE" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=1,MCP_BASE_URL=${MCP_URL}" \
    --allow-unauthenticated \
    --quiet
else
  gcloud builds submit \
    --tag "gcr.io/${PROJECT_ID}/tennis-debrief-agent" \
    --project "$PROJECT_ID" \
    --quiet .
  gcloud run deploy tennis-debrief-agent \
    --image "gcr.io/${PROJECT_ID}/tennis-debrief-agent" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=1,MCP_BASE_URL=${MCP_URL}" \
    --allow-unauthenticated \
    --quiet
fi

AGENT_URL=$(gcloud run services describe tennis-debrief-agent \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format="value(status.url)")
ok "Agent UI deployed: $AGENT_URL"

# ── IAM: allow agent to call MCP ─────────────────────────────────────────────

log "Configuring IAM (agent → MCP)..."
SA=$(gcloud run services describe tennis-debrief-agent \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format="value(spec.template.spec.serviceAccountName)")

gcloud run services add-iam-policy-binding tennis-debrief-mcp \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --member="serviceAccount:${SA}" \
  --role="roles/run.invoker" \
  --quiet
ok "IAM binding applied."

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}==========================================="
echo -e "✅  Deployment complete!"
echo -e "==========================================="
echo -e "App URL:  ${AGENT_URL}"
echo -e "MCP URL:  ${MCP_URL} (private)"
echo -e "${NC}"
