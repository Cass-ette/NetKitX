#!/bin/bash
# NetKitX Production Server Status Check
# Usage: ./scripts/status.sh

SERVER="root@156.225.20.57"
PROJECT_PATH="/opt/NetKitX"
COMPOSE_FILE="docker-compose.prod.yml"

echo "📊 NetKitX Production Status"
echo "=============================="
echo ""

echo "🐳 Container Status:"
ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE ps"

echo ""
echo "💾 Disk Usage:"
ssh $SERVER "df -h | grep -E '(Filesystem|/dev/vda)'"

echo ""
echo "🔒 SSL Certificate:"
ssh $SERVER "certbot certificates 2>/dev/null | grep -A 3 'wql.me' || echo 'Certbot not found or no certificates'"

echo ""
echo "🌐 Site Status:"
curl -s -o /dev/null -w "HTTPS: %{http_code}\n" https://wql.me
curl -s -o /dev/null -w "API Health: %{http_code}\n" https://wql.me/api/health

echo ""
echo "📝 Recent Backend Logs (last 10 lines):"
ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE logs backend --tail 10"
