# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Functions related to writing DICOM data."""

from collections.abc import Sequence, MutableSequence, Iterable
from copy import deepcopy
from io import BufferedIOBase
from struct import pack
from typing import BinaryIO, Any, cast
from collections.abc import Callable
import zlib

from pydicom import config
from pydicom.charset import default_encoding, convert_encodings, encode_string
from pydicom.dataelem import (
    convert_raw_data_element,
    DataElement,
    RawDataElement,
)
from pydicom.dataset import Dataset, validate_file_meta, FileMetaDataset
from pydicom.filebase import DicomFile, DicomBytesIO, DicomIO, WriteableBuffer
from pydicom.fileutil import (
    path_from_pathlike,
    PathType,
    buffer_remaining,
    read_buffer,
    reset_buffer_position,
)
from pydicom.misc import warn_and_log
from pydicom.multival import MultiValue
from pydicom.tag import (
    Tag,
    BaseTag,
    ItemTag,
    ItemDelimiterTag,
    SequenceDelimiterTag,
    tag_in_exception,
    _LUT_DESCRIPTOR_TAGS,
)
from pydicom.uid import (
    DeflatedExplicitVRLittleEndian,
    UID,
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,
)
from pydicom.valuerep import (
    PersonName,
    IS,
    DSclass,
    DA,
    DT,
    TM,
    EXPLICIT_VR_LENGTH_32,
    VR,
    AMBIGUOUS_VR,
    CUSTOMIZABLE_CHARSET_VR,
)
from pydicom.values import convert_numbers

if config.have_numpy:
    import numpy

# Ambiguous VR Correction
# (0018,9810) Zero Velocity Pixel Value
# (0022,1452) Mapped Pixel Value
# (0028,0104)/(0028,0105) Smallest/Largest Valid Pixel Value
# (0028,0106)/(0028,0107) Smallest/Largest Image Pixel Value
# (0028,0108)/(0028,0109) Smallest/Largest Pixel Value in Series
# (0028,0110)/(0028,0111) Smallest/Largest Image Pixel Value in Plane
# (0028,0120) Pixel Padding Value
# (0028,0121) Pixel Padding Range Limit
# (0028,1101-1103) Red/Green/Blue Palette Color Lookup Table Descriptor
# (0028,3002) LUT Descriptor
# (0040,9216)/(0040,9211) Real World Value First/Last Value Mapped
# (0060,3004)/(0060,3006) Histogram First/Last Bin Value
_AMBIGUOUS_US_SS_TAGS = {
    0x00189810,
    0x00221452,
    0x00280104,
    0x00280105,
    0x00280106,
    0x00280107,
    0x00280108,
    0x00280109,
    0x00280110,
    0x00280111,
    0x00280120,
    0x00280121,
    0x00281101,
    0x00281102,
    0x00281103,
    0x00283002,
    0x00409211,
    0x00409216,
    0x00603004,
    0x00603006,
}

# (5400,0110) Channel Minimum Value
# (5400,0112) Channel Maximum Value
# (5400,100A) Waveform Padding Data
# (5400,1010) Waveform Data
_AMBIGUOUS_OB_OW_TAGS = {0x54000110, 0x54000112, 0x5400100A, 0x54001010}

# (60xx,3000) Overlay Data
_OVERLAY_DATA_TAGS = {x << 16 | 0x3000 for x in range(0x6000, 0x601F, 2)}


def _correct_ambiguous_vr_element(
    elem: DataElement,
    ancestors: list[Dataset],
    is_little_endian: bool,
) -> DataElement:
    """Implementation for `correct_ambiguous_vr_element`.
    See `correct_ambiguous_vr_element` for description.
    """
    # The zeroth dataset is the nearest, the last is the root dataset
    ds = ancestors[0]

    # 'OB or OW': 7fe0,0010 PixelData
    if elem.tag == 0x7FE00010:
        # Compressed Pixel Data
        # PS3.5 Annex A.4
        #   If encapsulated, VR is OB and length is undefined
        if elem.is_undefined_length:
            elem.VR = VR.OB
        elif ds.original_encoding[0]:
            # Non-compressed Pixel Data - Implicit Little Endian
            # PS3.5 Annex A1: VR is always OW
            elem.VR = VR.OW
        else:
            # Non-compressed Pixel Data - Explicit VR
            # PS3.5 Annex A.2:
            # If BitsAllocated is > 8 then VR shall be OW,
            # else may be OB or OW.
            # If we get here, the data has not been written before
            # or has been converted from Implicit Little Endian,
            # so we default to OB for BitsAllocated 1 or 8
            elem.VR = VR.OW if cast(int, ds.BitsAllocated) > 8 else VR.OB

    # 'US or SS' and dependent on PixelRepresentation
    elif elem.tag in _AMBIGUOUS_US_SS_TAGS:
        # US if PixelRepresentation value is 0x0000, else SS
        #   For references, see the list at
        #   https://github.com/pydicom/pydicom/pull/298
        # PixelRepresentation is usually set in the root dataset

        # If correcting during write, or after implicit read when the
        #   element is on the same level as pixel representation
        pixel_rep = next(
            (
                cast(int, x.PixelRepresentation)
                for x in ancestors
                if getattr(x, "PixelRepresentation", None) is not None
            ),
            None,
        )

        if pixel_rep is None:
            # If correcting after implicit read when the element isn't
            #   on the same level as pixel representation
            pixel_rep = next(
                (x._pixel_rep for x in ancestors if hasattr(x, "_pixel_rep")),
                None,
            )

        if pixel_rep is None:
            # If no pixel data is present, none if these tags is used,
            # so we can just ignore a missing PixelRepresentation in this case
            pixel_rep = 1
            if (
                "PixelRepresentation" not in ds
                and "PixelData" not in ds
                or ds.PixelRepresentation == 0
            ):
                pixel_rep = 0

        elem.VR = VR.US if pixel_rep == 0 else VR.SS
        byte_type = "H" if pixel_rep == 0 else "h"

        if elem.VM == 0:
            return elem

        # Need to handle type check for elements with VM > 1
        elem_value = elem.value if elem.VM == 1 else cast(Sequence[Any], elem.value)[0]
        if not isinstance(elem_value, int):
            elem.value = convert_numbers(
                cast(bytes, elem.value), is_little_endian, byte_type
            )

    # 'OB or OW' and dependent on WaveformBitsAllocated
    elif elem.tag in _AMBIGUOUS_OB_OW_TAGS:
        # If WaveformBitsAllocated is > 8 then OW, otherwise may be
        #   OB or OW.
        #   See PS3.3 C.10.9.1.
        if ds.original_encoding[0]:
            elem.VR = VR.OW
        else:
            elem.VR = VR.OW if cast(int, ds.WaveformBitsAllocated) > 8 else VR.OB

    # 'US or OW': 0028,3006 LUTData
    elif elem.tag == 0x00283006:
        # First value in LUT Descriptor is how many values in
        #   LUTData, if there's only one value then must be US
        # As per PS3.3 C.11.1.1.1
        if cast(Sequence[int], ds.LUTDescriptor)[0] == 1:
            elem.VR = VR.US
            if elem.VM == 0:
                return elem

            elem_value = (
                elem.value if elem.VM == 1 else cast(Sequence[Any], elem.value)[0]
            )
            if not isinstance(elem_value, int):
                elem.value = convert_numbers(
                    cast(bytes, elem.value), is_little_endian, "H"
                )
        else:
            elem.VR = VR.OW

    # 'OB or OW': 60xx,3000 OverlayData and dependent on Transfer Syntax
    elif elem.tag in _OVERLAY_DATA_TAGS:
        # Implicit VR must be OW, explicit VR may be OB or OW
        #   as per PS3.5 Section 8.1.2 and Annex A
        elem.VR = VR.OW

    return elem


