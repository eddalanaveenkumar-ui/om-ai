"""Per-workflow UI telemetry, propagated by asyncio.to_thread to browser workers."""
from contextvars import ContextVar
import re

activity_sink = ContextVar('activity_sink', default=None)


def activity(event, **details):
    sink = activity_sink.get()
    if sink is not None:
        sink(dict(event=event, **details))


def requests_input(task):
    # A browser classification alone must not reduce an explicit input sequence
    # to opening a URL. Ignore hostnames/paths when looking for action verbs.
    task = re.sub(r'https?://\S+', '', task, flags=re.I)
    return bool(re.search(r'\b(?:click|double[- ]?click|right[- ]?click|scroll|type|paste|press|hotkey)\b', task, re.I))
