from io import BytesIO
from typing import TYPE_CHECKING
import warnings

from pydicom.uid import (
    JPEGBaseline8Bit,
    JPEGExtended12Bit,
    JPEG2000Lossless,
    JPEG2000,
)

try:
    from PIL import Image, features

    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

try:
    import numpy

    HAVE_NP = True
except ImportError:
    HAVE_NP = False


if TYPE_CHECKING:  # pragma: no cover
    from pydicom.pixels.decoders.base import DecoderOptions


DECODER_DEPENDENCIES = {
    JPEGBaseline8Bit: ("pillow>=7.0.0",),
    JPEGExtended12Bit: ("pillow>=7.0.0",),
    JPEG2000Lossless: ("pillow>=7.0.0", "numpy"),
    JPEG2000: ("pillow>=7.0.0", "numpy"),
}

_LIBJPEG_SYNTAXES = [JPEGBaseline8Bit, JPEGExtended12Bit]
_OPENJPEG_SYNTAXES = [JPEG2000Lossless, JPEG2000]


# TODO: 12 bit for JPEGExtended12Bit?
def is_available(uid: str) -> bool:
    """Return ``True`` if a pixel data decoder for `uid` is available for use,
    ``False`` otherwise.
    """
    if not HAVE_PIL:
        return False

    if uid in _LIBJPEG_SYNTAXES:
        # if transfer_syntax == JPEGExtended12Bit and ds.BitsAllocated != 8:
        #     raise NotImplementedError(
        #         f"{JPEGExtended12Bit} - {JPEGExtended12Bit.name} is only supported "
        #         "by Pillow if (0028,0100) Bits Allocated = 8"
        #     )

        return features.check_codec("jpg")

    if uid in _OPENJPEG_SYNTAXES and HAVE_NP:
        return features.check_codec("jpg_2000")

    return False


def _decode_frame(src: bytes, opts: "DecoderOptions") -> bytearray:
    tsyntax = opts["transfer_syntax_uid"]

    image = Image.open(BytesIO(src))
    if tsyntax in _LIBJPEG_SYNTAXES:
        # TODO: update from that closed PR
        if opts["photometric_interpretation"] == "RGB":
            # This hack ensures that RGB color images, which were not
            #   color transformed (i.e. not transformed into YCbCr color space)
            #   upon JPEG compression are decompressed correctly.
            # Since Pillow assumes that images were transformed into YCbCr color
            #   space prior to compression, setting the value of "mode" to YCbCr
            #   signals Pillow to not apply any color transformation upon
            #   decompression.
            if "adobe_transform" not in image.info:
                image.draft("YCbCr", image.size)
    else:
        # Pillow converts N-bit signed/unsigned data to 8- or 16-bit unsigned data
        #   See Pillow src/libImaging/Jpeg2KDecode.c::j2ku_gray_i
        # Undo pillow processing -> can this be done via pillow?
        pass

    return bytearray(image.tobytes())


def foo():
    # Return and use DecodeRunner for J2K post processing...

    # arr = numpy.frombuffer(pixel_bytes, pixel_dtype(ds))
    # arr = numpy.asarray(img, dtype=pixel_dtype(opts))  # or whatever

    # Pillow converts N-bit signed/unsigned data to 8- or 16-bit unsigned data
    #   See Pillow src/libImaging/Jpeg2KDecode.c::j2ku_gray_i
    shift = bits_allocated - bits_stored
    if j2k_precision != bits_stored and opts["j2k_corrections"]:
        warnings.warn(
            f"The (0028,0101) 'Bits Stored' value ({bits_stored}-bit) "
            f"doesn't match the JPEG 2000 data ({j2k_precision}-bit). "
            "It's recommended that you change the 'Bits Stored' value to "
            f"{j2k_precision}"
        )

        # Corrections based on J2K data
        shift = bits_allocated - j2k_precision
        if not j2k_sign and j2k_sign != pixel_representation:
            # Convert unsigned J2K data to 2's complement
            arr = numpy.right_shift(arr, shift)
        else:
            if pixel_representation == 1:
                # Pillow converts signed data to unsigned
                #   so we need to undo this conversion
                arr -= 2 ** (bits_allocated - 1)

            if shift:
                arr = numpy.right_shift(arr, shift)

    else:
        # Corrections based on dataset elements
        if pixel_representation == 1:
            arr -= 2 ** (bits_allocated - 1)

        if shift:
            arr = numpy.right_shift(arr, shift)

    return bytearray(arr.tobytes())
