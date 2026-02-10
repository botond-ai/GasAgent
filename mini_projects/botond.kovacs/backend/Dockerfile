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

# Copy gaztorveny.pdf to the expected location for the backend
COPY data/files/gaztorveny.pdf /app/gaztorveny.pdf
COPY data/files /app/data/files

# Create data directories
RUN mkdir -p data/users data/sessions data/files

# Expose port
EXPOSE 80

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
