"""Use the `pylibjpeg <https://github.com/pydicom/pylibjpeg/>`_ package
to convert supported pixel data to a :class:`numpy.ndarray`.

**Supported data**

The numpy handler supports the conversion of data in the (7FE0,0010)
*Pixel Data* elements to a :class:`~numpy.ndarray` provided the
related :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module elements have
values given in the table below.

+------------------------------------------------+---------------+----------+
| Element                                        | Supported     |          |
+-------------+---------------------------+------+ values        |          |
| Tag         | Keyword                   | Type |               |          |
+=============+===========================+======+===============+==========+
| (0028,0002) | SamplesPerPixel           | 1    | 1, 3          | Required |
+-------------+---------------------------+------+---------------+----------+
| (0028,0004) | PhotometricInterpretation | 1    | MONOCHROME1,  | Required |
|             |                           |      | MONOCHROME2,  |          |
|             |                           |      | RGB,          |          |
|             |                           |      | YBR_FULL,     |          |
|             |                           |      | YBR_FULL_422  |          |
+-------------+---------------------------+------+---------------+----------+
| (0028,0006) | PlanarConfiguration       | 1C   | 0, 1          | Optional |
+-------------+---------------------------+------+---------------+----------+
| (0028,0008) | NumberOfFrames            | 1C   | N             | Optional |
+-------------+---------------------------+------+---------------+----------+
| (0028,0010) | Rows                      | 1    | N             | Required |
+-------------+---------------------------+------+---------------+----------+
| (0028,0011) | Columns                   | 1    | N             | Required |
+-------------+---------------------------+------+---------------+----------+
| (0028,0100) | BitsAllocated             | 1    | 8, 16         | Required |
+-------------+---------------------------+------+---------------+----------+
| (0028,0103) | PixelRepresentation       | 1    | 0, 1          | Required |
+-------------+---------------------------+------+---------------+----------+

"""

import logging

try:
    import numpy as np
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

try:
    import pylibjpeg
    from pylibjpeg.pydicom.utils import get_pixel_data_decoders
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

from pydicom.encaps import generate_pixel_data_frame
from pydicom.pixel_data_handlers.util import (
    pixel_dtype, get_expected_length, reshape_pixel_array
)
from pydicom.uid import (
    JPEGBaseline,
    JPEGExtended,
    JPEGLosslessP14,
    JPEGLossless,
    JPEGLSLossless,
    JPEGLSLossy,
    JPEG2000Lossless,
    JPEG2000
)


LOGGER = logging.getLogger(__name__)


HANDLER_NAME = 'pylibjpeg'
if HAVE_PYLIBJPEG:
    _DECODERS = get_pixel_data_decoders()

_LIBJPEG_SYNTAXES = [
    JPEGBaseline,
    JPEGExtended,
    JPEGLosslessP14,
    JPEGLossless,
    JPEGLSLossless,
    JPEGLSLossy
]
_OPENJPEG_SYNTAXES = [JPEG2000Lossless, JPEG2000]
SUPPORTED_TRANSFER_SYNTAXES = _LIBJPEG_SYNTAXES + _OPENJPEG_SYNTAXES

DEPENDENCIES = {
    'numpy': ('http://www.numpy.org/', 'NumPy'),
}


def is_available():
    """Return ``True`` if the handler has its dependencies met."""
    return HAVE_NP and HAVE_PYLIBJPEG


def supports_transfer_syntax(tsyntax):
    """Return ``True`` if the handler supports the `tsyntax`.

    Parameters
    ----------
    tsyntax : pydicom.uid.UID
        The *Transfer Syntax UID* of the *Pixel Data* that is to be used with
        the handler.
    """
    return tsyntax in SUPPORTED_TRANSFER_SYNTAXES


