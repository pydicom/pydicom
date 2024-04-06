# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Utilities for pixel data handling."""

from collections.abc import Iterable, Iterator, ByteString
import importlib
import logging
from pathlib import Path
from os import PathLike
from struct import unpack, Struct
from sys import byteorder
from typing import BinaryIO, Any, cast, TYPE_CHECKING

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.charset import default_encoding
from pydicom._dicom_dict import DicomDictionary

from pydicom.misc import warn_and_log
from pydicom.tag import BaseTag
from pydicom.uid import UID

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset


LOGGER = logging.getLogger(__name__)

# All non-retired group 0x0028 elements
_GROUP_0028 = {
    k for k, v in DicomDictionary.items() if k >> 16 == 0x0028 and v[3] == ""
}
# The minimum required Image Pixel module elements used by encoding/decoding
_IMAGE_PIXEL = {
    0x00280002: "samples_per_pixel",
    0x00280004: "photometric_interpretation",
    0x00280006: "planar_configuration",
    0x00280008: "number_of_frames",
    0x00280010: "rows",
    0x00280011: "columns",
    0x00280100: "bits_allocated",
    0x00280101: "bits_stored",
    0x00280103: "pixel_representation",
}
# Default tags to look for with pixel_array() and iter_pixels()
_DEFAULT_TAGS = {k for k in _IMAGE_PIXEL.keys()} | {0x7FE00001, 0x7FE00002}
_PIXEL_KEYWORDS = {
    (0x7FE0, 0x0008): "FloatPixelData",
    (0x7FE0, 0x0009): "DoubleFloatPixelData",
    (0x7FE0, 0x0010): "PixelData",
}
# Lookup table for unpacking bit-packed data
_UNPACK_LUT: dict[int, bytes] = {
    k: bytes(int(s) for s in reversed(f"{k:08b}")) for k in range(256)
}

# JPEG/JPEG-LS SOF markers
_SOF = {
    b"\xFF\xC0",
    b"\xFF\xC1",
    b"\xFF\xC2",
    b"\xFF\xC3",
    b"\xFF\xC5",
    b"\xFF\xC6",
    b"\xFF\xC7",
    b"\xFF\xC9",
    b"\xFF\xCA",
    b"\xFF\xCB",
    b"\xFF\xCD",
    b"\xFF\xCE",
    b"\xFF\xCF",
    b"\xFF\xF7",
}
# JPEG APP markers, all in range (0xFFE0, 0xFFEF)
_APP = {x.to_bytes(length=2, byteorder="big") for x in range(0xFFE0, 0xFFF0)}
_UNPACK_SHORT = Struct(">H").unpack


def _array_common(
    f: BinaryIO, specific_tags: list[BaseTag | int], **kwargs: Any
) -> tuple["Dataset", dict[str, Any]]:
    """Return a dataset from `f` and a corresponding decoding options dict.

    Parameters
    ----------
    f : BinaryIO
        The opened file-like containing the DICOM dataset, positioned at the
        start of the file.
    specific_tags : list[BaseTag | int]
        A list of additional tags to be read from the dataset and possibly
        returned via the `ds_out` dataset.
    kwargs : dict[str, Any]
        Required and optional arguments for the pixel data decoding functions.

    Returns
    -------
    tuple[Dataset, dict[str, Any]]

        * A dataset containing the group 0x0028 elements, the extended offset
          elements (if any) and elements from `specific_tags`.
        * The required and optional arguments for the pixel data decoding
          functions.
    """
    from pydicom.filereader import (
        read_preamble,
        _read_file_meta_info,
        read_dataset,
        _at_pixel_data,
    )

    # Read preamble (if present)
    read_preamble(f, force=True)

    # Read the File Meta (if present)
    file_meta = _read_file_meta_info(f)
    tsyntax = kwargs.setdefault(
        "transfer_syntax_uid",
        file_meta.get("TransferSyntaxUID", None),
    )
    if not tsyntax:
        raise AttributeError(
            "'transfer_syntax_uid' is required if the dataset in 'src' is not "
            "in the DICOM File Format"
        )

    tsyntax = UID(tsyntax)

    # Get the *Image Pixel* module 0028 elements, any extended offsets and
    #   any other tags wanted by the user
    ds = read_dataset(
        f,
        is_implicit_VR=tsyntax.is_implicit_VR,
        is_little_endian=tsyntax.is_little_endian,
        stop_when=_at_pixel_data,
        specific_tags=specific_tags,
    )
    ds.file_meta = file_meta

    opts = as_pixel_options(ds, **kwargs)
    opts["transfer_syntax_uid"] = tsyntax

    # We are either at the start of the element tag for a pixel data
    #   element or at EOF because there were none
    try:
        data = f.read(8)
        assert len(data) == 8
    except Exception:
        raise AttributeError(
            "The dataset in 'src' has no 'Pixel Data', 'Float Pixel Data' or "
            "'Double Float Pixel Data' element, no pixel data to decode"
        )

    endianness = "><"[tsyntax.is_little_endian]
    if tsyntax.is_implicit_VR:
        vr = None
        group, elem, length = unpack(f"{endianness}HHL", data)
    else:
        # Is always 32-bit extended length for pixel data VRs
        group, elem, vr, length = unpack(f"{endianness}HH2sH", data)
        opts["pixel_vr"] = vr.decode(default_encoding)
        unpack(f"{endianness}L", f.read(4))

    # We should now be positioned at the start of the pixel data value
    opts["pixel_keyword"] = _PIXEL_KEYWORDS[(group, elem)]

    return ds, opts


