#!/bin/bash
# NetKitX Production Logs Viewer
# Usage: ./scripts/logs.sh [service] [--follow]
# Examples:
#   ./scripts/logs.sh              # All services, last 50 lines
#   ./scripts/logs.sh backend      # Backend only, last 50 lines
#   ./scripts/logs.sh backend -f   # Backend, follow mode

SERVER="root@156.225.20.57"
PROJECT_PATH="/opt/NetKitX"
COMPOSE_FILE="docker-compose.prod.yml"

SERVICE="${1:-}"
FOLLOW="${2:-}"

if [ "$FOLLOW" == "-f" ] || [ "$FOLLOW" == "--follow" ]; then
    echo "📝 Following logs for ${SERVICE:-all services}... (Ctrl+C to exit)"
    ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE logs -f $SERVICE"
else
    echo "📝 Recent logs for ${SERVICE:-all services}:"
    ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE logs --tail 50 $SERVICE"
fi
