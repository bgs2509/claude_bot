"""Сервис загрузки файлов в директорию проекта."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("ai-steward.services.upload")

# Расширения, которые точно текстовые
TEXT_EXTENSIONS: set[str] = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx",
    ".html", ".css", ".json", ".yaml", ".yml", ".toml",
    ".xml", ".csv", ".sql", ".sh", ".bash", ".zsh",
    ".c", ".cpp", ".h", ".hpp", ".java", ".go", ".rs",
    ".rb", ".php", ".ini", ".cfg", ".conf", ".log",
    ".gitignore", ".dockerignore", ".editorconfig",
}

# Имена файлов без расширения, которые текстовые
TEXT_FILENAMES: set[str] = {
    "makefile", "dockerfile", "vagrantfile", "gemfile",
    "rakefile", "procfile", "readme", "license", "changelog",
}


def is_binary_file(filename: str, mime_type: str | None = None) -> bool:
    """Определить, является ли файл бинарным. По умолчанию — binary (безопаснее)."""
    ext = Path(filename).suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return False
    if Path(filename).name.lower() in TEXT_FILENAMES:
        return False
    if mime_type and mime_type.startswith("text/"):
        return False
    return True


def generate_photo_filename() -> str:
    """Имя для фото: photo_YYYYMMDD_HHMMSS.jpg."""
    now = datetime.now(timezone.utc)
    return now.strftime("photo_%Y%m%d_%H%M%S.jpg")


def add_date_suffix(filename: str) -> str:
    """Добавить дату к имени: name_YYYYMMDD_HHMMSS.ext."""
    p = Path(filename)
    suffix = datetime.now(timezone.utc).strftime("_%Y%m%d_%H%M%S")
    return f"{p.stem}{suffix}{p.suffix}"


def check_collision(project_dir: Path, filename: str) -> bool:
    """Проверить, существует ли файл в проекте."""
    return (project_dir / filename).exists()


def save_uploaded_file(
    tmp_path: str,
    project_dir: Path,
    filename: str,
    *,
    overwrite: bool = True,
) -> Path:
    """Переместить файл из tmp в project_dir. При overwrite=False добавляет date suffix."""
    if not overwrite and (project_dir / filename).exists():
        filename = add_date_suffix(filename)
    target = project_dir / filename
    shutil.move(tmp_path, str(target))
    log.info("Файл сохранён: %s", target)
    return target


def read_text_content(file_path: Path, max_chars: int = 10_000) -> str | None:
    """Прочитать текст файла (до max_chars). None если не удалось."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return content.replace("\x00", "")[:max_chars]
    except Exception:
        log.warning("Не удалось прочитать как текст: %s", file_path)
        return None


def build_file_prompt(
    filename: str,
    file_path: Path,
    is_binary: bool,
    caption: str,
    ocr_text: str | None = None,
) -> str:
    """Промпт для Claude. Текстовый → содержимое. Бинарный → путь."""
    if not is_binary:
        content = read_text_content(file_path)
        if content:
            return (
                f"Пользователь загрузил файл `{filename}` в проект.\n"
                f"Путь: `{file_path.name}`\n\n"
                f"Содержимое:\n```\n{content}\n```\n\n"
                f"Задача: {caption}"
            )

    parts = [
        f"Пользователь загрузил файл `{filename}` в проект.",
        f"Путь: `{file_path.name}`",
    ]
    if ocr_text:
        parts.append(f"OCR текст:\n```\n{ocr_text}\n```")
    parts.append(f"Задача: {caption}")
    return "\n\n".join(parts)
