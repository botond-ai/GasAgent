# MCP Server Dockerfile (optional - for separate container deployment)

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY backend/ /app/backend/

# Install Python dependencies
WORKDIR /app/backend
RUN pip install -q --no-cache-dir -r requirements.txt
RUN pip install -q --no-cache-dir -r mcp_server/requirements.txt

# Setup Django
ENV DJANGO_SETTINGS_MODULE=core.settings

# Expose MCP server (stdio by default, could be HTTP)
ENTRYPOINT ["python", "-m", "mcp_server"]
