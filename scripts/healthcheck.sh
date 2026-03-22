#!/bin/bash
# Healthcheck скрипт — проверяет работоспособность и отправляет алерты
# Cron: */5 * * * * /home/claude/ai-steward/scripts/healthcheck.sh
set -euo pipefail

# Настройки (заполнить)
ALERT_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
ALERT_CHAT_ID="${ALERT_CHAT_ID:-}"

send_alert() {
    local message="$1"
    if [[ -n "$ALERT_BOT_TOKEN" && -n "$ALERT_CHAT_ID" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${ALERT_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${ALERT_CHAT_ID}" \
            -d "text=${message}" \
            -d "parse_mode=HTML" > /dev/null 2>&1
    fi
}

ALERTS=""

# Проверка 1: Бот запущен
if ! systemctl is-active --quiet ai-steward; then
    ALERTS+="🔴 ai-steward НЕ запущен!\n"
    # Попытка перезапуска
    sudo systemctl restart ai-steward 2>/dev/null
    sleep 3
    if systemctl is-active --quiet ai-steward; then
        ALERTS+="🟢 Перезапуск успешен\n"
    else
        ALERTS+="🔴 Перезапуск НЕ удался\n"
    fi
fi

# Проверка 2: Диск
DISK_USAGE=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
if (( DISK_USAGE > 80 )); then
    ALERTS+="⚠️ Диск: ${DISK_USAGE}%\n"
fi

# Проверка 3: RAM
RAM_USAGE=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
if (( RAM_USAGE > 90 )); then
    ALERTS+="⚠️ RAM: ${RAM_USAGE}%\n"
fi

# Проверка 4: Бэкап свежий
LATEST_BACKUP=$(ls -t /home/claude/backups/backup-*.tar.gz 2>/dev/null | head -1)
if [[ -n "$LATEST_BACKUP" ]]; then
    BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 3600 ))
    if (( BACKUP_AGE > 48 )); then
        ALERTS+="⚠️ Бэкап устарел: ${BACKUP_AGE}ч назад\n"
    fi
fi

# Отправить алерт если есть проблемы
if [[ -n "$ALERTS" ]]; then
    HOSTNAME=$(hostname)
    send_alert "🚨 <b>Alert: ${HOSTNAME}</b>

${ALERTS}
$(date '+%Y-%m-%d %H:%M')"
fi