def correct_ambiguous_vr_element(
    elem: DataElement | RawDataElement,
    ds: Dataset,
    is_little_endian: bool,
    ancestors: list[Dataset] | None = None,
) -> DataElement | RawDataElement:
    """Attempt to correct the ambiguous VR element `elem`.

    When it's not possible to correct the VR, the element will be returned
    unchanged. Currently the only ambiguous VR elements not corrected for are
    all retired or part of DICONDE.

    If the VR is corrected and is 'US' or 'SS' then the value will be updated
    using the :func:`~pydicom.values.convert_numbers` function.

    .. versionchanged:: 3.0

        The `ancestors` keyword argument was added.

    Parameters
    ----------
    elem : dataelem.DataElement or dataelem.RawDataElement
        The element with an ambiguous VR.
    ds : dataset.Dataset
        The dataset containing `elem`.
    is_little_endian : bool
        The byte ordering of the values in the dataset.
    ancestors : list[pydicom.dataset.Dataset] | None
        A list of the ancestor datasets to look through when trying to find
        the relevant element value to use in VR correction. Should be ordered
        from closest to furthest. If ``None`` then will build itself
        automatically starting at `ds` (default).

    Returns
    -------
    dataelem.DataElement or dataelem.RawDataElement
        The corrected element
    """
    ancestors = [ds] if ancestors is None else ancestors

    if elem.VR in AMBIGUOUS_VR:
        # convert raw data elements before handling them
        if isinstance(elem, RawDataElement):
            elem = convert_raw_data_element(elem, ds=ds)
            ds.__setitem__(elem.tag, elem)

        try:
            _correct_ambiguous_vr_element(elem, ancestors, is_little_endian)
        except AttributeError as e:
            raise AttributeError(
                f"Failed to resolve ambiguous VR for tag {elem.tag}: {e}"
            )

    return elem


def correct_ambiguous_vr(
    ds: Dataset,
    is_little_endian: bool,
    ancestors: list[Dataset] | None = None,
) -> Dataset:
    """Iterate through `ds` correcting ambiguous VR elements (if possible).

    When it's not possible to correct the VR, the element will be returned
    unchanged. Currently the only ambiguous VR elements not corrected for are
    all retired or part of DICONDE.

    If the VR is corrected and is 'US' or 'SS' then the value will be updated
    using the :func:`~pydicom.values.convert_numbers` function.

    .. versionchanged:: 3.0

        The `ancestors` keyword argument was added.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset containing ambiguous VR elements.
    is_little_endian : bool
        The byte ordering of the values in the dataset.
    ancestors : list[pydicom.dataset.Dataset] | None
        A list of the ancestor datasets to look through when trying to find
        the relevant element value to use in VR correction. Should be ordered
        from closest to furthest. If ``None`` then will build itself
        automatically starting at `ds` (default).

    Returns
    -------
    ds : dataset.Dataset
        The corrected dataset

    Raises
    ------
    AttributeError
        If a tag is missing in `ds` that is required to resolve the ambiguity.
    """
    # Construct the tree if `ds` is the root level dataset
    # tree = Tree(ds) if tree is None else tree
    ancestors = [ds] if ancestors is None else ancestors

    # Iterate through the elements
    for elem in ds.elements():
        # raw data element sequences can be written as they are, because we
        # have ensured that the transfer syntax has not changed at this point
        if elem.VR == VR.SQ:
            elem = ds[elem.tag]
            for item in cast(MutableSequence["Dataset"], elem.value):
                ancestors.insert(0, item)
                correct_ambiguous_vr(item, is_little_endian, ancestors)
        elif elem.VR in AMBIGUOUS_VR:
            correct_ambiguous_vr_element(elem, ds, is_little_endian, ancestors)

    del ancestors[0]
    return ds


def write_numbers(fp: DicomIO, elem: DataElement, struct_format: str) -> None:
    """Write a "value" of type struct_format from the dicom file.

    "Value" can be more than one number.

    Parameters
    ----------
    fp : file-like
        The file-like to write the encoded data to.
    elem : dataelem.DataElement
        The element to encode.
    struct_format : str
        The character format as used by the struct module.
    """
    value = elem.value
    if value is None or value == "":
        return  # don't need to write anything for no or empty value

    endianChar = "><"[fp.is_little_endian]
    format_string = endianChar + struct_format
    try:
        try:
            # works only if list, not if string or number
            value.append
        except AttributeError:  # is a single value - the usual case
            fp.write(pack(format_string, value))
        else:
            # Some ambiguous VR elements ignore the VR for part of the value
            # e.g. LUT Descriptor is 'US or SS' and VM 3, but the first and
            #   third values are always US (the third should be <= 16, so SS is OK)
            if struct_format == "h" and elem.tag in _LUT_DESCRIPTOR_TAGS and value:
                fp.write(pack(f"{endianChar}H", value[0]))
                value = value[1:]

            fp.write(pack(f"{endianChar}{len(value)}{struct_format}", *value))
    except Exception as exc:
        raise OSError(f"{exc}\nfor data_element:\n{elem}")


