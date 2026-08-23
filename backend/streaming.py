"""
backend/streaming.py

Runs a blocking agent function in a background thread and relays its
progress to the client as Server-Sent Events (SSE). If the client aborts
the connection (closes the fetch / clicks the Abort button), Starlette
raises GeneratorExit at our current yield -- we catch that and set the
threading.Event the agent loop checks between steps, so work actually
stops rather than just being ignored client-side.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Callable, Iterator

_SENTINEL = object()


import math

def _sanitize_for_json(obj):
    """Recursively replace NaN/Infinity (which Python's json module allows
    but the JSON spec and browsers do not) with None, so every SSE payload
    is guaranteed to be valid, parseable JSON on the client side."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    return obj


def sse(event_type: str, data: dict) -> str:
    clean = _sanitize_for_json(data)
    return f"event: {event_type}\ndata: {json.dumps(clean, default=str)}\n\n"


def stream_run(run_fn: Callable[[threading.Event, "queue.Queue"], None]) -> Iterator[str]:
    """
    run_fn(cancel_event, q) does the actual work in a background thread,
    pushing sse(...) strings onto q as progress happens, and MUST push
    _SENTINEL onto q exactly once when finished (success, error, or
    cancellation) -- wrap its body in try/finally to guarantee this.
    """
    q: "queue.Queue" = queue.Queue()
    cancel_event = threading.Event()

    thread = threading.Thread(target=run_fn, args=(cancel_event, q), daemon=True)
    thread.start()

    try:
        while True:
            item = q.get()
            if item is _SENTINEL:
                break
            yield item
    except GeneratorExit:
        cancel_event.set()
        raise
    finally:
        cancel_event.set()