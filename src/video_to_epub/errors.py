"""Custom exception types for user-facing errors."""


class VideoToEpubError(Exception):
    """Base class for expected application errors."""


class DependencyError(VideoToEpubError):
    """Raised when a required dependency or external tool is missing/wrong."""


class InputError(VideoToEpubError):
    """Raised when the input video or temp directory is invalid/unreadable."""


class OutputError(VideoToEpubError):
    """Raised when the output path is invalid or cannot be written."""


class ProcessingError(VideoToEpubError):
    """Raised when transcription, frame analysis, or EPUB generation fails."""