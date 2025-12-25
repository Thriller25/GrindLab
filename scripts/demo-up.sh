#!/bin/bash
# GrindLab Demo Startup Script (Linux/macOS)
# Usage: ./scripts/demo-up.sh [clean]

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/docker-compose.demo.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ Error: $COMPOSE_FILE not found"
    exit 1
fi

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Start Docker and try again."
    exit 1
fi

# Clean option
if [ "$1" = "clean" ]; then
    echo "🗑️  Cleaning up containers and volumes..."
    docker-compose -f "$COMPOSE_FILE" down -v
    docker volume rm grindlab-demo-db 2>/dev/null || true
fi

echo "🚀 Starting GrindLab Demo..."
echo "   Building images and starting services..."
docker-compose -f "$COMPOSE_FILE" up --build

echo ""
echo "✅ GrindLab Demo is ready!"
echo ""
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:8001"
echo "   Health:    http://localhost:8001/health"
echo ""
echo "Stop with: Ctrl+C or 'docker-compose -f docker-compose.demo.yml down'"
