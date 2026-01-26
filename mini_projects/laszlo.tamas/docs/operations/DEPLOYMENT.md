# Deployment Guide - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A teljes production deployment guide Docker alapú környezetekhez. CI/CD pipeline, infrastructure as code, monitoring és security konfigurációval.

## Használat

### Local deployment
```bash
# Production build
docker-compose -f docker-compose.prod.yml up --build -d

# Health check
curl http://localhost:8000/health/

# Logs monitoring
docker-compose logs -f backend
```

### Staging deployment
```bash
# Environment setup
export ENVIRONMENT=staging
export DATABASE_URL=postgresql://user:pass@staging-db:5432/kr_staging

# Deploy with secrets
docker stack deploy -c docker-compose.staging.yml knowledge-router-staging
```

### Production deployment
```bash
# Kubernetes deployment
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmaps.yaml
kubectl apply -f k8s/deployment.yaml
```

## Technikai implementáció

### Docker Production Configuration
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: knowledge-router-backend-prod
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - DATABASE_URL=${DATABASE_URL}
      - QDRANT_URL=${QDRANT_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REDIS_URL=${REDIS_URL}
    ports:
      - "${API_PORT:-8000}:8000"
    volumes:
      - app-logs:/app/logs
      - uploaded-documents:/app/uploads
    depends_on:
      - postgres
      - qdrant
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - knowledge-router-net

  postgres:
    image: postgres:15
    container_name: knowledge-router-db-prod
    restart: unless-stopped
    environment:
      - POSTGRES_DB=k_r_prod
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./backend/database/migrations:/docker-entrypoint-initdb.d
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d k_r_prod"]
      interval: 30s
      timeout: 5s
      retries: 5
    networks:
      - knowledge-router-net

  qdrant:
    image: qdrant/qdrant:latest
    container_name: knowledge-router-qdrant-prod
    restart: unless-stopped
    ports:
      - "${QDRANT_PORT:-6333}:6333"
    volumes:
      - qdrant-storage:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
    networks:
      - knowledge-router-net

  redis:
    image: redis:7-alpine
    container_name: knowledge-router-redis-prod
    restart: unless-stopped
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    networks:
      - knowledge-router-net

  nginx:
    image: nginx:alpine
    container_name: knowledge-router-nginx-prod
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
      - nginx-logs:/var/log/nginx
    depends_on:
      - backend
    networks:
      - knowledge-router-net

volumes:
  postgres-data:
    driver: local
  qdrant-storage:
    driver: local
  redis-data:
    driver: local
  app-logs:
    driver: local
  uploaded-documents:
    driver: local
  nginx-logs:
    driver: local

networks:
  knowledge-router-net:
    driver: bridge
```

### Production Dockerfile
```dockerfile
# backend/Dockerfile.prod
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash app

# Copy installed packages from builder
COPY --from=builder /root/.local /home/app/.local

# Set environment variables
ENV PATH=/home/app/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV ENVIRONMENT=production

# Switch to app user
USER app
WORKDIR /app

# Copy application code
COPY --chown=app:app . .

# Create necessary directories
RUN mkdir -p /app/logs /app/uploads

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health/ || exit 1

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Kubernetes Deployment
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: knowledge-router-backend
  namespace: knowledge-router
  labels:
    app: knowledge-router-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: knowledge-router-backend
  template:
    metadata:
      labels:
        app: knowledge-router-backend
    spec:
      containers:
      - name: backend
        image: knowledge-router:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: knowledge-router-secrets
              key: database-url
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: knowledge-router-secrets
              key: openai-api-key
        - name: ENVIRONMENT
          value: "production"
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
          requests:
            memory: "1Gi" 
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        volumeMounts:
        - name: logs
          mountPath: /app/logs
        - name: uploads
          mountPath: /app/uploads
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: knowledge-router-logs
      - name: uploads
        persistentVolumeClaim:
          claimName: knowledge-router-uploads

---
apiVersion: v1
kind: Service
metadata:
  name: knowledge-router-backend-service
  namespace: knowledge-router
spec:
  selector:
    app: knowledge-router-backend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: knowledge-router-ingress
  namespace: knowledge-router
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.knowledge-router.com
    secretName: knowledge-router-tls
  rules:
  - host: api.knowledge-router.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: knowledge-router-backend-service
            port:
              number: 80
```

### Database Migration
```python
# deployment/migrate.py
import asyncio
import asyncpg
import os
from pathlib import Path

async def run_migrations():
    """Run database migrations in production."""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not set")
    
    conn = await asyncpg.connect(database_url)
    
    try:
        # Get current migration version
        try:
            current_version = await conn.fetchval(
                "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
            )
        except asyncpg.UndefinedTableError:
            current_version = 0
            
        # Find migration files
        migration_dir = Path(__file__).parent.parent / "backend" / "database" / "migrations"
        migration_files = sorted(migration_dir.glob("*.sql"))
        
        for migration_file in migration_files:
            version = int(migration_file.stem.split('_')[0])
            
            if version > current_version:
                print(f"Running migration {version}: {migration_file.name}")
                
                with open(migration_file) as f:
                    migration_sql = f.read()
                    
                await conn.execute(migration_sql)
                
                # Record migration
                await conn.execute(
                    """
                    INSERT INTO schema_migrations (version, filename, applied_at)
                    VALUES ($1, $2, NOW())
                    """,
                    version, migration_file.name
                )
                
                print(f"Migration {version} completed")
                
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(run_migrations())
```

### Environment Configuration
```bash
# .env.prod
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://kr_user:secure_password@postgres:5432/k_r_prod
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Vector Store
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_SIZE=1536

# LLM API
OPENAI_API_KEY=sk-your-production-key
OPENAI_MODEL=gpt-4
OPENAI_RATE_LIMIT_RPM=500

# Redis Cache
REDIS_URL=redis://:secure_redis_password@redis:6379/0
REDIS_TTL_SECONDS=3600

# Security
SECRET_KEY=your-ultra-secure-secret-key-here
ALLOWED_HOSTS=api.knowledge-router.com,localhost
CORS_ORIGINS=https://app.knowledge-router.com

# Monitoring
PROMETHEUS_ENABLED=true
TRACING_ENABLED=true
LOG_STRUCTURED=true

# Performance
WORKER_PROCESSES=4
MAX_REQUEST_SIZE_MB=50
REQUEST_TIMEOUT_SECONDS=300
```

### CI/CD Pipeline (GitHub Actions)
```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: knowledge-router

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
    - name: Checkout repository
      uses: actions/checkout@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v2
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: ./backend
        file: ./backend/Dockerfile.prod
        push: true
        tags: |
          ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:latest
          ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

    - name: Deploy to production
      uses: azure/k8s-deploy@v3
      with:
        method: kubectl
        kubeconfig: ${{ secrets.KUBECONFIG }}
        manifests: |
          k8s/deployment.yaml
          k8s/service.yaml
          k8s/ingress.yaml
        images: |
          ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}

    - name: Run health checks
      run: |
        sleep 60
        curl -f https://api.knowledge-router.com/health/ || exit 1
```

## Funkció-specifikus konfiguráció

```ini
# Deployment settings
DEPLOYMENT_ENVIRONMENT=production
CONTAINER_REGISTRY=ghcr.io/company/knowledge-router
IMAGE_TAG=latest

# Resource limits
CPU_LIMIT=1000m
MEMORY_LIMIT=2Gi
REPLICA_COUNT=3

# Storage
PERSISTENT_VOLUME_SIZE=100Gi
STORAGE_CLASS=fast-ssd

# Networking
INGRESS_CLASS=nginx
ENABLE_TLS=true
RATE_LIMIT_RPS=100

# Backup
BACKUP_SCHEDULE="0 2 * * *"
BACKUP_RETENTION_DAYS=30
```