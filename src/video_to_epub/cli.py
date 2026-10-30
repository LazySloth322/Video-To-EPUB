"""Command-line interface."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional

from .config import parse_args
from .dependencies import check_dependencies
from .epub_builder import build_epub
from .errors import InputError, OutputError, VideoToEpubError
from .events import build_events
from .frames import extract_screenshots
from .transcription import transcribe_video
from .utils import eprint


def _derive_output_path(input_path: Path, output_arg: Optional[Path]) -> Path:
    if output_arg is None:
        return input_path.with_suffix(".epub")
    return output_arg.expanduser()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        input_path = args.input_video.expanduser()

        if not input_path.exists():
            raise InputError(f"Input video not found: {input_path}")
        if not input_path.is_file():
            raise InputError(f"Input path is not a file: {input_path}")
        if not os.access(input_path, os.R_OK):
            raise InputError(f"Input video is not readable: {input_path}")

        input_path = input_path.resolve()

        output_path = _derive_output_path(input_path, args.output)

        if output_path.exists() and output_path.is_dir():
            raise OutputError(f"Output path is a directory: {output_path}")

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OutputError(
                f"Cannot create output directory {output_path.parent}: {exc}"
            ) from exc

        if output_path.exists() and not args.overwrite:
            raise OutputError(
                f"Output file already exists: {output_path}. Use --overwrite to replace it."
            )

        if not args.quiet:
            eprint("Checking dependencies...")

        check_dependencies(quiet=args.quiet)

        temp_root: Optional[Path] = None
        if args.temp_dir is not None:
            temp_root = args.temp_dir.expanduser()
            try:
                temp_root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise InputError(f"Cannot create temp directory {temp_root}: {exc}") from exc

        temp_context = None
        if args.keep_temp:
            temp_dir = Path(
                tempfile.mkdtemp(
                    prefix="video_to_epub_",
                    dir=str(temp_root) if temp_root else None,
                )
            )
            if not args.quiet:
                eprint(f"Temporary files will be kept in: {temp_dir}")
        else:
            temp_context = tempfile.TemporaryDirectory(
                prefix="video_to_epub_",
                dir=str(temp_root) if temp_root else None,
            )
            temp_dir = Path(temp_context.name)

        try:
            screenshots_dir = temp_dir / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)

            segments, detected_language = transcribe_video(
                video_path=input_path,
                language=args.language,
                device=args.device,
                quiet=args.quiet,
            )

            screenshots = extract_screenshots(
                video_path=input_path,
                output_dir=screenshots_dir,
                interval_seconds=args.interval_seconds,
                resize_width=args.resize_width,
                pixel_diff_threshold=args.pixel_diff_threshold,
                change_threshold=args.change_threshold,
                confirm_samples=args.confirm_samples,
                debounce_seconds=args.debounce_seconds,
                screenshot_width=args.screenshot_width,
                jpeg_quality=args.jpeg_quality,
                save_first=True,
                quiet=args.quiet,
            )

            events = build_events(segments, screenshots)
            title = args.title if args.title is not None else input_path.stem
            epub_language = detected_language or args.language

            temp_output = temp_dir / "book.epub"

            build_epub(
                output_path=temp_output,
                events=events,
                title=title,
                language=epub_language,
                author=args.author,
                input_path=input_path,
                quiet=args.quiet,
                plain_text=args.plain_text,
            )

            if output_path.exists():
                if output_path.is_dir():
                    raise OutputError(f"Output path is a directory: {output_path}")
                if not args.overwrite:
                    raise OutputError(
                        f"Output file already exists: {output_path}. Use --overwrite."
                    )
                output_path.unlink()

            try:
                shutil.move(str(temp_output), str(output_path))
            except OSError as exc:
                raise OutputError(f"Failed to move final EPUB into place: {exc}") from exc

            if not args.quiet:
                eprint(f"Done: {output_path}")

            return 0

        finally:
            if temp_context is not None:
                temp_context.cleanup()

    except VideoToEpubError as exc:
        eprint(f"Error: {exc}")
        return 2
    except KeyboardInterrupt:
        eprint("Interrupted.")
        return 130
    except Exception as exc:
        if args.debug:
            raise
        eprint(f"Unexpected error: {exc}")
        eprint("Re-run with --debug for a full traceback.")
        return 1