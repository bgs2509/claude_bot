"""Сервис распознавания текста на изображениях (OCR)."""

import logging
import os
import subprocess

from claude_bot.state import AppState

log = logging.getLogger("claude-bot.ocr")


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
        log.warning("OCR: tesseract недоступен")
        return "(tesseract не установлен — OCR недоступен)"

    try:
        from PIL import Image
        import pytesseract

        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang="rus+eng")
        if text.strip():
            log.info("OCR: %d символов из %s", len(text.strip()), file_path)
            return text.strip()
        log.info("OCR: текст не распознан в %s", file_path)
        return "(текст на фото не распознан)"
    except Exception as e:
        return f"(ошибка OCR: {e})"
    finally:
        if delete:
            try:
                os.unlink(file_path)
            except OSError:
                pass