def as_pixel_options(ds: "Dataset", **kwargs: Any) -> dict[str, Any]:
    """Return a dict containing the image pixel element values from `ds`.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        A dataset containing Image Pixel module elements.
    **kwargs
        A :class:`dict` containing (key, value) pairs to be used to override the
        values taken from `ds`. For example, if ``kwargs = {'rows': 64}`` then
        the returned :class:`dict` will have a 'rows' value of 64 rather than
        whatever ``ds.Rows`` may be.

    Returns
    -------
    dict[str, Any]
        A dictionary which may contain the following keys, depending on which
        elements are present in `ds` and the contents of `kwargs`:

        * `samples_per_pixel`
        * `photometric_interpretation`
        * `planar_configuration`
        * `number_of_frames` (always present)
        * `rows`
        * `columns`
        * `bits_allocated`
        * `bits_stored`
        * `pixel_representation`
    """
    opts = {
        attr: ds[tag].value for tag, attr in _IMAGE_PIXEL.items() if tag in ds._dict
    }

    # Ensure we have a valid 'number_of_frames'
    if 0x00280008 not in ds._dict:
        opts["number_of_frames"] = 1

    nr_frames = opts["number_of_frames"]
    nr_frames = int(nr_frames) if isinstance(nr_frames, str) else nr_frames
    opts["number_of_frames"] = 1 if nr_frames in (None, 0) else nr_frames

    # Extended Offset Table
    if 0x7FE00001 in ds._dict and 0x7FE00001 in ds._dict:
        opts["extended_offsets"] = (
            ds.ExtendedOffsetTable,
            ds.ExtendedOffsetTableLengths,
        )

    opts.update(kwargs)

    return opts


def expand_ybr422(src: ByteString, bits_allocated: int) -> bytes:
    """Return ``YBR_FULL_422`` data expanded to ``YBR_FULL``.

    Uncompressed datasets with a (0028,0004) *Photometric Interpretation* of
    ``"YBR_FULL_422"`` are subsampled in the horizontal direction by halving
    the number of Cb and Cr pixels (i.e. there are two Y pixels for every Cb
    and Cr pixel). This function expands the ``YBR_FULL_422`` data to remove
    the subsampling and the output is therefore ``YBR_FULL``.

    Parameters
    ----------
    src : bytes or bytearray
        The YBR_FULL_422 pixel data to be expanded.
    bits_allocated : int
        The number of bits used to store each pixel, as given by (0028,0100)
        *Bits Allocated*.

    Returns
    -------
    bytes
        The expanded data (as YBR_FULL).
    """
    # YBR_FULL_422 is Y Y Cb Cr (i.e. 2 Y pixels for every Cb and Cr pixel)
    n_bytes = bits_allocated // 8
    length = len(src) // 2 * 3
    dst = bytearray(length)

    step_src = n_bytes * 4
    step_dst = n_bytes * 6
    for ii in range(n_bytes):
        c_b = src[2 * n_bytes + ii :: step_src]
        c_r = src[3 * n_bytes + ii :: step_src]

        dst[0 * n_bytes + ii :: step_dst] = src[0 * n_bytes + ii :: step_src]
        dst[1 * n_bytes + ii :: step_dst] = c_b
        dst[2 * n_bytes + ii :: step_dst] = c_r

        dst[3 * n_bytes + ii :: step_dst] = src[1 * n_bytes + ii :: step_src]
        dst[4 * n_bytes + ii :: step_dst] = c_b
        dst[5 * n_bytes + ii :: step_dst] = c_r

    return bytes(dst)


def get_expected_length(ds: "Dataset", unit: str = "bytes") -> int:
    """Return the expected length (in terms of bytes or pixels) of the *Pixel
    Data*.

    +------------------------------------------------+-------------+
    | Element                                        | Required or |
    +-------------+---------------------------+------+ optional    |
    | Tag         | Keyword                   | Type |             |
    +=============+===========================+======+=============+
    | (0028,0002) | SamplesPerPixel           | 1    | Required    |
    +-------------+---------------------------+------+-------------+
    | (0028,0004) | PhotometricInterpretation | 1    | Required    |
    +-------------+---------------------------+------+-------------+
    | (0028,0008) | NumberOfFrames            | 1C   | Optional    |
    +-------------+---------------------------+------+-------------+
    | (0028,0010) | Rows                      | 1    | Required    |
    +-------------+---------------------------+------+-------------+
    | (0028,0011) | Columns                   | 1    | Required    |
    +-------------+---------------------------+------+-------------+
    | (0028,0100) | BitsAllocated             | 1    | Required    |
    +-------------+---------------------------+------+-------------+

    Parameters
    ----------
    ds : Dataset
        The :class:`~pydicom.dataset.Dataset` containing the Image Pixel module
        and *Pixel Data*.
    unit : str, optional
        If ``'bytes'`` then returns the expected length of the *Pixel Data* in
        whole bytes and NOT including an odd length trailing NULL padding
        byte. If ``'pixels'`` then returns the expected length of the *Pixel
        Data* in terms of the total number of pixels (default ``'bytes'``).

    Returns
    -------
    int
        The expected length of the *Pixel Data* in either whole bytes or
        pixels, excluding the NULL trailing padding byte for odd length data.
    """
    rows = cast(int, ds.Rows)
    columns = cast(int, ds.Columns)
    samples_per_pixel = cast(int, ds.SamplesPerPixel)
    bits_allocated = cast(int, ds.BitsAllocated)

    length = rows * columns * samples_per_pixel
    length *= get_nr_frames(ds)

    if unit == "pixels":
        return length

    # Correct for the number of bytes per pixel
    if bits_allocated == 1:
        # Determine the nearest whole number of bytes needed to contain
        #   1-bit pixel data. e.g. 10 x 10 1-bit pixels is 100 bits, which
        #   are packed into 12.5 -> 13 bytes
        length = length // 8 + (length % 8 > 0)
    else:
        length *= bits_allocated // 8

    # DICOM Standard, Part 4, Annex C.7.6.3.1.2
    if ds.PhotometricInterpretation == "YBR_FULL_422":
        length = length // 3 * 2

    return length


