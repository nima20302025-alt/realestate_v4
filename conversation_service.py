# -*- coding: utf-8 -*-
"""High-level chat entry point shared by the CLI and the web UI."""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional, Tuple

import repositories as repo
from agent import ToolTraceItem, TurnResult

logger = logging.getLogger(__name__)

FALLBACK_RESPONSE = (
    "Sorry, something went wrong on my end while processing that. "
    "Could you try again in a moment?"
)

# Last tool trace per customer (for Gradio activity panel)
_LAST_TRACE: dict[int, List[ToolTraceItem]] = {}


def get_last_trace(customer_id: Optional[int]) -> List[ToolTraceItem]:
    if not customer_id:
        return []
    return list(_LAST_TRACE.get(customer_id) or [])


def chat_with_trace(customer_id: int, user_message: str) -> Tuple[str, List[ToolTraceItem]]:
    """Run a turn and return (reply, tool_trace)."""
    repo.save_message(customer_id, "user", user_message)
    history = repo.load_history(customer_id)
    prior = history[:-1] if history else []

    try:
        from agent import run_turn

        result: TurnResult = run_turn(customer_id, user_message, history=prior)
        response = result.response or "I'm sorry, I couldn't process that. Could you rephrase?"
        trace = result.tool_trace or []
    except Exception as exc:
        logger.exception("Agent turn failed for customer_id=%s", customer_id)
        response = FALLBACK_RESPONSE
        if os.environ.get("SHOW_ERRORS", "1") != "0":
            response += f"\n\n[debug] {type(exc).__name__}: {str(exc)[:300]}"
        trace = []

    _LAST_TRACE[customer_id] = trace
    repo.save_message(customer_id, "assistant", response)
    return response, trace


def chat(customer_id: int, user_message: str, graph: Any = None) -> str:
    """Persist + reply. `graph` ignored (legacy kwarg)."""
    response, _ = chat_with_trace(customer_id, user_message)
    return response
