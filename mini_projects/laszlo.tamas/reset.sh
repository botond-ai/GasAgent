#!/bin/bash
# ===========================
# Knowledge Router - Reset Script (Bash)
# ===========================
# This script completely resets the local environment:
# - Stops all containers
# - Removes containers and volumes
# - Starts fresh containers with clean databases

echo "🔄 Knowledge Router - Environment Reset"
echo "============================================"
echo ""

# Step 1: Stop and remove containers
echo "🛑 Stopping containers..."
docker-compose down

# Step 2: Remove volumes (clean slate)
echo "🗑️  Removing volumes (this will DELETE all data)..."
docker volume rm k_r_postgres_data 2>/dev/null || true
docker volume rm k_r_qdrant_storage 2>/dev/null || true

# Step 2.1: Remove bind-mounted data directories
echo "🗑️  Removing bind-mounted data directories..."
rm -rf data/postgres/* 2>/dev/null || true
rm -rf data/qdrant/* 2>/dev/null || true
echo "✅ All data cleared"

# Step 3: Start fresh
echo ""
echo "✨ Starting fresh environment..."
docker-compose up -d

# Step 4: Wait for services
echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Step 5: Show status
echo ""
echo "✅ Reset complete!"
echo ""
echo "📊 Container Status:"
docker-compose ps

echo ""
echo "🌐 Access the application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   Qdrant:   http://localhost:6333/dashboard"
echo ""
echo "📝 Seed data (4 tenants, 3 users) auto-loaded on backend startup"
