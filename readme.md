# video-to-epub

Convert a video presentation into an EPUB book containing:

- a timestamped speech transcript produced by **original OpenAI Whisper**
  (`openai-whisper`) using the **`turbo`** model;
- screenshots of slides/scenes detected from the video;
- transcript segments and screenshots interleaved chronologically.

This project deliberately uses the normal Python Whisper API:

```python
import whisper
model = whisper.load_model("turbo")
```

It does **not** use `faster-whisper`, CTranslate2, or the OpenAI API.

---

## Architecture

High-level pipeline:

```text
video file
  -> validate input/output/dependencies
  -> transcribe audio with openai-whisper turbo
  -> sequentially decode video frames with PyAV
  -> sample frames every N seconds
  -> detect persistent visual changes with grayscale pixel-diff heuristic
  -> save screenshots to temporary directory
  -> merge transcript segments and screenshots by timestamp
  -> build EPUB with ebooklib
  -> normalize EPUB zip timestamps for more reproducible output
```

Transcription and frame analysis run sequentially for reliability. Parallel execution
is possible but can contend for CPU/GPU/disk/FFmpeg resources and complicates error
handling.

---

## Requirements

- Python 3.9+
- FFmpeg executable available on `PATH`
- GPU is optional. Whisper `turbo` can run on CPU, but GPU is much faster.

### Python packages

Runtime dependencies are listed in `requirements.txt`:

```txt
openai-whisper>=20240930
av>=11.0.0
Pillow>=10.0.0
numpy>=1.24.0
ebooklib>=0.18
```

Install:

```bash
python -m pip install -r requirements.txt
```

Or, if using the package metadata:

```bash
python -m pip install -e .
```

For CUDA GPUs:

```bash
python -m pip install -r requirements.txt
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

For tests:

```bash
python -m pip install -r requirements-dev.txt
```

or:

```bash
python -m pip install -e .[dev]
```

---

## FFmpeg setup

`openai-whisper` requires the `ffmpeg` command-line executable to extract audio from
video files.

Verify:

```bash
ffmpeg -version
```

### macOS

```bash
brew install ffmpeg
```

### Debian/Ubuntu

```bash
sudo apt update
sudo apt install ffmpeg
```

### Fedora

```bash
sudo dnf install ffmpeg
```

### Windows

Use one of:

```powershell
winget install Gyan.FFmpeg
```

or:

```powershell
choco install ffmpeg
```

Then restart your terminal and verify:

```powershell
ffmpeg -version
```

---

## Usage

From the project root:

```bash
python video_to_epub.py presentation.mp4 --output presentation.epub
```

If `--output` is omitted, the output EPUB path is derived from the input filename:

```bash
python video_to_epub.py presentation.mp4
```

Use GPU explicitly:

```bash
python video_to_epub.py presentation.mp4 \
  --output presentation.epub \
  --device cuda
```

Force English transcription without translation:

```bash
python video_to_epub.py presentation.mp4 \
  --output presentation.epub \
  --language en
```

Keep temporary screenshots for debugging:

```bash
python video_to_epub.py presentation.mp4 \
  --output presentation.epub \
  --keep-temp
```

Overwrite an existing output file:

```bash
python video_to_epub.py presentation.mp4 \
  --output presentation.epub \
  --overwrite
```

More aggressive slide-change detection:

```bash
python video_to_epub.py presentation.mp4 \
  --output presentation.epub \
  --interval-seconds 2.0 \
  --pixel-diff-threshold 8 \
  --change-threshold 0.01
```

Less sensitive detection for noisy/animated videos:

```bash
python video_to_epub.py presentation.mp4 \
  --output presentation.epub \
  --interval-seconds 5.0 \
  --pixel-diff-threshold 20 \
  --change-threshold 0.05 \
  --confirm-samples 2 \
  --debounce-seconds 2.0
