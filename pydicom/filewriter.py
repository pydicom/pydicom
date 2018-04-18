# Copyright 2008-2017 pydicom authors. See LICENSE file for details.
"""Functions related to writing DICOM data."""
from __future__ import absolute_import
from struct import pack

from pydicom import compat
from pydicom.compat import in_py2
from pydicom.charset import default_encoding, text_VRs, convert_encodings
from pydicom.datadict import keyword_for_tag
from pydicom.dataelem import DataElement_from_raw
from pydicom.dataset import Dataset
from pydicom.filebase import DicomFile, DicomFileLike, DicomBytesIO
from pydicom.multival import MultiValue
from pydicom.tag import (Tag, ItemTag, ItemDelimiterTag, SequenceDelimiterTag,
                         tag_in_exception)
from pydicom.uid import (PYDICOM_IMPLEMENTATION_UID, ImplicitVRLittleEndian,
                         ExplicitVRBigEndian,
                         UncompressedPixelTransferSyntaxes)
from pydicom.valuerep import extra_length_VRs
from pydicom.values import convert_numbers
from pydicom._version import __version_info__


def correct_ambiguous_vr_element(elem, ds, is_little_endian):
    """Attempt to correct the ambiguous VR element `elem`.

    When it's not possible to correct the VR, the element will be returned
    unchanged. Currently the only ambiguous VR elements not corrected for are
    all retired or part of DICONDE.

    If the VR is corrected and is 'US' or 'SS' then the value will be updated
    using the pydicom.values.convert_numbers() method.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The element with an ambiguous VR.
    ds : pydicom.dataset.Dataset
        The dataset containing `elem`.
    is_little_endian : bool
        The byte ordering of the values in the dataset.

    Returns
    -------
    elem : pydicom.dataelem.DataElement
        The corrected element
    """
    if 'or' in elem.VR:
        # convert raw data elements before handling them
        if elem.is_raw:
            elem = DataElement_from_raw(elem)
            ds.__setitem__(elem.tag, elem)

        # 'OB or OW': 7fe0,0010 PixelData
        if elem.tag == 0x7fe00010:

            try:
                # Compressed Pixel Data
                # PS3.5 Annex A.4
                #   If encapsulated, VR is OB and length is undefined
                if elem.is_undefined_length:
                    elem.VR = 'OB'
                else:
                    # Non-compressed Pixel Data
                    # If BitsAllocated is > 8 then OW, else may be OB or OW
                    #   as per PS3.5 Annex A.2. For BitsAllocated < 8 test the
                    #    size of each pixel to see if its written in OW or OB
                    if ds.BitsAllocated > 8:
                        elem.VR = 'OW'
                    else:
                        if len(ds.PixelData) / (ds.Rows * ds.Columns) == 2:
                            elem.VR = 'OW'
                        elif len(ds.PixelData) / (ds.Rows * ds.Columns) == 1:
                            elem.VR = 'OB'
            except AttributeError:
                pass

        # 'US or SS' and dependent on PixelRepresentation
        elif elem.tag in [
                0x00189810, 0x00221452, 0x00280104, 0x00280105, 0x00280106,
                0x00280107, 0x00280108, 0x00280109, 0x00280110, 0x00280111,
                0x00280120, 0x00280121, 0x00281101, 0x00281102, 0x00281103,
                0x00283002, 0x00409211, 0x00409216, 0x00603004, 0x00603006
        ]:
            # US if PixelRepresenation value is 0x0000, else SS
            #   For references, see the list at
            #   https://github.com/darcymason/pydicom/pull/298
            if 'PixelRepresentation' in ds:
                if ds.PixelRepresentation == 0:
                    elem.VR = 'US'
                    byte_type = 'H'
                else:
                    elem.VR = 'SS'
                    byte_type = 'h'
                elem.value = convert_numbers(elem.value, is_little_endian,
                                             byte_type)

        # 'OB or OW' and dependent on WaveformBitsAllocated
        elif elem.tag in [0x54000100, 0x54000112, 0x5400100A, 0x54001010]:
            # If WaveformBitsAllocated is > 8 then OW, otherwise may be
            #   OB or OW, however not sure how to handle this.
            #   See PS3.3 C.10.9.1.
            if 'WaveformBitsAllocated' in ds:
                if ds.WaveformBitsAllocated > 8:
                    elem.VR = 'OW'

        # 'US or OW': 0028,3006 LUTData
        elif elem.tag in [0x00283006]:
            if 'LUTDescriptor' in ds:
                # First value in LUT Descriptor is how many values in
                #   LUTData, if there's only one value then must be US
                # As per PS3.3 C.11.1.1.1
                if ds.LUTDescriptor[0] == 1:
                    elem.VR = 'US'
                    elem.value = convert_numbers(elem.value, is_little_endian,
                                                 'H')
                else:
                    elem.VR = 'OW'

        # 'OB or OW': 60xx,3000 OverlayData and dependent on Transfer Syntax
        elif (elem.tag.group in range(0x6000, 0x601F, 2)
              and elem.tag.elem == 0x3000):
            # Implicit VR must be OW, explicit VR may be OB or OW
            #   as per PS3.5 Section 8.1.2 and Annex A
            if ds.is_implicit_VR:
                elem.VR = 'OW'

    return elem


