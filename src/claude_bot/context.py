"""Контекст запроса через contextvars (request_id, user_id, observability)."""

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="---")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="---")

# Observability: статус и саммари результата обработки
obs_status_var: contextvars.ContextVar[str] = contextvars.ContextVar("obs_status", default="ok")
obs_output_var: contextvars.ContextVar[str] = contextvars.ContextVar("obs_output", default="")
