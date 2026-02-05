FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Create data directories
RUN mkdir -p data/users data/sessions data/files

# Expose port (Render sets PORT dynamically)
EXPOSE 8000

# Run server (optimized for Render free tier 512MB RAM)
# Use shell form to interpolate $PORT environment variable
CMD gunicorn core.wsgi:application \
     --bind 0.0.0.0:${PORT:-8000} \
     --workers 1 \
     --threads 2 \
     --timeout 120 \
     --max-requests 100 \
     --max-requests-jitter 10
