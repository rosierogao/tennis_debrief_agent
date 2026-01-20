# Dockerfile for MCP Memory Server (Cloud Run deployment)

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY mcp_memory_server/ ./mcp_memory_server/
COPY shared/ ./shared/

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Run MCP server
CMD ["uvicorn", "mcp_memory_server.app:app", "--host", "0.0.0.0", "--port", "8080"]