def write_OBvalue(fp: DicomIO, elem: DataElement) -> None:
    """Write a data_element with VR of 'other byte' (OB)."""

    if elem.is_buffered:
        bytes_written = 0
        buffer = cast(BufferedIOBase, elem.value)
        with reset_buffer_position(buffer):
            for chunk in read_buffer(buffer):
                bytes_written += fp.write(chunk)
    else:
        bytes_written = fp.write(cast(bytes, elem.value))

    if bytes_written % 2:
        fp.write(b"\x00")


def write_OWvalue(fp: DicomIO, elem: DataElement) -> None:
    """Write a data_element with VR of 'other word' (OW).

    Note: This **does not currently do the byte swapping** for Endian state.
    """

    if elem.is_buffered:
        bytes_written = 0
        buffer = cast(BufferedIOBase, elem.value)
        with reset_buffer_position(buffer):
            for chunk in read_buffer(buffer):
                bytes_written += fp.write(chunk)
    else:
        bytes_written = fp.write(cast(bytes, elem.value))

    if bytes_written % 2:
        fp.write(b"\x00")


def write_UI(fp: DicomIO, elem: DataElement) -> None:
    """Write a data_element with VR of 'unique identifier' (UI)."""
    write_string(fp, elem, "\0")  # pad with 0-byte to even length


def _is_multi_value(val: Any) -> bool:
    """Return True if `val` is a multi-value container."""
    if config.have_numpy and isinstance(val, numpy.ndarray):
        return True

    return isinstance(val, MultiValue | list | tuple)


def multi_string(val: str | Iterable[str]) -> str:
    """Put a string together with delimiter if has more than one value"""
    if _is_multi_value(val):
        return "\\".join(val)

    return cast(str, val)


def write_PN(
    fp: DicomIO, elem: DataElement, encodings: list[str] | None = None
) -> None:
    if not encodings:
        encodings = [default_encoding]

    val: list[PersonName]
    if elem.VM == 1:
        val = [cast(PersonName, elem.value)]
    else:
        val = cast(list[PersonName], elem.value)

    enc = b"\\".join([elem.encode(encodings) for elem in val])
    if len(enc) % 2 != 0:
        enc += b" "

    fp.write(enc)


def write_string(fp: DicomIO, elem: DataElement, padding: str = " ") -> None:
    """Write a single or multivalued ASCII string."""
    val = multi_string(cast(str | Iterable[str], elem.value))
    if val is not None:
        if len(val) % 2 != 0:
            val += padding  # pad to even length

        if isinstance(val, str):
            val = val.encode(default_encoding)  # type: ignore[assignment]

        fp.write(val)  # type: ignore[arg-type]


def write_text(
    fp: DicomIO, elem: DataElement, encodings: list[str] | None = None
) -> None:
    """Write a single or multivalued text string."""
    encodings = encodings or [default_encoding]
    val = elem.value
    if val is not None:
        if _is_multi_value(val):
            val = cast(Sequence[bytes] | Sequence[str], val)
            if isinstance(val[0], str):
                val = cast(Sequence[str], val)
                val = b"\\".join([encode_string(val, encodings) for val in val])
            else:
                val = cast(Sequence[bytes], val)
                val = b"\\".join([val for val in val])
        else:
            val = cast(bytes | str, val)
            if isinstance(val, str):
                val = encode_string(val, encodings)

        if len(val) % 2 != 0:
            val = val + b" "  # pad to even length
        fp.write(val)


def write_number_string(fp: DicomIO, elem: DataElement) -> None:
    """Handle IS or DS VR - write a number stored as a string of digits."""
    # If the DS or IS has an original_string attribute, use that, so that
    # unchanged data elements are written with exact string as when read from
    # file
    val = elem.value
    if _is_multi_value(val):
        val = cast(Sequence[IS] | Sequence[DSclass], val)
        val = "\\".join(
            x.original_string if hasattr(x, "original_string") else str(x) for x in val
        )
    else:
        val = cast(IS | DSclass, val)
        if hasattr(val, "original_string"):
            val = val.original_string
        else:
            val = str(val)

    if len(val) % 2 != 0:
        val = val + " "  # pad to even length

    val = bytes(val, default_encoding)

    fp.write(val)


def _format_DA(val: DA | None) -> str:
    if val is None:
        return ""

    if hasattr(val, "original_string"):
        return val.original_string

    return val.strftime("%Y%m%d")


def write_DA(fp: DicomIO, elem: DataElement) -> None:
    val = elem.value
    if isinstance(val, str):
        write_string(fp, elem)
    else:
        if _is_multi_value(val):
            val = cast(Sequence[DA], val)
            val = "\\".join(x if isinstance(x, str) else _format_DA(x) for x in val)
        else:
            val = _format_DA(cast(DA, val))

        if len(val) % 2 != 0:
            val = val + " "  # pad to even length

        if isinstance(val, str):
            val = val.encode(default_encoding)

        fp.write(val)


def _format_DT(val: DT | None) -> str:
    if val is None:
        return ""

    if hasattr(val, "original_string"):
        return val.original_string

    if val.microsecond > 0:
        return val.strftime("%Y%m%d%H%M%S.%f%z")

    return val.strftime("%Y%m%d%H%M%S%z")


def write_DT(fp: DicomIO, elem: DataElement) -> None:
    val = elem.value
    if isinstance(val, str):
        write_string(fp, elem)
    else:
        if _is_multi_value(val):
            val = cast(Sequence[DT], val)
            val = "\\".join(x if isinstance(x, str) else _format_DT(x) for x in val)
        else:
            val = _format_DT(cast(DT, val))

        if len(val) % 2 != 0:
            val = val + " "  # pad to even length

        if isinstance(val, str):
            val = val.encode(default_encoding)

        fp.write(val)


def _format_TM(val: TM | None) -> str:
    if val is None:
        return ""

    if hasattr(val, "original_string"):
        return val.original_string

    if val.microsecond > 0:
        return val.strftime("%H%M%S.%f")

    return val.strftime("%H%M%S")


def write_TM(fp: DicomIO, elem: DataElement) -> None:
    val = elem.value
    if isinstance(val, str):
        write_string(fp, elem)
    else:
        if _is_multi_value(val):
            val = cast(Sequence[TM], val)
            val = "\\".join(x if isinstance(x, str) else _format_TM(x) for x in val)
        else:
            val = _format_TM(cast(TM, val))

        if len(val) % 2 != 0:
            val = val + " "  # pad to even length

        if isinstance(val, str):
            val = val.encode(default_encoding)

        fp.write(val)


