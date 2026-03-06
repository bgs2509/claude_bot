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
echo ""

# ffmpeg (для голосовых)
if ! command -v ffmpeg &>/dev/null; then
    echo "[1/4] Установка ffmpeg..."
    sudo apt install -y ffmpeg
else
    echo "[1/4] ffmpeg уже установлен"
fi

# tesseract (для OCR)
if ! command -v tesseract &>/dev/null; then
    echo "[2/4] Установка tesseract..."
    sudo apt install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
else
    echo "[2/4] tesseract уже установлен"
fi

# Python venv и зависимости
echo "[3/4] Настройка Python окружения..."
cd "$BOT_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  venv создан"
else
    echo "  venv уже существует"
fi
source venv/bin/activate
pip install -r requirements.txt --quiet
echo "  Зависимости установлены"

# .env
echo "[4/4] Проверка .env..."
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
echo "  source venv/bin/activate"
echo "  export \$(grep -v '^#' .env | xargs)"
echo "  python bot.py"
