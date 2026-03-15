# Вариант C: Файловая конвенция SKILL.md + reference.md

**Дата:** 2026-03-15
**Контекст:** Выбор архитектуры для переиспользования стандартов python-ai-guide в 10-20+ проектах через Claude Code Skills.

## Суть подхода

Skills организуются по конвенции: `SKILL.md` содержит краткую версию (L0+L1), `reference.md` — полную (L2). Claude загружает `SKILL.md` при вызове, а `reference.md` читает через инструмент `Read` **только когда нужны детали**. Никакого дополнительного кода, серверов или зависимостей.

```
~/.claude/skills/quality-cascade/
├── SKILL.md          →  Описание + краткие принципы (~30 строк, ~300 токенов)
└── reference.md      →  Полный текст с примерами (~200 строк, ~2000 токенов)
```

---

## Как работает загрузка (3 фазы)

### Фаза 1: Метаданные (старт сессии)

При начале сессии Claude загружает **только `name` и `description`** каждого skill'а.

- Стоимость: ~100 токенов на skill
- 10 skill'ов = ~1,000 токенов (пренебрежимо)
- 50 skill'ов = ~5,000 токенов (всё ещё мало)
- Бюджет: 2% контекстного окна (можно переопределить через `SLASH_COMMAND_TOOL_CHAR_BUDGET`)

Claude видит **что доступно**, но не загружает содержимое.

