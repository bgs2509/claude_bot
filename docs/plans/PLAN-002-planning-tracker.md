# PLAN-002: Система планирования и отслеживания дня

**Task:** TASK-002
**ADR:** ADR-011
**Дата:** 2026-03-17

---

## Контекст

Существующий модуль уведомлений (notify.json, NotificationManager, Notification-модель) покрывает лишь часть потребностей: он умеет отправлять напоминания по расписанию, но не управляет задачами дня, не показывает утренний дайджест и не переносит незавершённые пункты. Требуется рефакторинг в единую систему планирования: новая модель PlanItem объединяет уведомления и задачи, файл хранилища меняется с notify.json на planner.json с автоматической бесшовной миграцией. Архитектурное решение — Вариант A (единая модель), принятое в ADR-011, позволяет избежать дублирования логики между двумя разными типами сущностей. Результатом станет команда /plan с навигацией по дням, утренний и вечерний дайджесты, перенос незавершённых задач и конфликт-детекция при создании.

---

## Содержание

1. Слой моделей — PlanItem и PlannerFile
2. Слой сервиса — planner_service с CRUD, конфликтами и миграцией
3. Конфигурация и константы — новые поля Settings и метки статусов
4. Форматирование — planner_formatter (SRP: отдельный модуль)
5. PlannerManager — цикл сканирования, дайджесты, перенос задач
6. Клавиатуры — навигационная клавиатура /plan
7. Хэндлеры — команда /plan, inline-коллбэки, алиас /notify
8. Точка входа — обновление __main__.py и errors.py
9. Очистка — удаление старых файлов уведомлений

---

## Краткая версия плана

### Этап 1: Слой моделей — PlanItem и PlannerFile

1. **Проблема** — Модель Notification не имеет полей для приоритета, статуса, переноса задач и временного диапазона, поэтому её нельзя расширить без нарушения обратной совместимости.
2. **Действие** — Создать файл `models/planner.py` с Pydantic-моделями PlanItem (все поля из FR-1) и PlannerFile (обёртка `{items: [PlanItem]}`), повторно использовав RepeatRule из `models/notification.py`.
3. **Результат** — Единая типизированная модель данных, которую используют все остальные слои; старый models/notification.py остаётся нетронутым до этапа 8.
4. **Зависимости** — Нет; это первый этап.
5. **Риски** — Неверно выбранные типы полей (например, `date` vs `str`) потребуют исправлений во всех слоях сразу.
6. **Без этого** — Ни сервис, ни менеджер, ни хэндлеры не имеют согласованной структуры данных; весь последующий код невозможно написать.

---

### Этап 2: Слой сервиса — planner_service с CRUD, конфликтами и миграцией

1. **Проблема** — Нужен сервис, умеющий читать/писать planner.json, находить конфликты по времени и мигрировать существующие данные из notify.json.
2. **Действие** — Создать `services/planner_service.py` с методами: `load`, `save`, `add`, `remove`, `update`, `get_by_date`, `get_active`, `is_due`, `mark_sent`, `find_conflicts`, `migrate_from_notify`; логика миграции читает notify.json, конвертирует Notification → PlanItem, записывает planner.json, переименовывает notify.json → notify.json.bak.
3. **Результат** — Полноценный CRUD-сервис с полной логикой напоминаний (is_due/mark_sent), который на старте автоматически переносит данные из notify.json без потерь и умеет выявлять временные пересечения.
4. **Зависимости** — Этап 1 (модели PlanItem, PlannerFile).
5. **Риски** — При миграции поле remind_before может отсутствовать в старых записях — нужны дефолты; файл notify.json может отсутствовать — миграция должна молча пропускать этот случай.
6. **Без этого** — Данные некуда читать и писать; PlannerManager и хэндлеры не могут работать.

---

### Этап 3: Конфигурация и константы — новые поля Settings и метки статусов

