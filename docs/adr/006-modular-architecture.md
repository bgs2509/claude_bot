# ADR-006: Модульная архитектура handlers/services/middlewares

**Статус:** Принято
**Дата:** 2026-03-06

## Контекст

В v1.0.0 бот был монолитом (`bot.py`, ~500 строк). С добавлением проектов, сессий, FSM и пагинации код стал сложно поддерживать. Нужна структура для разделения ответственности.

## Решение

Трёхслойная архитектура в `src/ai_steward/`:

```
handlers/       — обработчики Telegram-событий (роутеры aiogram)
  commands.py   — /help, /menu, /new, /model, /voice, /status, /cancel
  menu.py       — inline callback для проектов/сессий + FSM
  text.py       — текстовые сообщения
  voice.py      — голосовые сообщения
  photo.py      — фотографии
  document.py   — документы

services/       — бизнес-логика (без зависимости от aiogram)
  claude.py     — вызов Claude Code CLI
  storage.py    — JSON-хранилище проектов/сессий
  speech.py     — STT и TTS
  ocr.py        — распознавание текста на фото
  format_telegram.py — Markdown → Telegram HTML

middlewares/    — сквозная логика
  auth.py       — авторизация, роли, лимиты, проброс зависимостей
```

Ключевые аргументы:
- **Разделение ответственности** — handlers знают о Telegram, services — нет.
- **Тестируемость** — services можно тестировать без aiogram.
- **Масштабируемость** — новый тип сообщений = новый файл в handlers/.
- **Роутеры aiogram** — каждый handler регистрирует свой Router, порядок важен (text.py — последний, catch-all).

## Альтернативы

- **Монолит** — был в v1.0.0, перестал масштабироваться.
- **Domain-driven (по фичам)** — `features/voice/`, `features/projects/` — избыточно для текущего размера.
- **Чистая архитектура (ports/adapters)** — слишком много абстракций для бота с 12 файлами.