def correct_ambiguous_vr(ds, is_little_endian):
    """Iterate through `ds` correcting ambiguous VR elements (if possible).

    When it's not possible to correct the VR, the element will be returned
    unchanged. Currently the only ambiguous VR elements not corrected for are
    all retired or part of DICONDE.

    If the VR is corrected and is 'US' or 'SS' then the value will be updated
    using the pydicom.values.convert_numbers() method.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset containing ambiguous VR elements.
    is_little_endian : bool
        The byte ordering of the values in the dataset.

    Returns
    -------
    ds : pydicom.dataset.Dataset
        The corrected dataset
    """
    # if we want to write with the same endianess and VR handling as
    # the read dataset we want to preserve raw data elements
    if ds.write_like_original():
        dataset_elements = ds.elements()
    else:
        dataset_elements = ds

    # Iterate through the elements
    for elem in dataset_elements:
        # raw data element sequences can be written as they are, because we
        # have ensured that the transfer syntax has not changed at this point
        if elem.VR == 'SQ' and not elem.is_raw:
            for item in elem:
                correct_ambiguous_vr(item, is_little_endian)
        elif 'or' in elem.VR:
            correct_ambiguous_vr_element(elem, ds, is_little_endian)
    return ds


def write_numbers(fp, data_element, struct_format):
    """Write a "value" of type struct_format from the dicom file.

    "Value" can be more than one number.

    struct_format -- the character format as used by the struct module.

    """
    endianChar = '><' [fp.is_little_endian]
    value = data_element.value
    if value == "":
        return  # don't need to write anything for empty string

    format_string = endianChar + struct_format
    try:
        try:
            value.append  # works only if list, not if string or number
        except AttributeError:  # is a single value - the usual case
            fp.write(pack(format_string, value))
        else:
            for val in value:
                fp.write(pack(format_string, val))
    except Exception as e:
        raise IOError(
            "{0}\nfor data_element:\n{1}".format(str(e), str(data_element)))


def write_OBvalue(fp, data_element):
    """Write a data_element with VR of 'other byte' (OB)."""
    fp.write(data_element.value)


def write_OWvalue(fp, data_element):
    """Write a data_element with VR of 'other word' (OW).

    Note: This **does not currently do the byte swapping** for Endian state.
    """
    # XXX for now just write the raw bytes without endian swapping
    fp.write(data_element.value)


def write_UI(fp, data_element):
    """Write a data_element with VR of 'unique identifier' (UI)."""
    write_string(fp, data_element, '\0')  # pad with 0-byte to even length


def _is_multi_value(val):
    """Return True if `val` is a multi-value container."""
    return isinstance(val, (MultiValue, list, tuple))


def multi_string(val):
    """Put a string together with delimiter if has more than one value"""
    if _is_multi_value(val):
        # \ is escape chr, so "\\" gives single backslash
        return "\\".join(val)
    else:
        return val


def write_PN(fp, data_element, padding=b' ', encoding=None):
    if not encoding:
        encoding = [default_encoding] * 3

    if data_element.VM == 1:
        val = [data_element.value, ]
    else:
        val = data_element.value

    if isinstance(val[0], compat.text_type) or not in_py2:
        try:
            val = [elem.encode(encoding) for elem in val]
        except TypeError:
            val = [elem.encode(encoding[0]) for elem in val]

    val = b'\\'.join(val)

    if len(val) % 2 != 0:
        val = val + padding

    fp.write(val)