1. **Проблема** — В Settings нет полей `plan_morning_time` и `plan_evening_time` для дайджестов; в constants.py нет emoji-меток статусов задач.
2. **Действие** — Добавить два поля в `config.py` (Settings), добавить словарь статус→emoji и строковые константы для /plan в `constants.py`.
3. **Результат** — PlannerManager берёт времена дайджестов из конфига; хэндлеры и менеджер используют единые константы для форматирования.
4. **Зависимости** — Нет технических зависимостей; желательно выполнять после этапа 1, чтобы знать точный список статусов.
5. **Риски** — Добавление полей без дефолтов сломает запуск у пользователей без обновлённого .env; нужны разумные значения по умолчанию.
6. **Без этого** — PlannerManager упадёт при обращении к несуществующим полям конфига; форматирование статусов придётся хардкодить в нескольких местах.

---

### Этап 4: Форматирование — planner_formatter (SRP)

1. **Проблема** — Логика форматирования PlanItem (статусы, длительность, дайджесты) нужна и в хэндлерах /plan, и в PlannerManager для дайджестов — размещение в хэндлере нарушает SRP и создаёт дублирование.
2. **Действие** — Создать `services/planner_formatter.py` с функциями: `format_day_plan`, `format_item_past`, `format_item_future`, `format_morning_digest`, `format_evening_summary`, `format_week_overview`. Сортировка: сначала с time_start хронологически, затем без времени по приоритету.
3. **Результат** — Единый модуль форматирования, используемый и хэндлерами и менеджером без дублирования.
4. **Зависимости** — Этапы 1, 3 (модели, константы).
5. **Риски** — Нет значимых.
6. **Без этого** — Форматирование дублируется в двух местах; изменение формата требует правок в нескольких файлах.

---

### Этап 5: PlannerManager — цикл сканирования, дайджесты, перенос задач (зависит от 1-4)

1. **Проблема** — NotificationManager нужно заменить новым менеджером, умеющим: слать напоминания для PlanItem, отправлять утренний/вечерний дайджест, переносить незавершённые задачи из прошлого дня.
2. **Действие** — Создать `services/planner_manager.py` с классом PlannerManager: единый цикл сканирования через asyncio, методы `_send_reminders`, `_morning_digest`, `_evening_summary`, `_carry_over`; уведомления отправляются через поле `remind_before` и `time_start` каждого PlanItem.
3. **Результат** — Рабочий фоновый процесс, заменяющий NotificationManager и реализующий FR-10, FR-11, FR-12, FR-13, FR-15.
4. **Зависимости** — Этапы 1, 2, 3 (модели, сервис, конфиг).
5. **Риски** — Двойная отправка напоминаний при перезапуске бота, если sent_reminders не сохраняется корректно; перенос задач может создать дубли при многократном запуске за одну ночь.
6. **Без этого** — Напоминания не отправляются, дайджесты отсутствуют, незавершённые задачи теряются.

---

### Этап 6: Клавиатуры — навигационная клавиатура /plan

1. **Проблема** — В keyboards.py нет функции для построения навигационной клавиатуры /plan с кнопками «◀ Вчера», «Завтра ▶», «Послезавтра ▶▶», «📅 Неделя».
2. **Действие** — Добавить функцию `build_plan_keyboard(date: date) -> InlineKeyboardMarkup` в `keyboards.py`, используя уже существующий паттерн построения inline-клавиатур проекта.
3. **Результат** — Переиспользуемый строитель клавиатуры, который хэндлер /plan вызывает при каждом отображении дня.
4. **Зависимости** — Этап 3 (нужны константы для callback_data префиксов).
5. **Риски** — Нет значимых рисков; паттерн уже отработан в keyboards.py.
6. **Без этого** — Хэндлер /plan не может отобразить навигацию; придётся строить клавиатуру прямо в хэндлере, нарушая разделение ответственности.

---

### Этап 7: Хэндлеры — команда /plan, inline-коллбэки, алиас /notify