def get_image_pixel_ids(ds: "Dataset") -> dict[str, int]:
    """Return a dict of the pixel data affecting element's :func:`id` values.

    +------------------------------------------------+
    | Element                                        |
    +-------------+---------------------------+------+
    | Tag         | Keyword                   | Type |
    +=============+===========================+======+
    | (0028,0002) | SamplesPerPixel           | 1    |
    +-------------+---------------------------+------+
    | (0028,0004) | PhotometricInterpretation | 1    |
    +-------------+---------------------------+------+
    | (0028,0006) | PlanarConfiguration       | 1C   |
    +-------------+---------------------------+------+
    | (0028,0008) | NumberOfFrames            | 1C   |
    +-------------+---------------------------+------+
    | (0028,0010) | Rows                      | 1    |
    +-------------+---------------------------+------+
    | (0028,0011) | Columns                   | 1    |
    +-------------+---------------------------+------+
    | (0028,0100) | BitsAllocated             | 1    |
    +-------------+---------------------------+------+
    | (0028,0101) | BitsStored                | 1    |
    +-------------+---------------------------+------+
    | (0028,0103) | PixelRepresentation       | 1    |
    +-------------+---------------------------+------+
    | (7FE0,0008) | FloatPixelData            | 1C   |
    +-------------+---------------------------+------+
    | (7FE0,0009) | DoubleFloatPixelData      | 1C   |
    +-------------+---------------------------+------+
    | (7FE0,0010) | PixelData                 | 1C   |
    +-------------+---------------------------+------+

    Parameters
    ----------
    ds : Dataset
        The :class:`~pydicom.dataset.Dataset` containing the pixel data.

    Returns
    -------
    dict
        A dict containing the :func:`id` values for the elements that affect
        the pixel data.

    """
    keywords = [
        "SamplesPerPixel",
        "PhotometricInterpretation",
        "PlanarConfiguration",
        "NumberOfFrames",
        "Rows",
        "Columns",
        "BitsAllocated",
        "BitsStored",
        "PixelRepresentation",
        "FloatPixelData",
        "DoubleFloatPixelData",
        "PixelData",
    ]

    return {kw: id(getattr(ds, kw, None)) for kw in keywords}


def get_j2k_parameters(codestream: bytes) -> dict[str, object]:
    """Return a dict containing JPEG 2000 component parameters.

    .. versionadded:: 2.1

    Parameters
    ----------
    codestream : bytes
        The JPEG 2000 (ISO/IEC 15444-1) codestream to be parsed.

    Returns
    -------
    dict
        A dict containing parameters for the first component sample in the
        JPEG 2000 `codestream`, or an empty dict if unable to parse the data.
        Available parameters are ``{"precision": int, "is_signed": bool}``.
    """
    try:
        # First 2 bytes must be the SOC marker - if not then wrong format
        if codestream[0:2] != b"\xff\x4f":
            return {}

        # SIZ is required to be the second marker - Figure A-3 in 15444-1
        if codestream[2:4] != b"\xff\x51":
            return {}

        # See 15444-1 A.5.1 for format of the SIZ box and contents
        ssiz = codestream[42]
        if ssiz & 0x80:
            return {"precision": (ssiz & 0x7F) + 1, "is_signed": True}

        return {"precision": ssiz + 1, "is_signed": False}
    except (IndexError, TypeError):
        pass

    return {}


