# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Use pylibjpeg <https://github.com/pydicom/pylibjpeg> to decompress encoded
*Pixel Data*.

This module is not intended to be used directly.
"""

from typing import cast

from pydicom import uid
from pydicom.pixels.decoders.base import DecodeRunner
from pydicom.pixels.utils import _passes_version_check
from pydicom.pixels.common import PhotometricInterpretation as PI

try:
    from pylibjpeg.utils import get_pixel_data_decoders, Decoder

    # {UID: {plugin name: function}}
    _DECODERS = cast(
        dict[uid.UID, dict[str, "Decoder"]], get_pixel_data_decoders(version=2)
    )
except ImportError:
    _DECODERS = {}


DECODER_DEPENDENCIES = {
    uid.JPEGBaseline8Bit: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.1"),
    uid.JPEGExtended12Bit: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.1"),
    uid.JPEGLossless: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.1"),
    uid.JPEGLosslessSV1: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.1"),
    uid.JPEGLSLossless: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.1"),
    uid.JPEGLSNearLossless: ("pylibjpeg>=2.0", "pylibjpeg-libjpeg>=2.1"),
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
    """Return ``True`` if the decoder has its dependencies met, ``False`` otherwise"""
    if not _passes_version_check("pylibjpeg", (2, 0)):
        return False

    if uid in _LIBJPEG_SYNTAXES:
        return _passes_version_check("libjpeg", (2, 0, 2))

    if uid in _OPENJPEG_SYNTAXES:
        return _passes_version_check("openjpeg", (2, 0))

    if uid in _RLE_SYNTAXES:
        return _passes_version_check("rle", (2, 0))

    return False


def _decode_frame(src: bytes, runner: DecodeRunner) -> bytearray:  # type: ignore[return]
    """Return the decoded image data in `src` as a :class:`bytearray`."""
    tsyntax = runner.transfer_syntax

    # Currently only one pylibjpeg plugin is available per UID
    #   so decode using the first available decoder
    for _, func in sorted(_DECODERS[tsyntax].items()):
        # `version=2` to return frame as bytearray
        frame = cast(bytearray, func(src, version=2, **runner.options))

        # pylibjpeg-rle returns decoded data as planar configuration 1
        if tsyntax == uid.RLELossless:
            runner.set_option("planar_configuration", 1)

        if tsyntax in _OPENJPEG_SYNTAXES:
            # pylibjpeg-openjpeg returns YBR_ICT and YBR_RCT as RGB
            if runner.photometric_interpretation in (PI.YBR_ICT, PI.YBR_RCT):
                runner.set_option("photometric_interpretation", PI.RGB)

            # pylibjpeg-openjpeg pixel container size is based on J2K precision
            precision = runner.get_option("j2k_precision", runner.bits_stored)
            if 0 < precision <= 8:
                runner.set_option("bits_allocated", 8)
            elif 8 < precision <= 16:
                runner.set_option("bits_allocated", 16)
            elif 16 < precision <= 32:
                runner.set_option("bits_allocated", 32)

        if tsyntax in uid.JPEGLSTransferSyntaxes:
            # pylibjpeg-libjpeg always returns JPEG-LS data as color-by-pixel
            runner.set_option("planar_configuration", 0)

            # pylibjpeg-libjpeg pixel container size is based on JPEG-LS precision
            precision = runner.get_option("jls_precision", runner.bits_stored)
            if 0 < precision <= 8:
                runner.set_option("bits_allocated", 8)
            elif 8 < precision <= 16:
                runner.set_option("bits_allocated", 16)

        return frame
