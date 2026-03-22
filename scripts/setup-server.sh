#!/bin/bash
# Скрипт первоначальной настройки VPS для AI Steward Telegram Bot
# Запускать от root: bash setup-server.sh
set -euo pipefail

echo "=== Настройка VPS для AI Steward Bot ==="

# Обновление системы
echo "[1/8] Обновление системы..."
apt update && apt upgrade -y

# Создание пользователя
echo "[2/8] Создание пользователя claude..."
if id "claude" &>/dev/null; then
    echo "  Пользователь claude уже существует"
else
    adduser --disabled-password --gecos "Claude Bot" claude
    usermod -aG sudo claude
    echo "  Пользователь claude создан"
fi

# Node.js 22
echo "[3/8] Установка Node.js 22..."
if command -v node &>/dev/null; then
    echo "  Node.js уже установлен: $(node --version)"
else
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt install -y nodejs
    echo "  Node.js установлен: $(node --version)"
fi

# Python и утилиты
echo "[4/8] Установка Python и утилит..."
apt install -y \
    python3 python3-pip python3-venv python3-dev \
    git curl wget unzip htop jq \
    ffmpeg \
    tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng \
    make

# Docker
echo "[5/8] Установка Docker..."
if command -v docker &>/dev/null; then
    echo "  Docker уже установлен: $(docker --version)"
else
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker claude
    echo "  Docker установлен"
fi

# Swap
echo "[6/8] Настройка swap..."
if swapon --show | grep -q '/swapfile'; then
    echo "  Swap уже настроен"
else
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "  Swap 2GB создан"
fi

# uv
echo "[7/8] Установка uv..."
if su - claude -c "command -v uv" &>/dev/null; then
    echo "  uv уже установлен"
else
    su - claude -c "curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  uv установлен"
fi

# Claude Code
echo "[8/8] Установка Claude Code..."
npm install -g @anthropic-ai/claude-code
echo "  Claude Code установлен: $(claude --version 2>/dev/null || echo 'проверьте вручную')"

echo ""
echo "=== Настройка завершена ==="
echo ""
echo "Следующие шаги:"
echo "1. Настроить SSH ключи: ssh-copy-id claude@$(hostname -I | awk '{print $1}')"
echo "2. Запустить скрипт безопасности: bash scripts/setup-security.sh"
echo "3. Переключиться на пользователя: su - claude"
echo "4. Авторизовать Claude: claude auth login (OAuth через браузер)"
echo "5. Настроить бота (см. docs/DEPLOYMENT.md)"