**Источник:** [Skills — Where skills live](https://code.claude.com/docs/en/skills.md#where-skills-live)

### Фаза 2: SKILL.md (при вызове)

Когда skill вызван (вручную `/quality-review` или автоматически по description), Claude читает полный `SKILL.md` с диска.

- Стоимость: 300-5,000 токенов (зависит от размера)
- Рекомендация: до 500 строк
- Перечитывается каждый раз (нет кеша между вызовами)
- Изменения в файле видны мгновенно (live reload)

### Фаза 3: Поддерживающие файлы (по требованию)

Если `SKILL.md` ссылается на `reference.md`, Claude читает его через `Read` **только если задача требует деталей**.

- Стоимость: 0 токенов пока не прочитан
- Claude решает сам — нужен ли reference.md для текущей задачи
- Файл читается через Read tool, **не дублируется** в каждом сообщении контекста (в отличие от MCP-ответов)

**Это ключевое преимущество Варианта C:** reference.md прочитан через Read = одноразовая загрузка. MCP-ответ = включается в историю и пересылается в каждом сообщении.

**Источник:** [Skills — Add supporting files](https://code.claude.com/docs/en/skills.md#add-supporting-files)

---

## Структура skill'а

### Минимальный пример

```yaml
# ~/.claude/skills/quality-cascade/SKILL.md
---
name: quality-cascade
description: 17 принципов качества Python-кода. Используй при ревью, рефакторинге и написании нового кода.
---

## Принципы (краткая версия)

1. **DRY** — нет дублирования логики
2. **SRP** — один класс/функция = одна ответственность
3. **LoD** — не лезь в чужие внутренности (a.b.c.d — плохо)
4. **KISS** — простое решение лучше сложного
5. **Fail Fast** — валидация на входе, guard clauses
...

**Красные флаги:** except pass, god class >300 строк, magic numbers

Полный текст с примерами и антипаттернами: см. [reference.md](reference.md)
```

### reference.md

```markdown
# Quality Cascade — полная версия

## Принцип 1: DRY

### Описание
...

### Примеры нарушений
...

### Как исправить
...

## Принцип 2: SRP
...
```

### Расширенная структура (для крупных skill'ов)

```
quality-cascade/
├── SKILL.md              # Навигация + краткая версия (200 строк)
├── reference.md          # Полные принципы с примерами (500 строк)
└── examples.md           # Примеры ревью (300 строк)

security/
├── SKILL.md              # OWASP Top 10 — краткий чек-лист
├── reference/
│   ├── auth.md           # Аутентификация и авторизация
│   ├── injection.md      # SQL/Command injection
│   └── validation.md     # Валидация входных данных
└── scripts/
    └── check_secrets.sh  # Скрипт проверки секретов в коде
```

**Источник:** [Best practices — Pattern 2: Domain-organized](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#pattern-1-high-level-guide-with-references)

---

## Поведение description — как Claude выбирает skills

Description — **единственное** что определяет автозагрузку. Claude использует **семантическое сопоставление** (не regex, не ключевые слова) через свою языковую модель.

### Правила хорошего description

```yaml
# ✅ Хорошо — конкретно, с триггерами
description: >
  17 принципов качества Python-кода (DRY, SRP, LoD, KISS).
  Используй при ревью кода, рефакторинге, написании новых модулей.

# ❌ Плохо — слишком абстрактно
description: Помогает с качеством кода
```

### Что включать в description

1. **ЧТО делает** — "17 принципов качества Python-кода"
2. **КОГДА использовать** — "при ревью, рефакторинге, написании нового кода"
3. **Ключевые слова** — "DRY, SRP, LoD, KISS" (помогают семантическому матчингу)

### Ограничения

- Максимум 1,024 символа
- Нельзя XML-теги
- Писать от третьего лица ("Проверяет код...", не "Я проверяю...")

**Источник:** [Best practices — Writing effective descriptions](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#writing-effective-descriptions)

---

## Расход токенов — детальный расчёт

### Базовые размеры

| Компонент | Строк | Токенов |
|-----------|-------|---------|
| Description (1 skill) | 2-3 | ~100 |
| SKILL.md body (краткая версия) | 30-50 | ~300-500 |
| reference.md (полная версия) | 150-500 | ~1,500-5,000 |

### Сценарий: 10 core skills, сессия 20 сообщений

**Ревью кода (5 запросов) — нужны 3 skill'а с деталями:**
- Descriptions всех: 1,000 токенов (загружены всегда)
- SKILL.md × 3: 900-1,500 токенов
- reference.md × 1-3: 1,500-5,000 токенов (Claude решает сколько нужно)
- **Итого: 3,400-7,500 токенов на запрос**

**Написание кода (10 запросов) — фоновый контекст, детали не нужны:**
- Descriptions: 1,000 токенов
- SKILL.md × 0-2 (автозагрузка): 0-600 токенов
- reference.md: не читается
- **Итого: 1,000-1,600 токенов на запрос**

**Простые вопросы (5 запросов) — skills не нужны:**
- Descriptions: 1,000 токенов
- Остальное: 0
- **Итого: 1,000 токенов на запрос**

### Сравнение с другими вариантами

| Метрика | Без тиеринга | Вариант C | MCP (A/B/D) |
|---------|-------------|-----------|-------------|
| Среднее за сессию | ~100,000 | ~34,000 | ~46,000 |
| Экономия | — | **66%** | 54% |
| Мусорные токены | 40-60% | 10-20% | 10-20% |

**Почему C экономнее MCP:** reference.md прочитан через Read = данные в одном сообщении. MCP-ответ = включается в tool_result и **пересылается в каждом последующем запросе** пока не будет сжат.

---

## Сильные стороны

### 1. Ноль кода, ноль зависимостей

Никакого MCP-сервера, embedding-провайдера, базы данных. Только .md файлы в `~/.claude/skills/`. Работает на любой машине с Claude Code.

### 2. Лучшая экономия токенов (-66%)

Парадоксально, самый простой вариант экономит больше всех. Причина: `reference.md` читается через `Read` tool и не дублируется в истории сообщений, в отличие от MCP-ответов.

### 3. Live reload

Изменил `SKILL.md` или `reference.md` — Claude видит изменения при следующем вызове. Не нужно перезапускать сервер, переиндексировать базу, перезагружать сессию.

### 4. Git-версионирование

Все skill'ы — обычные .md файлы. Можно хранить в git, делать PR, откатывать, отслеживать историю изменений.

### 5. Прозрачность

Видно что Claude загрузил — каждый Read tool call отображается в чате. В отличие от автозагрузки `user-invocable: false`, где непонятно что и когда подгрузилось.

### 6. Быстрый старт

Время на создание: ~2.5 часа (написать 10 skill'ов + reference файлы). Для сравнения: MCP-варианты = 4-6 часов, OpenViking = 5-7 часов.

### 7. Масштабируемость описаний

При 100 skill'ах описания = ~10,000 токенов (~2% контекста). Система работает до 100+ skill'ов без деградации.

---

## Слабые стороны

### 1. Нет семантического поиска

Claude выбирает skill только по description (семантическое сопоставление LLM). При 30+ skill'ах с похожими описаниями Claude может выбрать не тот skill или пропустить нужный.

**Митигация:** Писать максимально специфичные description с ключевыми словами-триггерами. Избегать пересекающихся описаний.

### 2. Нет гарантии что reference.md будет/не будет прочитан

Claude **сам решает** нужен ли reference.md. Это может привести к:
- **Перерасходу:** Claude читает reference.md когда хватило бы SKILL.md
- **Недозагрузке:** Claude не читает reference.md когда детали нужны

**Митигация:** Чёткие указания в SKILL.md: "Для ревью кода ОБЯЗАТЕЛЬНО прочитай reference.md. Для написания нового кода — достаточно принципов выше."

### 3. Ручное разделение на L0/L1/L2

Нужно вручную решить что идёт в SKILL.md (краткая версия), а что в reference.md (полная). Для 10 skill'ов из python-ai-guide (~22 файлов) — это ~2 часа ручной работы.

**Митигация:** Один раз сделать — потом обновлять инкрементально.

### 4. Нет памяти между сессиями (для skills)

Skills не запоминают что работало, а что нет. Каждая сессия начинается с нуля.

**Митигация:** Claude Code имеет собственную систему memory (`~/.claude/projects/*/memory/`). Это не связано со skills, но покрывает потребность в памяти.

### 5. Нет автоматического профилирования по типу проекта

Skill не знает, что проект — монолит или микросервис. Нужно либо:
- Явно вызывать `/quality-review-monolith`
- Либо полагаться на CLAUDE.md проекта (где указан тип архитектуры)

**Митигация:** В CLAUDE.md проекта указывать тип архитектуры. Skill может содержать инструкцию: "Прочитай CLAUDE.md проекта, найди тип архитектуры, применяй соответствующие правила."

### 6. Дублирование при обновлении python-ai-guide

При изменении python-ai-guide нужно вручную обновить соответствующие skill'ы.

**Митигация:** Можно использовать `!cat` preprocessing для динамической загрузки:
```yaml
---
name: quality-cascade
description: 17 принципов качества Python-кода
---
!`cat /home/bgs/Henry_Bud_GitHub/python-ai-guide/development/quality-cascade.md | head -50`

Полная версия: см. [reference.md](reference.md)
```
Но это создаёт зависимость от пути к python-ai-guide.

### 7. Claude может автозагрузить ненужный skill

Если description слишком широкий, Claude может загрузить skill когда он не нужен, потратив токены впустую.

**Митигация:**
- `disable-model-invocation: true` — только ручной вызов, Claude не загрузит сам
- Узкие, специфичные description

---

## Приоритеты skill'ов

При конфликте имён (один skill на нескольких уровнях):

| Приоритет | Уровень | Путь |
|-----------|---------|------|
| 1 (высший) | Enterprise | Управляется админом |
| 2 | Personal | `~/.claude/skills/<name>/SKILL.md` |
| 3 | Project | `.claude/skills/<name>/SKILL.md` |
| 4 (низший) | Plugin | `<plugin>/skills/<name>/SKILL.md` |

Проектный skill может **переопределить** глобальный с тем же именем. Это позволяет иметь глобальный `quality-cascade` и проектный `quality-cascade` с дополнениями.

**Источник:** [Skills — Where skills live](https://code.claude.com/docs/en/skills.md#where-skills-live)

---

## Динамический контент (!`command`)

Skills поддерживают preprocessing — выполнение shell-команд **до** отправки Claude:

```yaml
---
name: project-stats
description: Статистика текущего проекта
---

## Текущее состояние
- Файлов Python: !`find . -name "*.py" | wc -l`
- Строк кода: !`find . -name "*.py" -exec wc -l {} + | tail -1`
- Последний коммит: !`git log --oneline -1`
```

Claude получает **результат**, не команду. Полезно для skill'ов, которые должны знать состояние проекта.

**Источник:** [Skills — Inject dynamic context](https://code.claude.com/docs/en/skills.md#inject-dynamic-context)

---

## context: fork + reference файлы

При использовании `context: fork` skill запускается в изолированном subagent контексте:

```yaml
---
name: deep-quality-review
description: Глубокий ревью качества кода
context: fork
agent: Explore
---

Проверь код по принципам quality-cascade.
Полные принципы: см. [reference.md](reference.md)
```

Subagent **может** читать reference.md через Read — поддерживающие файлы работают нормально в forked контексте.

**Источник:** [Skills — Run skills in a subagent](https://code.claude.com/docs/en/skills.md#run-skills-in-a-subagent)

---

## Рекомендуемая структура для python-ai-guide

```
~/.claude/skills/
├── quality-cascade/
│   ├── SKILL.md              # 17 принципов — краткий чек-лист (40 строк)
│   └── reference.md          # Полные принципы + антипаттерны + примеры
│
├── error-handling/
│   ├── SKILL.md              # Иерархия исключений, retry — кратко (30 строк)
│   └── reference.md          # Маппинг HTTP ↔ исключения, шаблоны
│
├── security/
│   ├── SKILL.md              # OWASP Top 10 — чек-лист (30 строк)
│   └── reference/
│       ├── auth.md           # Аутентификация
│       ├── injection.md      # Injection-атаки
│       └── validation.md     # Валидация входных данных
│
├── logging/
│   ├── SKILL.md              # Log-Driven Design — принципы (30 строк)
│   └── reference.md          # AI-Readable Logging, structured logging
│
├── testing/
│   ├── SKILL.md              # 3 уровня тестов, покрытие (30 строк)
│   └── reference.md          # AAA-паттерн, фикстуры, моки
│
├── create-adr/
│   └── SKILL.md              # Генератор ADR (disable-model-invocation: true)
│
├── completion-report/
│   └── SKILL.md              # Генератор completion report
│
└── init-project/
    └── SKILL.md              # Инициализация .claude/ для нового проекта
```

---

## Когда переходить на другой вариант

| Сигнал | Действие |
|--------|----------|
| Claude часто загружает не тот skill | Уточнить descriptions. Если не помогает → MCP с поиском (Вариант B) |
| Skill'ов стало 30+ | Рассмотреть MCP с FTS5 (Вариант B) |
| Claude всегда читает reference.md | Значит SKILL.md недостаточно информативен — расширить краткую версию |
| Claude никогда не читает reference.md | Значит reference.md избыточен — можно убрать |
| Нужна память между сессиями (для skills) | Использовать Claude Code memory или рассмотреть OpenViking |
| Стоимость токенов критична | Вариант A (MCP тиеринг) — даёт явный контроль L0/L1/L2 |

---

## Источники

- [Claude Code — Extend Claude with skills](https://code.claude.com/docs/en/skills.md)
- [Claude API — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Claude Code — Manage costs effectively](https://code.claude.com/docs/en/costs.md)
- [Claude Code — Features overview](https://code.claude.com/docs/en/features-overview.md)
