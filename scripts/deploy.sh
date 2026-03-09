#!/bin/bash
# NetKitX Production Deployment Script
# Usage: ./scripts/deploy.sh [--migrate]

set -e

SERVER="root@156.225.20.57"
PROJECT_PATH="/opt/NetKitX"
COMPOSE_FILE="docker-compose.prod.yml"

echo "🚀 Starting NetKitX deployment to production..."

# Check if we're in the right directory
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Error: Must run from NetKitX root directory"
    exit 1
fi

# Push to GitHub
echo "📤 Pushing to GitHub..."
git push origin develop

# Deploy to server
echo "🔄 Pulling latest code on server..."
ssh $SERVER "cd $PROJECT_PATH && git pull"

echo "🐳 Building and restarting containers..."
ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE up -d --build"

# Run migrations if requested
if [ "$1" == "--migrate" ]; then
    echo "🗄️  Running database migrations..."
    sleep 5  # Wait for backend to start
    ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE exec backend alembic upgrade head"
fi

echo "✅ Deployment complete!"
echo "🌐 Site: https://wql.me"
echo ""
echo "📊 Check status: ssh $SERVER 'cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE ps'"
echo "📝 View logs: ssh $SERVER 'cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE logs -f'"
