"""Контекст запроса через contextvars (request_id, user_id)."""

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="---")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id", default="---")