1. **Проблема** — Команда /notify реализует старую логику уведомлений; нужна новая команда /plan с отображением задач дня, навигацией и фильтрацией по категории.
2. **Действие** — В `handlers/commands.py` переписать обработчик /plan (c форматированием элементов по FR-6/FR-7), добавить callback-хэндлеры для навигации и смены статуса, добавить алиас /notify → /plan в `handlers/commands.py`.
3. **Результат** — Пользователь может вызвать /plan или /notify, листать дни кнопками, видеть статусы прошлых задач, менять статус через inline-кнопки.
4. **Зависимости** — Этапы 1, 2, 3, 5 (модели, сервис, константы, клавиатура).
5. **Риски** — Callback-данные с датой могут превысить лимит Telegram в 64 байта при сложной схеме — нужно экономное кодирование (например, `plan:2026-03-17`).
6. **Без этого** — Пользователь не видит план дня; вся фронтальная часть функциональности отсутствует.

---

### Этап 8: Точка входа — обновление __main__.py и errors.py

1. **Проблема** — __main__.py инициализирует NotificationManager; errors.py содержит ключи ошибок для уведомлений; оба файла нужно обновить под новые имена.
2. **Действие** — В `__main__.py` заменить импорт и инициализацию NotificationManager на PlannerManager; в `errors.py` добавить/обновить ключи ошибок, связанных с planner.
3. **Результат** — Бот стартует с PlannerManager; все ошибки planner-слоя имеют user-friendly сообщения.
4. **Зависимости** — Этапы 1–6 (все предыдущие).
5. **Риски** — Если PlannerManager не инициализирован до диспетчера — команды /plan упадут при первом вызове.
6. **Без этого** — Бот запускается со старым менеджером или не запускается вовсе; ошибки planner-сервиса показывают внутренние сообщения пользователю.

---

### Этап 9: Очистка — удаление старых файлов уведомлений

1. **Проблема** — После полного перехода models/notification.py, services/notification_service.py, services/notification_manager.py становятся мёртвым кодом.
2. **Действие** — Удалить три старых файла; убедиться, что нет оставшихся импортов через `grep`; убедиться, что notify.json не читается нигде, кроме логики миграции в planner_service.
3. **Результат** — Кодовая база не содержит устаревших модулей; миграция по-прежнему работает (читает notify.json если есть, затем игнорирует).
4. **Зависимости** — Этап 7 (бот должен успешно стартовать без старых файлов).
5. **Риски** — Случайно удалённые RepeatRule или другие переиспользуемые части; нужно перенести их в models/planner.py до удаления.
6. **Без этого** — Мёртвый код остаётся в репозитории и создаёт путаницу при будущих изменениях.

---

## Полная версия плана

> **Исправления по результатам py-quality review:**
> - Добавлен этап 4 (planner_formatter) — SRP, нет дублирования форматирования
> - FR-3: notify.json переименовывается в notify.json.bak после миграции
> - FR-4: добавлены remove, is_due, mark_sent, get_active в planner_service
> - update() принимает типизированный PlanItemPatch вместо **kwargs
> - set_status() принимает PlanItemStatus (Literal) вместо str
> - carry-over: last_carry_date персистируется в PlannerFile
> - Дайджесты: метод _admin_uids() для определения получателей
> - datetime.utcnow() заменён на datetime.now(timezone.utc)

---

## Этап 1: Слой моделей — PlanItem и PlannerFile

**Файл:** `src/claude_bot/models/planner.py`

Создать новый файл, не трогая `models/notification.py` до этапа 8. Перенести `RepeatRule` из notification.py или импортировать напрямую — на усмотрение, но к этапу 8 RepeatRule должна жить только в planner.py.

Поля PlanItem (все Optional если не указано иное):

