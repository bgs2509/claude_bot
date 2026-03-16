# PLAN-001: Модуль уведомлений

**Task:** TASK-001
**Дата:** 2026-03-16
**Статус:** Готов к реализации

---

## Контекст

Telegram-бот предоставляет доступ к Claude Code CLI и хранит данные пользователей по проектам в файловой системе. Пользователям нужна система напоминаний — медикаменты, события, задачи — которая работает автономно в фоне и отправляет сообщения в нужное время. Сейчас у бота нет механизма отложенных или повторяющихся уведомлений, поэтому пользователи не могут настраивать регулярные напоминания через бот. Модуль должен органично встроиться в существующую архитектуру: хранить данные рядом с проектами в `notify.json`, работать фоновым asyncio-циклом по образцу существующего `analytics.py`, и отправлять сообщения через `bot.send_message()`.

---

## Содержание

1. Pydantic-модели уведомлений
2. NotificationService — операции с notify.json
3. NotificationManager — фоновый цикл и отправка
4. Конфигурация: NOTIFY_SCAN_INTERVAL
5. Константы категорий и эмодзи
6. Обработка ошибок уведомлений
7. Команда /notify
8. Интеграция в точку входа

---

## Краткая версия плана

### Этап 1: Pydantic-модели уведомлений

1. **Проблема** — Нет типизированного представления уведомления: поля, правила повтора, статусы.
2. **Действие** — Создать файл `src/claude_bot/models/notification.py` с моделями `RepeatRule`, `Notification` и `NotifyFile`.
3. **Результат** — Все компоненты работают с единым типизированным объектом уведомления, валидация входных данных через Pydantic.
4. **Зависимости** — Независимый этап, выполняется первым.
5. **Риски** — Ошибки в описании типов полей (особенно `repeat.days`) могут привести к несовместимости при чтении существующих `notify.json`.
6. **Без этого** — Все последующие этапы не могут работать с уведомлениями типобезопасно.

### Этап 2: NotificationService — операции с notify.json

1. **Проблема** — Нет слоя для чтения и записи `notify.json` из директорий проектов.
2. **Действие** — Создать класс `NotificationService` в `src/claude_bot/services/notifier.py` с методами загрузки, сохранения, добавления, удаления, обновления и фильтрации активных уведомлений. Добавить метод `is_due()` для проверки, наступило ли время уведомления, и `next_occurrence()` для расчёта следующего срабатывания повторяющихся уведомлений.
3. **Результат** — Единая точка работы с `notify.json`; менеджер и обработчики команд не работают с файловой системой напрямую.
4. **Зависимости** — Этап 1 (модели).
5. **Риски** — Логика `is_due()` для weekly/monthly может давать дубли при перезапуске бота, если не отслеживать последнюю отправку.
6. **Без этого** — `NotificationManager` не может читать и сохранять уведомления.

### Этап 3: NotificationManager — фоновый цикл и отправка

1. **Проблема** — Нет механизма, который регулярно проверяет уведомления и отправляет их пользователям.
2. **Действие** — Создать класс `NotificationManager` (в том же `services/notifier.py`) с методами `init()`, `_scan_loop()`, `_check_and_send()`, `_send()`, `_format_notification()` и `close()`. Цикл обходит всех пользователей из `storage`, все их проекты и проверяет `notify.json` каждые `NOTIFY_SCAN_INTERVAL` секунд.
3. **Результат** — Уведомления отправляются автоматически в нужное время; ошибки одного проекта не ломают сканирование остальных.
4. **Зависимости** — Этапы 1 и 2 (модели и сервис), Этап 4 (конфиг).
5. **Риски** — При `NOTIFY_SCAN_INTERVAL=60` возможен сдвиг до 60 секунд от запланированного времени; бот не переживает длительный даунтайм без механизма "догонки".
6. **Без этого** — Вся система уведомлений не работает — уведомления хранятся, но никогда не отправляются.

### Этап 4: Конфигурация NOTIFY_SCAN_INTERVAL

1. **Проблема** — Интервал сканирования зашит в коде, нельзя настроить без правки исходников.
2. **Действие** — Добавить поле `notify_scan_interval: int = 60` в класс `Settings` в `src/claude_bot/config.py` и добавить `NOTIFY_SCAN_INTERVAL=60` в `.env.example`.
3. **Результат** — Оператор может задать интервал через переменную окружения без изменения кода.
4. **Зависимости** — Независим от других этапов, но должен быть готов до Этапа 3.
5. **Риски** — Слишком маленький интервал (например, 5 секунд) создаст лишнюю нагрузку на файловую систему при большом числе проектов.
6. **Без этого** — Интервал придётся хардкодить в `NotificationManager`, что нарушает принцип конфигурируемости.

### Этап 5: Константы категорий и эмодзи

