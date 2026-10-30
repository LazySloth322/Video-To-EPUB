"""Image comparison and slide-change detection primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image

from .errors import ProcessingError


@dataclass(frozen=True)
class Screenshot:
    path: Path
    timestamp: float
    filename: str
    index: int


@dataclass
class DetectorDecision:
    save: bool
    index: int = 0
    timestamp: float = 0.0
    reason: str = ""


def resize_grayscale(
    image: Image.Image,
    resize_width: int,
    target_size: Optional[Tuple[int, int]] = None,
) -> Tuple[np.ndarray, Tuple[int, int]]:
    """
    Convert an RGB image to grayscale and resize it to a stable target size.

    target_size is (width, height). If None, height is derived from the first image.
    """
    width, height = image.size
    if width <= 0 or height <= 0:
        raise ProcessingError("Cannot resize an image with zero width or height.")

    if target_size is None:
        target_height = max(1, int(round(height * resize_width / width)))
        target_size = (resize_width, target_height)

    gray = image.convert("L")
    resized = gray.resize(target_size, Image.Resampling.BILINEAR)
    array = np.asarray(resized, dtype=np.uint8)
    return array, target_size


def compute_change_fraction(
    prev: np.ndarray,
    curr: np.ndarray,
    pixel_diff_threshold: int,
) -> float:
    """
    Return the fraction of pixels whose absolute grayscale difference exceeds
    pixel_diff_threshold.
    """
    if prev.size == 0:
        return 0.0

    if prev.shape != curr.shape:
        # Safety fallback. Normal operation keeps target_size stable.
        curr_image = Image.fromarray(curr).resize(
            (prev.shape[1], prev.shape[0]),
            Image.Resampling.BILINEAR,
        )
        curr = np.asarray(curr_image, dtype=np.uint8)

    diff = np.abs(curr.astype(np.int16) - prev.astype(np.int16))
    changed = np.count_nonzero(diff > pixel_diff_threshold)
    return float(changed) / float(diff.size)


class SlideChangeDetector:
    """
    Detect persistent visual changes relative to the last accepted reference frame.

    This intentionally compares against the reference slide rather than only the
    immediately previous sampled frame. That makes fades/persistent changes easier
    to detect, but animated backgrounds or camera motion can still cause false
    positives. Adjust thresholds, interval, confirmation, and debounce as needed.
    """

    def __init__(
        self,
        pixel_diff_threshold: int,
        change_threshold: float,
        confirm_samples: int = 1,
        debounce_seconds: float = 0.0,
        save_first: bool = True,
    ) -> None:
        self._pixel_diff_threshold = pixel_diff_threshold
        self._change_threshold = change_threshold
        self._confirm_samples = max(1, confirm_samples)
        self._debounce_seconds = max(0.0, debounce_seconds)
        self._save_first = save_first

        self._reference_gray: Optional[np.ndarray] = None
        self._pending_count = 0
        self._last_saved_time: Optional[float] = None
        self._index = 0

    def process(self, gray: np.ndarray, timestamp: float) -> DetectorDecision:
        if self._reference_gray is None:
            self._reference_gray = gray
            if self._save_first:
                self._index += 1
                self._last_saved_time = timestamp
                return DetectorDecision(
                    save=True,
                    index=self._index,
                    timestamp=timestamp,
                    reason="first_frame",
                )
            return DetectorDecision(save=False, reason="first_frame_reference")

        fraction = compute_change_fraction(
            self._reference_gray,
            gray,
            self._pixel_diff_threshold,
        )

        if fraction >= self._change_threshold:
            self._pending_count += 1
        else:
            self._pending_count = 0

        if self._pending_count >= self._confirm_samples:
            if (
                self._debounce_seconds > 0
                and self._last_saved_time is not None
                and timestamp - self._last_saved_time < self._debounce_seconds
            ):
                # Keep the reference unchanged so a persistent change can still be
                # accepted after the debounce window expires.
                self._pending_count = self._confirm_samples
                return DetectorDecision(save=False, reason="debounced")

            self._index += 1
            self._last_saved_time = timestamp
            self._reference_gray = gray
            self._pending_count = 0
            return DetectorDecision(
                save=True,
                index=self._index,
                timestamp=timestamp,
                reason="change",
            )

        return DetectorDecision(save=False, reason=f"fraction={fraction:.4f}")