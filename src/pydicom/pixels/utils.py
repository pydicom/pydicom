# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Utilities for pixel data handling."""

from collections.abc import Iterable, Iterator, ByteString
import importlib
import logging
from pathlib import Path
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
from pydicom.encaps import encapsulate, encapsulate_extended
from pydicom.misc import warn_and_log
from pydicom.tag import BaseTag
from pydicom.uid import (
    UID,
    JPEGLSNearLossless,
    JPEG2000,
    ExplicitVRLittleEndian,
    generate_uid,
)
from pydicom.valuerep import VR

if TYPE_CHECKING:  # pragma: no cover
    from os import PathLike
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

    .. versionadded:: 3.0

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
    if nr_frames in (None, 0):
        warn_and_log(
            f"A value of '{nr_frames}' for (0028,0008) 'Number of Frames' is invalid, "
            "assuming 1 frame"
        )
        nr_frames = 1

    opts["number_of_frames"] = nr_frames

    # Extended Offset Table
    if 0x7FE00001 in ds._dict and 0x7FE00001 in ds._dict:
        opts["extended_offsets"] = (
            ds.ExtendedOffsetTable,
            ds.ExtendedOffsetTableLengths,
        )

    opts.update(kwargs)

    return opts


def compress(
    ds: "Dataset",
    transfer_syntax_uid: str,
    arr: "np.ndarray | None" = None,
    *,
    encoding_plugin: str = "",
    encapsulate_ext: bool = False,
    generate_instance_uid: bool = True,
    jls_error: int | None = None,
    j2k_cr: list[float] | None = None,
    j2k_psnr: list[float] | None = None,
    **kwargs: Any,
) -> "Dataset":
    """Compress uncompressed pixel data and update `ds` in-place with the
    resulting :dcm:`encapsulated<part05/sect_A.4.html>` codestream.

    .. versionadded:: 3.0

    The dataset `ds` must already have the following
    :dcm:`Image Pixel<part03/sect_C.7.6.3.html>` module elements present
    with correct values that correspond to the resulting compressed
    pixel data:

    * (0028,0002) *Samples per Pixel*
    * (0028,0004) *Photometric Interpretation*
    * (0028,0008) *Number of Frames* (if more than 1 frame will be present)
    * (0028,0010) *Rows*
    * (0028,0011) *Columns*
    * (0028,0100) *Bits Allocated*
    * (0028,0101) *Bits Stored*
    * (0028,0103) *Pixel Representation*

    If *Samples per Pixel* is greater than 1 then the following element
    is also required:

    * (0028,0006) *Planar Configuration*

    This method will add the file meta dataset if none is present and add
    or modify the following elements:

    * (0002,0010) *Transfer Syntax UID*
    * (7FE0,0010) *Pixel Data*

    If the compressed pixel data is too large for encapsulation using a
    basic offset table then an :dcm:`extended offset table
    <part03/sect_C.7.6.3.html>` will also be used, in which case the
    following elements will also be added:

    * (7FE0,0001) *Extended Offset Table*
    * (7FE0,0002) *Extended Offset Table Lengths*

    If `generate_instance_uid` is ``True`` (default) then a new (0008,0018) *SOP
    Instance UID* value will be generated.

    **Supported Transfer Syntax UIDs**

    +-----------------------------------------------+-----------+----------------------------------+
    | UID                                           |  Plugins  | Encoding Guide                   |
    +------------------------+----------------------+           |                                  |
    | Name                   | Value                |           |                                  |
    +========================+======================+===========+==================================+
    | *JPEG-LS Lossless*     |1.2.840.10008.1.2.4.80| pyjpegls  | :doc:`JPEG-LS                    |
    +------------------------+----------------------+           | </guides/encoding/jpeg_ls>`      |
    | *JPEG-LS Near Lossless*|1.2.840.10008.1.2.4.81|           |                                  |
    +------------------------+----------------------+-----------+----------------------------------+
    | *JPEG 2000 Lossless*   |1.2.840.10008.1.2.4.90| pylibjpeg | :doc:`JPEG 2000                  |
    +------------------------+----------------------+           | </guides/encoding/jpeg_2k>`      |
    | *JPEG 2000*            |1.2.840.10008.1.2.4.91|           |                                  |
    +------------------------+----------------------+-----------+----------------------------------+
    | *RLE Lossless*         | 1.2.840.10008.1.2.5  | pydicom,  | :doc:`RLE Lossless               |
    |                        |                      | pylibjpeg,| </guides/encoding/rle_lossless>` |
    |                        |                      | gdcm      |                                  |
    +------------------------+----------------------+-----------+----------------------------------+

    Examples
    --------

    Compress the existing uncompressed *Pixel Data* in place:

    >>> from pydicom import examples
    >>> from pydicom.pixels import compress
    >>> from pydicom.uid import RLELossless
    >>> ds = examples.ct
    >>> compress(ds, RLELossless)
    >>> ds.save_as("ct_rle_lossless.dcm")

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset to be compressed.
    transfer_syntax_uid : pydicom.uid.UID
        The UID of the :dcm:`transfer syntax<part05/chapter_10.html>` to
        use when compressing the pixel data.
    arr : numpy.ndarray, optional
        Compress the uncompressed pixel data in `arr` and use it
        to set the *Pixel Data*. If `arr` is not used then the existing
        uncompressed *Pixel Data* in the dataset will be compressed instead.
        The :attr:`~numpy.ndarray.shape`, :class:`~numpy.dtype` and
        contents of the array should match the dataset.
    encoding_plugin : str, optional
        Use `encoding_plugin` to compress the pixel data. See the
        :doc:`user guide </guides/user/image_data_compression>` for a list of
        plugins available for each UID and their dependencies. If not
        specified then all available plugins will be tried (default).
    encapsulate_ext : bool, optional
        If ``True`` then force the addition of an extended offset table.
        If ``False`` (default) then an extended offset table
        will be added if needed for large amounts of compressed *Pixel
        Data*, otherwise just the basic offset table will be used.
    generate_instance_uid : bool, optional
        If ``True`` (default) then generate a new (0008,0018) *SOP Instance UID*
        value for the dataset using :func:`~pydicom.uid.generate_uid`, otherwise
        keep the original value.
    jls_error : int, optional
        **JPEG-LS Near Lossless only**. The allowed absolute compression error
        in the pixel values.
    j2k_cr : list[float], optional
        **JPEG 2000 only**. A list of the compression ratios to use for each
        quality layer. There must be at least one quality layer and the
        minimum allowable compression ratio is ``1``. When using multiple
        quality layers they should be ordered in decreasing value from left
        to right. For example, to use 2 quality layers with 20x and 5x
        compression ratios then `j2k_cr` should be ``[20, 5]``. Cannot be
        used with `j2k_psnr`.
    j2k_psnr : list[float], optional
        **JPEG 2000 only**. A list of the peak signal-to-noise ratios (in dB)
        to use for each quality layer. There must be at least one quality
        layer and when using multiple quality layers they should be ordered
        in increasing value from left to right. For example, to use 2
        quality layers with PSNR of 80 and 300 then `j2k_psnr` should be
        ``[80, 300]``. Cannot be used with `j2k_cr`.
    **kwargs
        Optional keyword parameters for the encoding plugin may also be
        present. See the :doc:`encoding plugins options
        </guides/encoding/encoder_plugin_options>` for more information.
    """
    from pydicom.dataset import FileMetaDataset
    from pydicom.pixels import get_encoder

    # Disallow overriding the dataset's image pixel module element values
    for option in _IMAGE_PIXEL.values():
        kwargs.pop(option, None)

    uid = UID(transfer_syntax_uid)
    encoder = get_encoder(uid)
    if not encoder.is_available:
        missing = "\n".join([f"    {s}" for s in encoder.missing_dependencies])
        raise RuntimeError(
            f"The pixel data encoder for '{uid.name}' is unavailable because all "
            f"of its plugins are missing dependencies:\n{missing}"
        )

    if uid == JPEGLSNearLossless and jls_error is not None:
        kwargs["jls_error"] = jls_error

    if uid == JPEG2000:
        if j2k_cr is not None:
            kwargs["j2k_cr"] = j2k_cr

        if j2k_psnr is not None:
            kwargs["j2k_psnr"] = j2k_psnr

    if arr is None:
        # Check the dataset compression state
        file_meta = ds.get("file_meta", {})
        tsyntax = file_meta.get("TransferSyntaxUID", "")
        if not tsyntax:
            raise AttributeError(
                "Unable to determine the initial compression state of the dataset "
                "as there's no (0002,0010) 'Transfer Syntax UID' element in the "
                "dataset's 'file_meta' attribute"
            )

        if tsyntax.is_compressed:
            raise ValueError("Only uncompressed datasets may be compressed")

        # Encode the current uncompressed *Pixel Data*
        frame_iterator = encoder.iter_encode(
            ds, encoding_plugin=encoding_plugin, **kwargs
        )
    else:
        # Encode from an array - no need to check dataset compression state
        #   because we'll be using new pixel data
        opts = as_pixel_options(ds, **kwargs)
        frame_iterator = encoder.iter_encode(
            arr, encoding_plugin=encoding_plugin, **opts
        )

    # Encode!
    encoded = [f for f in frame_iterator]

    # Encapsulate the encoded *Pixel Data*
    nr_frames = len(encoded)
    total = (nr_frames - 1) * 8 + sum([len(f) for f in encoded[:-1]])
    if encapsulate_ext or total > 2**32 - 1:
        (
            ds.PixelData,
            ds.ExtendedOffsetTable,
            ds.ExtendedOffsetTableLengths,
        ) = encapsulate_extended(encoded)
    else:
        ds.PixelData = encapsulate(encoded)

    # PS3.5 Annex A.4 - encapsulated pixel data uses undefined length
    elem = ds["PixelData"]
    elem.is_undefined_length = True
    # PS3.5 Section 8.2 and Annex A.4 - encapsulated pixel data uses OB
    elem.VR = VR.OB

    # Clear `pixel_array` as lossy compression may give different results
    ds._pixel_array = None
    ds._pixel_id = {}

    # Set the correct *Transfer Syntax UID*
    if not hasattr(ds, "file_meta"):
        ds.file_meta = FileMetaDataset()

    ds.file_meta.TransferSyntaxUID = uid

    if generate_instance_uid:
        instance_uid = generate_uid()
        ds.SOPInstanceUID = instance_uid
        ds.file_meta.MediaStorageSOPInstanceUID = instance_uid

    return ds


