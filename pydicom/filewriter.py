# filewriter.py
"""Write a dicom media file."""
from __future__ import absolute_import
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

from struct import pack

from pydicom import compat
from pydicom.config import logger

from pydicom.compat import in_py2
from pydicom.charset import default_encoding, text_VRs, convert_encodings
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
from pydicom.filebase import DicomFile, DicomFileLike
from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement
from pydicom.tag import Tag, ItemTag, ItemDelimiterTag, SequenceDelimiterTag
from pydicom.valuerep import extra_length_VRs
from pydicom.tagtools import tag_in_exception


def write_numbers(fp, data_element, struct_format):
    """Write a "value" of type struct_format from the dicom file.

    "Value" can be more than one number.

    struct_format -- the character format as used by the struct module.

    """
    endianChar = '><'[fp.is_little_endian]
    value = data_element.value
    if value == "":
        return  # don't need to write anything for empty string

    format_string = endianChar + struct_format
    try:
        try:
            value.append   # works only if list, not if string or number
        except AttributeError:  # is a single value - the usual case
            fp.write(pack(format_string, value))
        else:
            for val in value:
                fp.write(pack(format_string, val))
    except Exception as e:
        raise IOError("{0}\nfor data_element:\n{1}".format(str(e), str(data_element)))


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


def multi_string(val):
    """Put a string together with delimiter if has more than one value"""
    if isinstance(val, (list, tuple)):
        return "\\".join(val)  # \ is escape chr, so "\\" gives single backslash
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
        val = [elem.encode(encoding) for elem in val]

    val = b'\\'.join(val)

    if len(val) % 2 != 0:
        val = val + padding

    fp.write(val)


def write_string(fp, data_element, padding=' ', encoding=default_encoding):
    """Write a single or multivalued string."""
    val = multi_string(data_element.value)
    if len(val) % 2 != 0:
        val = val + padding  # pad to even length

    if isinstance(val, compat.text_type):
        val = val.encode(encoding)

    fp.write(val)


def write_number_string(fp, data_element, padding=' '):
    """Handle IS or DS VR - write a number stored as a string of digits."""
    # If the DS or IS has an original_string attribute, use that, so that
    # unchanged data elements are written with exact string as when read from file
    val = data_element.value
    if isinstance(val, (list, tuple)):
        val = "\\".join((x.original_string if hasattr(x, 'original_string')
                         else str(x) for x in val))
    else:
        val = val.original_string if hasattr(val, 'original_string') else str(val)
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
        if isinstance(val, (list, tuple)):
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
        if isinstance(val, (list, tuple)):
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
        if isinstance(val, (list, tuple)):
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
    fp.write_tag(data_element.tag)

    VR = data_element.VR
    if not fp.is_implicit_VR:
        if len(VR) != 2:
            msg = "Cannot write ambiguous VR of '%s' for data element with tag %r." % (VR, data_element.tag)
            msg += "\nSet the correct VR before writing, or use an implicit VR transfer syntax"
            raise ValueError(msg)
        if not in_py2:
            fp.write(bytes(VR, default_encoding))
        else:
            fp.write(VR)
        if VR in extra_length_VRs:
            fp.write_US(0)   # reserved 2 bytes
    if VR not in writers:
        raise NotImplementedError("write_data_element: unknown Value Representation '{0}'".format(VR))

    length_location = fp.tell()  # save location for later.
    if not fp.is_implicit_VR and VR not in ['OB', 'OW', 'OF', 'SQ', 'UT', 'UN']:
        fp.write_US(0)  # Explicit VR length field is only 2 bytes
    else:
        fp.write_UL(0xFFFFFFFF)   # will fill in real length value later if not undefined length item

    encoding = convert_encodings(encoding)

    writer_function, writer_param = writers[VR]
    if VR in text_VRs:
        writer_function(fp, data_element, encoding=encoding[1])
    elif VR in ('PN', 'SQ'):
        writer_function(fp, data_element, encoding=encoding)
    else:
        # Many numeric types use the same writer but with numeric format parameter
        if writer_param is not None:
            writer_function(fp, data_element, writer_param)
        else:
            writer_function(fp, data_element)

    #  print DataElement(tag, VR, value)

    is_undefined_length = False
    if hasattr(data_element, "is_undefined_length") and data_element.is_undefined_length:
        is_undefined_length = True
    location = fp.tell()
    fp.seek(length_location)
    if not fp.is_implicit_VR and VR not in ['OB', 'OW', 'OF', 'SQ', 'UT', 'UN']:
        fp.write_US(location - length_location - 2)  # 2 is length of US
    else:
        # write the proper length of the data_element back in the length slot, unless is SQ with undefined length.
        if not is_undefined_length:
            fp.write_UL(location - length_location - 4)  # 4 is length of UL
    fp.seek(location)  # ready for next data_element
    if is_undefined_length:
        fp.write_tag(SequenceDelimiterTag)
        fp.write_UL(0)  # 4-byte 'length' of delimiter data item


