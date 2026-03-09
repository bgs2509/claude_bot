"""Общие файловые утилиты для AI-провайдеров."""

from pathlib import Path

MEDIA_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".csv",
    ".xlsx",
    ".mp3",
    ".mp4",
}


def snapshot_media(cwd: Path) -> set[Path]:
    """Снимок медиа-файлов в корне директории (без рекурсии)."""

    return {
        path for path in cwd.iterdir()
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    }


def prepare_output_dir(cwd: Path) -> set[Path]:
    """Подготовить директорию _output/ и вернуть снимок медиа до запуска."""

    cwd.mkdir(parents=True, exist_ok=True)
    output_dir = cwd / "_output"
    output_dir.mkdir(exist_ok=True)

    for old_file in output_dir.iterdir():
        if old_file.is_file():
            old_file.unlink()

    return snapshot_media(cwd)


def collect_output_files(cwd: Path, before: set[Path]) -> list[Path]:
    """Собрать файлы из _output/ и новые медиа из корня."""

    files: list[Path] = []
    output_dir = cwd / "_output"
    if output_dir.exists():
        files.extend(path for path in output_dir.iterdir() if path.is_file())

    after = snapshot_media(cwd)
    files.extend(after - before)
    return files
