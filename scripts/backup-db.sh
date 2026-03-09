#!/bin/bash
# NetKitX Production Database Backup
# Usage: ./scripts/backup-db.sh

SERVER="root@156.225.20.57"
PROJECT_PATH="/opt/NetKitX"
COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="netkitx_backup_${TIMESTAMP}.sql"

echo "💾 Starting database backup..."

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Create backup on server and download
echo "📦 Creating backup on server..."
ssh $SERVER "cd $PROJECT_PATH && docker compose -f $COMPOSE_FILE exec -T db pg_dump -U netkitx netkitx" > "$BACKUP_DIR/$BACKUP_FILE"

if [ $? -eq 0 ]; then
    # Compress the backup
    echo "🗜️  Compressing backup..."
    gzip "$BACKUP_DIR/$BACKUP_FILE"

    echo "✅ Backup complete: $BACKUP_DIR/${BACKUP_FILE}.gz"
    echo "📊 Size: $(du -h "$BACKUP_DIR/${BACKUP_FILE}.gz" | cut -f1)"

    # Keep only last 7 backups
    echo "🧹 Cleaning old backups (keeping last 7)..."
    ls -t $BACKUP_DIR/netkitx_backup_*.sql.gz | tail -n +8 | xargs -r rm

    echo ""
    echo "📁 Available backups:"
    ls -lh $BACKUP_DIR/netkitx_backup_*.sql.gz 2>/dev/null || echo "No backups found"
else
    echo "❌ Backup failed!"
    rm -f "$BACKUP_DIR/$BACKUP_FILE"
    exit 1
fi