```python
class PlanItem(BaseModel):
    id: str                          # uuid4, обязательное
    title: str                       # обязательное
    description: str | None = None
    category: str = "task"           # task / event / block / произвольная строка
    priority: Literal["high", "medium", "low", "none"] = "none"
    date: date                       # обязательное, тип datetime.date
    time_start: time | None = None
    time_end: time | None = None
    deadline: datetime | None = None
    remind_before: list[int] = []    # минуты до time_start
    repeat: RepeatRule | None = None
    recipients: list[int] = []       # Telegram user_id
    status: Literal["pending", "in_progress", "done", "skipped", "cancelled"] = "pending"
    carried_over: bool = False
    carried_from: date | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: int | None = None    # Telegram user_id
    sent_reminders: list[int] = []   # хранит remind_before значения, для которых уже слали
```

Модель файла:

```python
class PlannerFile(BaseModel):
    items: list[PlanItem] = []
```

---

## Этап 2: Слой сервиса — planner_service с CRUD, конфликтами и миграцией

**Файл:** `src/claude_bot/services/planner_service.py`

Путь к файлу берётся из `Settings.planner_file` (новое поле, дефолт: `data/planner.json`).

Ключевые методы:

```python
class PlannerService:
    def __init__(self, settings: Settings): ...

    def load(self) -> PlannerFile: ...
    def save(self, pf: PlannerFile) -> None: ...

    def add(self, item: PlanItem) -> list[PlanItem]:
        """Добавляет item, возвращает список конфликтующих элементов (может быть пустым)."""

    def remove(self, item_id: str) -> bool:
        """Удалить элемент по ID. Возвращает True если найден."""

    def update(self, item_id: str, patch: PlanItemPatch) -> PlanItem | None:
        """Обновить элемент. PlanItemPatch — Pydantic-модель с Optional-полями."""

    def get_by_date(self, d: date) -> list[PlanItem]: ...
    def get_active(self, project_path: Path) -> list[PlanItem]:
        """Все активные элементы (status не в {done, cancelled, skipped})."""

    def is_due(self, item: PlanItem, now: datetime) -> list[int]:
        """Проверить какие remind_before нужно отправить. Логика из notification_service."""

    def mark_sent(self, project_path: Path, item: PlanItem, sent_minutes: list[int]) -> None:
        """Пометить напоминания как отправленные."""

    def find_conflicts(self, item: PlanItem, existing: list[PlanItem]) -> list[PlanItem]:
        """Конфликт = оба имеют time_start + time_end и интервалы пересекаются."""

    def mark_done(self, item_id: str) -> None: ...
    def mark_skipped(self, item_id: str) -> None: ...
    def set_status(self, item_id: str, status: PlanItemStatus) -> None:
        """PlanItemStatus = Literal['pending','in_progress','done','skipped','cancelled']"""

    def migrate_from_notify(self) -> int:
        """Читает notify.json если есть, конвертирует Notification → PlanItem,
        сохраняет в planner.json, переименовывает notify.json → notify.json.bak.
        Возвращает кол-во мигрированных записей.
        Пропускает если notify.json отсутствует или planner.json уже существует."""
```

Поля маппинга Notification → PlanItem при миграции:
- `id` → `id`
- `title` → `title`
- `message` → `description`
- `category` → `category`
- `scheduled_time.date()` → `date`
- `scheduled_time.time()` → `time_start`
- `remind_before` → `remind_before` (оборачивать в список если было scalar)
- `recipients` → `recipients`
- `status` → `status` (маппинг: `sent` → `done`, `cancelled` → `cancelled`, иначе `pending`)
- `created_at` → `created_at`

---

## Этап 3: Конфигурация и константы — новые поля Settings и метки статусов

**Файлы:** `src/claude_bot/config.py`, `src/claude_bot/constants.py`

В `config.py` добавить в класс Settings:

```python
planner_file: Path = Path("data/planner.json")
plan_morning_time: time = time(8, 0)   # время утреннего дайджеста
plan_evening_time: time = time(21, 0)  # время вечернего дайджеста
```

В `constants.py` добавить:

```python
# Статусы PlanItem
PLAN_STATUS_EMOJI = {
    "done":      "✅",
    "skipped":   "📦",
    "cancelled": "❌",
    "pending":   "⬜",
    "in_progress": "🔄",
}

# Callback-префиксы для /plan
PLAN_CB_DAY   = "plan:day:"      # plan:day:2026-03-17
PLAN_CB_WEEK  = "plan:week"
PLAN_CB_STATUS = "plan:status:"  # plan:status:{item_id}:{new_status}
```

---

## Этап 4: Форматирование — planner_formatter

**Файл:** `src/claude_bot/services/planner_formatter.py`

Выделенный модуль форматирования (SRP — хэндлеры и PlannerManager используют одни функции):

```python
def format_day_plan(d: date, items: list[PlanItem], now: datetime) -> str:
    """Форматирует план дня в HTML. Сортировка: сначала с time_start (хронологически),
    затем без времени (по приоритету: high > medium > low > none).
    Алгоритм: sorted(items, key=lambda x: (x.time_start is None, x.time_start or time.min, PRIORITY_ORDER[x.priority]))"""

def format_item_past(item: PlanItem) -> str:
    """Элемент прошлого дня: ✅ done / 📦 перенесено на DD.MM / ❌ cancelled / ⬜ не выполнено."""

def format_item_future(item: PlanItem) -> str:
    """Элемент будущего: '10:00 (1ч 30мин) Название' если time_start+time_end, иначе '10:00 Название'."""

def format_item_current(item: PlanItem, now: datetime) -> str:
    """Элемент текущего дня: статус-эмодзи + время + название."""

def format_morning_digest(items: list[PlanItem], carried: list[PlanItem]) -> str:
    """Утренний дайджест: план дня + перенесённые задачи."""

def format_evening_summary(items: list[PlanItem]) -> str:
    """Вечерний итог: done/pending/skipped + completion rate %."""

def format_week_overview(days: dict[date, list[PlanItem]]) -> str:
    """Обзор недели: краткий список по дням."""
```

---

## Этап 5: PlannerManager — цикл сканирования, дайджесты, перенос задач

**Файл:** `src/claude_bot/services/planner_manager.py`

```python
class PlannerManager:
    def __init__(self, bot: Bot, settings: Settings, service: PlannerService): ...

    async def start(self) -> None:
        """Запускает migrate_from_notify(), затем asyncio-задачу _loop()."""

    async def stop(self) -> None: ...

    async def _loop(self) -> None:
        """Раз в 30 секунд вызывает _tick()."""

    async def _tick(self) -> None:
        """_carry_over() при смене даты, _send_reminders(), _morning_digest(),
        _evening_summary()."""

    async def _carry_over(self) -> None:
        """Для каждого PlanItem со статусом pending/in_progress и date < today
        создаёт копию с новой date=today, carried_over=True, carried_from=старая дата."""

    async def _send_reminders(self) -> None:
        """Для каждого сегодняшнего PlanItem с time_start проверяет remind_before:
        если текущее время попало в окно [time_start - remind_before мин, time_start - remind_before мин + 30с]
        и значение отсутствует в sent_reminders — отправляет и добавляет в sent_reminders."""

    async def _morning_digest(self) -> None:
        """В plan_morning_time ± 30с отправляет сводку задач на сегодня."""

    async def _evening_summary(self) -> None:
        """В plan_evening_time ± 30с отправляет итог дня: сколько done/pending/% выполнения."""
```

Защита от дублей при carry-over: добавить поле `last_carry_date: date | None = None` в `PlannerFile`. При старте менеджера читать его из файла. Перед переносом проверять: если `last_carry_date == today` — пропустить. После успешного переноса записать `last_carry_date = today` в файл.

Получатели дайджестов: метод `_admin_uids() -> list[int]` итерирует `settings.users`, возвращает uid с `role == "admin"`.

---

## Этап 6: Клавиатуры — навигационная клавиатура /plan