def needs_to_convert_to_RGB(ds):
    """Return ``True`` if the *Pixel Data* should to be converted from YCbCr to
    RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def should_change_PhotometricInterpretation_to_RGB(ds):
    """Return ``True`` if the *Photometric Interpretation* should be changed
    to RGB.

    This affects JPEG transfer syntaxes.
    """
    return False


def as_array(ds):
    """Return the entire *Pixel Data* as an :class:`~numpy.ndarray`.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The :class:`Dataset` containing an :dcm:`Image Pixel
        <part03/sect_C.7.6.3.html>` module and the *Pixel Data* to be
        converted.

    Returns
    -------
    numpy.ndarray
        The contents of (7FE0,0010) *Pixel Data* as an ndarray with shape
        (rows, columns), (rows, columns, components), (frames, rows, columns),
        or (frames, rows, columns, components) depending on the dataset.
    """
    return reshape_pixel_array(ds, get_pixeldata(ds))


def generate_frames(ds):
    """Yield a *Pixel Data* frame from `ds` as an :class:`~numpy.ndarray`.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The :class:`Dataset` containing an :dcm:`Image Pixel
        <part03/sect_C.7.6.3.html>` module and the *Pixel Data* to be
        converted.

    Yields
    -------
    numpy.ndarray
        A single frame of (7FE0,0010) *Pixel Data* as an ndarray with
        shape (rows, columns) or (rows, columns, components), depending
        on the dataset.
    """
    tsyntax = ds.file_meta.TransferSyntaxUID
    # The check of transfer syntax must be first
    if tsyntax not in _DECODERS:
        if tsyntax in _OPENJPEG_SYNTAXES:
            plugin = 'pylibjpeg-openjpeg'
        else:
            plugin = 'pylibjpeg-libjpeg'

        raise NotImplementedError(
            f"Unable to convert the Pixel Data as the {plugin} plugin is "
            f"not installed"
        )

    # Check required elements
    required_elements = [
        'BitsAllocated', 'Rows', 'Columns', 'PixelRepresentation',
        'SamplesPerPixel', 'PhotometricInterpretation', 'PixelData',
    ]
    missing = [elem for elem in required_elements if elem not in ds]
    if missing:
        raise AttributeError(
            "Unable to convert the pixel data as the following required "
            "elements are missing from the dataset: " + ", ".join(missing)
        )

    decoder = _DECODERS[tsyntax]
    LOGGER.debug(f"Decoding {tsyntax.name} encoded Pixel Data using {decoder}")

    nr_frames = getattr(ds, 'NumberOfFrames', 1)
    image_px_module = ds.group_dataset(0x0028)
    dtype = pixel_dtype(ds)
    for frame in generate_pixel_data_frame(ds.PixelData, nr_frames):
        arr = decoder(frame, image_px_module)

        # View and reshape as pylibjpeg returns a 1D uint8 ndarray
        arr = arr.view(dtype)

        if ds.SamplesPerPixel == 1:
            yield arr.reshape(ds.Rows, ds.Columns)

        if planar_configuration == 0:
            yield arr.reshape(ds.Rows, ds.Columns, ds.SamplesPerPixel)

        arr = arr.reshape(ds.SamplesPerPixel, ds.Rows, ds.Columns)
        yield arr.transpose(1, 2, 0)


def get_pixeldata(ds):
    """Return a :class:`numpy.ndarray` of the pixel data.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The :class:`Dataset` containing an :dcm:`Image Pixel
        <part03/sect_C.7.6.3.html>` module and the *Pixel Data* to be
        converted.

    Returns
    -------
    numpy.ndarray
        The contents of (7FE0,0010) *Pixel Data* as a 1D array.

    Raises
    ------
    AttributeError
        If `ds` is missing a required element.
    NotImplementedError
        If `ds` contains pixel data in an unsupported format.
    ValueError
        If the actual length of the pixel data doesn't match the expected
        length.
    """
    tsyntax = ds.file_meta.TransferSyntaxUID
    # The check of transfer syntax must be first
    if tsyntax not in _DECODERS:
        if tsyntax in _OPENJPEG_SYNTAXES:
            plugin = 'pylibjpeg-openjpeg'
        else:
            plugin = 'pylibjpeg-libjpeg'

        raise NotImplementedError(
            f"Unable to convert the Pixel Data as the {plugin} plugin is "
            f"not installed"
        )

    # Check required elements
    required_elements = [
        'BitsAllocated', 'Rows', 'Columns', 'PixelRepresentation',
        'SamplesPerPixel', 'PhotometricInterpretation', 'PixelData',
    ]
    missing = [elem for elem in required_elements if elem not in ds]
    if missing:
        raise AttributeError(
            "Unable to convert the pixel data as the following required "
            "elements are missing from the dataset: " + ", ".join(missing)
        )

    # Calculate the expected length of the pixel data (in bytes)
    #   Note: this does NOT include the trailing null byte for odd length data
    expected_len = get_expected_length(ds)
    if ds.PhotometricInterpretation == 'YBR_FULL_422':
        # JPEG Transfer Syntaxes
        # Plugin should have already resampled the pixel data
        #   see PS3.3 C.7.6.3.1.2
        expected_len = expected_len // 2 * 3

    p_interp = ds.PhotometricInterpretation

    # How long each frame is in bytes
    nr_frames = getattr(ds, 'NumberOfFrames', 1)
    frame_len = expected_len // nr_frames

    # The decoded data will be placed here
    arr = np.empty(expected_len, np.uint8)

    decoder = _DECODERS[tsyntax]
    LOGGER.debug(f"Decoding {tsyntax.name} encoded Pixel Data using {decoder}")

    # Generators for the encoded JPEG image frame(s) and insertion offsets
    generate_frames = generate_pixel_data_frame(ds.PixelData, nr_frames)
    generate_offsets = range(0, expected_len, frame_len)
    for frame, offset in zip(generate_frames, generate_offsets):
        # Encoded JPEG data to be sent to the decoder
        arr[offset:offset + frame_len] = decoder(
            frame, ds.group_dataset(0x0028)
        )

    return arr.view(pixel_dtype(ds))
