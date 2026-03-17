"""Emoji и текстовые константы для UI (единый источник правды)."""

# Emoji
EMOJI_ACTIVE = "▶️"
EMOJI_INACTIVE = "📁"
EMOJI_SESSION = "💬"
EMOJI_HOME = "🏠"
EMOJI_CREATE = "➕"
EMOJI_MORE = "📋"
EMOJI_REACTION = "👌"

# Уведомления
EMOJI_MEDICATION = "💊"
EMOJI_EVENT = "🎭"
EMOJI_TODO = "✅"
EMOJI_REMINDER = "🔔"

CATEGORY_EMOJI: dict[str, str] = {
    "medication": EMOJI_MEDICATION,
    "event": EMOJI_EVENT,
    "todo": EMOJI_TODO,
    "reminder": EMOJI_REMINDER,
}

DAY_NAMES_RU: dict[str, str] = {
    "mon": "пн", "tue": "вт", "wed": "ср", "thu": "чт",
    "fri": "пт", "sat": "сб", "sun": "вс",
}

NOTIFY_DESC_PREVIEW_LEN = 100

# Планировщик — статусы
EMOJI_PLAN_PENDING = "⬜"
EMOJI_PLAN_IN_PROGRESS = "🔄"
EMOJI_PLAN_DONE = "✅"
EMOJI_PLAN_SKIPPED = "⏭"
EMOJI_PLAN_CANCELLED = "❌"
EMOJI_PLAN_CARRIED = "📦"

PLAN_STATUS_EMOJI: dict[str, str] = {
    "pending": EMOJI_PLAN_PENDING,
    "in_progress": EMOJI_PLAN_IN_PROGRESS,
    "done": EMOJI_PLAN_DONE,
    "skipped": EMOJI_PLAN_SKIPPED,
    "cancelled": EMOJI_PLAN_CANCELLED,
}

# Планировщик — приоритеты
PRIORITY_ORDER: dict[str, int] = {
    "high": 0,
    "medium": 1,
    "low": 2,
    "none": 3,
}

PRIORITY_EMOJI: dict[str, str] = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🔵",
    "none": "",
}

# Callback-префиксы для /plan
PLAN_CB_DAY = "plan:d:"       # plan:d:2026-03-17
PLAN_CB_WEEK = "plan:week"
PLAN_CB_FILTER = "plan:f:"    # plan:f:tasks

PLAN_DESC_PREVIEW_LEN = 100

# Тексты reply-кнопок
BUTTON_MORE = f"{EMOJI_MORE} Ещё"
BUTTON_HOME = f"{EMOJI_HOME} Общий"
BUTTON_CREATE_PROJECT = f"{EMOJI_CREATE} Проект"