def write_string(fp, data_element, padding=' ', encoding=default_encoding):
    """Write a single or multivalued string."""
    val = multi_string(data_element.value)
    if val is not None:
        if len(val) % 2 != 0:
            val = val + padding  # pad to even length
        if isinstance(val, compat.text_type):
            val = val.encode(encoding)
        fp.write(val)


def write_number_string(fp, data_element, padding=' '):
    """Handle IS or DS VR - write a number stored as a string of digits."""
    # If the DS or IS has an original_string attribute, use that, so that
    # unchanged data elements are written with exact string as when read from
    # file
    val = data_element.value

    if _is_multi_value(val):
        val = "\\".join((x.original_string
                         if hasattr(x, 'original_string') else str(x)
                         for x in val))
    else:
        if hasattr(val, 'original_string'):
            val = val.original_string
        else:
            val = str(val)

    if len(val) % 2 != 0:
        val = val + padding  # pad to even length

    if not in_py2:
        val = bytes(val, default_encoding)

    fp.write(val)


def _format_DA(val):
    if val is None:
        return ''
    elif hasattr(val, 'original_string'):
        return val.original_string
    else:
        return val.strftime("%Y%m%d")


def write_DA(fp, data_element, padding=' '):
    val = data_element.value
    if isinstance(val, (str, compat.string_types)):
        write_string(fp, data_element, padding)
    else:
        if _is_multi_value(val):
            val = "\\".join((x if isinstance(x, (str, compat.string_types))
                             else _format_DA(x) for x in val))
        else:
            val = _format_DA(val)
        if len(val) % 2 != 0:
            val = val + padding  # pad to even length

        if isinstance(val, compat.string_types):
            val = val.encode(default_encoding)

        fp.write(val)


def _format_DT(val):
    if hasattr(val, 'original_string'):
        return val.original_string
    elif val.microsecond > 0:
        return val.strftime("%Y%m%d%H%M%S.%f%z")
    else:
        return val.strftime("%Y%m%d%H%M%S%z")


def write_DT(fp, data_element, padding=' '):
    val = data_element.value
    if isinstance(val, (str, compat.string_types)):
        write_string(fp, data_element, padding)
    else:
        if _is_multi_value(val):
            val = "\\".join((x if isinstance(x, (str, compat.string_types))
                             else _format_DT(x) for x in val))
        else:
            val = _format_DT(val)
        if len(val) % 2 != 0:
            val = val + padding  # pad to even length

        if isinstance(val, compat.string_types):
            val = val.encode(default_encoding)

        fp.write(val)


def _format_TM(val):
    if val is None:
        return ''
    elif hasattr(val, 'original_string'):
        return val.original_string
    elif val.microsecond > 0:
        return val.strftime("%H%M%S.%f")
    else:
        return val.strftime("%H%M%S")


def write_TM(fp, data_element, padding=' '):
    val = data_element.value
    if isinstance(val, (str, compat.string_types)):
        write_string(fp, data_element, padding)
    else:
        if _is_multi_value(val):
            val = "\\".join((x if isinstance(x, (str, compat.string_types))
                             else _format_TM(x) for x in val))
        else:
            val = _format_TM(val)
        if len(val) % 2 != 0:
            val = val + padding  # pad to even length

        if isinstance(val, compat.string_types):
            val = val.encode(default_encoding)

        fp.write(val)


