# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Utilities for pixel data handling."""

from collections.abc import Iterable, Iterator
from enum import Enum, unique
import importlib
import logging
from pathlib import Path
from os import PathLike
from struct import unpack
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
    * JPEG 2000 encoded data whose signedness doesn't match the expected
      :ref:`pixel representation<pixel_representation>` will be
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
    * JPEG 2000 encoded data whose signedness doesn't match the expected
      :ref:`pixel representation<pixel_representation>` will be
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


def _get_jls_parameters(src: bytes) -> dict[str, int]:
    """Return a dict containing JPEG-LS component parameters.

    Parameters
    ----------
    src : bytes
        The JPEG-LS (ISO/IEC 14495-1) codestream to be parsed.

    Returns
    -------
    dict[str, int]
        A dict containing JPEG-LS coding parameters or an empty dict if unable
        to parse the data. Available parameters are:

        * ``precision``: int
        * ``height``: int
        * ``width``: int
        * ``components``: int
        * ``interleave_mode``: int
        * ``lossy_error``: int
    """
    info = {}
    try:
        # First 2 bytes should be the SOI marker - otherwise wrong format
        #   or has a SPIFF header
        if src[0:2] != b"\xFF\xD8":
            return info

        # Skip to the SOF55 (JPEG-LS) marker
        offset = 2
        while (marker := src[offset:offset + 2]) != b"\xFF\xF7":
            length = unpack(">H", src[offset + 2:offset + 4])[0]
            offset += length + 2

        # Next 2 bytes are marker length, then 1 byte precision
        sof_length = unpack(">H", src[offset + 2:offset + 4])[0]
        info["precision"] = unpack("B", src[offset + 4:offset + 5])[0]
        # Then 2 bytes rows, 2 bytes columns, 1 byte number of components in frame
        info["height"] = unpack(">H", src[offset + 5:offset + 7])[0]
        info["width"] = unpack(">H", src[offset + 7:offset + 9])[0]
        info["components"] = unpack("B", src[offset + 9:offset + 10])[0]
        offset += 2 + sof_length

        # Skip to the SOS marker
        while (marker := src[offset:offset + 2]) != b"\xFF\xDA":
            length = unpack(">H", src[offset + 2:offset + 4])[0]
            offset += length + 2

        # Next 2 bytes are marker length, then 1 byte number of components in scan
        sos_length = unpack(">H", src[offset + 2:offset + 4])[0]
        nr_components = unpack("B", src[offset + 4:offset + 5])[0]
        # Skip past the component Td and Ta values
        offset += 5 + nr_components
        info["lossy_error"] = unpack("B", src[offset:offset + 1])[0]
        info["interleave_mode"] = unpack("B", src[offset + 1:offset + 2])[0]
    except (IndexError, TypeError):
        pass

    return info