def write_dataset(fp, dataset, parent_encoding=default_encoding):
    """Write a Dataset dictionary to the file. Return the total length written."""

    dataset_encoding = dataset.get('SpecificCharacterSet', parent_encoding)

    fpStart = fp.tell()
    # data_elements must be written in tag order
    tags = sorted(dataset.keys())

    for tag in tags:
        with tag_in_exception(tag):
            # write_data_element(fp, dataset.get_item(tag), dataset_encoding)  XXX for writing raw tags without converting to DataElement
            write_data_element(fp, dataset[tag], dataset_encoding)

    return fp.tell() - fpStart


def write_sequence(fp, data_element, encoding):
    """Write a dicom Sequence contained in data_element to the file fp."""
    # write_data_element has already written the VR='SQ' (if needed) and
    #    a placeholder for length"""
    sequence = data_element.value
    for dataset in sequence:
        write_sequence_item(fp, dataset, encoding)


def write_sequence_item(fp, dataset, encoding):
    """Write an item (dataset) in a dicom Sequence to the dicom file fp."""
    # see Dicom standard Part 5, p. 39 ('03 version)
    # This is similar to writing a data_element, but with a specific tag for Sequence Item
    fp.write_tag(ItemTag)   # marker for start of Sequence Item
    length_location = fp.tell()  # save location for later.
    fp.write_UL(0xffffffff)   # will fill in real value later if not undefined length
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
        iter(data_element.value)  # see if is multi-valued AT;  # Note will fail if Tag ever derived from true tuple rather than being a long
    except TypeError:
        tag = Tag(data_element.value)   # make sure is expressed as a Tag instance
        fp.write_tag(tag)
    else:
        tags = [Tag(tag) for tag in data_element.value]
        for tag in tags:
            fp.write_tag(tag)


def _write_file_meta_info(fp, meta_dataset):
    """Write the dicom group 2 dicom storage File Meta Information to the file.

    The file should already be positioned past the 128 byte preamble.
    Raises ValueError if the required data_elements (elements 2,3,0x10,0x12)
    are not in the dataset. If the dataset came from a file read with
    read_file(), then the required data_elements should already be there.
    """
    fp.write(b'DICM')

    # File meta info is always LittleEndian, Explicit VR. After will change these
    #    to the transfer syntax values set in the meta info
    fp.is_little_endian = True
    fp.is_implicit_VR = False

    if Tag((2, 1)) not in meta_dataset:
        meta_dataset.add_new((2, 1), 'OB', b"\0\1")   # file meta information version

    # Now check that required meta info tags are present:
    missing = []
    for element in [2, 3, 0x10, 0x12]:
        if Tag((2, element)) not in meta_dataset:
            missing.append(Tag((2, element)))
    if missing:
        raise ValueError("Missing required tags {0} for file meta information".format(str(missing)))

    # Put in temp number for required group length, save current location to come back
    meta_dataset[(2, 0)] = DataElement((2, 0), 'UL', 0)  # put 0 to start
    group_length_data_element_size = 12  # !based on DICOM std ExplVR
    group_length_tell = fp.tell()

    # Write the file meta datset, including temp group length
    length = write_dataset(fp, meta_dataset)
    group_length = length - group_length_data_element_size  # counts from end of that

    # Save end of file meta to go back to
    end_of_file_meta = fp.tell()

    # Go back and write the actual group length
    fp.seek(group_length_tell)
    group_length_data_element = DataElement((2, 0), 'UL', group_length)
    write_data_element(fp, group_length_data_element)

    # Return to end of file meta, ready to write remainder of the file
    fp.seek(end_of_file_meta)