def write_data_element(fp, data_element, encoding=default_encoding):
    """Write the data_element to file fp according to dicom media storage rules.
    """
    # Write element's tag
    fp.write_tag(data_element.tag)

    # If explicit VR, write the VR
    VR = data_element.VR
    if not fp.is_implicit_VR:
        if len(VR) != 2:
            msg = ("Cannot write ambiguous VR of '{}' for data element with "
                   "tag {}.\nSet the correct VR before writing, or use an "
                   "implicit VR transfer syntax".format(
                       VR, repr(data_element.tag)))
            raise ValueError(msg)
        if not in_py2:
            fp.write(bytes(VR, default_encoding))
        else:
            fp.write(VR)
        if VR in extra_length_VRs:
            fp.write_US(0)  # reserved 2 bytes

    # write into a buffer to avoid seeking back which can be expansive
    buffer = DicomBytesIO()
    buffer.is_little_endian = fp.is_little_endian
    buffer.is_implicit_VR = fp.is_implicit_VR

    if data_element.is_raw:
        # raw data element values can be written as they are
        buffer.write(data_element.value)
        is_undefined_length = data_element.length == 0xFFFFFFFF
    else:
        if VR not in writers:
            raise NotImplementedError(
                "write_data_element: unknown Value Representation "
                "'{0}'".format(VR))

        encoding = convert_encodings(encoding)
        writer_function, writer_param = writers[VR]
        is_undefined_length = data_element.is_undefined_length
        if VR in text_VRs:
            writer_function(buffer, data_element, encoding=encoding[1])
        elif VR in ('PN', 'SQ'):
            writer_function(buffer, data_element, encoding=encoding)
        else:
            # Many numeric types use the same writer but with numeric format
            # parameter
            if writer_param is not None:
                writer_function(buffer, data_element, writer_param)
            else:
                writer_function(buffer, data_element)

    # valid pixel data with undefined length shall contain encapsulated
    # data, e.g. sequence items - raise ValueError otherwise (see #238)
    if is_undefined_length and data_element.tag == 0x7fe00010:
        val = data_element.value
        if (fp.is_little_endian and not
                val.startswith(b'\xfe\xff\x00\xe0') or
                not fp.is_little_endian and
                not val.startswith(b'\xff\xfe\xe0\x00')):
            raise ValueError('Pixel Data with undefined length must '
                             'start with an item tag')

    value_length = buffer.tell()
    if (not fp.is_implicit_VR and VR not in extra_length_VRs and
            not is_undefined_length):
        fp.write_US(value_length)  # Explicit VR length field is only 2 bytes
    else:
        # write the proper length of the data_element in the length slot,
        # unless is SQ with undefined length.
        fp.write_UL(0xFFFFFFFF if is_undefined_length else value_length)

    fp.write(buffer.getvalue())
    if is_undefined_length:
        fp.write_tag(SequenceDelimiterTag)
        fp.write_UL(0)  # 4-byte 'length' of delimiter data item


def write_dataset(fp, dataset, parent_encoding=default_encoding):
    """Write a Dataset dictionary to the file. Return the total length written.

    Attempt to correct ambiguous VR elements when explicit little/big
      encoding Elements that can't be corrected will be returned unchanged.
    """
    if not fp.is_implicit_VR:
        dataset = correct_ambiguous_vr(dataset, fp.is_little_endian)

    dataset_encoding = dataset.get('SpecificCharacterSet', parent_encoding)

    fpStart = fp.tell()
    # data_elements must be written in tag order
    tags = sorted(dataset.keys())

    for tag in tags:
        # do not write retired Group Length (see PS3.5, 7.2)
        if tag.element == 0 and tag.group > 6:
            continue
        with tag_in_exception(tag):
            # write_data_element(fp, dataset.get_item(tag), dataset_encoding)
            # XXX for writing raw tags without converting to DataElement
            write_data_element(fp, dataset.get_item(tag), dataset_encoding)

    return fp.tell() - fpStart


def write_sequence(fp, data_element, encoding):
    """Write a dicom Sequence contained in data_element to the file fp."""
    # write_data_element has already written the VR='SQ' (if needed) and
    #    a placeholder for length"""
    sequence = data_element.value
    for dataset in sequence:
        write_sequence_item(fp, dataset, encoding)


def write_sequence_item(fp, dataset, encoding):
    """Write an item (dataset) in a dicom Sequence to the dicom file fp.

    This is similar to writing a data_element, but with a specific tag for
    Sequence Item

    see Dicom standard Part 5, p. 39 ('03 version)
    """
    fp.write_tag(ItemTag)  # marker for start of Sequence Item
    length_location = fp.tell()  # save location for later.
    # will fill in real value later if not undefined length
    fp.write_UL(0xffffffff)
    write_dataset(fp, dataset, parent_encoding=encoding)
    if getattr(dataset, "is_undefined_length_sequence_item", False):
        fp.write_tag(ItemDelimiterTag)
        fp.write_UL(0)  # 4-bytes 'length' field for delimiter item
    else:  # we will be nice and set the lengths for the reader of this file
        location = fp.tell()
        fp.seek(length_location)
        fp.write_UL(location - length_location - 4)  # 4 is length of UL
        fp.seek(location)  # ready for next data_element