1. **Проблема** — Эмодзи категорий разбросаны по коду или отсутствуют, нет централизованного словаря.
2. **Действие** — Добавить в `src/claude_bot/constants.py` константы `EMOJI_MEDICATION`, `EMOJI_EVENT`, `EMOJI_TODO`, `EMOJI_REMINDER`, `EMOJI_NOTIFY` и словарь `CATEGORY_EMOJI` для маппинга категории → эмодзи.
3. **Результат** — Форматирование уведомлений и команда `/notify` используют единый источник эмодзи.
4. **Зависимости** — Независим, выполняется до Этапов 3 и 7.
5. **Риски** — Минимальные.
6. **Без этого** — Эмодзи в сообщениях будут задублированы или рассинхронизированы между форматтером и командой.

### Этап 6: Обработка ошибок уведомлений

1. **Проблема** — В `errors.py` нет пользовательских сообщений об ошибках, специфичных для модуля уведомлений.
2. **Действие** — Добавить строки ошибок в словарь `USER_MESSAGES` в `src/claude_bot/errors.py` для случаев: уведомление не найдено, ошибка чтения `notify.json`, ошибка парсинга.
3. **Результат** — Пользователь получает понятное сообщение при сбое вместо технической трассировки стека.
4. **Зависимости** — Этап 1 (понимание структуры ошибок).
5. **Риски** — Минимальные.
6. **Без этого** — При ошибках чтения `notify.json` пользователь увидит сырое исключение или ничего.

### Этап 7: Команда /notify

1. **Проблема** — Пользователь не может посмотреть список своих уведомлений через бот напрямую.
2. **Действие** — Добавить обработчик команды `/notify` в `src/claude_bot/handlers/commands.py`: без аргументов — список активных уведомлений текущего проекта, с аргументом `all` — по всем проектам пользователя.
3. **Результат** — Пользователь в любой момент может запросить список уведомлений прямо в чате.
4. **Зависимости** — Этапы 1, 2, 5 (модели, сервис, константы).
5. **Риски** — При большом числе уведомлений сообщение может превысить лимит Telegram (4096 символов); нужна пагинация или обрезка через `send_long()`.
6. **Без этого** — Пользователь может управлять уведомлениями только через Claude в чате, без прямого просмотра.

### Этап 8: Интеграция в точку входа

1. **Проблема** — `NotificationManager` создан, но не запущен: бот стартует без фонового цикла уведомлений.
2. **Действие** — В `src/claude_bot/__main__.py` создать экземпляр `NotificationManager`, вызвать `init()` перед `start_polling()`, зарегистрировать `/notify` в списке команд бота через `bot.set_my_commands()`, и вызвать `close()` при завершении.
3. **Результат** — Фоновый цикл уведомлений запускается вместе с ботом и корректно завершается при остановке.
4. **Зависимости** — Все предыдущие этапы.
5. **Риски** — Если `init()` вызывается до инициализации `storage`, список проектов будет пустым в первый цикл — некритично, следующий цикл исправит.
6. **Без этого** — Весь модуль уведомлений создан, но мёртв: ни одно уведомление не будет отправлено.

---

## Полная версия плана

## Этап 1: Pydantic-модели уведомлений

**Файл:** `src/claude_bot/models/notification.py` (новый; создать директорию `models/__init__.py`)

**Модели:**

```python
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime
import uuid

RepeatType = Literal["daily", "weekly", "monthly"] | None
WeekDay = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
Category = Literal["medication", "event", "todo", "reminder"]
NotificationStatus = Literal["active", "paused", "completed"]

class RepeatRule(BaseModel):
    type: RepeatType = None
    days: list[WeekDay] = []        # для weekly
    time: str = "09:00"             # "HH:MM"
    day: int | None = None          # для monthly (1-31)

class Notification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    category: Category = "reminder"
    datetime: datetime                    # первое/единственное срабатывание
    remind_before: list[int] = [0]        # минут до: [0] = в момент
    repeat: RepeatRule | None = None
    recipients: list[int]                 # Telegram user_id
    status: NotificationStatus = "active"
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: int

class NotifyFile(BaseModel):
    notifications: list[Notification] = []
```

---

## Этап 2: NotificationService — операции с notify.json

**Файл:** `src/claude_bot/services/notifier.py` (новый)

**Путь к файлу:** `{projects_dir}/{project_name}/notify.json`

**Методы класса `NotificationService`:**

```python
class NotificationService:
    FILENAME = "notify.json"

    def load(self, project_path: Path) -> NotifyFile
    def save(self, project_path: Path, data: NotifyFile) -> None
    def add(self, project_path: Path, notification: Notification) -> None
    def remove(self, project_path: Path, notification_id: str) -> None
    def update(self, project_path: Path, notification_id: str, updates: dict) -> None
    def get_active(self, project_path: Path) -> list[Notification]
    def is_due(self, notification: Notification, now: datetime) -> bool
    def next_occurrence(self, notification: Notification) -> datetime | None
    def mark_sent(self, project_path: Path, notification: Notification) -> None
```

**Логика `is_due()`:**
- Если `status != "active"` — `False`
- Если `repeat` — проверить совпадение текущего дня/времени по типу повтора с допуском ±30 сек (половина минуты, чтобы не пропустить на границе интервала)
- Если `repeat is None` — проверить `notification.datetime <= now`

**Логика `next_occurrence()`:**
- `daily`: следующий день в `repeat.time`
- `weekly`: следующий подходящий день недели в `repeat.time`
- `monthly`: следующий месяц в `repeat.day` + `repeat.time`

