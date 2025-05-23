# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Use the `GDCM <https://sourceforge.net/projects/gdcm/>`_ Python package to
decode pixel transfer syntaxes.
"""

from copy import deepcopy
import sys
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset


try:
    import numpy

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    import gdcm
    from gdcm import DataElement

    HAVE_GDCM = True
except ImportError:
    HAVE_GDCM = False

from pydicom import config
from pydicom.encaps import generate_frames, generate_fragmented_frames
import pydicom.uid
from pydicom.uid import UID, JPEG2000, JPEG2000Lossless
from pydicom.pixels.utils import (
    get_expected_length,
    pixel_dtype,
    get_j2k_parameters,
    get_nr_frames,
)


HANDLER_NAME = "GDCM"

DEPENDENCIES = {
    "numpy": ("https://numpy.org/", "NumPy"),
    "gdcm": ("https://sourceforge.net/projects/gdcm/", "GDCM"),
}

SUPPORTED_TRANSFER_SYNTAXES = [
    pydicom.uid.JPEGBaseline8Bit,
    pydicom.uid.JPEGExtended12Bit,
    pydicom.uid.JPEGLossless,
    pydicom.uid.JPEGLosslessSV1,
    pydicom.uid.JPEGLSLossless,
    pydicom.uid.JPEGLSNearLossless,
    pydicom.uid.JPEG2000Lossless,
    pydicom.uid.JPEG2000,
]

should_convert_these_syntaxes_to_RGB = [pydicom.uid.JPEGBaseline8Bit]


def is_available() -> bool:
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_NP and HAVE_GDCM


def _is_big_endian_system() -> bool:
    """Wrapper to allow testing the big endian fixes on little endian systems."""
    return sys.byteorder == "big"


def needs_to_convert_to_RGB(ds: "Dataset") -> bool:
    """Return ``True`` if the *Pixel Data* should to be converted from YCbCr to
    RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def should_change_PhotometricInterpretation_to_RGB(ds: "Dataset") -> bool:
    """Return ``True`` if the *Photometric Interpretation* should be changed
    to RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def supports_transfer_syntax(transfer_syntax: UID) -> bool:
    """Return ``True`` if the handler supports the `transfer_syntax`.

    Parameters
    ----------
    transfer_syntax : uid.UID
        The Transfer Syntax UID of the *Pixel Data* that is to be used with
        the handler.
    """
    return transfer_syntax in SUPPORTED_TRANSFER_SYNTAXES


def create_data_element(ds: "Dataset") -> "DataElement":
    """Return a ``gdcm.DataElement`` for the *Pixel Data*.

    Parameters
    ----------
    ds : dataset.Dataset
        The :class:`~pydicom.dataset.Dataset` containing the *Pixel
        Data*.

    Returns
    -------
    gdcm.DataElement
        The converted *Pixel Data* element.
    """
    elem = gdcm.DataElement(gdcm.Tag(0x7FE0, 0x0010))
    fragments = gdcm.SequenceOfFragments.New()
    nr_frames = get_nr_frames(ds, warn=False)
    fragment_gen = generate_fragmented_frames(ds.PixelData, number_of_frames=nr_frames)
    for frame_fragments in fragment_gen:
        for fragment_data in frame_fragments:
            fragment = gdcm.Fragment()
            fragment.SetByteStringValue(fragment_data)
            fragments.AddFragment(fragment)

    elem.SetValue(fragments.GetPointer())

    return elem


def create_image(ds: "Dataset") -> "gdcm.Image":
    """Return a ``gdcm.Image``.

    Parameters
    ----------
    ds : dataset.Dataset
        The :class:`~pydicom.dataset.Dataset` containing the Image
        Pixel module.

    Returns
    -------
    gdcm.Image
    """
    image = gdcm.Image()
    number_of_frames = get_nr_frames(ds, warn=False)
    image.SetNumberOfDimensions(2 if number_of_frames == 1 else 3)
    image.SetDimensions((ds.Columns, ds.Rows, number_of_frames))

    pi_type = gdcm.PhotometricInterpretation.GetPIType(ds.PhotometricInterpretation)
    image.SetPhotometricInterpretation(gdcm.PhotometricInterpretation(pi_type))

    tsyntax = ds.file_meta.TransferSyntaxUID
    ts_type = gdcm.TransferSyntax.GetTSType(str.__str__(tsyntax))
    image.SetTransferSyntax(gdcm.TransferSyntax(ts_type))
    pixel_format = gdcm.PixelFormat(
        ds.SamplesPerPixel,
        ds.BitsAllocated,
        ds.BitsStored,
        ds.HighBit,
        ds.PixelRepresentation,
    )
    image.SetPixelFormat(pixel_format)
    if "PlanarConfiguration" in ds:
        image.SetPlanarConfiguration(ds.PlanarConfiguration)

    return image


# Due to SWIG issues, it appears that GDCM cannot return more than (typically)
#   2**31 - 1 bytes when using gdcm.Image.GetBuffer(), although this may actually
#   be as low as 2**15 - 1 bytes depending on the system architecture.
# Because of this we cannot guarantee that GDCM will succeed as a single frame of
#   data may be larger - however in most cases its only multi-frame data that will
#   exceed that limit.
_GDCM_MAX_BUFFER_SIZE = 2**31 - 1


def get_pixeldata(ds: "Dataset") -> "numpy.ndarray":
    """Use the GDCM package to decode *Pixel Data*.

    Returns
    -------
    numpy.ndarray
        A correctly sized (but not shaped) array of the entire data volume

    Raises
    ------
    ImportError
        If the required packages are not available.
    TypeError
        If the image could not be read by GDCM or if the *Pixel Data* type is
        unsupported.
    AttributeError
        If the decoded amount of data does not match the expected amount.
    """
    if not HAVE_GDCM:
        raise ImportError("The GDCM handler requires both gdcm and numpy")

    # Check to see if it's possible to decode any of the pixel data
    frame_length = ds.Columns * ds.Rows * ds.SamplesPerPixel * ds.BitsAllocated // 8
    if frame_length > _GDCM_MAX_BUFFER_SIZE:
        raise ValueError(
            "GDCM cannot decode the pixel data as each frame will be larger than "
            "GDCM's maximum buffer size"
        )

    expected_length_bytes = get_expected_length(ds)
    if ds.PhotometricInterpretation == "YBR_FULL_422":
        # GDCM has already resampled the pixel data, see PS3.3 C.7.6.3.1.2
        expected_length_bytes = expected_length_bytes // 2 * 3

    # Create the gdcm.Image that will hold the encapsulated pixel data
    image = create_image(ds)

    # GDCM returns char* as type str, Python decodes this to unicode strings by default
    # The SWIG docs mention that they always decode byte streams as utf-8 strings,
    #   with the `surrogateescape` error handler configured.
    # Therefore, we can encode them back to a bytearray by using the same parameters.
    if expected_length_bytes > _GDCM_MAX_BUFFER_SIZE:
        # Decode the pixel data in parts of no greater than _GDCM_MAX_BUFFER_SIZE
        elem = gdcm.DataElement(gdcm.Tag(0x7FE0, 0x0010))
        fragments = gdcm.SequenceOfFragments.New()
        elem.SetValue(fragments.GetPointer())

        buffer = bytearray()
        frame_count = 0
        number_of_frames = get_nr_frames(ds, warn=False)
        frame_generator = generate_fragmented_frames(
            ds.PixelData, number_of_frames=number_of_frames
        )
        for idx, frame_fragments in enumerate(frame_generator):
            for fragment_data in frame_fragments:
                fragment = gdcm.Fragment()
                fragment.SetByteStringValue(fragment_data)
                fragments.AddFragment(fragment)

            frame_count += 1

            # Do a decode and reset if either:
            # * The length of decoded pixel data will be greater than the limit on the
            #   next iteration, or
            # * We are at the end of the pixel data
            if (
                idx == number_of_frames - 1
                or (frame_count + 1) * frame_length > _GDCM_MAX_BUFFER_SIZE
            ):
                image.SetNumberOfDimensions(2 if frame_count == 1 else 3)
                image.SetDimensions((ds.Columns, ds.Rows, frame_count))
                image.SetDataElement(elem)
                data = cast(bytes, image.GetBuffer().encode("utf-8", "surrogateescape"))
                buffer.extend(data)

                fragments.Clear()
                frame_count = 0

        pixel_bytearray = bytes(buffer)
    else:
        # Decode the entire pixel data in one go
        elem = create_data_element(ds)
        image.SetDataElement(elem)
        pixel_str = image.GetBuffer()
        pixel_bytearray = cast(bytes, pixel_str.encode("utf-8", "surrogateescape"))

    # On big endian systems GDCM returns data as big endian :(
    if _is_big_endian_system() and ds.BitsAllocated > 8:
        b = bytearray(pixel_bytearray)
        if ds.BitsAllocated == 16:
            b[::2], b[1::2] = b[1::2], b[::2]
        elif ds.BitsAllocated == 32:
            b[::4], b[1::4], b[2::4], b[3::4] = b[3::4], b[2::4], b[1::4], b[::4]

        pixel_bytearray = bytes(b)

    # Here we need to be careful because in some cases, GDCM reads a
    # buffer that is too large, so we need to make sure we only include
    # the first n_rows * n_columns * dtype_size bytes.
    if len(pixel_bytearray) > expected_length_bytes:
        # We make sure that all the bytes after are in fact zeros
        padding = pixel_bytearray[expected_length_bytes:]
        if numpy.any(numpy.frombuffer(padding, numpy.byte)):
            pixel_bytearray = pixel_bytearray[:expected_length_bytes]
        else:
            # We revert to the old behavior which should then result
            #   in a Numpy error later on.
            pass

    numpy_dtype = pixel_dtype(ds)
    arr = numpy.frombuffer(pixel_bytearray, dtype=numpy_dtype)

    expected_length_pixels = get_expected_length(ds, "pixels")
    if arr.size != expected_length_pixels:
        raise AttributeError(
            f"Amount of pixel data {arr.size} does not match the "
            f"expected data {expected_length_pixels}"
        )

    tsyntax = ds.file_meta.TransferSyntaxUID
    if config.APPLY_J2K_CORRECTIONS and tsyntax in [JPEG2000, JPEG2000Lossless]:
        nr_frames = get_nr_frames(ds)
        codestream = next(generate_frames(ds.PixelData, number_of_frames=nr_frames))

        params = get_j2k_parameters(codestream)
        j2k_precision = cast(int, params.setdefault("precision", ds.BitsStored))
        j2k_sign = params.setdefault("is_signed", None)

        if not j2k_sign and ds.PixelRepresentation == 1:
            # Convert unsigned J2K data to 2's complement
            shift = cast(int, ds.BitsAllocated) - j2k_precision
            # Need a copy of the pixel module to avoid modifying the original
            pixel_module = deepcopy(ds.group_dataset(0x0028))
            pixel_module.PixelRepresentation = 0
            # Reinterpret values as unsigned values
            arr = arr.astype(pixel_dtype(pixel_module))
            # Bit shift so the sign bit ends up as the MSB
            numpy.left_shift(arr, shift, out=arr)
            # Reinterpret values as signed to match the dataset
            arr = arr.astype(numpy_dtype)
            # Bit shift back to the original position, which maintains the
            #   sign bit but sets the pixel value back to the original
            numpy.right_shift(arr, shift, out=arr)

    if should_change_PhotometricInterpretation_to_RGB(ds):
        ds.PhotometricInterpretation = "RGB"

    return cast("numpy.ndarray", arr.copy())
