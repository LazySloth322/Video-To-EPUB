"""Whisper transcription using the original openai-whisper Python API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .errors import DependencyError, ProcessingError
from .utils import eprint


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


def transcribe_video(
    video_path: Path,
    language: Optional[str] = None,
    device: Optional[str] = None,
    quiet: bool = False,
) -> Tuple[List[Segment], Optional[str]]:
    """
    Transcribe video audio with openai-whisper turbo.

    Returns transcript segments and detected language code, if available.
    """
    try:
        import whisper
    except ImportError as exc:
        raise DependencyError(
            "openai-whisper is not installed. Install it with: "
            "python -m pip install -r requirements.txt"
        ) from exc

    try:
        models = whisper.available_models()
    except Exception:
        models = []

    if "turbo" not in models:
        raise DependencyError(
            "The installed openai-whisper package does not expose the 'turbo' model. "
            "Upgrade with: python -m pip install --upgrade openai-whisper."
        )

    if not quiet:
        eprint(f"Loading Whisper turbo model (device={device or 'auto'})...")

    try:
        model = whisper.load_model("turbo", device=device)
    except Exception as exc:
        raise ProcessingError(f"Failed to load Whisper turbo model: {exc}") from exc

    if not quiet:
        eprint("Transcribing audio with Whisper turbo...")

    try:
        # task="transcribe" explicitly avoids translation.
        result = model.transcribe(
            str(video_path),
            language=language,
            task="transcribe",
            verbose=False,
        )
    except Exception as exc:
        raise ProcessingError(f"Whisper transcription failed: {exc}") from exc

    segments: List[Segment] = []

    for raw in result.get("segments", []):
        try:
            start = float(raw.get("start", 0.0))
            end = float(raw.get("end", start))
            text = str(raw.get("text", "")).strip()
        except (TypeError, ValueError):
            continue

        if not text:
            continue

        if start < 0 or start != start:  # NaN check
            start = 0.0
        if end < start or end != end:
            end = start

        segments.append(Segment(start=start, end=end, text=text))

    detected_language = result.get("language")
    if detected_language is not None:
        detected_language = str(detected_language)

    if not quiet:
        eprint(
            "Transcription complete: "
            f"{len(segments)} segments, language={detected_language or 'unknown'}"
        )

    return segments, detected_language