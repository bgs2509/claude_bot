"""Сервисы распознавания и синтеза речи."""

import asyncio
import logging
import os
import tempfile

from ai_steward.config import Settings
from ai_steward.state import AppState

log = logging.getLogger("ai-steward.speech")


def get_whisper_model(settings: Settings, state: AppState):
    """Ленивая загрузка Whisper модели."""
    if state.whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            state.whisper_model = WhisperModel(
                settings.whisper_model,
                device=settings.whisper_device,
                compute_type="int8",
            )
            log.info("Whisper модель '%s' загружена", settings.whisper_model)
        except ImportError as e:
            log.warning("faster-whisper не загружен, STT недоступен: %s", e)
            return None
    return state.whisper_model


async def transcribe_voice(
    file_path: str, settings: Settings, state: AppState
) -> str | None:
    """Транскрибировать голосовое сообщение в текст."""
    model = get_whisper_model(settings, state)
    if model is None:
        log.warning("STT: модель Whisper недоступна, пропуск транскрибации")
        return None

    # Конвертировать ogg → wav через ffmpeg
    wav_path = file_path.replace(".ogg", ".wav")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", file_path, "-ar", "16000", "-ac", "1", wav_path,
        "-y", "-loglevel", "error",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_data = await proc.communicate()

    if proc.returncode != 0:
        log.error(
            "STT: ffmpeg конвертация провалилась (код %d): %s",
            proc.returncode, stderr_data.decode().strip(),
        )
        return None

    # Транскрибация
    try:
        segments, _ = model.transcribe(wav_path, language="ru")
        text = " ".join(s.text for s in segments).strip()
    except Exception as e:
        log.error("STT: ошибка транскрибации Whisper: %s", e)
        return None

    if not text:
        log.info("STT: Whisper вернул пустой результат (тишина/шум?)")

    # Удалить временные файлы
    for p in (file_path, wav_path):
        try:
            os.unlink(p)
        except OSError:
            pass

    return text


async def synthesize_speech(text: str, settings: Settings) -> str | None:
    """Синтезировать речь из текста через edge-tts."""
    try:
        import edge_tts
    except ImportError:
        log.warning("TTS: edge_tts не установлен")
        return None

    # Ограничить длину текста для TTS (edge-tts имеет лимит)
    if len(text) > 3000:
        text = text[:3000] + "..."

    output_path = tempfile.mktemp(suffix=".mp3")
    communicate = edge_tts.Communicate(text, settings.tts_voice)
    await communicate.save(output_path)
    log.info("TTS: %d символов синтезировано", len(text))
    return output_path
