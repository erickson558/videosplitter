"""Project-specific exceptions for the video splitter application."""


class VideoSplitterError(Exception):
    """Base exception for all split-related errors."""


class InvalidSplitConfigError(VideoSplitterError):
    """Raised when split configuration values are invalid."""


class FFmpegBinaryNotFoundError(VideoSplitterError):
    """Raised when FFmpeg is not available."""


class SplitExecutionError(VideoSplitterError):
    """Raised when FFmpeg fails while splitting the video."""

