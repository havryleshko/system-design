# Dockerfile for self-hosting or advanced deployments
# Usage: docker build -t langgraph-backend .
#        docker run -p 2024:2024 --env-file .env langgraph-backend

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install LangGraph CLI and API
RUN pip install --no-cache-dir langgraph-cli langgraph-api

# Copy application code
COPY . .

# Expose port (Render sets $PORT, default to 2024)
EXPOSE 2024

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:${PORT:-2024}/ok || exit 1

# Start LangGraph server
# Use PORT environment variable if set (Render), otherwise default to 2024
CMD langgraph dev --host 0.0.0.0 --port ${PORT:-2024} --no-reload --config langgraph.json

