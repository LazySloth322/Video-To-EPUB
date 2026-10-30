"""Sequential video frame sampling and screenshot extraction using PyAV."""

from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple

import av
from PIL import Image

from .errors import ProcessingError, VideoToEpubError
from .images import Screenshot, SlideChangeDetector, resize_grayscale
from .utils import eprint, format_filename_timestamp


def extract_screenshots(
    video_path: Path,
    output_dir: Path,
    interval_seconds: float,
    resize_width: int,
    pixel_diff_threshold: int,
    change_threshold: float,
    confirm_samples: int,
    debounce_seconds: float,
    screenshot_width: int,
    jpeg_quality: int,
    save_first: bool = True,
    quiet: bool = False,
) -> List[Screenshot]:
    """
    Decode the video sequentially, sample frames at interval_seconds, detect changes,
    and save screenshots into output_dir.

    This does not repeatedly seek from the start of the file. It does decode through
    the video stream, which is robust for variable-frame-rate material but can be
    slower than keyframe-only heuristics.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    detector = SlideChangeDetector(
        pixel_diff_threshold=pixel_diff_threshold,
        change_threshold=change_threshold,
        confirm_samples=confirm_samples,
        debounce_seconds=debounce_seconds,
        save_first=save_first,
    )

    screenshots: List[Screenshot] = []
    next_sample_time = 0.0
    timeline_offset: Optional[float] = None
    target_size: Optional[Tuple[int, int]] = None
    frame_index = 0
    eps = min(1e-3, interval_seconds / 10.0)

    try:
        with av.open(str(video_path)) as container:
            if not container.streams.video:
                if not quiet:
                    eprint(
                        "Warning: no video stream found; continuing without screenshots."
                    )
                return []

            stream = container.streams.video[0]

            # Helpful on multi-core machines, but not essential.
            try:
                stream.codec_context.thread_type = "AUTO"
            except Exception:
                pass

            if not quiet:
                eprint("Sampling video frames and detecting slide changes...")

            for frame in container.decode(stream):
                raw_time = frame.time

                if raw_time is None:
                    if frame.pts is not None and stream.time_base is not None:
                        raw_time = float(frame.pts * stream.time_base)
                    else:
                        fps = float(stream.average_rate) if stream.average_rate else 30.0
                        raw_time = frame_index / fps

                if timeline_offset is None:
                    timeline_offset = float(raw_time)

                timestamp = float(raw_time) - timeline_offset
                if timestamp < 0 or timestamp != timestamp:
                    timestamp = 0.0

                frame_index += 1

                if not math.isfinite(timestamp):
                    continue

                if timestamp + eps < next_sample_time:
                    continue

                try:
                    pil_image = frame.to_image()
                except Exception as exc:
                    raise ProcessingError(
                        f"Failed to convert decoded video frame to image at "
                        f"timestamp {timestamp:.3f}s: {exc}"
                    ) from exc

                gray, target_size = resize_grayscale(
                    pil_image,
                    resize_width=resize_width,
                    target_size=target_size,
                )

                decision = detector.process(gray, timestamp)

                if decision.save:
                    save_image = pil_image

                    if (
                        screenshot_width
                        and screenshot_width > 0
                        and pil_image.width > screenshot_width
                    ):
                        new_height = max(
                            1,
                            int(round(pil_image.height * screenshot_width / pil_image.width)),
                        )
                        save_image = pil_image.resize(
                            (screenshot_width, new_height),
                            Image.Resampling.LANCZOS,
                        )

                    filename = (
                        f"slide_{decision.index:04d}_"
                        f"{format_filename_timestamp(timestamp)}.jpg"
                    )
                    path = output_dir / filename

                    try:
                        save_image.convert("RGB").save(
                            path,
                            format="JPEG",
                            quality=jpeg_quality,
                            optimize=True,
                        )
                    except Exception as exc:
                        raise ProcessingError(
                            f"Failed to save screenshot {filename}: {exc}"
                        ) from exc

                    screenshots.append(
                        Screenshot(
                            path=path,
                            timestamp=timestamp,
                            filename=filename,
                            index=decision.index,
                        )
                    )

                    if not quiet:
                        eprint(
                            f"  saved screenshot {filename} at {timestamp:.3f}s"
                        )

                next_sample_time = timestamp + interval_seconds

    except VideoToEpubError:
        raise
    except Exception as exc:
        raise ProcessingError(f"Failed to analyze video frames: {exc}") from exc

    if not quiet:
        eprint(f"Frame analysis complete: {len(screenshots)} screenshots")

    return screenshots