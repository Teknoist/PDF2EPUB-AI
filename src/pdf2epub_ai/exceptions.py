"""Application-specific exceptions."""


class Pdf2EpubError(Exception):
    """Base exception for recoverable conversion failures."""


class DependencyMissingError(Pdf2EpubError):
    """Raised when an optional binary or Python package is required but unavailable."""


class OcrEngineError(Pdf2EpubError):
    """Raised when an OCR engine fails to process a page or document."""


class EpubValidationError(Pdf2EpubError):
    """Raised when EPUB generation cannot produce a valid archive."""


class ConversionCancelledError(Pdf2EpubError):
    """Raised when the user cancels an active conversion."""
