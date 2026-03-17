# Completion Report: TASK-002 — Система планирования и отслеживания дня

**Дата:** 2026-03-17
**Задача:** [TASK-002](../backlog/TASK-002-planning-tracker.md)

## Результат

Реализована система планирования дня, расширяющая модуль уведомлений (TASK-001) до полноценного трекера с поддержкой задач, событий, временных блоков и напоминаний.

## Что сделано

### Новые модули
- `models/planner.py` — единая модель `PlanItem` (Pydantic v2) с поддержкой статусов, приоритетов, повторений, carry-over
- `services/planner_service.py` — CRUD операции с `planner.json`, миграция из `notify.json`, логика напоминаний и конфликтов
- `services/planner_formatter.py` — форматирование плана в HTML (день, неделя, утренний/вечерний дайджест)
- `services/planner_manager.py` — фоновый цикл: напоминания, дайджесты, carry-over незавершённых задач

### Изменённые модули
- `handlers/commands.py` — команда `/plan` с навигацией по дням и обзором недели
- `keyboards.py` — `build_plan_keyboard()` для inline-навигации
- `config.py` — настройки `plan_morning_time`, `plan_evening_time`
- `constants.py` — константы статусов, приоритетов, emoji, callback-префиксов
- `errors.py` — user-friendly сообщения для ошибок планировщика
- `__main__.py` — инициализация `PlannerManager` вместо `NotificationManager`

### Архитектурные решения
- ADR-011: единая модель `PlanItem` вместо раздельных Notification/Task/Event
- Автомиграция `notify.json` → `planner.json` (старый файл переименовывается в `.bak`)
- `/notify` сохранена на старом сервисе для обратной совместимости

## Верификация

- Все импорты проверены (`models/planner`, `planner_manager`, `handlers/commands`)
- Quality gate и security review пройдены
