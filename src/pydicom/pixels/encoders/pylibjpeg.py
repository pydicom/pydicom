# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Interface for *Pixel Data* encoding, not intended to be used directly."""

from typing import cast

from pydicom.pixels.encoders.base import EncodeRunner
from pydicom.pixels.common import PhotometricInterpretation as PI
from pydicom.pixels.utils import _passes_version_check
from pydicom import uid

try:
    from pylibjpeg.utils import get_pixel_data_encoders, Encoder

    _ENCODERS = get_pixel_data_encoders()
except ImportError:
    _ENCODERS = {}


ENCODER_DEPENDENCIES = {
    uid.JPEG2000Lossless: ("numpy", "pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.2"),
    uid.JPEG2000: ("numpy", "pylibjpeg>=2.0", "pylibjpeg-openjpeg>=2.2"),
    uid.RLELossless: ("numpy", "pylibjpeg>=2.0", "pylibjpeg-rle>=2.0"),
}
_OPENJPEG_SYNTAXES = [uid.JPEG2000Lossless, uid.JPEG2000]
_RLE_SYNTAXES = [uid.RLELossless]


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data encoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not _passes_version_check("pylibjpeg", (2, 0)):
        return False

    if uid in _OPENJPEG_SYNTAXES:
        return _passes_version_check("openjpeg", (2, 2))

    if uid in _RLE_SYNTAXES:
        return _passes_version_check("rle", (2, 0))

    return False


def _encode_frame(src: bytes, runner: EncodeRunner) -> bytes | bytearray:
    """Return `src` as an encoded codestream."""
    encoder = cast(Encoder, _ENCODERS[runner.transfer_syntax])

    tsyntax = runner.transfer_syntax
    if tsyntax == uid.RLELossless:
        return cast(bytes, encoder(src, **runner.options))

    opts = dict(runner.options)
    if runner.photometric_interpretation == PI.RGB:
        opts["use_mct"] = False

    cr = opts.pop("compression_ratios", opts.get("j2k_cr", None))
    psnr = opts.pop("signal_noise_ratios", opts.get("j2k_psnr", None))
    if tsyntax == uid.JPEG2000Lossless:
        if cr or psnr:
            raise ValueError(
                "A lossy configuration option is being used with a transfer "
                "syntax of 'JPEG 2000 Lossless' - did you mean to use 'JPEG "
                "2000' instead?"
            )

        return cast(bytes, encoder(src, **opts))

    if not cr and not psnr:
        raise ValueError(
            "The 'JPEG 2000' transfer syntax requires a lossy configuration "
            "option such as 'j2k_cr' or 'j2k_psnr'"
        )

    if cr and psnr:
        raise ValueError(
            "Multiple lossy configuration options are being used with the "
            "'JPEG 2000' transfer syntax, please specify only one"
        )

    cs = encoder(src, **opts, compression_ratios=cr, signal_noise_ratios=psnr)

    return cast(bytes, cs)
