#!/bin/bash
# Скрипт установки зависимостей на локальной машине (Ubuntu)
# Запуск: bash scripts/setup-local.sh
set -euo pipefail

BOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Локальная установка Claude Code Bot ==="
echo "Директория: $BOT_DIR"
echo ""

# Проверка уже установленного
echo "Проверка установленных компонентов:"
echo "  Python:    $(python3 --version 2>/dev/null || echo 'НЕТ')"
echo "  Node.js:   $(node --version 2>/dev/null || echo 'НЕТ')"
echo "  Claude:    $(claude --version 2>/dev/null || echo 'НЕТ')"
echo "  ffmpeg:    $(ffmpeg -version 2>/dev/null | head -1 || echo 'НЕТ')"
echo "  tesseract: $(tesseract --version 2>/dev/null | head -1 || echo 'НЕТ')"
echo "  uv:        $(uv --version 2>/dev/null || echo 'НЕТ')"
echo ""

# ffmpeg (для голосовых)
if ! command -v ffmpeg &>/dev/null; then
    echo "[1/5] Установка ffmpeg..."
    sudo apt install -y ffmpeg
else
    echo "[1/5] ffmpeg уже установлен"
fi

# tesseract (для OCR)
if ! command -v tesseract &>/dev/null; then
    echo "[2/5] Установка tesseract..."
    sudo apt install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
else
    echo "[2/5] tesseract уже установлен"
fi

# uv
if ! command -v uv &>/dev/null; then
    echo "[3/5] Установка uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[3/5] uv уже установлен"
fi

# Python зависимости через uv
echo "[4/5] Установка Python зависимостей..."
cd "$BOT_DIR"
uv sync
echo "  Зависимости установлены"

# .env
echo "[5/5] Проверка .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  .env создан из .env.example"
    echo "  ⚠️  ЗАПОЛНИ .env перед запуском!"
    echo "     - TELEGRAM_BOT_TOKEN (от @BotFather)"
    echo "     - PROJECTS_DIR (путь к проектам, например /home/$USER/projects)"
else
    echo "  .env уже существует"
fi

echo ""
echo "=== Установка завершена ==="
echo ""
echo "Запуск бота:"
echo "  cd $BOT_DIR"
echo "  make run"
echo ""
echo "Или напрямую:"
echo "  uv run claude-bot"
