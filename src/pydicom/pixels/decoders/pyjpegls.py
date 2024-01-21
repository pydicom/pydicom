# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Use pyjpegls <https://github.com/pydicom/pyjpegls> to decompress encoded
*Pixel Data*.

This module is not intended to be used directly.
"""

from pydicom import uid
from pydicom.pixels.utils import _passes_version_check
from pydicom.pixels.decoders.base import DecodeRunner

try:
    import jpeg_ls

except ImportError:
    pass


DECODER_DEPENDENCIES = {
    uid.JPEGLSLossless: ("jpeg_ls>=1.1"),
    uid.JPEGLSNearLossless: ("jpeg_ls>=1.1"),
}


def is_available(uid: str) -> bool:
    """Return ``True`` if the decoder has its dependencies met, ``False`` otherwise"""
    return _passes_version_check("jpeg_ls", (1, 1))


def _decode_frame(src: bytes, runner: DecodeRunner) -> bytearray:
    """Return the decoded image data in `src` as a :class:`bytearray`."""
    return jpeg_ls.decode_from_buffer(src)