def decompress(
    ds: "Dataset",
    *,
    as_rgb: bool = True,
    generate_instance_uid: bool = True,
    decoding_plugin: str = "",
    **kwargs: Any,
) -> "Dataset":
    """Perform an in-place decompression of a dataset with a compressed *Transfer
    Syntax UID*.

    .. versionadded:: 3.0

    .. warning::

        This function requires `NumPy <https://numpy.org/>`_ and may require
        the installation of additional packages to perform the actual pixel
        data decoding. See the :doc:`pixel data decompression documentation
        </guides/user/image_data_handlers>` for more information.

    * The dataset's *Transfer Syntax UID* will be set to *Explicit
      VR Little Endian*.
    * The *Pixel Data* will be decompressed in its entirety and the
      *Pixel Data* element's value updated with the uncompressed data,
      padded to an even length.
    * The *Pixel Data* element's VR will be set to **OB** if *Bits
      Allocated* <= 8, otherwise it will be set to **OW**.
    * The :attr:`DataElement.is_undefined_length
      <pydicom.dataelem.DataElement.is_undefined_length>` attribute for the
      *Pixel Data* element will be set to ``False``.
    * Any :dcm:`image pixel<part03/sect_C.7.6.3.html>` module elements may be
      modified as required to match the uncompressed *Pixel Data*.
    * If `generate_instance_uid` is ``True`` (default) then a new (0008,0018) *SOP
      Instance UID* value will be generated.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        A dataset containing compressed *Pixel Data* to be decoded and the
        corresponding *Image Pixel* module elements, along with a
        :attr:`~pydicom.dataset.FileDataset.file_meta` attribute containing a
        suitable (0002,0010) *Transfer Syntax UID*.
    as_rgb : bool, optional
        if ``True`` (default) then convert pixel data with a YCbCr
        :ref:`photometric interpretation<photometric_interpretation>` such as
        ``"YBR_FULL_422"`` to RGB.
    generate_instance_uid : bool, optional
        If ``True`` (default) then generate a new (0008,0018) *SOP Instance UID*
        value for the dataset using :func:`~pydicom.uid.generate_uid`, otherwise
        keep the original value.
    decoding_plugin : str, optional
        The name of the decoding plugin to use when decoding compressed
        pixel data. If no `decoding_plugin` is specified (default) then all
        available plugins will be tried and the result from the first successful
        one yielded. For information on the available plugins for each
        decoder see the :doc:`API documentation</reference/pixels.decoders>`.
    kwargs : dict[str, Any], optional
        Optional keyword parameters for the decoding plugin may also be
        present. See the :doc:`decoding plugins options
        </guides/decoding/decoder_options>` for more information.

    Returns
    -------
    pydicom.dataset.Dataset
        The dataset `ds` decompressed in-place.
    """
    # TODO: v4.0 remove support for `pixel_data_handlers` module
    from pydicom.pixels import get_decoder

    if "PixelData" not in ds:
        raise AttributeError(
            "Unable to decompress as the dataset has no (7FE0,0010) 'Pixel Data' element"
        )

    file_meta = ds.get("file_meta", {})
    tsyntax = file_meta.get("TransferSyntaxUID", "")
    if not tsyntax:
        raise AttributeError(
            "Unable to determine the initial compression state as there's no "
            "(0002,0010) 'Transfer Syntax UID' element in the dataset's 'file_meta' "
            "attribute"
        )

    uid = UID(tsyntax)
    if not uid.is_compressed:
        raise ValueError("The dataset is already uncompressed")

    use_pdh = kwargs.get("use_pdh", False)
    frames: list[bytes]
    if use_pdh:
        ds.convert_pixel_data(decoding_plugin)
        frames = [ds.pixel_array.tobytes()]
    else:
        decoder = get_decoder(uid)
        if not decoder.is_available:
            missing = "\n".join([f"    {s}" for s in decoder.missing_dependencies])
            raise RuntimeError(
                f"Unable to decompress as the plugins for the '{uid.name}' decoder "
                f"are all missing dependencies:\n{missing}"
            )

        # Disallow decompression of individual frames
        kwargs.pop("index", None)
        frame_generator = decoder.iter_array(
            ds,
            decoding_plugin=decoding_plugin,
            as_rgb=as_rgb,
            **kwargs,
        )
        frames = []
        for arr, image_pixel in frame_generator:
            frames.append(arr.tobytes())

    # Part 5, Section 8.1.1: 32-bit Value Length field
    value_length = sum(len(frame) for frame in frames)
    if value_length >= 2**32 - 1:
        raise ValueError(
            "Unable to decompress as the length of the uncompressed pixel data "
            "will be greater than the maximum allowed by the DICOM Standard"
        )

    # Pad with 0x00 if odd length
    nr_frames = len(frames)
    if value_length % 2:
        frames.append(b"\x00")

    elem = ds["PixelData"]
    elem.value = b"".join(frame for frame in frames)
    elem.is_undefined_length = False
    elem.VR = VR.OB if ds.BitsAllocated <= 8 else VR.OW

    # Update the transfer syntax
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    if generate_instance_uid:
        instance_uid = generate_uid()
        ds.SOPInstanceUID = instance_uid
        ds.file_meta.MediaStorageSOPInstanceUID = instance_uid

    if not use_pdh:
        # Update the image pixel elements
        ds.PhotometricInterpretation = image_pixel["photometric_interpretation"]
        if cast(int, image_pixel["samples_per_pixel"]) > 1:
            ds.PlanarConfiguration = cast(int, image_pixel["planar_configuration"])

        if "NumberOfFrames" in ds or nr_frames > 1:
            ds.NumberOfFrames = nr_frames

        ds._pixel_array = None
        ds._pixel_id = {}

    return ds


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