def write_UN(fp, data_element):
    """Write a byte string for an DataElement of value 'UN' (unknown)."""
    fp.write(data_element.value)


def write_ATvalue(fp, data_element):
    """Write a data_element tag to a file."""
    try:
        iter(data_element.value)  # see if is multi-valued AT;
        # Note will fail if Tag ever derived from true tuple rather than being
        # a long
    except TypeError:
        # make sure is expressed as a Tag instance
        tag = Tag(data_element.value)
        fp.write_tag(tag)
    else:
        tags = [Tag(tag) for tag in data_element.value]
        for tag in tags:
            fp.write_tag(tag)


def write_file_meta_info(fp, file_meta, enforce_standard=True):
    """Write the File Meta Information elements in `file_meta` to `fp`.

    If `enforce_standard` is True then the file-like `fp` should be positioned
    past the 128 byte preamble + 4 byte prefix (which should already have been
    written).

    DICOM File Meta Information Group Elements
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    From the DICOM standard, Part 10 Section 7.1, any DICOM file shall contain
    a 128-byte preamble, a 4-byte DICOM prefix 'DICM' and (at a minimum) the
    following Type 1 DICOM Elements (from Table 7.1-1):
        * (0002,0000) FileMetaInformationGroupLength, UL, 4
        * (0002,0001) FileMetaInformationVersion, OB, 2
        * (0002,0002) MediaStorageSOPClassUID, UI, N
        * (0002,0003) MediaStorageSOPInstanceUID, UI, N
        * (0002,0010) TransferSyntaxUID, UI, N
        * (0002,0012) ImplementationClassUID, UI, N

    If `enforce_standard` is True then (0002,0000) will be added/updated,
    (0002,0001) and (0002,0012) will be added if not already present and the
    other required elements will be checked to see if they exist. If
    `enforce_standard` is False then `file_meta` will be written as is after
    minimal validation checking.

    The following Type 3/1C Elements may also be present:
        * (0002,0013) ImplementationVersionName, SH, N
        * (0002,0016) SourceApplicationEntityTitle, AE, N
        * (0002,0017) SendingApplicationEntityTitle, AE, N
        * (0002,0018) ReceivingApplicationEntityTitle, AE, N
        * (0002,0100) PrivateInformationCreatorUID, UI, N
        * (0002,0102) PrivateInformation, OB, N

    If `enforce_standard` is True then (0002,0013) will be added/updated.

    Encoding
    ~~~~~~~~
    The encoding of the File Meta Information shall be Explicit VR Little
    Endian

    Parameters
    ----------
    fp : file-like
        The file-like to write the File Meta Information to.
    file_meta : pydicom.dataset.Dataset
        The File Meta Information DataElements.
    enforce_standard : bool
        If False, then only the File Meta Information elements already in
        `file_meta` will be written to `fp`. If True (default) then a DICOM
        Standards conformant File Meta will be written to `fp`.

    Raises
    ------
    ValueError
        If `enforce_standard` is True and any of the required File Meta
        Information elements are missing from `file_meta`, with the
        exception of (0002,0000), (0002,0001) and (0002,0012).
    ValueError
        If any non-Group 2 Elements are present in `file_meta`.
    """
    # Check that no non-Group 2 Elements are present
    for elem in file_meta.elements():
        if elem.tag.group != 0x0002:
            raise ValueError("Only File Meta Information Group (0002,eeee) "
                             "elements must be present in 'file_meta'.")

    # The Type 1 File Meta Elements are only required when `enforce_standard`
    #   is True, except for FileMetaInformationGroupLength and
    #   FileMetaInformationVersion, which may or may not be present
    if enforce_standard:
        # Will be updated with the actual length later
        if 'FileMetaInformationGroupLength' not in file_meta:
            file_meta.FileMetaInformationGroupLength = 0

        if 'FileMetaInformationVersion' not in file_meta:
            file_meta.FileMetaInformationVersion = b'\x00\x01'

        if 'ImplementationClassUID' not in file_meta:
            file_meta.ImplementationClassUID = PYDICOM_IMPLEMENTATION_UID

        if 'ImplementationVersionName' not in file_meta:
            file_meta.ImplementationVersionName = (
                'PYDICOM ' + ".".join(str(x) for x in __version_info__))

        # Check that required File Meta Elements are present
        missing = []
        for element in [0x0002, 0x0003, 0x0010]:
            if Tag(0x0002, element) not in file_meta:
                missing.append(Tag(0x0002, element))
        if missing:
            msg = "Missing required File Meta Information elements from " \
                  "'file_meta':\n"
            for tag in missing:
                msg += '\t{0} {1}\n'.format(tag, keyword_for_tag(tag))
            raise ValueError(msg[:-1])  # Remove final newline

    # Only used if FileMetaInformationGroupLength is present.
    #   FileMetaInformationGroupLength has a VR of 'UL' and so has a value that
    #   is 4 bytes fixed. The total length of when encoded as Explicit VR must
    #   therefore be 12 bytes.
    end_group_length_elem = fp.tell() + 12

    # The 'is_little_endian' and 'is_implicit_VR' attributes will need to be
    #   set correctly after the File Meta Info has been written.
    fp.is_little_endian = True
    fp.is_implicit_VR = False

    # Write the File Meta Information Group elements to `fp`
    write_dataset(fp, file_meta)

    # If FileMetaInformationGroupLength is present it will be the first written
    #   element and we must update its value to the correct length.
    if 'FileMetaInformationGroupLength' in file_meta:
        # Save end of file meta to go back to
        end_of_file_meta = fp.tell()

        # Update the FileMetaInformationGroupLength value, which is the number
        #   of bytes from the end of the FileMetaInformationGroupLength element
        #   to the end of all the File Meta Information elements
        group_length = int(end_of_file_meta - end_group_length_elem)
        file_meta.FileMetaInformationGroupLength = group_length
        fp.seek(end_group_length_elem - 12)
        write_data_element(fp, file_meta[0x00020000])

        # Return to end of the file meta, ready to write remainder of the file
        fp.seek(end_of_file_meta)


