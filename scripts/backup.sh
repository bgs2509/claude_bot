#!/bin/bash
# Скрипт автоматического бэкапа
# Использование: bash backup.sh
# Cron: 0 3 * * * /home/claude/ai-steward/scripts/backup.sh >> /home/claude/backups/backup.log 2>&1
set -euo pipefail

BACKUP_DIR="/home/claude/backups"
DATE=$(date +%Y-%m-%d)
BACKUP_FILE="$BACKUP_DIR/backup-$DATE.tar.gz"
MAX_BACKUPS=7  # Хранить последние N бэкапов

echo "[$DATE] Начало бэкапа..."

mkdir -p "$BACKUP_DIR"

# Собираем бэкап
tar czf "$BACKUP_FILE" \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='.venv' \
    /home/claude/ai-steward/ \
    /home/claude/projects/ \
    /home/claude/.claude/settings.json \
    2>/dev/null || true

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$DATE] Бэкап создан: $BACKUP_FILE ($SIZE)"

# Удалить старые бэкапы
cd "$BACKUP_DIR"
ls -t backup-*.tar.gz 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | while read -r old; do
    rm -f "$old"
    echo "[$DATE] Удалён старый бэкап: $old"
done

echo "[$DATE] Бэкап завершён"