def write_file(filename, dataset, write_like_original=True):
    """Store a FileDataset to the filename specified.

    Parameters
    ----------
    filename : str
        Name of file to save new DICOM file to.
    dataset : FileDataset
        Dataset holding the DICOM information; e.g. an object
        read with read_file().
    write_like_original : boolean
        If True (default), preserves the following information from
        the dataset:
        -preamble -- if no preamble in read file, than not used here
        -hasFileMeta -- if writer did not do file meta information,
            then don't write here either
        -seq.is_undefined_length -- if original had delimiters, write them now too,
            instead of the more sensible length characters
        - is_undefined_length_sequence_item -- for datasets that belong to a
            sequence, write the undefined length delimiters if that is
            what the original had.
        If False, produces a "nicer" DICOM file for other readers,
            where all lengths are explicit.

    See Also
    --------
    pydicom.dataset.FileDataset
        Dataset class with relevant attrs and information.
    pydicom.dataset.Dataset.save_as
        Write a DICOM file from a dataset that was read in with read_file().
        save_as wraps write_file.

    Notes
    -----
    Set dataset.preamble if you want something other than 128 0-bytes.
    If the dataset was read from an existing dicom file, then its preamble
    was stored at read time. It is up to the user to ensure the preamble is still
    correct for its purposes.

    If there is no Transfer Syntax tag in the dataset, then set
    dataset.is_implicit_VR and dataset.is_little_endian
    to determine the transfer syntax used to write the file.
    """

    # Decide whether to write DICOM preamble. Should always do so unless trying to mimic the original file read in
    preamble = getattr(dataset, "preamble", None)
    if not preamble and not write_like_original:
        preamble = b"\0" * 128
    file_meta = dataset.file_meta
    if file_meta is None:
        file_meta = Dataset()
    if 'TransferSyntaxUID' not in file_meta:
        if dataset.is_little_endian and dataset.is_implicit_VR:
            file_meta.add_new((2, 0x10), 'UI', ImplicitVRLittleEndian)
        elif dataset.is_little_endian and not dataset.is_implicit_VR:
            file_meta.add_new((2, 0x10), 'UI', ExplicitVRLittleEndian)
        elif not dataset.is_little_endian and not dataset.is_implicit_VR:
            file_meta.add_new((2, 0x10), 'UI', ExplicitVRBigEndian)
        else:
            raise NotImplementedError("pydicom has not been verified for Big Endian with Implicit VR")

    caller_owns_file = True
    # Open file if not already a file object
    if isinstance(filename, compat.string_types):
        fp = DicomFile(filename, 'wb')
        # caller provided a file name; we own the file handle
        caller_owns_file = False
    else:
        fp = DicomFileLike(filename)

    try:
        if preamble:
            fp.write(preamble)  # blank 128 byte preamble
            _write_file_meta_info(fp, file_meta)

        # Set file VR, endian. MUST BE AFTER writing META INFO (which changes to Explicit LittleEndian)
        fp.is_implicit_VR = dataset.is_implicit_VR
        fp.is_little_endian = dataset.is_little_endian

        write_dataset(fp, dataset)
    finally:
        if not caller_owns_file:
            fp.close()

# Map each VR to a function which can write it
# for write_numbers, the Writer maps to a tuple (function, struct_format)
#                                  (struct_format is python's struct module format)
writers = {'UL': (write_numbers, 'L'),
           'SL': (write_numbers, 'l'),
           'US': (write_numbers, 'H'),
           'SS': (write_numbers, 'h'),
           'FL': (write_numbers, 'f'),
           'FD': (write_numbers, 'd'),
           'OF': (write_numbers, 'f'),
           'OB': (write_OBvalue, None),
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
           'UN': (write_UN, None),
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
