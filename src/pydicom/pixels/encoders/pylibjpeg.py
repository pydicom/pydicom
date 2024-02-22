# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Interface for *Pixel Data* encoding, not intended to be used directly."""

from typing import cast

from pydicom.pixels.encoders.base import EncodeRunner
from pydicom.pixels.utils import _passes_version_check
from pydicom import uid

try:
    from pylibjpeg.utils import get_pixel_data_encoders

    _ENCODERS = get_pixel_data_encoders()
except ImportError:
    _ENCODERS = {}


ENCODER_DEPENDENCIES = {
    uid.RLELossless: ("numpy", "pylibjpeg>=2.0", "pylibjpeg-rle>=2.0"),
}
_RLE_SYNTAXES = [uid.RLELossless]


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data encoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not _passes_version_check("pylibjpeg", (2, 0)):
        return False

    if uid in _RLE_SYNTAXES:
        return _passes_version_check("rle", (2, 0))

    return False


def encode_pixel_data(src: bytes, runner: EncodeRunner) -> bytes | bytearray:
    """Return the encoded image data in `src`.

    Parameters
    ----------
    src : bytes
        The raw image frame data to be encoded.
    **kwargs
        Parameters to pass to the encoder function.

    Returns
    -------
    bytes
        The encoded image data.
    """
    encoder = _ENCODERS[runner.transfer_syntax]

    return cast(bytes, encoder(src, **runner.options))