def _get_jpg_parameters(src: bytes) -> dict[str, Any]:
    """Return a dict containing JPEG or JPEG-LS encoding parameters.

    Parameters
    ----------
    src : bytes
        The JPEG (ISO/IEC 10918-1) or JPEG-LS (ISO/IEC 14495-1) codestream to
        be parsed.

    Returns
    -------
    dict[str, int | dict[bytes, bytes] | list[int]]
        A dict containing JPEG or JPEG-LS encoding parameters or an empty dict
        if unable to parse the data. Available parameters are:

        * ``precision``: int
        * ``height``: int
        * ``width``: int
        * ``components``: int
        * ``component_ids``: list[int]
        * ``app``: dict[bytes: bytes]
        * ``interleave_mode``: int, JPEG-LS only
        * ``lossy_error``: int, JPEG-LS only
    """
    info: dict[str, Any] = {}
    try:
        # First 2 bytes should be the SOI marker - otherwise wrong format
        #   or non-conformant (JFIF or SPIFF header)
        if src[0:2] != b"\xFF\xD8":
            return info

        # Skip to the SOF0 to SOF15 (JPEG) or SOF55 (JPEG-LS) marker
        # We skip through any other segments except APP as they sometimes
        #   contain color space information (such as Adobe's APP14)
        offset = 2
        app_markers = {}
        while (marker := src[offset : offset + 2]) not in _SOF:
            length = _UNPACK_SHORT(src[offset + 2 : offset + 4])[0]
            if marker in _APP:
                # `length` counts from the first byte of the APP length
                app_markers[marker] = src[offset + 4 : offset + 2 + length]

            offset += length + 2  # at the start of the next marker

        if app_markers:
            info["app"] = app_markers

        # SOF segment layout is identical for JPEG and JPEG-LS
        #   2 byte SOF marker
        #   2 bytes header length
        #   1 byte precision (bits stored)
        #   2 bytes rows
        #   2 bytes columns
        #   1 byte number of components in frame (samples per pixel)
        #   for _ in range(number of components):
        #       1 byte component ID
        #       4/4 bits horizontal/vertical sampling factors
        #       1 byte table selector
        offset += 2  # at the start of the SOF length
        info["precision"] = src[offset + 2]
        info["height"] = _UNPACK_SHORT(src[offset + 3 : offset + 5])[0]
        info["width"] = _UNPACK_SHORT(src[offset + 5 : offset + 7])[0]
        info["components"] = src[offset + 7]

        # Parse the component IDs - these are sometimes used to denote the color
        #   space of the input by using ASCII codes for the IDs (such as R G B)
        offset += 8  # start of the component IDs
        info["component_ids"] = []
        for _ in range(info["components"]):
            info["component_ids"].append(src[offset])
            offset += 3

        # `offset` is at the start of the next marker

        # If JPEG then return
        if marker != b"\xFF\xF7":
            return info

        # Skip to the SOS marker
        while src[offset : offset + 2] != b"\xFF\xDA":
            offset += _UNPACK_SHORT(src[offset + 2 : offset + 4])[0] + 2

        # `offset` is at the start of the SOS marker

        # SOS segment layout is the same for JPEG and JPEG-LS
        #   2 byte SOS marker
        #   2 bytes header length
        #   1 byte number of components in scan
        #   for _ in range(number of components):
        #       1 byte scan component ID selector
        #       4/4 bits DC/AC entropy table selectors
        #   1 byte start spectral selector (JPEG) or NEAR (JPEG-LS)
        #   1 byte end spectral selector (JPEG) or ILV (JPEG-LS)
        #   4/4 bits approx bit high/low
        offset += 5 + src[offset + 4] * 2
        info["lossy_error"] = src[offset]
        info["interleave_mode"] = src[offset + 1]
    except Exception:
        return {}

    return info


def get_nr_frames(ds: "Dataset", warn: bool = True) -> int:
    """Return NumberOfFrames or 1 if NumberOfFrames is None or 0.

    Parameters
    ----------
    ds : dataset.Dataset
        The :class:`~pydicom.dataset.Dataset` containing the Image Pixel module
        corresponding to the data in `arr`.
    warn : bool
        If ``True`` (the default), a warning is issued if NumberOfFrames
        has an invalid value.

    Returns
    -------
    int
        An integer for the NumberOfFrames or 1 if NumberOfFrames is None or 0
    """
    nr_frames: int | None = getattr(ds, "NumberOfFrames", 1)
    # 'NumberOfFrames' may exist in the DICOM file but have value equal to None
    if not nr_frames:  # None or 0
        if warn:
            warn_and_log(
                f"A value of {nr_frames} for (0028,0008) 'Number of Frames' is "
                "non-conformant. It's recommended that this value be "
                "changed to 1"
            )
        nr_frames = 1

    return nr_frames


