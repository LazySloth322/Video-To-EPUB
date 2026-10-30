"""EPUB generation using ebooklib."""

from __future__ import annotations

import html
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

from .errors import ProcessingError, VideoToEpubError
from .events import Event
from .utils import eprint, format_timecode


CSS = """\
body {
  margin: 1em;
  line-height: 1.45;
}

h1 {
  margin-top: 0;
}

.segment {
  margin: 0.65em 0;
}

.timestamp {
  font-family: monospace;
  font-size: 0.9em;
  color: #555555;
}

figure.slide {
  margin: 1em 0;
  page-break-inside: avoid;
}

figure.slide img {
  max-width: 100%;
  height: auto;
}

figcaption {
  font-size: 0.9em;
  color: #555555;
  margin-top: 0.35em;
}
"""

def _clean_text(value: str) -> str:
    return " ".join(str(value).split())

def render_xhtml(
    events: List[Event],
    title: str,
    language: str,
    plain_text: bool = False,
) -> str:
    """
    Render merged events as EPUB XHTML.

    Transcript text is HTML-escaped so it cannot break markup.
    """
    safe_title = html.escape(title, quote=True)
    safe_lang = html.escape(language or "und", quote=True)

    parts: List[str] = [
        '<html xmlns="http://www.w3.org/1999/xhtml" ',
        f'xml:lang="{safe_lang}" lang="{safe_lang}">\n',
        "<head>\n",
        '<meta charset="utf-8"/>\n',
        f"<title>{safe_title}</title>\n",
        '<link rel="stylesheet" type="text/css" href="styles.css"/>\n',
        "</head>\n",
        "<body>\n",
        f"<h1>{safe_title}</h1>\n",
    ]

    if plain_text:
        buffer: List[str] = []

        def flush_buffer() -> None:
            nonlocal buffer
            if not buffer:
                return

            text = html.escape(" ".join(buffer), quote=False)
            if text:
                parts.append(f'<p class="segment">{text}</p>\n')

            buffer = []

        for event in events:
            if event.kind == "segment" and event.segment is not None:
                text = _clean_text(event.segment.text)
                if text:
                    buffer.append(text)

            elif event.kind == "image" and event.screenshot is not None:
                flush_buffer()

                shot = event.screenshot
                src = f"images/{html.escape(shot.filename, quote=True)}"
                alt = f"Slide screenshot {shot.index}"
                caption = f"Slide {shot.index}"

                parts.append('<figure class="slide">\n')
                parts.append(
                    f'<img src="{src}" alt="{html.escape(alt, quote=True)}"/>\n'
                )
                parts.append(
                    f"<figcaption>{html.escape(caption, quote=False)}</figcaption>\n"
                )
                parts.append("</figure>\n")

        flush_buffer()
        parts.append("</body>\n</html>\n")
        return "".join(parts)

    for event in events:
        if event.kind == "segment" and event.segment is not None:
            timecode = format_timecode(event.segment.start)
            text = html.escape(event.segment.text, quote=False)
            parts.append(
                '<p class="segment">'
                f'<span class="timestamp">[{html.escape(timecode, quote=False)}]</span> '
                f"{text}"
                "</p>\n"
            )

        elif event.kind == "image" and event.screenshot is not None:
            shot = event.screenshot
            timecode = format_timecode(shot.timestamp)
            src = f"images/{html.escape(shot.filename, quote=True)}"
            alt = f"Slide screenshot at {timecode}"
            caption = (
                f"Screenshot at {html.escape(timecode, quote=False)} "
                f"({shot.timestamp:.3f} s)"
            )

            parts.append('<figure class="slide">\n')
            parts.append(
                f'<img src="{src}" alt="{html.escape(alt, quote=True)}"/>\n'
            )
            parts.append(f"<figcaption>{caption}</figcaption>\n")
            parts.append("</figure>\n")

    parts.append("</body>\n</html>\n")
    return "".join(parts)


def _normalize_epub_zip(path: Path) -> None:
    """
    Rewrite the EPUB zip with sorted entries and fixed timestamps.

    This improves reproducibility. The required mimetype entry is kept first and
    stored uncompressed.
    """
    fixed_date = (1980, 1, 1, 0, 0, 0)
    tmp_path = path.parent / (path.name + ".normalized")

    with zipfile.ZipFile(path, "r") as zin:
        infos = sorted(
            zin.infolist(),
            key=lambda info: (0 if info.filename == "mimetype" else 1, info.filename),
        )

        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for info in infos:
                data = zin.read(info.filename)
                new_info = zipfile.ZipInfo(filename=info.filename, date_time=fixed_date)
                new_info.compress_type = (
                    zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
                )
                new_info.external_attr = info.external_attr
                zout.writestr(new_info, data)

    tmp_path.replace(path)


def build_epub(
    output_path: Path,
    events: List[Event],
    title: str,
    language: Optional[str],
    author: Optional[str],
    input_path: Path,
    quiet: bool = False,
    plain_text: bool = False,
) -> None:
    """
    Create a valid EPUB file containing transcript text and embedded screenshots.
    """
    try:
        from ebooklib import epub
    except ImportError as exc:
        raise ProcessingError(
            "ebooklib is not installed. Install dependencies with: "
            "python -m pip install -r requirements.txt"
        ) from exc

    output_path = Path(output_path)
    input_path = Path(input_path)
    lang = language or "und"

    try:
        input_size = input_path.stat().st_size
    except OSError:
        input_size = 0

    # Deterministic identifier based on non-machine-specific input metadata.
    identifier = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"video-to-epub://{input_path.name}?size={input_size}&title={title}",
    )

    book = epub.EpubBook()
    book.set_identifier(str(identifier))
    book.set_title(title)
    book.set_language(lang)
    book.add_metadata("DC", "source", input_path.name)
    book.add_metadata("EPUB", "generator", "video-to-epub")

    if author:
        book.add_author(author)

    css_item = epub.EpubItem(
        uid="style",
        file_name="styles.css",
        media_type="text/css",
        content=CSS.encode("utf-8"),
    )
    book.add_item(css_item)

    xhtml_content = render_xhtml(
        events,
        title=title,
        language=lang,
        plain_text=True, # was `plain_text=plain_text`
    )
    chapter = epub.EpubHtml(
        title=title,
        file_name="transcript.xhtml",
        lang=lang,
    )
    chapter.content = xhtml_content
    book.add_item(chapter)

    seen_image_files: set[str] = set()

    for event in events:
        if event.kind != "image" or event.screenshot is None:
            continue

        shot = event.screenshot
        if shot.filename in seen_image_files:
            continue
        seen_image_files.add(shot.filename)

        try:
            image_bytes = shot.path.read_bytes()
        except OSError as exc:
            raise ProcessingError(
                f"Failed to read screenshot file {shot.path}: {exc}"
            ) from exc

        image_item = epub.EpubItem(
            uid=f"image_{shot.index}",
            file_name=f"images/{shot.filename}",
            media_type="image/jpeg",
            content=image_bytes,
        )
        book.add_item(image_item)

    book.toc = (
        epub.Link(
            "transcript.xhtml",
            title,
            "transcript",
        ),
    )

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not quiet:
        eprint("Writing EPUB...")

    try:
        epub.write_epub(str(output_path), book, {})
    except VideoToEpubError:
        raise
    except Exception as exc:
        raise ProcessingError(f"Failed to write EPUB: {exc}") from exc

    try:
        _normalize_epub_zip(output_path)
    except Exception as exc:
        if not quiet:
            eprint(f"Warning: could not normalize EPUB zip timestamps: {exc}")