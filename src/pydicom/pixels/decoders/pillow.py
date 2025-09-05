# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Use Pillow <https://github.com/python-pillow/Pillow> to decompress encoded
*Pixel Data*.

This module is not intended to be used directly.
"""

from io import BytesIO
from typing import cast

from pydicom import uid
from pydicom.pixels.utils import _passes_version_check
from pydicom.pixels.common import PhotometricInterpretation as PI
from pydicom.pixels.decoders.base import DecodeRunner

try:
    from PIL import Image, features
except ImportError:
    pass

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False


DECODER_DEPENDENCIES = {
    uid.JPEGBaseline8Bit: ("pillow>=10.3",),
    uid.JPEGExtended12Bit: ("pillow>=10.3",),
    uid.JPEG2000Lossless: ("numpy", "pillow>=10.3"),
    uid.JPEG2000: ("numpy", "pillow>=10.3"),
}

_LIBJPEG_SYNTAXES = [uid.JPEGBaseline8Bit, uid.JPEGExtended12Bit]
_OPENJPEG_SYNTAXES = [uid.JPEG2000Lossless, uid.JPEG2000]


def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data decoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not _passes_version_check("PIL", (10, 3)):
        return False

    if uid in _LIBJPEG_SYNTAXES:
        return bool(features.check_codec("jpg"))  # type: ignore[no-untyped-call]

    if uid in _OPENJPEG_SYNTAXES:
        return bool(features.check_codec("jpg_2000")) and HAVE_NP  # type: ignore[no-untyped-call]

    return False


def _decode_frame(src: bytes, runner: DecodeRunner) -> bytes:
    """Return the decoded image data in `src` as a :class:`bytes`."""
    runner.set_frame_option(runner.index, "decoding_plugin", "pillow")

    tsyntax = runner.transfer_syntax
    bits_allocated = runner.bits_allocated

    # libjpeg only supports 8-bit JPEG Extended (can be 8 or 12 in the JPEG standard)
    if tsyntax == uid.JPEGExtended12Bit and runner.bits_stored != 8:
        raise NotImplementedError(
            "Pillow does not support 'JPEG Extended' for samples with 12-bit precision"
        )

    image = Image.open(BytesIO(src), formats=("JPEG", "JPEG2000"))
    if tsyntax in _LIBJPEG_SYNTAXES:
        if runner.samples_per_pixel != 1:
            # Multi-sample image: ensure the output color space is correct
            cs = runner.get_frame_option(runner.index, "photometric_interpretation")
            convert_to_rgb = runner.get_option("as_rgb", False) and "YBR" in cs

            if "adobe_transform" not in image.info:
                # If the Adobe APP14 marker is not present then Pillow assumes that JPEG
                #    images were transformed into YCbCr color space prior to compression
                if convert_to_rgb:
                    # Pillow will default to applying a YCbCr -> RGB conversion
                    runner.set_frame_option(
                        runner.index, "photometric_interpretation", PI.RGB
                    )
                else:
                    # Use Image.draft() to signal no color transformation
                    image.draft("YCbCr", image.size)  # type: ignore[no-untyped-call]
            elif image.info["adobe_transform"] == 1:  # 0: RGB, 1: YCbCr
                # If the Adobe APP14 marker is present then Pillow uses the value to
                #   determine the color space and defaults to returning RGB
                if convert_to_rgb:
                    runner.set_frame_option(
                        runner.index, "photometric_interpretation", PI.RGB
                    )
                elif "YBR" in cs:
                    image.draft("YCbCr", image.size)  # type: ignore[no-untyped-call]

        return cast(bytes, image.tobytes())

    # JPEG 2000
    # The precision from the J2K codestream is more appropriate because the
    #   decoder will use it to create the output integers
    precision = runner.get_frame_option(
        runner.index, "j2k_precision", runner.bits_stored
    )
    # pillow's pixel container size is based on precision
    if 0 < precision <= 8:
        bits_allocated = 8
    elif 8 < precision <= 16:
        # Pillow converts >= 9-bit RGB/YCbCr data to 8-bit
        if runner.samples_per_pixel > 1:
            raise ValueError(
                f"Pillow cannot decode {precision}-bit multi-sample data correctly"
            )

        bits_allocated = 16
    else:
        raise ValueError(
            "only (0028,0101) 'Bits Stored' values of up to 16 are supported"
        )

    runner.set_frame_option(runner.index, "bits_allocated", bits_allocated)

    # Pillow converts N-bit signed/unsigned data to 8- or 16-bit unsigned data
    #   See Pillow src/libImaging/Jpeg2KDecode.c::j2ku_gray_i
    buffer = bytearray(image.tobytes())  # so the array is writeable
    del image
    dtype = runner.frame_dtype(runner.index)
    arr = np.frombuffer(buffer, dtype=f"<u{dtype.itemsize}")

    is_signed = runner.pixel_representation
    if runner.get_option("apply_j2k_sign_correction", False):
        is_signed = runner.get_frame_option(runner.index, "j2k_is_signed", is_signed)

    if is_signed and runner.pixel_representation == 1:
        # Re-view the unsigned integers as signed
        #   e.g. [0, 127, 128, 255] -> [0, 127, -128, -1]
        arr = arr.view(dtype)
        # Level-shift to match the unsigned integers range
        #   e.g. [0, 127, -128, -1] -> [-128, -1, 0, 127]
        arr -= np.int32(2 ** (bits_allocated - 1))

    if bit_shift := (bits_allocated - precision):
        # Bit shift to undo the upscaling of N-bit to 8- or 16-bit
        np.right_shift(arr, bit_shift, out=arr)

    # pillow returns YBR_ICT and YBR_RCT as RGB
    if runner.photometric_interpretation in (PI.YBR_ICT, PI.YBR_RCT):
        runner.set_frame_option(runner.index, "photometric_interpretation", PI.RGB)

    # Signal that single-bit data is represented in unpacked form
    if runner.bits_allocated == 1:
        runner.set_frame_option(runner.index, "bits_allocated", 8)

    return cast(bytes, arr.tobytes())
