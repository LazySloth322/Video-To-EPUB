import zipfile
from pathlib import Path

from PIL import Image

from video_to_epub.epub_builder import build_epub, render_xhtml
from video_to_epub.events import build_events
from video_to_epub.images import Screenshot
from video_to_epub.transcription import Segment


def test_render_xhtml_escapes_transcript_text():
    segment = Segment(start=0.0, end=1.0, text='<script>alert("x")</script>')
    events = build_events([segment], [])

    xhtml = render_xhtml(events, title="Test", language="en")

    assert "<script>" not in xhtml
    assert "&lt;script&gt;" in xhtml


def test_build_epub_creates_zip_with_transcript_and_image(tmp_path: Path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"not a real video, only used for metadata")

    image_path = tmp_path / "slide_0001_00-00-00.jpg"
    Image.new("RGB", (64, 36), color="white").save(
        image_path,
        format="JPEG",
        quality=80,
    )

    segment = Segment(start=0.0, end=1.0, text="Hello")
    screenshot = Screenshot(
        path=image_path,
        timestamp=0.0,
        filename=image_path.name,
        index=1,
    )

    events = build_events([segment], [screenshot])
    output = tmp_path / "out.epub"

    build_epub(
        output_path=output,
        events=events,
        title="Test Book",
        language="en",
        author=None,
        input_path=video,
        quiet=True,
    )

    assert output.exists()

    with zipfile.ZipFile(output, "r") as zf:
        names = zf.namelist()

        assert "mimetype" in names
        assert names[0] == "mimetype"
        assert zf.read("mimetype") == b"application/epub+zip"

        assert "transcript.xhtml" in names
        assert "styles.css" in names
        assert any(name.startswith("images/") for name in names)

        transcript = zf.read("transcript.xhtml").decode("utf-8")
        assert "Hello" in transcript
        assert "slide_0001_00-00-00.jpg" in transcript