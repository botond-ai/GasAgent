# Python backend Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better cache usage
COPY requirements.txt .

# Install build dependencies and build tools
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --upgrade pip \
    && pip install --no-cache-dir wheel setuptools hatchling \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/users data/sessions data/files

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