**Логика `mark_sent()`:**
- Для одноразовых (`repeat is None`) — устанавливает `status = "completed"`
- Для повторяющихся — обновляет `notification.datetime = next_occurrence(notification)`

---

## Этап 3: NotificationManager — фоновый цикл и отправка

**Файл:** `src/claude_bot/services/notifier.py` (добавить класс)

```python
class NotificationManager:
    def __init__(self, bot: Bot, settings: Settings, storage: SessionStorage):
        self.bot = bot
        self.settings = settings
        self.storage = storage
        self.service = NotificationService()
        self._task: asyncio.Task | None = None

    async def init(self) -> None:
        self._task = asyncio.create_task(self._scan_loop())

    async def close(self) -> None:
        if self._task:
            self._task.cancel()

    async def _scan_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.notify_scan_interval)
            await self._scan_all()

    async def _scan_all(self) -> None:
        # Обходим всех пользователей через storage
        # Для каждого — все проекты через storage.list_projects()
        # Для каждого проекта — _check_and_send()
        pass

    async def _check_and_send(self, uid: int, project_path: Path) -> None:
        # Загружаем notify.json, фильтруем is_due(), отправляем
        pass

    async def _send(self, uid: int, notification: Notification) -> None:
        # bot.send_message() с обработкой TelegramForbiddenError
        pass

    def _format_notification(self, notification: Notification) -> str:
        # HTML: эмодзи + title + description
        pass
```

**Группировка:** уведомления одному пользователю из одного цикла объединяются в одно сообщение, если их больше одного.

**Обработка ошибок:**
- `TelegramForbiddenError` (бот заблокирован) — логируем, пропускаем пользователя
- `Exception` при чтении `notify.json` — логируем с `project_path`, продолжаем

---

## Этап 4: Конфигурация NOTIFY_SCAN_INTERVAL

**Файл:** `src/claude_bot/config.py`

Добавить в класс `Settings`:

```python
notify_scan_interval: int = 60  # секунды между сканированиями notify.json
```

**Файл:** `.env.example`

Добавить секцию:

```dotenv
# Уведомления
NOTIFY_SCAN_INTERVAL=60
```

---

## Этап 5: Константы категорий и эмодзи

**Файл:** `src/claude_bot/constants.py`

Добавить:

```python
# Уведомления
EMOJI_MEDICATION = "💊"
EMOJI_EVENT = "🎭"
EMOJI_TODO = "✅"
EMOJI_REMINDER = "🔔"
EMOJI_NOTIFY = "🔔"

CATEGORY_EMOJI: dict[str, str] = {
    "medication": EMOJI_MEDICATION,
    "event": EMOJI_EVENT,
    "todo": EMOJI_TODO,
    "reminder": EMOJI_REMINDER,
}
```

---

## Этап 6: Обработка ошибок уведомлений

**Файл:** `src/claude_bot/errors.py`

Добавить в `USER_MESSAGES`:

```python
"notify_not_found": "Уведомление не найдено.",
"notify_read_error": "Не удалось прочитать файл уведомлений.",
"notify_parse_error": "Файл уведомлений повреждён.",
"notify_empty": "Уведомлений нет.",
```

---

## Этап 7: Команда /notify

**Файл:** `src/claude_bot/handlers/commands.py`

**Обработчик:**

```python
@router.message(Command("notify"))
async def cmd_notify(message: Message, settings: Settings, storage: SessionStorage, ...) -> None:
    arg = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    service = NotificationService()

    if arg == "all":
        # Собрать уведомления по всем проектам пользователя
        projects = storage.list_projects(settings.projects_dir)
        ...
    else:
        # Текущий проект пользователя
        project_path = ...
        notifications = service.get_active(project_path)

    if not notifications:
        await message.answer(USER_MESSAGES["notify_empty"])
        return

    text = _format_notify_list(notifications)
    await send_long(message, text)
```

**Формат списка уведомлений (HTML):**

```
🔔 <b>Активные уведомления</b>

💊 <b>Приём Индапамида</b>
Ежедневно в 06:00 (пн–пт)
Индапамид Ретард 1.5 мг — 1 таблетка утром натощак.

✅ <b>Купить продукты</b>
Один раз — 17 марта 2026, 18:00
```

Регистрация команды в `__main__.py`:
```python
BotCommand(command="notify", description="Список уведомлений")
```

---

## Этап 8: Интеграция в точку входа

**Файл:** `src/claude_bot/__main__.py`

Последовательность инициализации в функции `_run()`:

```python
# Создать менеджер (storage уже инициализирован)
notify_manager = NotificationManager(bot=bot, settings=settings, storage=storage)

# Запустить фоновый цикл
await notify_manager.init()

# Добавить /notify в список команд бота
await bot.set_my_commands([
    ...,
    BotCommand(command="notify", description="Список уведомлений"),
])

try:
    await dp.start_polling(bot)
finally:
    await notify_manager.close()
```

**Порядок завершения:**
1. `dp.stop_polling()`
2. `notify_manager.close()` — отменяет asyncio-задачу
3. `bot.session.close()`