def get_j2k_parameters(codestream: bytes) -> dict[str, Any]:
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
    offset = 0
    info: dict[str, Any] = {"jp2": False}

    # Account for the JP2 header (if present)
    # The first box is always 12 bytes long
    if codestream.startswith(b"\x00\x00\x00\x0C\x6A\x50\x20\x20"):
        info["jp2"] = True
        total_length = len(codestream)
        offset = 12
        # Iterate through the boxes, looking for the jp2c box
        while offset < total_length:
            length = int.from_bytes(codestream[offset : offset + 4], byteorder="big")
            if codestream[offset + 4 : offset + 8] == b"\x6A\x70\x32\x63":
                # The offset to the start of the J2K codestream
                offset += 8
                break

            offset += length

    try:
        # First 2 bytes must be the SOC marker - if not then wrong format
        if codestream[offset : offset + 2] != b"\xff\x4f":
            return {}

        # SIZ is required to be the second marker - Figure A-3 in 15444-1
        if codestream[offset + 2 : offset + 4] != b"\xff\x51":
            return {}

        # See 15444-1 A.5.1 for format of the SIZ box and contents
        ssiz = codestream[offset + 42]
        if ssiz & 0x80:
            info["precision"] = (ssiz & 0x7F) + 1
            info["is_signed"] = True
            return info

        info["precision"] = ssiz + 1
        info["is_signed"] = False
        return info
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
    src: "str | PathLike[str] | BinaryIO | Dataset",
    *,
    ds_out: "Dataset | None" = None,
    specific_tags: list[BaseTag | int] | None = None,
    indices: Iterable[int] | None = None,
    raw: bool = False,
    decoding_plugin: str = "",
    **kwargs: Any,
) -> Iterator["np.ndarray"]:
    """Yield decoded pixel data frames from `src` as :class:`~numpy.ndarray`.

    .. versionadded:: 3.0

    .. warning::

        This function requires `NumPy <https://numpy.org/>`_ and may require
        the installation of additional packages to perform the actual pixel
        data decompression. See the :doc:`pixel data decompression documentation
        </guides/user/image_data_handlers>` for more information.

    **Memory Usage**

    To minimize memory usage `src` should be the path to the dataset
    or a `file-like object <https://docs.python.org/3/glossary.html#term-file-object>`_
    containing the dataset.

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

    Read a DICOM dataset then iterate through all the pixel data frames::

        from pydicom import dcmread
        from pydicom.pixels import iter_pixels

        ds = dcmread("path/to/dataset.dcm")
        for arr in iter_pixels(ds):
            print(arr.shape)

    Iterate through all the pixel data frames in a dataset while minimizing
    memory usage::

        from pydicom.pixels import iter_pixels

        for arr in iter_pixels("path/to/dataset.dcm"):
            print(arr.shape)

    Iterate through the even frames for a dataset with 10 frames::

        from pydicom.pixels import iter_pixels

        with open("path/to/dataset.dcm", "rb") as f:
            for arr in iter_pixels(f, indices=range(0, 10, 2)):
                print(arr.shape)

    Parameters
    ----------
    src : str | PathLike[str] | file-like | pydicom.dataset.Dataset

        * :class:`str` | :class:`os.PathLike`: the path to a DICOM dataset
          containing pixel data, or
        * file-like: a `file-like object
          <https://docs.python.org/3/glossary.html#term-file-object>`_ in
          'rb' mode containing the dataset.
        * :class:`~pydicom.dataset.Dataset`: a dataset instance
    ds_out : pydicom.dataset.Dataset, optional
        A :class:`~pydicom.dataset.Dataset` that will be updated with the
        non-retired group ``0x0028`` image pixel module elements and the group
        ``0x0002`` file meta information elements from the dataset in `src`.
        **Only available when `src` is a path or file-like.**
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
        A single frame of decoded pixel data with shape:

        * (rows, columns) for single sample data
        * (rows, columns, samples) for multi-sample data

        A writeable :class:`~numpy.ndarray` is yielded by default. For
        native transfer syntaxes with ``view_only=True`` a read-only
        :class:`~numpy.ndarray` will be yielded.
    """
    from pydicom.dataset import Dataset
    from pydicom.pixels import get_decoder

    if isinstance(src, Dataset):
        ds: Dataset = src
        file_meta = getattr(ds, "file_meta", {})
        if not (tsyntax := file_meta.get("TransferSyntaxUID", None)):
            raise AttributeError(
                "Unable to decode the pixel data as the dataset's 'file_meta' "
                "has no (0002,0010) 'Transfer Syntax UID' element"
            )

        try:
            decoder = get_decoder(tsyntax)
        except NotImplementedError:
            raise NotImplementedError(
                "Unable to decode the pixel data as a (0002,0010) 'Transfer Syntax "
                f"UID' value of '{tsyntax.name}' is not supported"
            )

        opts = as_pixel_options(ds, **kwargs)
        iterator = decoder.iter_array(
            ds,
            indices=indices,
            validate=True,
            raw=raw,
            decoding_plugin=decoding_plugin,
            **opts,
        )
        for arr, _ in iterator:
            yield arr

        return

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

        tsyntax = opts["transfer_syntax_uid"]

        try:
            decoder = get_decoder(tsyntax)
        except NotImplementedError:
            raise NotImplementedError(
                "Unable to decode the pixel data as a (0002,0010) 'Transfer Syntax "
                f"UID' value of '{tsyntax.name}' is not supported"
            )

        iterator = decoder.iter_array(
            f,
            indices=indices,
            validate=True,
            raw=raw,
            decoding_plugin=decoding_plugin,
            **opts,
        )
        for arr, _ in iterator:
            yield arr

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
        LOGGER.debug(exc)

    return False


