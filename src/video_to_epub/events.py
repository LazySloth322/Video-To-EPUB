"""Chronological merging of transcript segments and screenshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .images import Screenshot
from .transcription import Segment


@dataclass(frozen=True)
class Event:
    time: float
    priority: int
    kind: str  # "segment" or "image"
    segment: Optional[Segment] = None
    screenshot: Optional[Screenshot] = None


def _safe_time(value: float) -> float:
    try:
        t = float(value)
    except (TypeError, ValueError):
        return 0.0
    if t != t or t < 0:  # NaN or negative
        return 0.0
    return t


def build_events(
    segments: List[Segment],
    screenshots: List[Screenshot],
) -> List[Event]:
    """
    Merge transcript segments and screenshots chronologically.

    Priority:
      0 = transcript segment
      1 = screenshot

    Therefore, if a screenshot timestamp equals a segment start timestamp, the
    segment is emitted before the screenshot.
    """
    events: List[Event] = []

    for segment in segments:
        events.append(
            Event(
                time=_safe_time(segment.start),
                priority=0,
                kind="segment",
                segment=segment,
                screenshot=None,
            )
        )

    for screenshot in screenshots:
        events.append(
            Event(
                time=_safe_time(screenshot.timestamp),
                priority=1,
                kind="image",
                segment=None,
                screenshot=screenshot,
            )
        )

    events.sort(key=lambda event: (event.time, event.priority))
    return events