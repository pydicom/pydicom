# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Use pyjpegls <https://github.com/pydicom/pyjpegls> to compress *Pixel Data*.

This module is not intended to be used directly.
"""

from typing import cast

from pydicom import uid
from pydicom.pixels.encoders.base import EncodeRunner
from pydicom.pixels.utils import _passes_version_check

try:
    import jpeg_ls

except ImportError:
    pass


ENCODER_DEPENDENCIES = {
    uid.JPEGLSLossless: ("numpy", "pyjpegls>=1.3"),
    uid.JPEGLSNearLossless: ("numpy", "pyjpegls>=1.3"),
}


def is_available(uid: str) -> bool:
    """Return ``True`` if the decoder has its dependencies met, ``False`` otherwise"""
    return _passes_version_check("jpeg_ls", (1, 3))


def _encode_frame(src: bytes, runner: EncodeRunner) -> bytearray:
    """Return the image data in `src` as a JPEG-LS encoded codestream."""
    lossy_error = runner.get_option("jls_error", 0)
    if lossy_error and runner.transfer_syntax == uid.JPEGLSLossless:
        raise ValueError(
            f"A 'jls_error' value of '{lossy_error}' is being used with a "
            "transfer syntax of 'JPEG-LS Lossless' - did you mean to use "
            "'JPEG-LS Near Lossless' instead?"
        )

    opts = {
        "rows": runner.rows,
        "columns": runner.columns,
        "samples_per_pixel": runner.samples_per_pixel,
        "bits_stored": runner.bits_stored,
    }

    if runner.samples_per_pixel > 1:
        opts["planar_configuration"] = runner.planar_configuration

    return cast(
        bytearray, jpeg_ls.encode_pixel_data(src, lossy_error=lossy_error, **opts)
    )