def pixel_array(
    src: "str | PathLike[str] | BinaryIO | Dataset",
    *,
    ds_out: "Dataset | None" = None,
    specific_tags: list[int] | None = None,
    index: int | None = None,
    raw: bool = False,
    decoding_plugin: str = "",
    **kwargs: Any,
) -> "np.ndarray":
    """Return decoded pixel data from `src` as :class:`~numpy.ndarray`.

    .. versionadded:: 3.0

    .. warning::

        This function requires `NumPy <https://numpy.org/>`_ and may require
        the installation of additional packages to perform the actual pixel
        data decompression. See the :doc:`pixel data decompression documentation
        </guides/user/image_data_handlers>` for more information.

    **Memory Usage**

    To minimize memory usage `src` should be the path to the dataset
    or a `file-like object <https://docs.python.org/3/glossary.html#term-file-object>`_
    containing the dataset.

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

     Read a DICOM dataset and return the entire pixel data::

        from pydicom import dcmread
        from pydicom.pixels import pixel_array

        ds = dcmread("path/to/dataset.dcm")
        arr = pixel_array(ds)

    Return the entire pixel data from a dataset while minimizing memory usage::

        from pydicom.pixels import pixel_array

        arr = pixel_array("path/to/dataset.dcm")

    Return the 3rd frame of a dataset containing at least 3 frames while
    minimizing memory usage::

        from pydicom.pixels import pixel_array

        with open("path/to/dataset.dcm", "rb") as f:
            arr = pixel_array(f, index=2)  # 'index' starts at 0

    Parameters
    ----------
    src : str | PathLike[str] | file-like | pydicom.dataset.Dataset

        * :class:`str` | :class:`os.PathLike`: the path to a DICOM dataset
          containing pixel data, or
        * file-like: a `file-like object
          <https://docs.python.org/3/glossary.html#term-file-object>`_ in
          'rb' mode containing the dataset.
        * :class:`~pydicom.dataset.Dataset`: a dataset instance
    ds_out : pydicom.dataset.Dataset, optional
        A :class:`~pydicom.dataset.Dataset` that will be updated with the
        non-retired group ``0x0028`` image pixel module elements and the group
        ``0x0002`` file meta information elements from the dataset in `src`.
        **Only available when `src` is a path or file-like.**
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
         One or more frames of decoded pixel data with shape:

        * (rows, columns) for single frame, single sample data
        * (rows, columns, samples) for single frame, multi-sample data
        * (frames, rows, columns) for multi-frame, single sample data
        * (frames, rows, columns, samples) for multi-frame, multi-sample data

        A writeable :class:`~numpy.ndarray` is returned by default. For
        native transfer syntaxes with ``view_only=True`` a read-only
        :class:`~numpy.ndarray` will be returned.
    """
    from pydicom.dataset import Dataset
    from pydicom.pixels import get_decoder

    if isinstance(src, Dataset):
        ds: Dataset = src
        file_meta = getattr(ds, "file_meta", {})
        if not (tsyntax := file_meta.get("TransferSyntaxUID", None)):
            raise AttributeError(
                "Unable to decode the pixel data as the dataset's 'file_meta' "
                "has no (0002,0010) 'Transfer Syntax UID' element"
            )

        try:
            decoder = get_decoder(tsyntax)
        except NotImplementedError:
            raise NotImplementedError(
                "Unable to decode the pixel data as a (0002,0010) 'Transfer Syntax "
                f"UID' value of '{tsyntax.name}' is not supported"
            )

        opts = as_pixel_options(ds, **kwargs)
        return decoder.as_array(
            ds,
            index=index,
            validate=True,
            raw=raw,
            decoding_plugin=decoding_plugin,
            **opts,
        )[0]

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
        tsyntax = opts["transfer_syntax_uid"]

        try:
            decoder = get_decoder(tsyntax)
        except NotImplementedError:
            raise NotImplementedError(
                "Unable to decode the pixel data as a (0002,0010) 'Transfer Syntax "
                f"UID' value of '{tsyntax.name}' is not supported"
            )

        arr, _ = decoder.as_array(
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
        * For single frame, multi-sample data (rows, columns, samples)
        * For multi-frame, single sample data (frames, rows, columns)
        * For multi-frame, multi-sample data (frames, rows, columns, samples)

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
            # Single sample
            arr = arr.reshape(nr_frames, rows, columns)
        else:
            # Multiple samples, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(nr_frames, rows, columns, nr_samples)
            else:
                arr = arr.reshape(nr_frames, nr_samples, rows, columns)
                arr = arr.transpose(0, 2, 3, 1)
    else:
        # Single frame
        if nr_samples == 1:
            # Single sample
            arr = arr.reshape(rows, columns)
        else:
            # Multiple samples, usually 3
            if planar_configuration == 0:
                arr = arr.reshape(rows, columns, nr_samples)
            else:
                arr = arr.reshape(nr_samples, rows, columns)
                arr = arr.transpose(1, 2, 0)

    return arr


def set_pixel_data(
    ds: "Dataset",
    arr: "np.ndarray",
    photometric_interpretation: str,
    bits_stored: int,
    *,
    generate_instance_uid: bool = True,
) -> None:
    """Use an :class:`~numpy.ndarray` to set a dataset's *Pixel Data* and related
    Image Pixel module elements.

    .. versionadded:: 3.0

    The following :dcm:`Image Pixel<part03/sect_C.7.6.3.3.html#table_C.7-11c>`
    module elements values will be added, updated or removed as necessary:

    * (0028,0002) *Samples per Pixel* using a value corresponding to
      `photometric_interpretation`.
    * (0028,0004) *Photometric Interpretation* from `photometric_interpretation`.
    * (0028,0006) *Planar Configuration* will be added and set to ``0`` if
      *Samples per Pixel* is > 1, otherwise it will be removed.
    * (0028,0008) *Number of Frames* from the array :attr:`~numpy.ndarray.shape`,
      however it will be removed if `arr` only contains a single frame.
    * (0028,0010) *Rows* and (0028,0011) *Columns* from the array
      :attr:`~numpy.ndarray.shape`.
    * (0028,0100) *Bits Allocated* from the array :class:`~numpy.dtype`.
    * (0028,0101) *Bits Stored* and (0028,0102) *High Bit* from `bits_stored`.
    * (0028,0103) *Pixel Representation* from the array :class:`~numpy.dtype`.

    In addition:

    * The *Transfer Syntax UID* will be set to *Explicit VR Little
      Endian* if it doesn't already exist or uses a compressed (encapsulated)
      transfer syntax.
    * If `generate_instance_uid` is ``True`` (default) then the *SOP Instance UID*
      will be added or updated.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The little endian encoded dataset to be modified.
    arr : np.ndarray
        An array with :class:`~numpy.dtype` uint8, uint16, int8 or int16. The
        array must be shaped as one of the following:

        * (rows, columns) for a single frame of grayscale data.
        * (frames, rows, columns) for multi-frame grayscale data.
        * (rows, columns, samples) for a single frame of multi-sample data
          such as RGB.
        * (frames, rows, columns, samples) for multi-frame, multi-sample data.
    photometric_interpretation : str
        The value to use for (0028,0004) *Photometric Interpretation*. Valid values
        are ``"MONOCHROME1"``, ``"MONOCHROME2"``, ``"PALETTE COLOR"``, ``"RGB"``,
        ``"YBR_FULL"``, ``"YBR_FULL_422"``.
    bits_stored : int
        The value to use for (0028,0101) *Bits Stored*. Must be no greater than
        the number of bits used by the :attr:`~numpy.dtype.itemsize` of `arr`.
    generate_instance_uid : bool, optional
        If ``True`` (default) then add or update the (0008,0018) *SOP Instance
        UID* element with a value generated using :func:`~pydicom.uid.generate_uid`.
    """
    from pydicom.dataset import FileMetaDataset
    from pydicom.pixels.common import PhotometricInterpretation as PI

    if (elem := ds.get(0x7FE00008, None)) or (elem := ds.get(0x7FE00009, None)):
        raise AttributeError(
            f"The dataset has an existing {elem.tag} '{elem.name}' element which "
            "indicates the (0008,0016) 'SOP Class UID' value is not suitable for a "
            f"dataset with 'Pixel Data'. The '{elem.name}' element should be deleted "
            "and the 'SOP Class UID' changed."
        )

    if not hasattr(ds, "file_meta"):
        ds.file_meta = FileMetaDataset()

    tsyntax = ds.file_meta.get("TransferSyntaxUID", None)
    if tsyntax and not tsyntax.is_little_endian:
        raise NotImplementedError(
            f"The dataset's transfer syntax '{tsyntax.name}' is big-endian, "
            "which is not supported"
        )

    # Make no changes to the dataset until after validation checks have passed!
    changes: dict[str, tuple[str, Any]] = {}

    shape, ndim, dtype = arr.shape, arr.ndim, arr.dtype
    if dtype.kind not in ("u", "i") or dtype.itemsize not in (1, 2):
        raise ValueError(
            f"Unsupported ndarray dtype '{dtype}', must be int8, int16, uint8 or "
            "uint16"
        )

    # Use `photometric_interpretation` to determine *Samples Per Pixel*
    # Don't support retired (such as CMYK) or inappropriate values (such as YBR_RCT)
    interpretations: dict[str, int] = {
        PI.MONOCHROME1: 1,
        PI.MONOCHROME2: 1,
        PI.PALETTE_COLOR: 1,
        PI.RGB: 3,
        PI.YBR_FULL: 3,
        PI.YBR_FULL_422: 3,
    }
    try:
        nr_samples = interpretations[photometric_interpretation]
    except KeyError:
        raise ValueError(
            "Unsupported 'photometric_interpretation' value "
            f"'{photometric_interpretation}'"
        )

    if nr_samples == 1:
        if ndim not in (2, 3):
            raise ValueError(
                f"An ndarray with '{photometric_interpretation}' data must have 2 or 3 "
                f"dimensions, not {ndim}"
            )

        # ndim = 3 is (frames, rows, columns), else (rows, columns)
        changes["NumberOfFrames"] = ("+", shape[0]) if ndim == 3 else ("-", None)
        changes["Rows"] = ("+", shape[1] if ndim == 3 else shape[0])
        changes["Columns"] = ("+", shape[2] if ndim == 3 else shape[1])
    else:
        if ndim not in (3, 4):
            raise ValueError(
                f"An ndarray with '{photometric_interpretation}' data must have 3 or 4 "
                f"dimensions, not {ndim}"
            )

        if shape[-1] != nr_samples:
            raise ValueError(
                f"An ndarray with '{photometric_interpretation}' data must have shape "
                f"(rows, columns, 3) or (frames, rows, columns, 3), not {shape}"
            )

        # ndim = 3 is (rows, columns, samples), else (frames, rows, columns, samples)
        changes["NumberOfFrames"] = ("-", None) if ndim == 3 else ("+", shape[0])
        changes["Rows"] = ("+", shape[0] if ndim == 3 else shape[1])
        changes["Columns"] = ("+", shape[1] if ndim == 3 else shape[2])

    if not 0 < bits_stored <= dtype.itemsize * 8:
        raise ValueError(
            f"Invalid 'bits_stored' value '{bits_stored}', must be greater than 0 and "
            "less than or equal to the number of bits for the ndarray's itemsize "
            f"'{arr.dtype.itemsize * 8}'"
        )

    # Check values in `arr` are in the range allowed by `bits_stored`
    actual_min, actual_max = arr.min(), arr.max()
    allowed_min = 0 if dtype.kind == "u" else -(2 ** (bits_stored - 1))
    allowed_max = (
        2**bits_stored - 1 if dtype.kind == "u" else 2 ** (bits_stored - 1) - 1
    )
    if actual_min < allowed_min or actual_max > allowed_max:
        raise ValueError(
            f"The range of values in the ndarray [{actual_min}, {actual_max}] is "
            f"greater than that allowed by the 'bits_stored' value [{allowed_min}, "
            f"{allowed_max}]"
        )

    changes["SamplesPerPixel"] = ("+", nr_samples)
    changes["PlanarConfiguration"] = ("+", 0) if nr_samples > 1 else ("-", None)
    changes["PhotometricInterpretation"] = ("+", photometric_interpretation)
    changes["BitsAllocated"] = ("+", dtype.itemsize * 8)
    changes["BitsStored"] = ("+", bits_stored)
    changes["HighBit"] = ("+", bits_stored - 1)
    changes["PixelRepresentation"] = ("+", 0 if dtype.kind == "u" else 1)

    # Update the Image Pixel module elements
    for keyword, (operation, value) in changes.items():
        if operation == "+":
            setattr(ds, keyword, value)
        elif operation == "-" and keyword in ds:
            del ds[keyword]

    # Part 3, C.7.6.3.1.2: YBR_FULL_422 data needs to be downsampled
    if photometric_interpretation == PI.YBR_FULL_422:
        # Y1 B1 R1 Y2 B1 R1 -> Y1 Y2 B1 R1
        arr = arr.ravel()
        out = np.empty(arr.size // 3 * 2, dtype=dtype)
        out[::4] = arr[::6]  # Y1
        out[1::4] = arr[3::6]  # Y2
        out[2::4] = arr[1::6]  # B
        out[3::4] = arr[2::6]  # R
        arr = out

    # Update the Pixel Data
    data = arr.tobytes()
    ds.PixelData = data if len(data) % 2 == 0 else b"".join((data, b"\x00"))
    elem = ds["PixelData"]
    elem.VR = VR.OB if ds.BitsAllocated <= 8 else VR.OW
    elem.is_undefined_length = False

    ds._pixel_array = None
    ds._pixel_id = {}

    if not tsyntax or tsyntax.is_compressed:
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian

    if generate_instance_uid:
        instance_uid = generate_uid()
        ds.SOPInstanceUID = instance_uid
        ds.file_meta.MediaStorageSOPInstanceUID = instance_uid


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
