# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Use pyjpegls <https://github.com/pydicom/pyjpegls> to decompress encoded
*Pixel Data*.

This module is not intended to be used directly.
"""
from typing import cast

from pydicom import uid
from pydicom.pixels.utils import _passes_version_check
from pydicom.pixels.decoders.base import DecodeRunner

try:
    import jpeg_ls

except ImportError:
    pass


DECODER_DEPENDENCIES = {
    uid.JPEGLSLossless: ("numpy", "jpeg_ls>=1.2"),
    uid.JPEGLSNearLossless: ("numpy", "jpeg_ls>=1.2"),
}


def is_available(uid: str) -> bool:
    """Return ``True`` if the decoder has its dependencies met, ``False`` otherwise"""
    return _passes_version_check("jpeg_ls", (1, 2))


def _decode_frame(src: bytes, runner: DecodeRunner) -> bytearray:
    """Return the decoded image data in `src` as a :class:`bytearray`."""
    buffer, info = jpeg_ls.decode_pixel_data(src)
    # Interleave mode 0 is colour-by-plane, 1 and 2 are colour-by-pixel
    if info["components"] > 1 and info["interleave_mode"] == 0:
        runner.set_option("planar_configuration", 1)

    return cast(bytearray, buffer)