def dcmwrite(filename, dataset, write_like_original=True):
    """Write `dataset` to the `filename` specified.

    If `write_like_original` is True then `dataset` will be written as is
    (after minimal validation checking) and may or may not contain all or parts
    of the File Meta Information (and hence may or may not be conformant with
    the DICOM File Format).
    If `write_like_original` is False, `dataset` will be stored in the DICOM
    File Format in accordance with DICOM Standard Part 10 Section 7. The byte
    stream of the `dataset` will be placed into the file after the DICOM File
    Meta Information.

    File Meta Information
    ---------------------
    The File Meta Information consists of a 128-byte preamble, followed by a 4
    byte DICOM prefix, followed by the File Meta Information Group elements.

    Preamble and Prefix
    ~~~~~~~~~~~~~~~~~~~
    The `dataset.preamble` attribute shall be 128-bytes long or None and is
    available for use as defined by the Application Profile or specific
    implementations. If the preamble is not used by an Application Profile or
    specific implementation then all 128 bytes should be set to 0x00. The
    actual preamble written depends on `write_like_original` and
    `dataset.preamble` (see the table below).

    +------------------+------------------------------+
    |                  | write_like_original          |
    +------------------+-------------+----------------+
    | dataset.preamble | True        | False          |
    +==================+=============+================+
    | None             | no preamble | 128 0x00 bytes |
    +------------------+------------------------------+
    | 128 bytes        | dataset.preamble             |
    +------------------+------------------------------+

    The prefix shall be the string 'DICM' and will be written if and only if
    the preamble is present.

    File Meta Information Group Elements
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    The preamble and prefix are followed by a set of DICOM Elements from the
    (0002,eeee) group. Some of these elements are required (Type 1) while
    others are optional (Type 3/1C). If `write_like_original` is True then the
    File Meta Information Group elements are all optional. See
    pydicom.filewriter.write_file_meta_info for more information on which
    elements are required.

    The File Meta Information Group elements should be included within their
    own Dataset in the `dataset.file_meta` attribute.

    If (0002,0010) 'Transfer Syntax UID' is included then the user must ensure
    it's value is compatible with the values for the `dataset.is_little_endian`
    and `dataset.is_implicit_VR` attributes. For example, if is_little_endian
    and is_implicit_VR are both True then the Transfer Syntax UID must be
    1.2.840.10008.1.2 'Implicit VR Little Endian'. See the DICOM standard
    Part 5 Section 10 for more information on Transfer Syntaxes.

    Encoding
    ~~~~~~~~
    The preamble and prefix are encoding independent. The File Meta Elements
    are encoded as Explicit VR Little Endian as required by the DICOM standard.

    Dataset
    -------
    A DICOM Dataset representing a SOP Instance related to a DICOM Information
    Object Definition. It is up to the user to ensure the `dataset` conforms
    to the DICOM standard.

    Encoding
    ~~~~~~~~
    The `dataset` is encoded as specified by the `dataset.is_little_endian`
    and `dataset.is_implicit_VR` attributes. It's up to the user to ensure
    these attributes are set correctly (as well as setting an appropriate value
    for `dataset.file_meta.TransferSyntaxUID` if present).

    Parameters
    ----------
    filename : str or file-like
        Name of file or the file-like to write the new DICOM file to.
    dataset : pydicom.dataset.FileDataset
        Dataset holding the DICOM information; e.g. an object read with
        pydicom.dcmread().
    write_like_original : bool
        If True (default), preserves the following information from
        the Dataset (and may result in a non-conformant file):
        - preamble -- if the original file has no preamble then none will be
            written.
        - file_meta -- if the original file was missing any required File Meta
            Information Group elements then they will not be added or written.
            If (0002,0000) 'File Meta Information Group Length' is present then
            it may have its value updated.
        - seq.is_undefined_length -- if original had delimiters, write them now
            too, instead of the more sensible length characters
        - is_undefined_length_sequence_item -- for datasets that belong to a
            sequence, write the undefined length delimiters if that is
            what the original had.
        If False, produces a file conformant with the DICOM File Format, with
        explicit lengths for all elements.

    See Also
    --------
    pydicom.dataset.FileDataset
        Dataset class with relevant attributes and information.
    pydicom.dataset.Dataset.save_as
        Write a DICOM file from a dataset that was read in with dcmread().
        save_as wraps dcmwrite.
    """
    # Check that dataset's group 0x0002 elements are only present in the
    #   `dataset.file_meta` Dataset - user may have added them to the wrong
    #   place
    if dataset.group_dataset(0x0002) != Dataset():
        raise ValueError("File Meta Information Group Elements (0002,eeee) "
                         "should be in their own Dataset object in the "
                         "'{0}.file_meta' "
                         "attribute.".format(dataset.__class__.__name__))

    # A preamble is required under the DICOM standard, however if
    #   `write_like_original` is True we treat it as optional
    preamble = getattr(dataset, 'preamble', None)
    if preamble and len(preamble) != 128:
        raise ValueError("'{0}.preamble' must be 128-bytes "
                         "long.".format(dataset.__class__.__name__))
    if not preamble and not write_like_original:
        # The default preamble is 128 0x00 bytes.
        preamble = b'\x00' * 128

    # File Meta Information is required under the DICOM standard, however if
    #   `write_like_original` is True we treat it as optional
    file_meta = getattr(dataset, 'file_meta', None)
    if not file_meta and not write_like_original:
        dataset.file_meta = Dataset()
        file_meta = dataset.file_meta

    # If enforcing the standard, correct the TransferSyntaxUID where possible,
    #   noting that the transfer syntax for is_implicit_VR = False and
    #   is_little_endian = True is ambiguous as it may be an encapsulated
    #   transfer syntax
    if not write_like_original:
        if dataset.is_little_endian and dataset.is_implicit_VR:
            file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        elif not dataset.is_little_endian and not dataset.is_implicit_VR:
            file_meta.TransferSyntaxUID = ExplicitVRBigEndian
        elif not dataset.is_little_endian and dataset.is_implicit_VR:
            raise NotImplementedError("Implicit VR Big Endian is not a "
                                      "supported Transfer Syntax.")

        if 'SOPClassUID' in dataset:
            file_meta.MediaStorageSOPClassUID = dataset.SOPClassUID
        if 'SOPInstanceUID' in dataset:
            file_meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID

    # Check for decompression, give warnings if inconsistencies
    # If decompressed, then pixel_array is now used instead of PixelData
    if dataset.is_decompressed:
        xfer = dataset.file_meta.TransferSyntaxUID
        if xfer not in UncompressedPixelTransferSyntaxes:
            raise ValueError("file_meta transfer SyntaxUID is compressed type "
                             "but pixel data has been decompressed")

        # Force PixelData to the decompressed version
        dataset.PixelData = dataset.pixel_array.tobytes()

    caller_owns_file = True
    # Open file if not already a file object
    if isinstance(filename, compat.string_types):
        fp = DicomFile(filename, 'wb')
        # caller provided a file name; we own the file handle
        caller_owns_file = False
    else:
        fp = DicomFileLike(filename)

    # if we want to write with the same endianess and VR handling as
    # the read dataset we want to preserve raw data elements for
    # performance reasons (which is done by get_item);
    # otherwise we use the default converting item getter
    if dataset.write_like_original():
        get_item = Dataset.get_item
    else:
        get_item = Dataset.__getitem__

    try:
        # WRITE FILE META INFORMATION
        if preamble:
            # Write the 'DICM' prefix if and only if we write the preamble
            fp.write(preamble)
            fp.write(b'DICM')

        if file_meta is not None:  # May be an empty Dataset
            # If we want to `write_like_original`, don't enforce_standard
            write_file_meta_info(fp, file_meta,
                                 enforce_standard=not write_like_original)

        # WRITE DATASET
        # The transfer syntax used to encode the dataset can't be changed
        #   within the dataset.
        # Write any Command Set elements now as elements must be in tag order
        #   Mixing Command Set with other elements is non-conformant so we
        #   require `write_like_original` to be True
        command_set = get_item(dataset, slice(0x00000000, 0x00010000))
        if command_set and write_like_original:
            fp.is_implicit_VR = True
            fp.is_little_endian = True
            write_dataset(fp, command_set)

        # Set file VR and endianness. MUST BE AFTER writing META INFO (which
        #   requires Explicit VR Little Endian) and COMMAND SET (which requires
        #   Implicit VR Little Endian)
        fp.is_implicit_VR = dataset.is_implicit_VR
        fp.is_little_endian = dataset.is_little_endian

        # Write non-Command Set elements now
        write_dataset(fp, get_item(dataset, slice(0x00010000, None)))
    finally:
        if not caller_owns_file:
            fp.close()


