# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Use pylibjpeg to decompress encoded *Pixel Data*.

This module is not intended to be used directly.
"""

from pydicom import uid

try:
    from pylibjpeg import __version__ as pyljv
    from pylibjpeg.utils import get_pixel_data_decoders

    HAVE_PYLIBJPEG = True
except ImportError:
    HAVE_PYLIBJPEG = False

try:
    from openjpeg import __version__ as ojv

    HAVE_OPENJPEG = True
except ImportError:
    HAVE_OPENJPEG = False

try:
    from libjpeg import __version__ as ljv

    HAVE_LIBJPEG = True
except ImportError:
    HAVE_LIBJPEG = False

try:
    from rle import __version__ as rlev

    HAVE_RLE = True
except ImportError:
    HAVE_RLE = False


DECODER_DEPENDENCIES = {
    uid.JPEGBaseline8Bit: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.0"),
    uid.JPEGExtended12Bit: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.0"),
    uid.JPEGLossless: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.0"),
    uid.JPEGLosslessSV1: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.0"),
    uid.JPEGLSLossless: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.0"),
    uid.JPEGLSNearLossless: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.0"),
    uid.JPEG2000Lossless: ("pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.0"),
    uid.JPEG2000: ("pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.0"),
    uid.HTJ2KLossless: ("pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.0"),
    uid.HTJ2KLosslessRPCL: ("pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.0"),
    uid.HTJ2K: ("pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.0"),
    uid.RLELossless: ("pylibjpeg>=2.0", "pylibjpeg-rle>=2.0"),
}

_LIBJPEG_SYNTAXES = [
    uid.JPEGBaseline8Bit,
    uid.JPEGExtended12Bit,
    uid.JPEGLossless,
    uid.JPEGLosslessSV1,
    uid.JPEGLSLossless,
    uid.JPEGLSNearLossless,
]
_OPENJPEG_SYNTAXES = [
    uid.JPEG2000Lossless,
    uid.JPEG2000,
    uid.HTJ2KLossless,
    uid.HTJ2KLosslessRPCL,
    uid.HTJ2K,
]
_RLE_SYNTAXES = [uid.RLELossless]


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data decoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not HAVE_PYLIBJPEG or [int(x) for x in pyljv.split(".")] < [2, 0]:
        return False

    if uid in _LIBJPEG_SYNTAXES and HAVE_LIBJPEG:
        return [int(x) for x in ljv.split(".")] >= [2, 0]

    if uid in _OPENJPEG_SYNTAXES and HAVE_OPENJPEG:
        return [int(x) for x in ojv.split(".")] >= [2, 0]

    if uid in _RLE_SYNTAXES and HAVE_RLE:
        return [int(x) for x in rlev.split(".")] >= [2, 0]

    return False


def _decode_frame(src: bytes, opts: "DecodeOptions") -> bytearray:
    tsyntax = opts["transfer_syntax_uid"]
    # {plugin: function}
    decoders = get_pixel_data_decoders(version=2)[tsyntax]

    # Currently only one pylibjpeg plugin is available per UID
    # so decode using the first available decoder
    for plugin_name, func in sorted(decoders.items()):
        # `version=2` to return frame as bytearray
        return func(src, version=2, **opts)