def write_data_element(
    fp: DicomIO,
    elem: DataElement | RawDataElement,
    encodings: str | list[str] | None = None,
) -> None:
    """Write the data_element to file fp according to
    dicom media storage rules.
    """
    # Write element's tag
    fp.write_tag(elem.tag)

    # write into a buffer to avoid seeking back which can be expansive
    buffer = DicomBytesIO()
    buffer.is_little_endian = fp.is_little_endian
    buffer.is_implicit_VR = fp.is_implicit_VR

    vr: str | None = elem.VR
    if not fp.is_implicit_VR and vr and len(vr) != 2:
        msg = (
            f"Cannot write ambiguous VR of '{vr}' for data element with "
            f"tag {elem.tag!r}.\nSet the correct VR before "
            f"writing, or use an implicit VR transfer syntax"
        )
        raise ValueError(msg)

    if elem.is_raw:
        elem = cast(RawDataElement, elem)
        # raw data element values can be written as they are
        buffer.write(cast(bytes, elem.value))
        is_undefined_length = elem.length == 0xFFFFFFFF
    else:
        elem = cast(DataElement, elem)
        if vr not in writers:
            raise NotImplementedError(
                f"write_data_element: unknown Value Representation '{vr}'"
            )

        encodings = encodings or [default_encoding]
        encodings = convert_encodings(encodings)
        fn, param = writers[cast(VR, vr)]
        is_undefined_length = elem.is_undefined_length
        if not elem.is_empty:
            if vr in CUSTOMIZABLE_CHARSET_VR or vr == VR.SQ:
                fn(buffer, elem, encodings=encodings)  # type: ignore[operator]
            else:
                # Many numeric types use the same writer but with
                # numeric format parameter
                if param is not None:
                    fn(buffer, elem, param)  # type: ignore[operator]
                elif not elem.is_buffered:
                    # defer writing a buffered value until after we have written the
                    # tag and length in the file
                    fn(buffer, elem)  # type: ignore[operator]

    # valid pixel data with undefined length shall contain encapsulated
    # data, e.g. sequence items - raise ValueError otherwise (see #238)
    if is_undefined_length and elem.tag == 0x7FE00010:
        if elem.is_buffered:
            value = cast(BufferedIOBase, elem.value)
            with reset_buffer_position(value):
                pixel_data_bytes = value.read(4)
        else:
            pixel_data_bytes = cast(bytes, elem.value)[:4]

        # Big endian encapsulation is non-conformant
        tag = b"\xFE\xFF\x00\xE0" if fp.is_little_endian else b"\xFF\xFE\xE0\x00"
        if not pixel_data_bytes.startswith(tag):
            raise ValueError(
                "The (7FE0,0010) 'Pixel Data' element value hasn't been "
                "encapsulated as required for a compressed transfer syntax - "
                "see pydicom.encaps.encapsulate() for more information"
            )

    value_length = (
        buffer.tell()
        if not elem.is_buffered
        else buffer_remaining(cast(BufferedIOBase, elem.value))
    )

    if (
        not fp.is_implicit_VR
        and vr not in EXPLICIT_VR_LENGTH_32
        and not is_undefined_length
        and value_length > 0xFFFF
    ):
        # see PS 3.5, section 6.2.2 for handling of this case
        warn_and_log(
            f"The value for the data element {elem.tag} exceeds the "
            f"size of 64 kByte and cannot be written in an explicit transfer "
            f"syntax. The data element VR is changed from '{vr}' to 'UN' "
            f"to allow saving the data."
        )
        vr = VR.UN

    # write the VR for explicit transfer syntax
    if not fp.is_implicit_VR:
        vr = cast(str, vr)
        fp.write(bytes(vr, default_encoding))

        if vr in EXPLICIT_VR_LENGTH_32:
            fp.write_US(0)  # reserved 2 bytes

    if (
        not fp.is_implicit_VR
        and vr not in EXPLICIT_VR_LENGTH_32
        and not is_undefined_length
    ):
        fp.write_US(value_length)  # Explicit VR length field is 2 bytes
    else:
        # write the proper length of the data_element in the length slot,
        # unless is SQ with undefined length.
        fp.write_UL(0xFFFFFFFF if is_undefined_length else value_length)

    # if the value is buffered, now we want to write the value directly to the fp
    if elem.is_buffered:
        fn(fp, elem)  # type: ignore[operator]
    else:
        fp.write(buffer.getvalue())

    if is_undefined_length:
        fp.write_tag(SequenceDelimiterTag)
        fp.write_UL(0)  # 4-byte 'length' of delimiter data item


EncodingType = tuple[bool | None, bool | None]


def write_dataset(
    fp: DicomIO, dataset: Dataset, parent_encoding: str | list[str] = default_encoding
) -> int:
    """Encode `dataset` and write the encoded data to `fp`.

    *Encoding*

    The `dataset` is encoded as specified by (in order of priority):

    * ``fp.is_implicit_VR`` and ``fp.is_little_endian``.
    * ``dataset.is_implicit_VR`` and ``dataset.is_little_endian``
    * If `dataset` has been decoded from a file or buffer then
      :attr:`~pydicom.dataset.Dataset.original_encoding`.

    Parameters
    ----------
    fp : pydicom.filebase.DicomIO
        The file-like to write the encoded dataset to.
    dataset : pydicom.dataset.Dataset
        The dataset to be encoded.
    parent_encoding : str | List[str], optional
        The character set to use for encoding strings, defaults to ``"iso8859"``.

    Returns
    -------
    int
        The number of bytes written to `fp`.
    """
    # TODO: Update in v4.0
    # In order of encoding priority

    fp_encoding: EncodingType = (
        getattr(fp, "_implicit_vr", None),
        getattr(fp, "_little_endian", None),
    )
    ds_encoding: EncodingType = (None, None)
    if not config._use_future:
        ds_encoding = (dataset.is_implicit_VR, dataset.is_little_endian)
    or_encoding = dataset.original_encoding

    if None in fp_encoding and None in ds_encoding and None in or_encoding:
        raise AttributeError(
            "'fp.is_implicit_VR' and 'fp.is_little_endian' attributes are required "
        )

    if None in fp_encoding:
        if None not in ds_encoding:
            fp_encoding = ds_encoding
        elif None not in or_encoding:
            fp_encoding = or_encoding

    fp.is_implicit_VR, fp.is_little_endian = cast(tuple[bool, bool], fp_encoding)
    get_item: Callable[[BaseTag], DataElement | RawDataElement] = dataset.get_item

    # This function is doing some heavy lifting:
    #   If implicit -> explicit, runs ambiguous VR correction
    #   If implicit -> explicit, RawDataElements -> DataElement (VR lookup)
    #   If charset changed, RawDataElements -> DataElement
    if (
        fp_encoding != or_encoding
        or dataset.original_character_set != dataset._character_set
    ):
        dataset = correct_ambiguous_vr(dataset, fp.is_little_endian)
        # Use __getitem__ instead or get_item to force parsing of RawDataElements into DataElements,
        # so we can re-encode them with the correct charset and encoding
        get_item = dataset.__getitem__

    dataset_encoding = cast(
        None | str | list[str], dataset.get("SpecificCharacterSet", parent_encoding)
    )

    fpStart = fp.tell()

    # data_elements must be written in tag order
    for tag in sorted(dataset.keys()):
        # do not write retired Group Length (see PS3.5, 7.2)
        if tag.element == 0 and tag.group > 6:
            continue

        with tag_in_exception(tag):
            write_data_element(fp, get_item(tag), dataset_encoding)

    return fp.tell() - fpStart


