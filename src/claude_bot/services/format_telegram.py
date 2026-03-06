"""Конвертация Markdown в Telegram HTML."""

import html
import re


def markdown_to_telegram_html(text: str) -> str:
    """Конвертация Markdown от Claude в HTML для Telegram."""
    # Сохраняем блоки кода, заменяя на плейсхолдеры
    code_blocks: list[tuple[str, str]] = []

    def _save_code_block(match: re.Match) -> str:
        lang = match.group(1) or ""
        code = match.group(2)
        idx = len(code_blocks)
        code_blocks.append((lang, code))
        return f"\x00CODEBLOCK{idx}\x00"

    text = re.sub(r"```(\w*)\n?(.*?)```", _save_code_block, text, flags=re.DOTALL)

    # Сохраняем инлайн-код
    inline_codes: list[str] = []

    def _save_inline_code(match: re.Match) -> str:
        code = match.group(1)
        idx = len(inline_codes)
        inline_codes.append(code)
        return f"\x00INLINE{idx}\x00"

    text = re.sub(r"`([^`\n]+)`", _save_inline_code, text)

    # Экранируем HTML-сущности в остальном тексте
    text = html.escape(text)

    # Заголовки → жирный текст
    text = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # **жирный**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # *курсив* (не внутри **)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    # Восстановить блоки кода
    for idx, (lang, code) in enumerate(code_blocks):
        escaped = html.escape(code.strip())
        if lang:
            replacement = f'<pre><code class="language-{html.escape(lang)}">{escaped}</code></pre>'
        else:
            replacement = f"<pre>{escaped}</pre>"
        text = text.replace(f"\x00CODEBLOCK{idx}\x00", replacement)

    # Восстановить инлайн-код
    for idx, code in enumerate(inline_codes):
        text = text.replace(f"\x00INLINE{idx}\x00", f"<code>{html.escape(code)}</code>")

    return text
