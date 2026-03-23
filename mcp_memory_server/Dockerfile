# Dockerfile for MCP Memory Server (Cloud Run deployment)

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (build context is mcp_memory_server/)
COPY . .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

EXPOSE 8080

# Run MCP server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