def write_sequence(fp: DicomIO, elem: DataElement, encodings: list[str]) -> None:
    """Write a sequence contained in `data_element` to the file-like `fp`.

    Parameters
    ----------
    fp : file-like
        The file-like to write the encoded data to.
    data_element : dataelem.DataElement
        The sequence element to write to `fp`.
    encodings : list of str
        The character encodings to use on text values.
    """
    # write_data_element has already written the VR='SQ' (if needed) and
    #    a placeholder for length"""
    for ds in cast(Iterable[Dataset], elem.value):
        write_sequence_item(fp, ds, encodings)


def write_sequence_item(fp: DicomIO, dataset: Dataset, encodings: list[str]) -> None:
    """Write a `dataset` in a sequence to the file-like `fp`.

    This is similar to writing a data_element, but with a specific tag for
    Sequence Item.

    See DICOM Standard, Part 5, :dcm:`Section 7.5<sect_7.5.html>`.

    Parameters
    ----------
    fp : file-like
        The file-like to write the encoded data to.
    dataset : Dataset
        The :class:`Dataset<pydicom.dataset.Dataset>` to write to `fp`.
    encodings : list of str
        The character encodings to use on text values.
    """
    fp.write_tag(ItemTag)  # marker for start of Sequence Item
    length_location = fp.tell()  # save location for later.
    # will fill in real value later if not undefined length
    fp.write_UL(0xFFFFFFFF)
    write_dataset(fp, dataset, parent_encoding=encodings)
    if getattr(dataset, "is_undefined_length_sequence_item", False):
        fp.write_tag(ItemDelimiterTag)
        fp.write_UL(0)  # 4-bytes 'length' field for delimiter item
    else:  # we will be nice and set the lengths for the reader of this file
        location = fp.tell()
        fp.seek(length_location)
        fp.write_UL(location - length_location - 4)  # 4 is length of UL
        fp.seek(location)  # ready for next data_element


def write_UN(fp: DicomIO, elem: DataElement) -> None:
    """Write a byte string for an DataElement of value 'UN' (unknown)."""
    fp.write(cast(bytes, elem.value))


def write_ATvalue(fp: DicomIO, elem: DataElement) -> None:
    """Write a data_element tag to a file."""
    try:
        iter(cast(Sequence[Any], elem.value))  # see if is multi-valued AT;
        # Note will fail if Tag ever derived from true tuple rather than being
        # a long
    except TypeError:
        # make sure is expressed as a Tag instance
        tag = Tag(cast(int, elem.value))
        fp.write_tag(tag)
    else:
        tags = [Tag(tag) for tag in cast(Sequence[int], elem.value)]
        for tag in tags:
            fp.write_tag(tag)


def write_file_meta_info(
    fp: DicomIO, file_meta: FileMetaDataset, enforce_standard: bool = True
) -> None:
    """Write the File Meta Information elements in `file_meta` to `fp`.

    If `enforce_standard` is ``True`` then the file-like `fp` should be
    positioned past the 128 byte preamble + 4 byte prefix (which should
    already have been written).

    **DICOM File Meta Information Group Elements**

    From the DICOM standard, Part 10,
    :dcm:`Section 7.1<part10/chapter_7.html#sect_7.1>`,  any DICOM file shall
    contain a 128-byte preamble, a 4-byte DICOM prefix 'DICM' and (at a
    minimum) the following Type 1 DICOM Elements (from
    :dcm:`Table 7.1-1<part10/chapter_7.html#table_7.1-1>`):

    * (0002,0000) *File Meta Information Group Length*, UL, 4
    * (0002,0001) *File Meta Information Version*, OB, 2
    * (0002,0002) *Media Storage SOP Class UID*, UI, N
    * (0002,0003) *Media Storage SOP Instance UID*, UI, N
    * (0002,0010) *Transfer Syntax UID*, UI, N
    * (0002,0012) *Implementation Class UID*, UI, N

    If `enforce_standard` is ``True`` then (0002,0000) will be added/updated,
    (0002,0001) and (0002,0012) will be added if not already present and the
    other required elements will be checked to see if they exist. If
    `enforce_standard` is ``False`` then `file_meta` will be written as is
    after minimal validation checking.

    The following Type 3/1C Elements may also be present:

    * (0002,0013) *Implementation Version Name*, SH, N
    * (0002,0016) *Source Application Entity Title*, AE, N
    * (0002,0017) *Sending Application Entity Title*, AE, N
    * (0002,0018) *Receiving Application Entity Title*, AE, N
    * (0002,0102) *Private Information*, OB, N
    * (0002,0100) *Private Information Creator UID*, UI, N

    If `enforce_standard` is ``True`` then (0002,0013) will be added/updated.

    *Encoding*

    The encoding of the *File Meta Information* shall be *Explicit VR Little
    Endian*.

    Parameters
    ----------
    fp : file-like
        The file-like to write the File Meta Information to.
    file_meta : pydicom.dataset.Dataset
        The File Meta Information elements.
    enforce_standard : bool
        If ``False``, then only the *File Meta Information* elements already in
        `file_meta` will be written to `fp`. If ``True`` (default) then a DICOM
        Standards conformant File Meta will be written to `fp`.

    Raises
    ------
    ValueError
        If `enforce_standard` is ``True`` and any of the required *File Meta
        Information* elements are missing from `file_meta`, with the
        exception of (0002,0000), (0002,0001) and (0002,0012).
    ValueError
        If any non-Group 2 Elements are present in `file_meta`.
    """
    validate_file_meta(file_meta, enforce_standard)

    if enforce_standard and "FileMetaInformationGroupLength" not in file_meta:
        # Will be updated with the actual length later
        file_meta.FileMetaInformationGroupLength = 0

    # Write the File Meta Information Group elements
    # first write into a buffer to avoid seeking back, that can be
    # expansive and is not allowed if writing into a zip file
    buffer = DicomBytesIO()
    buffer.is_little_endian = True
    buffer.is_implicit_VR = False
    write_dataset(buffer, file_meta)

    # If FileMetaInformationGroupLength is present it will be the first written
    #   element and we must update its value to the correct length.
    if "FileMetaInformationGroupLength" in file_meta:
        # Update the FileMetaInformationGroupLength value, which is the number
        #   of bytes from the end of the FileMetaInformationGroupLength element
        #   to the end of all the File Meta Information elements.
        # FileMetaInformationGroupLength has a VR of 'UL' and so has a value
        #   that is 4 bytes fixed. The total length of when encoded as
        #   Explicit VR must therefore be 12 bytes.
        file_meta.FileMetaInformationGroupLength = buffer.tell() - 12
        buffer.seek(0)
        write_data_element(buffer, file_meta[0x00020000])

    fp.write(buffer.getvalue())


