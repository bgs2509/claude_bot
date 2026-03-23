# Шаблоны CLAUDE.md для ai-steward

Шаблоны инструкций для иерархии CLAUDE.md. Используются при инициализации новых машин, юзеров и проектов.

## Иерархия

```
Уровень 0: ~/.claude/CLAUDE.md              — глобальные правила
            ~/.claude/rules/python-dev.md    — правила для Python-разработки
Уровень 1: ai-steward/CLAUDE.md             — правила бота, planner, шаблоны проектов
Уровень 2: {User}/CLAUDE.md                 — профиль юзера, стиль общения
Уровень 3: {User}/{Project}/CLAUDE.md       — правила конкретного проекта
```

Claude Code загружает ВСЕ CLAUDE.md от CWD вверх по дереву автоматически.

## Инициализация новой машины

1. Скопировать `templates/global/CLAUDE.md` → `~/.claude/CLAUDE.md`
2. Скопировать `templates/global/rules/python-dev.md` → `~/.claude/rules/python-dev.md`
3. Настроить `~/.claude/settings.json` (deny rules, sandbox, permissions)
4. Скопировать `templates/ai-steward/CLAUDE.md` → `/home/bgs/ai-steward/CLAUDE.md`
5. Адаптировать под конкретную машину: обновить список юзеров, стек, деплой

## Добавление нового юзера

1. Создать директорию `ai-steward/{UserName}/`
2. Создать `ai-steward/{UserName}/_output/`
3. Скопировать `templates/user/CLAUDE.md` → `ai-steward/{UserName}/CLAUDE.md`
4. Заполнить профиль по ответам на вопросы onboarding
5. Обновить список пользователей в `ai-steward/CLAUDE.md`

## Создание нового проекта

1. Создать директорию `ai-steward/{UserName}/{ProjectName}/`
2. Создать `ai-steward/{UserName}/{ProjectName}/_output/`
3. Выбрать тип проекта из `templates/projects/`
4. Скопировать соответствующий шаблон → `{ProjectName}/CLAUDE.md`
5. Адаптировать под конкретный проект
6. Создать `planner.json` если нужны напоминания (формат в `ai-steward/CLAUDE.md`)
7. Обновить список проектов в `{UserName}/CLAUDE.md`

## Плейсхолдеры в шаблонах

- `{USER_NAME}` — имя пользователя
- `{USER_AGE}` — возраст
- `{USER_GENDER}` — пол (М/Ж)
- `{USER_ROLE}` — роль (программист, домохозяйка, студент и т.д.)
- `{USER_INTERESTS}` — интересы через запятую
- `{USER_LEVEL}` — уровень (не-программист / начинающий / средний / эксперт)
- `{USER_TIMEZONE}` — часовой пояс
- `{USER_CHARACTER}` — персонаж для стиля общения
- `{PROJECT_NAME}` — название проекта
- `{TELEGRAM_USER_ID}` — Telegram ID для planner.json
