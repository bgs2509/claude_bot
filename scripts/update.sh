#!/bin/bash
# Скрипт обновления всех компонентов
# Запускать от пользователя claude: bash update.sh
set -euo pipefail

echo "=== Обновление Claude Code Bot ==="

# Claude Code
echo "[1/4] Обновление Claude Code..."
npm update -g @anthropic-ai/claude-code
echo "  Версия: $(claude --version 2>/dev/null || echo 'N/A')"

# MCP серверы (очистить кэш npx)
echo "[2/4] Очистка кэша MCP серверов..."
npx clear-npx-cache 2>/dev/null || true
echo "  Кэш очищен (свежие версии загрузятся при запуске)"

# Python зависимости
echo "[3/4] Обновление Python зависимостей..."
cd /home/claude/claude-bot
source venv/bin/activate
pip install -r requirements.txt --upgrade --quiet
deactivate
echo "  Зависимости обновлены"

# Перезапуск бота
echo "[4/4] Перезапуск бота..."
sudo systemctl restart claude-bot
sleep 2
STATUS=$(systemctl is-active claude-bot)
echo "  Статус бота: $STATUS"

echo ""
echo "=== Обновление завершено ==="
