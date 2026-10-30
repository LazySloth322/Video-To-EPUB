from pathlib import Path

from video_to_epub.events import build_events
from video_to_epub.images import Screenshot
from video_to_epub.transcription import Segment


def test_segment_preferred_over_image_at_same_timestamp():
    segment = Segment(start=10.0, end=12.0, text="hello")
    screenshot = Screenshot(
        path=Path("slide.jpg"),
        timestamp=10.0,
        filename="slide.jpg",
        index=1,
    )

    events = build_events([segment], [screenshot])

    assert events[0].kind == "segment"
    assert events[1].kind == "image"


def test_image_inside_segment_is_placed_after_segment():
    segment = Segment(start=10.0, end=20.0, text="hello")
    screenshot = Screenshot(
        path=Path("slide.jpg"),
        timestamp=15.0,
        filename="slide.jpg",
        index=1,
    )

    events = build_events([segment], [screenshot])

    assert events[0].kind == "segment"
    assert events[1].kind == "image"


def test_events_are_sorted_chronologically():
    segments = [
        Segment(start=30.0, end=35.0, text="third"),
        Segment(start=10.0, end=15.0, text="first"),
        Segment(start=20.0, end=25.0, text="second"),
    ]

    screenshots = [
        Screenshot(Path("b.jpg"), 25.0, "b.jpg", 2),
        Screenshot(Path("a.jpg"), 12.0, "a.jpg", 1),
    ]

    events = build_events(segments, screenshots)
    times = [event.time for event in events]

    assert times == sorted(times)
    assert [event.kind for event in events] == [
        "segment",
        "image",
        "segment",
        "image",
        "segment",
    ]