def iter_pixels(
    src: str | PathLike[str] | BinaryIO,
    *,
    ds_out: "Dataset | None" = None,
    specific_tags: list[BaseTag | int] | None = None,
    indices: Iterable[int] | None = None,
    raw: bool = False,
    decoding_plugin: str = "",
    **kwargs: Any,
) -> Iterator["np.ndarray"]:
    """Yield decoded pixel data frames from `src` as :class:`~numpy.ndarray`
    while minimizing memory usage.

    .. warning::

        This function requires `NumPy <https://numpy.org/>`_

    **Processing**

    The following processing operations on the raw pixel data are always
    performed:

    * Natively encoded bit-packed pixel data for a :ref:`bits allocated
      <bits_allocated>` of ``1`` will be unpacked.
    * Natively encoded pixel data with a :ref:`photometric interpretation
      <photometric_interpretation>` of ``"YBR_FULL_422"`` will
      have it's sub-sampling removed.
    * The output array will be reshaped to the specified dimensions.
    * JPEG-LS or JPEG 2000 encoded data whose signedness doesn't match the
      expected :ref:`pixel representation<pixel_representation>` will be
      converted to match.

    If ``raw = False`` (the default) then the following processing operation
    will also be performed:

    * Pixel data with a :ref:`photometric interpretation
      <photometric_interpretation>` of ``"YBR_FULL"`` or
      ``"YBR_FULL_422"`` will be converted to ``"RGB"``.

    Examples
    --------
    Iterate through all the pixel data frames in a dataset::

        for arr in iter_pixels("dataset.dcm"):
            print(arr.shape)

    Iterate through the even frames for a dataset with 10 frames::

        with open("dataset.dcm", "rb") as f:
            for arr in iter_pixels(f, indices=range(0, 10, 2)):
                print(arr.shape)

    Parameters
    ----------
    src : str | PathLike[str] | file-like

        * :class:`str` | :class:`os.PathLike`: the path to a DICOM dataset
          containing pixel data, or
        * file-like: a `file-like object
          <https://docs.python.org/3/glossary.html#term-file-object>`_ in
          'rb' mode containing the dataset.
    ds_out : pydicom.dataset.Dataset, optional
        A :class:`~pydicom.dataset.Dataset` that will be updated with the
        non-retired group ``0x0028`` image pixel module elements and the group
        ``0x0002`` file meta information elements from the dataset in `src` .
    specific_tags : list[int | pydicom.tag.BaseTag], optional
        A list of additional tags from the dataset in `src` to be added to the
        `ds_out` dataset.
    indices : Iterable[int] | None, optional
        If ``None`` (default) then iterate through the entire pixel data,
        otherwise only iterate through the frames specified by `indices`.
    raw : bool, optional
        If ``True`` then yield the decoded pixel data after only
        minimal processing (see the processing section above). If ``False``
        (default) then additional processing may be applied to convert the
        pixel data to it's most commonly used form (such as converting from
        YCbCr to RGB).
    decoding_plugin : str, optional
        The name of the decoding plugin to use when decoding compressed
        pixel data. If no `decoding_plugin` is specified (default) then all
        available plugins will be tried and the result from the first successful
        one yielded. For information on the available plugins for each
        decoder see the :doc:`API documentation</reference/pixels.decoders>`.
    **kwargs
        Optional keyword parameters for controlling decoding are also
        available, please see the :doc:`decoding options documentation
        </guides/decoding/decoder_options>` for more information.

    Yields
    -------
    numpy.ndarray
        The decoded and reshaped pixel data, with shape:

        * (rows, columns) for single plane data
        * (rows, columns, planes) for multi-plane data

        A writeable :class:`~numpy.ndarray` is yielded by default. For
        native transfer syntaxes with ``view_only=True`` a read-only
        :class:`~numpy.ndarray` will be yielded.
    """
    from pydicom.dataset import Dataset
    from pydicom.pixels import get_decoder

    f: BinaryIO
    if not hasattr(src, "read"):
        path = Path(src).resolve(strict=True)
        f = path.open("rb")
    else:
        f = cast(BinaryIO, src)
        file_offset = f.tell()
        f.seek(0)

    tags = _DEFAULT_TAGS
    if ds_out is not None:
        tags = set(specific_tags) if specific_tags else set()
        tags = tags | _GROUP_0028 | {0x7FE00001, 0x7FE00002}

    try:
        ds, opts = _array_common(f, list(tags), **kwargs)

        if isinstance(ds_out, Dataset):
            ds_out.file_meta = ds.file_meta
            ds_out.set_original_encoding(*ds.original_encoding)
            ds_out._dict.update(ds._dict)

        decoder = get_decoder(opts["transfer_syntax_uid"])
        yield from decoder.iter_array(
            f,
            indices=indices,
            validate=True,
            raw=raw,
            decoding_plugin=decoding_plugin,
            **opts,
        )
    finally:
        # Close the open file only if we were the ones that opened it
        if not hasattr(src, "read"):
            f.close()
        else:
            f.seek(file_offset)


def pack_bits(arr: "np.ndarray", pad: bool = True) -> bytes:
    """Pack a binary :class:`numpy.ndarray` for use with *Pixel Data*.

    Should be used in conjunction with (0028,0100) *Bits Allocated* = 1.

    .. versionchanged:: 2.1

        Added the `pad` keyword parameter and changed to allow `arr` to be
        2 or 3D.

    Parameters
    ----------
    arr : numpy.ndarray
        The :class:`numpy.ndarray` containing 1-bit data as ints. `arr` must
        only contain integer values of 0 and 1 and must have an 'uint'  or
        'int' :class:`numpy.dtype`. For the sake of efficiency it's recommended
        that the length of `arr` be a multiple of 8 (i.e. that any empty
        bit-padding to round out the byte has already been added). The input
        `arr` should either be shaped as (rows, columns) or (frames, rows,
        columns) or the equivalent 1D array used to ensure that the packed
        data is in the correct order.
    pad : bool, optional
        If ``True`` (default) then add a null byte to the end of the packed
        data to ensure even length, otherwise no padding will be added.

    Returns
    -------
    bytes
        The bit packed data.

    Raises
    ------
    ValueError
        If `arr` contains anything other than 0 or 1.

    References
    ----------
    DICOM Standard, Part 5,
    :dcm:`Section 8.1.1<part05/chapter_8.html#sect_8.1.1>` and
    :dcm:`Annex D<part05/chapter_D.html>`
    """
    if arr.shape == (0,):
        return b""

    # Test array
    if not np.array_equal(arr, arr.astype(bool)):
        raise ValueError(
            "Only binary arrays (containing ones or zeroes) can be packed."
        )

    if len(arr.shape) > 1:
        arr = arr.ravel()

    # The array length must be a multiple of 8, pad the end
    if arr.shape[0] % 8:
        arr = np.append(arr, np.zeros(8 - arr.shape[0] % 8))

    arr = np.packbits(arr.astype("u1"), bitorder="little")

    packed: bytes = arr.tobytes()
    if pad:
        return packed + b"\x00" if len(packed) % 2 else packed

    return packed


