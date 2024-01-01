# Copyright 2008-2022 pydicom authors. See LICENSE file for details.
"""
"""

from typing import TYPE_CHECKING

try:
    import pylibjpeg
    from pylibjpeg.utils import get_pixel_data_decoders

    HAVE_PYLIBJPEG = True
except ImportError:
    HAVE_PYLIBJPEG = False

try:
    import openjpeg

    HAVE_OPENJPEG = True
except ImportError:
    HAVE_OPENJPEG = False

try:
    import libjpeg

    HAVE_LIBJPEG = True
except ImportError:
    HAVE_LIBJPEG = False

try:
    import rle

    HAVE_RLE = True
except ImportError:
    HAVE_RLE = False


from pydicom.uid import (
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
    JPEG2000Lossless,
    JPEG2000,
    RLELossless,
)

if TYPE_CHECKING:  # pragma: no cover
    pass


DECODER_DEPENDENCIES = {
    JPEGBaseline8Bit: ("pylibjpeg", "pylibjpeg-libjpeg"),
    JPEGExtended12Bit: ("pylibjpeg", "pylibjpeg-libjpeg"),
    JPEGLossless: ("pylibjpeg", "pylibjpeg-libjpeg"),
    JPEGLosslessSV1: ("pylibjpeg", "pylibjpeg-libjpeg"),
    JPEGLSLossless: ("pylibjpeg", "pylibjpeg-libjpeg"),
    JPEGLSNearLossless: ("pylibjpeg", "pylibjpeg-libjpeg"),
    JPEG2000Lossless: ("pylibjpeg", "pylibjpeg-openjpeg"),
    JPEG2000: ("pylibjpeg", "pylibjpeg-openjpeg"),
    RLELossless: ("pylibjpeg", "pylibjpeg-rle"),
}


_LIBJPEG_SYNTAXES = [
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEGLossless,
    JPEGLosslessSV1,
    JPEGLSLossless,
    JPEGLSNearLossless,
]
_OPENJPEG_SYNTAXES = [JPEG2000Lossless, JPEG2000]
_RLE_SYNTAXES = [RLELossless]


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data decoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not HAVE_PYLIBJPEG:
        return False

    if uid in _LIBJPEG_SYNTAXES:
        return HAVE_LIBJPEG

    if uid in _OPENJPEG_SYNTAXES:
        return HAVE_OPENJPEG

    if uid in _RLE_SYNTAXES:
        return HAVE_RLE

    return False


def _decode_frame(src: bytes, opts: "DecodeOptions") -> bytes:
    _DECODERS = get_pixel_data_decoders(version="2")
    tsyntax = opts["transfer_syntax_uid"]
    return _DECODERS[tsyntax](src, **opts)
