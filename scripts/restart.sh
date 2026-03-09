#!/bin/bash
# NetKitX Production Quick Restart
# Usage: ./scripts/restart.sh [service]
# Examples:
#   ./scripts/restart.sh           # Restart all services
#   ./scripts/restart.sh backend   # Restart backend only

SERVER="root@156.225.20.57"
PROJECT_PATH="/opt/NetKitX"
COMPOSE_FILE="docker-compose.prod.yml"

SERVICE="${1:-}"

if [ -z "$SERVICE" ]; then
    echo "🔄 Restarting all services..."
    ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE restart"
else
    echo "🔄 Restarting $SERVICE..."
    ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE restart $SERVICE"
fi

echo "✅ Restart complete!"
echo ""
echo "📊 Container status:"
ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE ps"