def _passes_version_check(package_name: str, minimum_version: tuple[int, ...]) -> bool:
    """Return True if `package_name` is available and its version is greater or
    equal to `minimum_version`
    """
    try:
        module = importlib.import_module(package_name, "__version__")
        return tuple(int(x) for x in module.__version__.split(".")) >= minimum_version
    except Exception as exc:
        LOGGER.exception(exc)

    return False


def pixel_array(
    src: str | PathLike[str] | BinaryIO,
    *,
    ds_out: "Dataset | None" = None,
    specific_tags: list[int] | None = None,
    index: int | None = None,
    raw: bool = False,
    decoding_plugin: str = "",
    **kwargs: Any,
) -> "np.ndarray":
    """Return decoded pixel data from `src` as :class:`~numpy.ndarray` while
    minimizing memory usage.

    .. warning::

        This function requires `NumPy <https://numpy.org/>`_

    **Processing**

    The following processing operations on the raw pixel data are always
    performed:

    * Natively encoded bit-packed pixel data for a :ref:`bits allocated
      <bits_allocated>` of ``1`` will be unpacked.
    * Natively encoded pixel data with a :ref:`photometric interpretation
      <photometric_interpretation>` of ``"YBR_FULL_422"`` will
      have it's sub-sampling removed.
    * The output array will be reshaped to the specified dimensions.
    * JPEG-LS or JPEG 2000 encoded data whose signedness doesn't match the
      expected :ref:`pixel representation<pixel_representation>` will be
      converted to match.

    If ``raw = False`` (the default) then the following processing operation
    will also be performed:

    * Pixel data with a :ref:`photometric interpretation
      <photometric_interpretation>` of ``"YBR_FULL"`` or
      ``"YBR_FULL_422"`` will be converted to RGB.

    Examples
    --------

    Return the entire pixel data from a dataset::

        arr = pixel_array("path/to/dataset.dcm")

    Return the 3rd frame of a dataset containing at least 3 frames::

        with open("path/to/dataset.dcm", "rb") as f:
            arr = pixel_array(f, index=2)  # 'index' starts at 0

    Parameters
    ----------
    src : str | PathLike[str] | file-like

        * :class:`str` | :class:`os.PathLike`: the path to a DICOM dataset
          containing pixel data, or
        * file-like: a `file-like object
          <https://docs.python.org/3/glossary.html#term-file-object>`_ in
          'rb' mode containing the dataset.
    ds_out : pydicom.dataset.Dataset, optional
        A :class:`~pydicom.dataset.Dataset` that will be updated with the
        non-retired group ``0x0028`` image pixel module elements and the group
        ``0x0002`` file meta information elements from the dataset in `src` .
    specific_tags : list[int | pydicom.tag.BaseTag], optional
        A list of additional tags from the dataset in `src` to be added to the
        `ds_out` dataset.
    index : int | None, optional
        If ``None`` (default) then return an array containing all the
        frames in the pixel data, otherwise return only the frame from the
        specified `index`, which starts at 0 for the first frame.
    raw : bool, optional
        If ``True`` then return the decoded pixel data after only
        minimal processing (see the processing section above). If ``False``
        (default) then additional processing may be applied to convert the
        pixel data to it's most commonly used form (such as converting from
        YCbCr to RGB).
    decoding_plugin : str, optional
        The name of the decoding plugin to use when decoding compressed
        pixel data. If no `decoding_plugin` is specified (default) then all
        available plugins will be tried and the result from the first successful
        one returned. For information on the available plugins for each
        decoder see the :doc:`API documentation</reference/pixels.decoders>`.
    **kwargs
        Optional keyword parameters for controlling decoding, please see the
        :doc:`decoding options documentation</guides/decoding/decoder_options>`
        for more information.

    Returns
    -------
    numpy.ndarray
        The decoded and reshaped pixel data, with shape:

        * (rows, columns) for single frame, single plane data
        * (rows, columns, planes) for single frame, multi-plane data
        * (frames, rows, columns) for multi-frame, single plane data
        * (frames, rows, columns, planes) for multi-frame, multi-plane data

        A writeable :class:`~numpy.ndarray` is returned by default. For
        native transfer syntaxes with ``view_only=True`` a read-only
        :class:`~numpy.ndarray` will be returned.
    """
    from pydicom.dataset import Dataset
    from pydicom.pixels import get_decoder

    f: BinaryIO
    if not hasattr(src, "read"):
        path = Path(src).resolve(strict=True)
        f = path.open("rb")
    else:
        f = cast(BinaryIO, src)
        file_offset = f.tell()
        f.seek(0)

    tags = _DEFAULT_TAGS
    if ds_out is not None:
        tags = set(specific_tags) if specific_tags else set()
        tags = tags | _GROUP_0028 | {0x7FE00001, 0x7FE00002}

    try:
        ds, opts = _array_common(f, list(tags), **kwargs)

        decoder = get_decoder(opts["transfer_syntax_uid"])
        arr = decoder.as_array(
            f,
            index=index,
            validate=True,
            raw=raw,
            decoding_plugin=decoding_plugin,
            **opts,  # type: ignore[arg-type]
        )
    finally:
        # Close the open file only if we were the ones that opened it
        if not hasattr(src, "read"):
            f.close()
        else:
            f.seek(file_offset)

    if isinstance(ds_out, Dataset):
        ds_out.file_meta = ds.file_meta
        ds_out.set_original_encoding(*ds.original_encoding)
        ds_out._dict.update(ds._dict)

    return arr