```

---

## Command-line options

### Input/output

| Option | Default | Description |
|---|---:|---|
| `input_video` | required | Local input video file. |
| `-o`, `--output` | input stem + `.epub` | Output EPUB path. |
| `--overwrite` | off | Replace existing output file. |
| `--keep-temp` | off | Keep temporary files for debugging. |
| `--temp-dir` | system temp | Base directory for temporary files. |
| `--quiet` | off | Suppress progress messages. |
| `--debug` | off | Show full traceback for unexpected errors. |

### Transcription

| Option | Default | Description |
|---|---:|---|
| `--language` | automatic | Whisper language code, e.g. `en`. This selects transcription language, not translation. |
| `--device` | automatic | Whisper device, e.g. `cuda` or `cpu`. |

The application always uses Whisper `turbo` and `task="transcribe"`. It does not
translate unless the spoken language itself is the target language.

If your installed `openai-whisper` does not provide `turbo`, upgrade:

```bash
python -m pip install --upgrade openai-whisper
```

Verify:

```bash
python -c "import whisper; print(whisper.available_models())"
```

### Frame sampling and slide detection

| Option | Default | Description |
|---|---:|---|
| `--interval-seconds` | `5.0` | Approximate seconds between sampled frames. |
| `--pixel-diff-threshold` | `12` | Minimum absolute grayscale difference for one pixel to count as changed. Range 0-255. |
| `--change-threshold` | `0.2` | Minimum fraction of changed pixels required for a slide/scene change. Range 0-1. |
| `--resize-width` | `640` | Width used to downscale frames before comparison. |
| `--confirm-samples` | `1` | Number of consecutive changed samples required before saving. |
| `--debounce-seconds` | `1.0` | Minimum seconds between saved screenshots. |
| `--screenshot-width` | `1920` | Maximum saved screenshot width. `0` keeps original decoded width. |
| `--jpeg-quality` | `90` | JPEG quality for saved screenshots. |

### EPUB metadata

| Option | Default | Description |
|---|---:|---|
| `--title` | input filename stem | EPUB title. |
| `--author` | none | Optional EPUB author metadata. |

---

## Slide detection behavior and tuning

The detector compares each sampled frame to the last accepted reference frame.

- Increase `--pixel-diff-threshold` to ignore subtle compression/noise changes.
- Increase `--change-threshold` to require a larger portion of the frame to change.
- Decrease `--interval-seconds` to sample more often.
- Increase `--confirm-samples` to require a change to persist across multiple samples.
- Increase `--debounce-seconds` to avoid saving multiple screenshots too quickly.

Defaults:

```text
--pixel-diff-threshold 12
--change-threshold 0.2
```

These are reasonable starting points for static presentation slides. A full slide
change usually changes far more than 2% of pixels. Small text-only changes may require
lower thresholds. Animated backgrounds or camera motion may require higher thresholds,
longer intervals, confirmation, and debounce.

---

## Timestamps and VFR videos

The application uses PyAV and prefers frame timestamps (`frame.time` or PTS-based
timestamps). It normalizes the timeline so the first decoded frame starts at 0 seconds.

Limitations:

- Variable-frame-rate videos are handled as well as practical through container/frame
  timestamps.
- If a stream lacks usable PTS/time information, the code falls back to an approximate
  frame-index/fps calculation.
- Whisper timestamps are segment-level, not word-level.
- If `--confirm-samples > 1`, the saved screenshot timestamp is the timestamp of the
  sample that confirmed the change, not necessarily the first frame where the change
  began.
- If `--debounce-seconds` is too high, legitimate rapid slide changes may be suppressed
  or delayed.

---

## EPUB placement policy

Events are merged by timestamp:

- transcript segment event time = segment start;
- screenshot event time = screenshot timestamp;
- ties are resolved with transcript segment before screenshot.

Therefore, if a screenshot timestamp falls inside a transcript segment, the segment text
is placed before the screenshot. The screenshot caption retains its exact timestamp.

Example caption:

```text
Screenshot at 00:01:25.123 (85.123 s)
```

Generated screenshot filenames are human-readable and stable, for example:

```text
slide_0001_00-01-25.jpg
```

The exact numeric timestamp is preserved internally and used for ordering.

---

## Reproducibility

The application avoids embedding absolute machine-specific paths in EPUB metadata. The
EPUB identifier is derived deterministically from the input filename, file size, and
title. The final EPUB zip is rewritten with sorted entries and fixed zip timestamps.

Full bit-for-bit reproducibility can still be affected by library versions, Whisper
model outputs, and platform-specific decoding behavior.

---

## Tests

Tests do not download or run the Whisper model.

Run:

```bash
pytest
```

Covered areas:

- image difference calculation;
- grayscale resize behavior;
- slide-change detector first-frame, change, confirmation, and debounce logic;
- chronological event ordering;
- transcript segment vs screenshot tie-breaking;
- XHTML escaping;
- basic EPUB zip creation with embedded image.

---

## Known limitations

- Slide detection is heuristic. It is not perfect for animated slides, videos with
  camera motion, picture-in-picture layouts, or very subtle slide changes.
- Whisper `turbo` may require a significant download on first use.
- CPU transcription can be slow. Use `--device cuda` when available.
- Frame analysis decodes through the video stream. This is robust but can be slower
  than keyframe-only approaches, especially for long videos.
- The EPUB is generated as one main transcript chapter. Very long videos may produce a
  large XHTML document.
- Word-level synchronization is not invented. Only Whisper segment timestamps are used.
- If the input has no video stream, the tool continues with transcript-only output and
  warns.

---

## Example

```bash
python video_to_epub.py presentation.mp4 --output presentation.epub