"""Сервис распознавания текста на изображениях (OCR)."""

import logging
import os
import subprocess

from claude_bot.state import AppState

log = logging.getLogger("claude-bot")


def is_tesseract_available(state: AppState) -> bool:
    """Проверить доступность tesseract."""
    if state.tesseract_available is None:
        try:
            subprocess.run(
                ["tesseract", "--version"], capture_output=True, check=True
            )
            state.tesseract_available = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            state.tesseract_available = False
    return state.tesseract_available


async def ocr_image(file_path: str, state: AppState, *, delete: bool = True) -> str:
    """Извлечь текст из изображения через tesseract."""
    if not is_tesseract_available(state):
        return "(tesseract не установлен — OCR недоступен)"

    try:
        from PIL import Image
        import pytesseract

        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang="rus+eng")
        return text.strip() if text.strip() else "(текст на фото не распознан)"
    except Exception as e:
        return f"(ошибка OCR: {e})"
    finally:
        if delete:
            try:
                os.unlink(file_path)
            except OSError:
                pass
