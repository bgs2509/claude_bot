"""Каталог user-friendly сообщений об ошибках (SSOT)."""

USER_MESSAGES: dict[str, str] = {
    "claude_timeout": (
        "⏰ Claude не ответил за отведённое время.\n"
        "Попробуй:\n"
        "• Сократить запрос\n"
        "• Повторить через минуту\n"
        "• /cancel — отменить текущий запрос"
    ),
    "claude_error": (
        "Ошибка при обработке запроса.\n"
        "Попробуй:\n"
        "• Повторить запрос\n"
        "• /new — начать новую сессию\n"
        "• Если повторяется — обратись к администратору"
    ),
    "voice_not_recognized": (
        "Не удалось распознать голос.\n"
        "Попробуй:\n"
        "• Говорить чётче и ближе к микрофону\n"
        "• Отправить текстом"
    ),
    "file_too_large": (
        "Файл слишком большой (макс {limit_mb}MB).\n"
        "Попробуй отправить файл меньшего размера\n"
        "или скопировать нужный фрагмент текстом."
    ),
    "file_read_error": (
        "Не удалось прочитать файл.\n"
        "Поддерживаются текстовые файлы (UTF-8).\n"
        "Попробуй отправить содержимое текстом."
    ),
    "file_collision": "Файл `{filename}` уже существует в проекте.\nЧто сделать?",
    "no_active_project": (
        "Нет активного проекта.\n"
        "Используй /status для выбора или создания проекта."
    ),
    "notify_empty": "Активных уведомлений нет.",
    "notify_not_found": "Уведомление не найдено.",
    "notify_read_error": "Не удалось прочитать файл уведомлений.",
    "notify_parse_error": "Файл уведомлений повреждён.",
    "notify_write_error": "Не удалось сохранить уведомления.",
    "plan_empty": "На этот день план пуст.",
    "planner_read_error": "Не удалось прочитать план.",
    "planner_parse_error": "Файл плана повреждён.",
    "planner_write_error": "Не удалось сохранить план.",
    "planner_item_not_found": "Задача не найдена.",
    "unexpected_error": (
        "Произошла непредвиденная ошибка.\n"
        "Попробуй:\n"
        "• Повторить запрос\n"
        "• /new — начать новую сессию\n"
        "• Если повторяется — обратись к администратору"
    ),
}


def get_user_message(key: str, **kwargs: str | int) -> str:
    """Получить user-friendly сообщение. Поддерживает шаблоны: {param}."""
    template = USER_MESSAGES.get(key, USER_MESSAGES["unexpected_error"])
    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError:
            return template
    return template


class AppError(Exception):
    """Базовое исключение приложения."""

    def __init__(self, message: str, user_message_key: str = "unexpected_error") -> None:
        super().__init__(message)
        self.user_message_key = user_message_key


class DomainError(AppError):
    """Ошибка бизнес-логики (ожидаемая, не требует stack trace)."""


class InfrastructureError(AppError):
    """Ошибка инфраструктуры (внешние сервисы, ФС, CLI)."""
