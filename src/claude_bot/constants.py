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

# Тексты reply-кнопок
BUTTON_MORE = f"{EMOJI_MORE} Ещё"
BUTTON_HOME = f"{EMOJI_HOME} Общий"
BUTTON_CREATE_PROJECT = f"{EMOJI_CREATE} Проект"