write_file = dcmwrite  # write_file before pydicom 1.0, kept for compatibility

# Map each VR to a function which can write it
# for write_numbers, the Writer maps to a tuple (function, struct_format)
#   (struct_format is python's struct module format)
writers = {
    'UL': (write_numbers, 'L'),
    'SL': (write_numbers, 'l'),
    'US': (write_numbers, 'H'),
    'SS': (write_numbers, 'h'),
    'FL': (write_numbers, 'f'),
    'FD': (write_numbers, 'd'),
    'OF': (write_numbers, 'f'),
    'OB': (write_OBvalue, None),
    'OD': (write_OWvalue, None),
    'OL': (write_OWvalue, None),
    'UI': (write_UI, None),
    'SH': (write_string, None),
    'DA': (write_DA, None),
    'TM': (write_TM, None),
    'CS': (write_string, None),
    'PN': (write_PN, None),
    'LO': (write_string, None),
    'IS': (write_number_string, None),
    'DS': (write_number_string, None),
    'AE': (write_string, None),
    'AS': (write_string, None),
    'LT': (write_string, None),
    'SQ': (write_sequence, None),
    'UC': (write_string, None),
    'UN': (write_UN, None),
    'UR': (write_string, None),
    'AT': (write_ATvalue, None),
    'ST': (write_string, None),
    'OW': (write_OWvalue, None),
    'US or SS': (write_OWvalue, None),
    'US or OW': (write_OWvalue, None),
    'US or SS or OW': (write_OWvalue, None),
    'OW/OB': (write_OBvalue, None),
    'OB/OW': (write_OBvalue, None),
    'OB or OW': (write_OBvalue, None),
    'OW or OB': (write_OBvalue, None),
    'DT': (write_DT, None),
    'UT': (write_string, None),
}  # note OW/OB depends on other items, which we don't know at write time