def pixel_dtype(ds: "Dataset", as_float: bool = False) -> "np.dtype":
    """Return a :class:`numpy.dtype` for the pixel data in `ds`.

    Suitable for use with IODs containing the Image Pixel module (with
    ``as_float=False``) and the Floating Point Image Pixel and Double Floating
    Point Image Pixel modules (with ``as_float=True``).

    +------------------------------------------+------------------+
    | Element                                  | Supported        |
    +-------------+---------------------+------+ values           |
    | Tag         | Keyword             | Type |                  |
    +=============+=====================+======+==================+
    | (0028,0101) | BitsAllocated       | 1    | 1, 8, 16, 32, 64 |
    +-------------+---------------------+------+------------------+
    | (0028,0103) | PixelRepresentation | 1    | 0, 1             |
    +-------------+---------------------+------+------------------+

    Parameters
    ----------
    ds : Dataset
        The :class:`~pydicom.dataset.Dataset` containing the pixel data you
        wish to get the data type for.
    as_float : bool, optional
        If ``True`` then return a float dtype, otherwise return an integer
        dtype (default ``False``). Float dtypes are only supported when
        (0028,0101) *Bits Allocated* is 32 or 64.

    Returns
    -------
    numpy.dtype
        A :class:`numpy.dtype` suitable for containing the pixel data.

    Raises
    ------
    NotImplementedError
        If the pixel data is of a type that isn't supported by either numpy
        or *pydicom*.
    """
    if not HAVE_NP:
        raise ImportError("Numpy is required to determine the dtype.")

    # Prefer Transfer Syntax UID, fall back to the original encoding
    if hasattr(ds, "file_meta"):
        is_little_endian = ds.file_meta._tsyntax_encoding[1]
    else:
        is_little_endian = ds.original_encoding[1]

    if is_little_endian is None:
        raise AttributeError(
            "Unable to determine the endianness of the dataset, please set "
            "an appropriate Transfer Syntax UID in "
            f"'{type(ds).__name__}.file_meta'"
        )

    if not as_float:
        # (0028,0103) Pixel Representation, US, 1
        #   Data representation of the pixel samples
        #   0x0000 - unsigned int
        #   0x0001 - 2's complement (signed int)
        pixel_repr = cast(int, ds.PixelRepresentation)
        if pixel_repr == 0:
            dtype_str = "uint"
        elif pixel_repr == 1:
            dtype_str = "int"
        else:
            raise ValueError(
                "Unable to determine the data type to use to contain the "
                f"Pixel Data as a value of '{pixel_repr}' for '(0028,0103) "
                "Pixel Representation' is invalid"
            )
    else:
        dtype_str = "float"

    # (0028,0100) Bits Allocated, US, 1
    #   The number of bits allocated for each pixel sample
    #   PS3.5 8.1.1: Bits Allocated shall either be 1 or a multiple of 8
    #   For bit packed data we use uint8
    bits_allocated = cast(int, ds.BitsAllocated)
    if bits_allocated == 1:
        dtype_str = "uint8"
    elif bits_allocated > 0 and bits_allocated % 8 == 0:
        dtype_str += str(bits_allocated)
    else:
        raise ValueError(
            "Unable to determine the data type to use to contain the "
            f"Pixel Data as a value of '{bits_allocated}' for '(0028,0100) "
            "Bits Allocated' is invalid"
        )

    # Check to see if the dtype is valid for numpy
    try:
        dtype = np.dtype(dtype_str)
    except TypeError:
        raise NotImplementedError(
            f"The data type '{dtype_str}' needed to contain the Pixel Data "
            "is not supported by numpy"
        )

    # Correct for endianness of the system vs endianness of the dataset
    if is_little_endian != (byteorder == "little"):
        # 'S' swap from current to opposite
        dtype = dtype.newbyteorder("S")

    return dtype


