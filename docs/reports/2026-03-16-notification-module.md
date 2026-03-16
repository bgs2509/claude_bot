# Completion Report: Модуль уведомлений

## Task
- Task ID: TASK-001
- План: PLAN-001
- ADR: Нет

## Executive Summary

Реализован модуль персональных уведомлений: пользователи могут создавать напоминания (таблетки, события, задачи) через Claude, которые хранятся в `notify.json` в директории проекта. Фоновый цикл (`NotificationManager`) проверяет расписание и отправляет сообщения в Telegram. Поддерживаются единовременные и повторяющиеся уведомления (daily, weekly, monthly).

## Изменения

### Добавлено

| Файл | Описание |
|------|----------|
| `src/claude_bot/models/__init__.py` | Пакет моделей |
| `src/claude_bot/models/notification.py` | Pydantic-модели: `Notification`, `RepeatRule`, `NotifyFile` |
| `src/claude_bot/services/notification_service.py` | CRUD операции с `notify.json` (чтение, запись, фильтрация) |
| `src/claude_bot/services/notification_manager.py` | Фоновый цикл проверки расписания и отправки в Telegram |

### Изменено

| Файл | Описание |
|------|----------|
| `src/claude_bot/config.py` | Добавлено поле `notify_scan_interval` (тип `int`, из env `NOTIFY_SCAN_INTERVAL`) |
| `src/claude_bot/constants.py` | Эмодзи категорий уведомлений, `DAY_NAMES_RU`, `NOTIFY_DESC_PREVIEW_LEN` |
| `src/claude_bot/errors.py` | Сообщения об ошибках уведомлений (NotFoundError, ValidationError) |
| `src/claude_bot/handlers/commands.py` | Обработчик команды `/notify` и `/notify all` |
| `src/claude_bot/__main__.py` | Инициализация и интеграция `NotificationManager` в жизненный цикл бота |

## Результаты ревью

- [x] Quality Cascade — проверено (WARN→fixed)
- [x] Security чеклист — проверено (WARN→fixed)
- [x] Линтеры пройдены

### Ключевые исправления по итогам quality gate

| Тип | Проблема | Исправление |
|-----|----------|-------------|
| XSS | Поля `title`/`description` выводились без экранирования | Применён `html.escape()` перед вставкой в HTML-сообщение |
| Security | Получатели уведомлений не валидировались | Добавлена проверка против allowlist авторизованных пользователей |
| Validation | Поле `RepeatRule.time` принимало любую строку | Добавлена валидация через regex `^\d{2}:\d{2}$` |
| Bug | Еженедельные уведомления отображались как "Ежедневно" | Исправлена логика выбора строки в `DAY_NAMES_RU` |

## Результаты тестов

- Unit: не добавлялись (вне scope задачи)
- Integration: не добавлялись (вне scope задачи)
- Coverage: н/д

## Known Limitations

- Уведомления хранятся в `notify.json` рядом с сессиями проекта; при удалении проектной директории уведомления теряются.
- Команды создания/удаления уведомлений реализованы через Claude (естественный язык), прямых Telegram-команд для CRUD нет.
- Фоновый цикл использует `asyncio.sleep`, точность срабатывания ±`NOTIFY_SCAN_INTERVAL` секунд.

## Метрики

- Файлов добавлено: 4
- Файлов изменено: 5
- Тестов добавлено: 0
