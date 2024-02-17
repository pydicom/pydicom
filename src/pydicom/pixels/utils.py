# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Utilities for pixel data handling."""

from collections.abc import Iterable, Iterator
from enum import Enum, unique
import importlib
import logging
from pathlib import Path
from os import PathLike
from struct import unpack, Struct
from typing import BinaryIO, Any, Union, cast

try:
    import numpy as np

    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from pydicom.charset import default_encoding
from pydicom.dataset import Dataset
from pydicom._dicom_dict import DicomDictionary
from pydicom.filereader import (
    read_preamble,
    _read_file_meta_info,
    read_dataset,
    _at_pixel_data,
)
from pydicom.tag import BaseTag
from pydicom.uid import UID


LOGGER = logging.getLogger(__name__)

# All non-retired group 0x0028 elements
_GROUP_0028 = {
    k for k, v in DicomDictionary.items() if k >> 16 == 0x0028 and v[3] == ""
}
# The minimum required elements
_REQUIRED_TAGS = {
    0x00280002,
    0x00280004,
    0x00280006,
    0x00280008,
    0x00280010,
    0x00280011,
    0x00280100,
    0x00280101,
    0x00280103,
    0x7FE00001,
    0x7FE00002,
}
_PIXEL_KEYWORDS = {
    (0x7FE0, 0x0008): "FloatPixelData",
    (0x7FE0, 0x0009): "DoubleFloatPixelData",
    (0x7FE0, 0x0010): "PixelData",
}


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


# TODO: Python 3.11 switch to StrEnum
@unique
class PhotometricInterpretation(str, Enum):
    """Values for (0028,0004) *Photometric Interpretation*"""

    # Standard Photometric Interpretations from C.7.6.3.1.2 in Part 3
    MONOCHROME1 = "MONOCHROME1"
    MONOCHROME2 = "MONOCHROME2"
    PALETTE_COLOR = "PALETTE COLOR"
    RGB = "RGB"
    YBR_FULL = "YBR_FULL"
    YBR_FULL_422 = "YBR_FULL_422"
    YBR_ICT = "YBR_ICT"
    YBR_RCT = "YBR_RCT"
    HSV = "HSV"  # Retired
    ARGB = "ARGB"  # Retired
    CMYK = "CMYK"  # Retired
    YBR_PARTIAL_422 = "YBR_PARTIAL_422"  # Retired
    YBR_PARTIAL_420 = "YBR_PARTIAL_420"  # Retired

    # TODO: no longer needed if StrEnum
    def __str__(self) -> str:
        return str.__str__(self)


def pixel_array(
    src: str | PathLike[str] | BinaryIO,
    *,
    ds_out: Union["Dataset", None] = None,
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
    from pydicom.pixels import get_decoder

    f: BinaryIO
    if not hasattr(src, "read"):
        path = Path(src).resolve(strict=True)
        f = path.open("rb")
    else:
        f = cast(BinaryIO, src)
        file_offset = f.tell()
        f.seek(0)

    tags = _REQUIRED_TAGS
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


def iter_pixels(
    src: str | PathLike[str] | BinaryIO,
    *,
    ds_out: Union["Dataset", None] = None,
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
    from pydicom.pixels import get_decoder

    f: BinaryIO
    if not hasattr(src, "read"):
        path = Path(src).resolve(strict=True)
        f = path.open("rb")
    else:
        f = cast(BinaryIO, src)
        file_offset = f.tell()
        f.seek(0)

    tags = _REQUIRED_TAGS
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

    opts = kwargs
    opts = _as_options(ds, opts)
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
    if opts["pixel_keyword"] == "PixelData" and "pixel_representation" not in opts:
        raise AttributeError(
            "The dataset in 'src' is missing a required element: (0028,0103) "
            "Pixel Representation"
        )

    return ds, opts


def _as_options(ds: "Dataset", opts: dict[str, Any]) -> dict[str, Any]:
    """Return a decoding options dict created from the dataset `ds`.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset to use.
    opts : dict[str, Any]
        The required and optional arguments for the pixel data decoding
        functions. When supplied these should take priority over the
        corresponding `ds` element values.

    Returns
    -------
    dict
        The `opts` dict updated with values from `ds` (if required).
    """
    msg = "The dataset in 'src' is missing a required element: (0028,"
    bits_allocated = opts.get("bits_allocated", ds.get("BitsAllocated", None))
    if bits_allocated is None:
        raise AttributeError(f"{msg}0100) Bits Allocated")

    bits_stored = opts.get("bits_stored", ds.get("BitsStored", None))
    if bits_stored is None:
        raise AttributeError(f"{msg}0101) Bits Stored")

    columns = opts.get("columns", ds.get("Columns", None))
    if columns is None:
        raise AttributeError(f"{msg}0011) Columns")

    rows = opts.get("rows", ds.get("Rows", None))
    if rows is None:
        raise AttributeError(f"{msg}0010) Rows")

    number_of_frames = opts.get("number_of_frames", ds.get("NumberOfFrames", 1))

    photometric_interpretation = opts.get(
        "photometric_interpretation", ds.get("PhotometricInterpretation", None)
    )
    if photometric_interpretation is None:
        raise AttributeError(f"{msg}0004) Photometric Interpretation")

    samples_per_pixel = opts.get("samples_per_pixel", ds.get("SamplesPerPixel", None))
    if samples_per_pixel is None:
        raise AttributeError(f"{msg}0002) Samples per Pixel")

    if samples_per_pixel > 1:
        planar_configuration = opts.get(
            "planar_configuration", ds.get("PlanarConfiguration", None)
        )
        if planar_configuration is None:
            raise AttributeError(f"{msg}0006) Planar Configuration")

        opts["planar_configuration"] = planar_configuration

    opts["bits_allocated"] = bits_allocated
    opts["bits_stored"] = bits_stored
    opts["columns"] = columns
    opts["number_of_frames"] = number_of_frames if number_of_frames else 1
    opts["photometric_interpretation"] = photometric_interpretation
    opts["rows"] = rows
    opts["samples_per_pixel"] = samples_per_pixel

    pixel_representation = opts.get(
        "pixel_representation", ds.get("PixelRepresentation")
    )
    if pixel_representation is not None:
        opts["pixel_representation"] = pixel_representation

    # Encapsulation - Extended Offset Table
    if 0x7FE00001 in ds._dict and 0x7FE00002 in ds._dict:
        opts.setdefault(
            "extended_offsets",
            (ds.ExtendedOffsetTable, ds.ExtendedOffsetTableLengths),
        )

    return opts


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
# JPEG APP markers
_APP = {
    b"\xFF\xE0",
    b"\xFF\xE1",
    b"\xFF\xE2",
    b"\xFF\xE3",
    b"\xFF\xE4",
    b"\xFF\xE5",
    b"\xFF\xE6",
    b"\xFF\xE7",
    b"\xFF\xE8",
    b"\xFF\xE9",
    b"\xFF\xEA",
    b"\xFF\xEB",
    b"\xFF\xEC",
    b"\xFF\xED",
    b"\xFF\xEE",
    b"\xFF\xEF",
}
_UNPACK_SHORT = Struct(">H").unpack


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