def _determine_encoding(
    ds: Dataset,
    tsyntax: UID | None,
    implicit_vr: bool | None,
    little_endian: bool | None,
    force_encoding: bool,
) -> tuple[bool, bool]:
    """Return the encoding to use for `ds`.

    If `force_encoding` isn't ``True`` the priority is:

    1. The encoding corresponding to `tsyntax`
    2. The encoding set by `implicit_vr` and `little_endian`
    3. `Dataset.is_implicit_VR` and `Dataset.is_little_endian`
    4. `Dataset.original_encoding`

    If none of those are valid, raise an exception.

    If `force_encoding` is ``True`` then `implicit_vr` and `little_endian` are
    required.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset that is to be encoded.
    tsyntax : pydicom.uid.UID | None
        The dataset's public or private transfer syntax (if any). Private
        transfer syntaxes require `implicit_vr` and `little_endian` be used.
    implicit_vr : bool | None
        The VR encoding method (if supplied)
    little_endian : bool | None
        The encoding endianness (if supplied).
    force_encoding : bool
        If ``True`` then force the encoding to use `implicit_vr` and
        `little_endian`. Default ``False``.

    Returns
    -------
    tuple[bool, bool]
        The encoding to use as ``[use implicit VR, use little endian]``.

    Raises
    ------
    ValueError
        If unable to determine the encoding to use, if `transfer_syntax` is
        not a transfer syntax, or if there's an inconsistency between
        `transfer_syntax` and `implicit_vr` or `little_endian`.
    """
    arg_encoding = (implicit_vr, little_endian)
    if force_encoding:
        if None in arg_encoding:
            raise ValueError(
                "'implicit_vr' and 'little_endian' are required if "
                "'force_encoding' is used"
            )

        return cast(tuple[bool, bool], arg_encoding)

    # The default for little_endian is `None` so we can require the use of
    #   args with `force_encoding`, but we actually default it to `True`
    #   when `implicit_vr` is used as a fallback
    if implicit_vr is not None and little_endian is None:
        arg_encoding = (implicit_vr, True)

    ds_encoding: EncodingType = (None, None)
    if not config._use_future:
        ds_encoding = (ds.is_implicit_VR, ds.is_little_endian)

    fallback_encoding: EncodingType = (None, None)
    if None not in arg_encoding:
        fallback_encoding = arg_encoding
    elif None not in ds_encoding:
        fallback_encoding = ds_encoding
    elif None not in ds.original_encoding:
        fallback_encoding = ds.original_encoding

    if tsyntax is None:
        if None not in fallback_encoding:
            return cast(tuple[bool, bool], fallback_encoding)

        raise ValueError(
            "Unable to determine the encoding to use for writing the dataset, "
            "please set the file meta's Transfer Syntax UID or use the "
            "'implicit_vr' and 'little_endian' arguments"
        )

    if tsyntax.is_private and not tsyntax.is_transfer_syntax:
        if None in fallback_encoding:
            raise ValueError(
                "The 'implicit_vr' and 'little_endian' arguments are required "
                "when using a private transfer syntax"
            )

        return cast(tuple[bool, bool], fallback_encoding)

    if not tsyntax.is_transfer_syntax:
        raise ValueError(
            f"The Transfer Syntax UID '{tsyntax.name}' is not a valid "
            "transfer syntax"
        )

    # Check that supplied args match transfer syntax
    if implicit_vr is not None and implicit_vr != tsyntax.is_implicit_VR:
        raise ValueError(
            f"The 'implicit_vr' value is not consistent with the required "
            f"VR encoding for the '{tsyntax.name}' transfer syntax"
        )

    if little_endian is not None and little_endian != tsyntax.is_little_endian:
        raise ValueError(
            f"The 'little_endian' value is not consistent with the required "
            f"endianness for the '{tsyntax.name}' transfer syntax"
        )

    return (tsyntax.is_implicit_VR, tsyntax.is_little_endian)