def reshape_pixel_array(ds: "Dataset", arr: "np.ndarray") -> "np.ndarray":
    """Return a reshaped :class:`numpy.ndarray` `arr`.

    +------------------------------------------+-----------+----------+
    | Element                                  | Supported |          |
    +-------------+---------------------+------+ values    |          |
    | Tag         | Keyword             | Type |           |          |
    +=============+=====================+======+===========+==========+
    | (0028,0002) | SamplesPerPixel     | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0006) | PlanarConfiguration | 1C   | 0, 1      | Optional |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0008) | NumberOfFrames      | 1C   | N > 0     | Optional |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0010) | Rows                | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+
    | (0028,0011) | Columns             | 1    | N > 0     | Required |
    +-------------+---------------------+------+-----------+----------+

    (0028,0008) *Number of Frames* is required when *Pixel Data* contains
    more than 1 frame. (0028,0006) *Planar Configuration* is required when
    (0028,0002) *Samples per Pixel* is greater than 1. For certain
    compressed transfer syntaxes it is always taken to be either 0 or 1 as
    shown in the table below.

    +---------------------------------------------+-----------------------+
    | Transfer Syntax                             | Planar Configuration  |
    +------------------------+--------------------+                       |
    | UID                    | Name               |                       |
    +========================+====================+=======================+
    | 1.2.840.10008.1.2.4.50 | JPEG Baseline      | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.57 | JPEG Lossless,     | 0                     |
    |                        | Non-hierarchical   |                       |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.70 | JPEG Lossless,     | 0                     |
    |                        | Non-hierarchical,  |                       |
    |                        | SV1                |                       |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.80 | JPEG-LS Lossless   | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.81 | JPEG-LS Lossy      | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.90 | JPEG 2000 Lossless | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.4.91 | JPEG 2000 Lossy    | 0                     |
    +------------------------+--------------------+-----------------------+
    | 1.2.840.10008.1.2.5    | RLE Lossless       | 1                     |
    +------------------------+--------------------+-----------------------+

    .. versionchanged:: 2.1

        JPEG-LS transfer syntaxes changed to *Planar Configuration* of 0

    Parameters
    ----------
    ds : dataset.Dataset
        The :class:`~pydicom.dataset.Dataset` containing the Image Pixel module
        corresponding to the data in `arr`.
    arr : numpy.ndarray
        The 1D array containing the pixel data.

    Returns
    -------
    numpy.ndarray
        A reshaped array containing the pixel data. The shape of the array
        depends on the contents of the dataset:

        * For single frame, single sample data (rows, columns)
        * For single frame, multi-sample data (rows, columns, planes)
        * For multi-frame, single sample data (frames, rows, columns)
        * For multi-frame, multi-sample data (frames, rows, columns, planes)

    References
    ----------

    * DICOM Standard, Part 3,
      :dcm:`Annex C.7.6.3.1<part03/sect_C.7.6.3.html#sect_C.7.6.3.1>`
    * DICOM Standard, Part 5, :dcm:`Section 8.2<part05/sect_8.2.html>`
    """
    if not HAVE_NP:
        raise ImportError("Numpy is required to reshape the pixel array.")

    nr_frames = get_nr_frames(ds)
    nr_samples = cast(int, ds.SamplesPerPixel)

    if nr_samples < 1:
        raise ValueError(
            f"Unable to reshape the pixel array as a value of {nr_samples} "
            "for (0028,0002) 'Samples per Pixel' is invalid."
        )

    # Valid values for Planar Configuration are dependent on transfer syntax
    if nr_samples > 1:
        transfer_syntax = ds.file_meta.TransferSyntaxUID
        if transfer_syntax in [
            "1.2.840.10008.1.2.4.50",
            "1.2.840.10008.1.2.4.57",
            "1.2.840.10008.1.2.4.70",
            "1.2.840.10008.1.2.4.80",
            "1.2.840.10008.1.2.4.81",
            "1.2.840.10008.1.2.4.90",
            "1.2.840.10008.1.2.4.91",
        ]:
            planar_configuration = 0
        elif transfer_syntax in ["1.2.840.10008.1.2.5"]:
            planar_configuration = 1
        else:
            planar_configuration = ds.PlanarConfiguration

        if planar_configuration not in [0, 1]:
            raise ValueError(
                "Unable to reshape the pixel array as a value of "
                f"{planar_configuration} for (0028,0006) 'Planar "
                "Configuration' is invalid."
            )

    rows = cast(int, ds.Rows)
    columns = cast(int, ds.Columns)
    if nr_frames > 1:
        # Multi-frame
        if nr_samples == 1:
            # Single plane
            arr = arr.reshape(nr_frames, rows, columns)
        else:
            # Multiple planes, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(nr_frames, rows, columns, nr_samples)
            else:
                arr = arr.reshape(nr_frames, nr_samples, rows, columns)
                arr = arr.transpose(0, 2, 3, 1)
    else:
        # Single frame
        if nr_samples == 1:
            # Single plane
            arr = arr.reshape(rows, columns)
        else:
            # Multiple planes, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(rows, columns, nr_samples)
            else:
                arr = arr.reshape(nr_samples, rows, columns)
                arr = arr.transpose(1, 2, 0)

    return arr


def unpack_bits(src: bytes, as_array: bool = True) -> "np.ndarray | bytes":
    """Unpack the bit-packed data in `src`.

    Suitable for use when (0028,0011) *Bits Allocated* or (60xx,0100) *Overlay
    Bits Allocated* is 1.

    If `NumPy <https://numpy.org/>`_ is available then it will be used to
    unpack the data, otherwise only the standard library will be used, which
    is about 20 times slower.

    .. versionchanged:: 2.3

        Added the `as_array` keyword parameter, support for unpacking
        without NumPy, and added :class:`bytes` as a possible return type

    Parameters
    ----------
    src : bytes
        The bit-packed data.
    as_array : bool, optional
        If ``False`` then return the unpacked data as :class:`bytes`, otherwise
        return a :class:`numpy.ndarray` (default, requires NumPy).

    Returns
    -------
    bytes or numpy.ndarray
        The unpacked data as an :class:`numpy.ndarray` (if NumPy is available
        and ``as_array == True``) or :class:`bytes` otherwise.

    Raises
    ------
    ValueError
        If `as_array` is ``True`` and NumPy is not available.

    References
    ----------
    DICOM Standard, Part 5,
    :dcm:`Section 8.1.1<part05/chapter_8.html#sect_8.1.1>` and
    :dcm:`Annex D<part05/chapter_D.html>`
    """
    if HAVE_NP:
        arr = np.frombuffer(src, dtype="u1")
        arr = np.unpackbits(arr, bitorder="little")

        return arr if as_array else arr.tobytes()

    if as_array:
        raise ValueError("unpack_bits() requires NumPy if 'as_array = True'")

    return b"".join(map(_UNPACK_LUT.__getitem__, src))
