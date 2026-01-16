"""Custom static file storage backends."""

from whitenoise.compress import Compressor
from whitenoise.storage import CompressedManifestStaticFilesStorage


class GzipOnlyManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Static files storage that only uses gzip compression (no brotli).

    Brotli compression is slower and while it produces smaller files,
    gzip is universally supported and faster to generate. This reduces
    collectstatic time significantly on large projects.
    """

    def create_compressor(self, **kwargs):
        # Override to disable brotli compression
        kwargs["use_brotli"] = False
        return Compressor(**kwargs)