def dcmwrite(
    filename: PathType | BinaryIO | WriteableBuffer,
    dataset: Dataset,
    /,
    __write_like_original: bool | None = None,
    *,
    implicit_vr: bool | None = None,
    little_endian: bool | None = None,
    enforce_file_format: bool = False,
    force_encoding: bool = False,
    overwrite: bool = True,
    **kwargs: Any,
) -> None:
    """Write `dataset` to `filename`, which can be a path, a file-like or a
    writeable buffer.

    .. versionchanged:: 3.0

        Added the `enforce_file_format` and `overwrite` keyword arguments.

    .. deprecated:: 3.0

        `write_like_original` is deprecated and will be removed in v4.0, use
        `enforce_file_format` instead.

    If `enforce_file_format` is ``True`` then an attempt will be made to write
    `dataset` using the :dcm:`DICOM File Format <part10/chapter_7.html>`, or
    raise an exception if unable to do so.

    If `enforce_file_format` is ``False`` (default) then `dataset` will be
    written as-is (after minimal validation checking) and may or may not
    contain all or parts of the *File Meta Information* and hence may or may
    not be conformant with the DICOM File Format.

    **DICOM File Format**

    The *DICOM File Format* consists of a 128-byte preamble, a 4 byte
    ``b'DICM'`` prefix, the *File Meta Information Group* elements and finally
    the encoded `dataset`.

    **Preamble and Prefix**

    The ``dataset.preamble`` attribute shall be 128-bytes long or ``None``. The
    actual preamble written depends on `enforce_file_format` and
    ``dataset.preamble`` (see the table below).

    +------------------+------------------------------+
    |                  | enforce_file_format          |
    +------------------+-------------+----------------+
    | dataset.preamble | False       | True           |
    +==================+=============+================+
    | None             | no preamble | 128 0x00 bytes |
    +------------------+-------------+----------------+
    | 128 bytes        | dataset.preamble             |
    +------------------+------------------------------+

    The prefix shall be the bytestring ``b'DICM'`` and will be written if and
    only if the preamble is present.

    **File Meta Information Group Elements**

    The preamble and prefix are followed by a set of DICOM elements from the
    (0002,eeee) group. Some of these elements are required (Type 1) while
    others are optional (Type 3/1C). If `enforce_file_format` is ``False``
    then the *File Meta Information Group* elements are all optional, otherwise
    an attempt will be made to add the required elements using `dataset`. See
    :func:`~pydicom.filewriter.write_file_meta_info` for more information on
    which elements are required.

    The *File Meta Information Group* elements must be included within their
    own :class:`~pydicom.dataset.FileMetaDataset` in the ``dataset.file_meta``
    attribute.

    *Encoding*

    The preamble and prefix are encoding independent. The *File Meta
    Information Group* elements are encoded as *Explicit VR Little Endian* as
    required by the DICOM Standard.

    **Dataset**

    A DICOM Dataset representing a SOP Instance related to a DICOM Information
    Object Definition (IOD). It's up to the user to ensure `dataset` conforms
    to the requirements of the IOD.

    *Encoding*

    .. versionchanged:: 3.0

        Added the `implicit_vr` and `little_endian` arguments.

    The `dataset` is encoded as specified by (in order of priority):

    * The encoding corresponding to the set *Transfer Syntax UID* in
      :attr:`~pydicom.dataset.FileDataset.file_meta`.
    * The `implicit_vr` and `little_endian` arguments
    * :attr:`~pydicom.dataset.Dataset.is_implicit_VR` and
      :attr:`~pydicom.dataset.Dataset.is_little_endian`
    * :attr:`~pydicom.dataset.Dataset.original_encoding`

    .. warning::

        This function does not automatically convert `dataset` from little
        to big endian encoding (or vice versa). The endianness of values for
        elements with a VR of **OD**, **OF**, **OL**, **OW**, **OV** and
        **UN** must be converted manually prior to calling
        :func:`~pydicom.filewriter.dcmwrite`.

    Parameters
    ----------
    filename : str, PathLike, file-like or writeable buffer
        File path, file-like or writeable buffer to write the encoded `dataset`
        to. If using a writeable buffer it must have ``write()``, ``seek()``
        and ``tell()`` methods.
    dataset : pydicom.dataset.FileDataset
        The dataset to be encoded.
    write_like_original : bool, optional
        If ``True`` (default) then write `dataset` as-is, otherwise
        ensure that `dataset` is written in the DICOM File Format or
        raise an exception if that isn't possible. This parameter is
        deprecated, please use `enforce_file_format` instead.
    implicit_vr : bool, optional
        Required if `dataset` has no valid public *Transfer Syntax UID*
        set in the file meta and `dataset` has been created from scratch. If
        ``True`` then encode `dataset` using implicit VR, otherwise use
        explicit VR.
    little_endian : bool, optional
        Required if `dataset` has no valid public *Transfer Syntax UID*
        set in the file meta and `dataset` has been created from scratch. If
        ``True`` (default) then use little endian byte order when encoding
        `dataset`, otherwise use big endian.
    enforce_file_format : bool, optional
        If ``True`` then ensure `dataset` is written in the DICOM File
        Format or raise an exception if that isn't possible.

        If ``False`` (default) then write `dataset` as-is, preserving the
        following - which may result in a non-conformant file:

        - ``dataset.preamble``: if `dataset` has no preamble then none will
          be written
        - ``dataset.file_meta``: if `dataset` is missing any required *File
          Meta Information Group* elements then they will not be written.
    force_encoding : bool, optional
        If ``True`` then force the encoding to follow `implicit_vr` and
        `little_endian`. Cannot be used with `enforce_file_format`. Default
        ``False``.
    overwrite : bool, optional
        If ``False`` and `filename` is a :class:`str` or PathLike, then raise a
        :class:`FileExistsError` if a file already exists with the given filename
        (default ``True``).

    Raises
    ------
    ValueError

      * If group ``0x0000`` *Command Set* elements are present in `dataset`.
      * If group ``0x0002`` *File Meta Information Group* elements are present
        in `dataset`.
      * If ``dataset.preamble`` exists but is not 128 bytes long.

    See Also
    --------
    pydicom.dataset.Dataset
        Dataset class with relevant attributes and information.
    pydicom.dataset.Dataset.save_as
        Encode a dataset and write it to file, wraps ``dcmwrite()``.
    """
    # TODO: Remove in v4.0
    # Cover use of `write_like_original` as:
    #   optional arg - dcmwrite(fp, ds, write_like_original=bool)
    #   positional arg - dcmwrite(fp, ds, False)
    write_like_original: bool | None = kwargs.get("write_like_original", None)
    if None not in (__write_like_original, write_like_original):
        if config._use_future:
            raise TypeError(
                "'write_like_original' is no longer accepted as a positional "
                "or keyword argument, use 'enforce_file_format' instead"
            )

        raise TypeError(
            "'write_like_original' cannot be used as both a positional "
            "and keyword argument"
        )

    if write_like_original is None:
        write_like_original = __write_like_original

    if write_like_original is not None:
        if config._use_future:
            raise TypeError(
                "'write_like_original' is no longer accepted as a positional "
                "or keyword argument, use 'enforce_file_format' instead"
            )

        warn_and_log(
            (
                "'write_like_original' is deprecated and will be removed in "
                "v4.0, please use 'enforce_file_format' instead"
            ),
            DeprecationWarning,
        )
        enforce_file_format = not write_like_original

    # Ensure kwargs only contains `write_like_original`
    keys = [x for x in kwargs.keys() if x != "write_like_original"]
    if keys:
        raise TypeError(
            f"Invalid keyword argument(s) for dcmwrite(): {', '.join(keys)}"
        )

    cls_name = dataset.__class__.__name__

    # Check for disallowed tags
    bad_tags = [x >> 16 for x in dataset._dict if x >> 16 in (0, 2)]
    if bad_tags:
        if 0 in bad_tags:
            raise ValueError(
                "Command Set elements (0000,eeee) are not allowed when using "
                "dcmwrite(), use write_dataset() instead"
            )
        else:
            raise ValueError(
                "File Meta Information Group elements (0002,eeee) must be in a "
                f"FileMetaDataset instance in the '{cls_name}.file_meta' attribute"
            )

    if force_encoding and enforce_file_format:
        raise ValueError("'force_encoding' cannot be used with 'enforce_file_format'")

    # Avoid making changes to the original File Meta Information
    file_meta = FileMetaDataset()
    if hasattr(dataset, "file_meta"):
        file_meta = deepcopy(dataset.file_meta)

    tsyntax: UID | None = file_meta.get("TransferSyntaxUID", None)

    # The dataset encoding method
    encoding = _determine_encoding(
        dataset,
        tsyntax,
        implicit_vr,
        little_endian,
        force_encoding,
    )

    if not force_encoding and encoding == (True, False):
        raise ValueError(
            "Implicit VR and big endian is not a valid encoding combination"
        )

    preamble = getattr(dataset, "preamble", None)
    if preamble and len(preamble) != 128:
        raise ValueError(f"'{cls_name}.preamble' must be 128-bytes long")

    if enforce_file_format:
        # A valid File Meta Information is required
        if tsyntax is None:
            if encoding == (True, True):
                file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
            elif encoding == (False, False):
                file_meta.TransferSyntaxUID = ExplicitVRBigEndian

            tsyntax = file_meta.get("TransferSyntaxUID", None)

        # Ensure the file_meta Class and Instance UIDs are up to date
        #   but don't overwrite if nothing is set in the dataset
        meta_class = file_meta.get("MediaStorageSOPClassUID", None)
        ds_class = dataset.get("SOPClassUID", None)
        if meta_class is None or (ds_class and ds_class != meta_class):
            file_meta.MediaStorageSOPClassUID = ds_class

        meta_instance = file_meta.get("MediaStorageSOPInstanceUID", None)
        ds_instance = dataset.get("SOPInstanceUID", None)
        if meta_instance is None or (ds_instance and ds_instance != meta_instance):
            file_meta.MediaStorageSOPInstanceUID = ds_instance

        # Will raise if the file meta isn't valid
        validate_file_meta(file_meta, enforce_standard=True)

        # A preamble is required
        if not preamble:
            preamble = b"\x00" * 128

    if tsyntax and not tsyntax.is_private and tsyntax.is_transfer_syntax:
        # PS3.5 Annex A.4 - the length of encapsulated pixel data is undefined
        #   and native pixel data uses actual length
        if "PixelData" in dataset:
            dataset["PixelData"].is_undefined_length = tsyntax.is_compressed

    caller_owns_file = True
    # Open file if not already a file object
    filename = path_from_pathlike(filename)
    if isinstance(filename, str):
        # A path-like to be written to
        file_mode = "xb" if not overwrite else "wb"
        fp: DicomIO = DicomFile(filename, file_mode)
        # caller provided a file name; we own the file handle
        caller_owns_file = False
    elif isinstance(filename, DicomIO):
        # A wrapped writeable buffer, don't wrap it again
        fp = filename
    else:
        # Anything else
        try:
            fp = DicomIO(filename)
        except AttributeError as exc:
            raise TypeError(
                "dcmwrite: Expected a file path, file-like or writeable buffer, "
                f"but got {type(filename).__name__}"
            ) from exc

    # Set the encoding of the buffer/file-like
    fp.is_implicit_VR, fp.is_little_endian = encoding

    try:
        if preamble:
            # Write the 'DICM' prefix if and only if we write the preamble
            fp.write(preamble)
            fp.write(b"DICM")

        if file_meta:  # May be empty
            write_file_meta_info(fp, file_meta, enforce_standard=enforce_file_format)

        if tsyntax == DeflatedExplicitVRLittleEndian:
            # See PS3.5 section A.5
            # When writing, the entire dataset following the file meta data
            #   is encoded normally, then "deflate" compression applied
            buffer = DicomBytesIO()
            buffer.is_implicit_VR, buffer.is_little_endian = encoding
            write_dataset(buffer, dataset)

            # Compress the encoded data and write to file
            compressor = zlib.compressobj(wbits=-zlib.MAX_WBITS)
            deflated = bytearray(compressor.compress(buffer.getvalue()))
            deflated += compressor.flush()
            fp.write(deflated)
            if len(deflated) % 2:
                fp.write(b"\x00")

        else:
            write_dataset(fp, dataset)

    finally:
        if not caller_owns_file:
            fp.close()