**Файл:** `src/claude_bot/keyboards.py`

```python
from datetime import date, timedelta

def build_plan_keyboard(d: date) -> InlineKeyboardMarkup:
    yesterday  = d - timedelta(days=1)
    tomorrow   = d + timedelta(days=1)
    aftertomorrow = d + timedelta(days=2)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="◀ Вчера",        callback_data=f"{PLAN_CB_DAY}{yesterday}"),
            InlineKeyboardButton(text="Завтра ▶",       callback_data=f"{PLAN_CB_DAY}{tomorrow}"),
            InlineKeyboardButton(text="Послезавтра ▶▶", callback_data=f"{PLAN_CB_DAY}{aftertomorrow}"),
        ],
        [
            InlineKeyboardButton(text="📅 Неделя", callback_data=PLAN_CB_WEEK),
        ],
    ])
```

---

## Этап 7: Хэндлеры — команда /plan, inline-коллбэки, алиас /notify

**Файл:** `src/claude_bot/handlers/commands.py`

Форматирование — через `planner_formatter` (этап 4). Хэндлер только вызывает функции форматтера.

Обработчик `/plan [категория]`:
```python
@router.message(Command("plan"))
async def cmd_plan(message: Message, planner_service: PlannerService, ...):
    today = date.today()
    items = planner_service.get_by_date(today)
    # фильтр по категории если передана
    text = format_day_plan(today, items)
    await message.answer(text, reply_markup=build_plan_keyboard(today))
```

Callback-хэндлер для навигации:
```python
@router.callback_query(F.data.startswith(PLAN_CB_DAY))
async def cb_plan_day(call: CallbackQuery, planner_service: PlannerService, ...):
    d = date.fromisoformat(call.data.removeprefix(PLAN_CB_DAY))
    items = planner_service.get_by_date(d)
    text = format_day_plan(d, items)
    await call.message.edit_text(text, reply_markup=build_plan_keyboard(d))
```

Алиас `/notify`:
```python
@router.message(Command("notify"))
async def cmd_notify_alias(message: Message, **data):
    # forward to cmd_plan
    await cmd_plan(message, **data)
```

Фильтрация по категории (FR-17): принимать необязательный аргумент после команды (`/plan tasks`), передавать в `get_by_date` как фильтр.

---

## Этап 8: Точка входа — обновление __main__.py и errors.py

**Файл:** `src/claude_bot/__main__.py`

Заменить:
```python
# было
from claude_bot.services.notification_manager import NotificationManager
manager = NotificationManager(bot, settings, notification_service)

# стало
from claude_bot.services.planner_manager import PlannerManager
planner_service = PlannerService(settings)
manager = PlannerManager(bot, settings, planner_service)
```

Передать `planner_service` в диспетчер через `dp["planner_service"] = planner_service` для инжекции в хэндлеры.

**Файл:** `src/claude_bot/errors.py`

Добавить ключи:
```python
"planner.load_failed":    "Не удалось загрузить план. Попробуйте позже.",
"planner.save_failed":    "Не удалось сохранить изменения.",
"planner.item_not_found": "Задача не найдена.",
"planner.conflict":       "Обнаружен конфликт времени. Выберите действие.",
```

---

## Этап 9: Очистка — удаление старых файлов уведомлений

Файлы для удаления (только после успешного старта бота на этапе 8):
- `src/claude_bot/models/notification.py`
- `src/claude_bot/services/notification_service.py`
- `src/claude_bot/services/notification_manager.py`

Перед удалением убедиться:
1. `RepeatRule` перенесена в `models/planner.py`
2. Нет импортов этих модулей вне трёх удаляемых файлов (проверить grep)
3. `handlers/commands.py` уже не импортирует NotificationService/Manager
4. `__main__.py` уже использует PlannerManager

После удаления: notify.json.bak в директориях проектов — безвреден, миграция уже переименовала notify.json → notify.json.bak на этапе 2.
