# Dockerfile for Tennis Debrief Agent (Streamlit UI + ADK pipeline)
# Build context: repo root
# Deploy to Cloud Run alongside the MCP memory server.

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source packages
COPY agent/ ./agent/
COPY shared/ ./shared/
COPY streamlit_app.py .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# MCP server URL — override at deploy time with the Cloud Run service URL
ENV MCP_BASE_URL=http://localhost:8080

EXPOSE 8080

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