# Map each VR to a function which can write it
# for write_numbers, the Writer maps to a tuple (function, struct_format)
#   (struct_format is python's struct module format)
writers = {
    VR.AE: (write_string, None),
    VR.AS: (write_string, None),
    VR.AT: (write_ATvalue, None),
    VR.CS: (write_string, None),
    VR.DA: (write_DA, None),
    VR.DS: (write_number_string, None),
    VR.DT: (write_DT, None),
    VR.FD: (write_numbers, "d"),
    VR.FL: (write_numbers, "f"),
    VR.IS: (write_number_string, None),
    VR.LO: (write_text, None),
    VR.LT: (write_text, None),
    VR.OB: (write_OBvalue, None),
    VR.OD: (write_OWvalue, None),
    VR.OF: (write_OWvalue, None),
    VR.OL: (write_OWvalue, None),
    VR.OW: (write_OWvalue, None),
    VR.OV: (write_OWvalue, None),
    VR.PN: (write_PN, None),
    VR.SH: (write_text, None),
    VR.SL: (write_numbers, "l"),
    VR.SQ: (write_sequence, None),
    VR.SS: (write_numbers, "h"),
    VR.ST: (write_text, None),
    VR.SV: (write_numbers, "q"),
    VR.TM: (write_TM, None),
    VR.UC: (write_text, None),
    VR.UI: (write_UI, None),
    VR.UL: (write_numbers, "L"),
    VR.UN: (write_UN, None),
    VR.UR: (write_string, None),
    VR.US: (write_numbers, "H"),
    VR.UT: (write_text, None),
    VR.UV: (write_numbers, "Q"),
    VR.US_SS: (write_OWvalue, None),
    VR.US_OW: (write_OWvalue, None),
    VR.US_SS_OW: (write_OWvalue, None),
    VR.OB_OW: (write_OBvalue, None),
}
