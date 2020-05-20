# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Read a dicom media file"""


# Need zlib and io.BytesIO for deflate-compressed file
from io import BytesIO
import os
from struct import (Struct, unpack)
import warnings
import zlib

from pydicom import config
from pydicom.charset import (default_encoding, convert_encodings)
from pydicom.config import logger
from pydicom.datadict import dictionary_VR, tag_for_keyword
from pydicom.dataelem import (DataElement, RawDataElement,
                              DataElement_from_raw, empty_value_for_VR)
from pydicom.dataset import (Dataset, FileDataset, FileMetaDataset)
from pydicom.dicomdir import DicomDir
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomFile
from pydicom.fileutil import read_undefined_length_value, path_from_pathlike
from pydicom.misc import size_in_bytes
from pydicom.sequence import Sequence
from pydicom.tag import (ItemTag, SequenceDelimiterTag, TupleTag, Tag, BaseTag)
import pydicom.uid
from pydicom.util.hexutil import bytes2hex
from pydicom.valuerep import extra_length_VRs


def data_element_generator(fp,
                           is_implicit_VR,
                           is_little_endian,
                           stop_when=None,
                           defer_size=None,
                           encoding=default_encoding,
                           specific_tags=None):

    """Create a generator to efficiently return the raw data elements.

    .. note::

        This function is used internally - usually there is no need to call it
        from user code. To read data from a DICOM file, :func:`dcmread`
        shall be used instead.

    Parameters
    ----------
    fp : file-like
        The file-like to read from.
    is_implicit_VR : bool
        ``True`` if the data is encoded as implicit VR, ``False`` otherwise.
    is_little_endian : bool
        ``True`` if the data is encoded as little endian, ``False`` otherwise.
    stop_when : None, callable, optional
        If ``None`` (default), then the whole file is read. A callable which
        takes tag, VR, length, and returns ``True`` or ``False``. If it
        returns ``True``, ``read_data_element`` will just return.
    defer_size : int, str, None, optional
        See :func:`dcmread` for parameter info.
    encoding :
        Encoding scheme
    specific_tags : list or None
        See :func:`dcmread` for parameter info.

    Returns
    -------
    VR : str or None
        ``None`` if implicit VR, otherwise the VR read from the file.
    length : int
        The length of the DICOM data element (could be DICOM "undefined
        length" ``0xFFFFFFFFL``)
    value_bytes : bytes or str
        The raw bytes from the DICOM file (not parsed into Python types)
    is_little_endian : bool
        ``True`` if transfer syntax is little endian; else ``False``.
    """
    # Summary of DICOM standard PS3.5-2008 chapter 7:
    # If Implicit VR, data element is:
    #    tag, 4-byte length, value.
    #        The 4-byte length can be FFFFFFFF (undefined length)*
    #
    # If Explicit VR:
    #    if OB, OW, OF, SQ, UN, or UT:
    #       tag, VR, 2-bytes reserved (both zero), 4-byte length, value
    #           For all but UT, the length can be FFFFFFFF (undefined length)*
    #   else: (any other VR)
    #       tag, VR, (2 byte length), value
    # * for undefined length, a Sequence Delimitation Item marks the end
    #        of the Value Field.
    # Note, except for the special_VRs, both impl and expl VR use 8 bytes;
    #    the special VRs follow the 8 bytes with a 4-byte length

    # With a generator, state is stored, so we can break down
    #    into the individual cases, and not have to check them again for each
    #    data element

    if is_little_endian:
        endian_chr = "<"
    else:
        endian_chr = ">"
    if is_implicit_VR:
        element_struct = Struct(endian_chr + "HHL")
    else:  # Explicit VR
        # tag, VR, 2-byte length (or 0 if special VRs)
        element_struct = Struct(endian_chr + "HH2sH")
        extra_length_struct = Struct(endian_chr + "L")  # for special VRs
        extra_length_unpack = extra_length_struct.unpack  # for lookup speed

    # Make local variables so have faster lookup
    fp_read = fp.read
    fp_tell = fp.tell
    logger_debug = logger.debug
    debugging = config.debugging
    element_struct_unpack = element_struct.unpack
    defer_size = size_in_bytes(defer_size)

    tag_set = set()
    if specific_tags is not None:
        for tag in specific_tags:
            if isinstance(tag, str):
                tag = Tag(tag_for_keyword(tag))
            if isinstance(tag, BaseTag):
                tag_set.add(tag)
        tag_set.add(Tag(0x08, 0x05))
    has_tag_set = len(tag_set) > 0

    while True:
        # Read tag, VR, length, get ready to read value
        bytes_read = fp_read(8)
        if len(bytes_read) < 8:
            return  # at end of file
        if debugging:
            debug_msg = "{0:08x}: {1}".format(fp.tell() - 8,
                                              bytes2hex(bytes_read))

        if is_implicit_VR:
            # must reset VR each time; could have set last iteration (e.g. SQ)
            VR = None
            group, elem, length = element_struct_unpack(bytes_read)
        else:  # explicit VR
            group, elem, VR, length = element_struct_unpack(bytes_read)
            VR = VR.decode(default_encoding)
            if VR in extra_length_VRs:
                bytes_read = fp_read(4)
                length = extra_length_unpack(bytes_read)[0]
                if debugging:
                    debug_msg += " " + bytes2hex(bytes_read)
        if debugging:
            debug_msg = "%-47s  (%04x, %04x)" % (debug_msg, group, elem)
            if not is_implicit_VR:
                debug_msg += " %s " % VR
            if length != 0xFFFFFFFF:
                debug_msg += "Length: %d" % length
            else:
                debug_msg += "Length: Undefined length (FFFFFFFF)"
            logger_debug(debug_msg)

        # Positioned to read the value, but may not want to -- check stop_when
        value_tell = fp_tell()
        tag = TupleTag((group, elem))
        if stop_when is not None:
            # XXX VR may be None here!! Should stop_when just take tag?
            if stop_when(tag, VR, length):
                if debugging:
                    logger_debug("Reading ended by stop_when callback. "
                                 "Rewinding to start of data element.")
                rewind_length = 8
                if not is_implicit_VR and VR in extra_length_VRs:
                    rewind_length += 4
                fp.seek(value_tell - rewind_length)
                return

        # Reading the value
        # First case (most common): reading a value with a defined length
        if length != 0xFFFFFFFF:
            # don't defer loading of Specific Character Set value as it is
            # needed immediately to get the character encoding for other tags
            if has_tag_set and tag not in tag_set:
                # skip the tag if not in specific tags
                fp.seek(fp_tell() + length)
                continue

            if (defer_size is not None and length > defer_size and
                    tag != BaseTag(0x00080005)):
                # Flag as deferred by setting value to None, and skip bytes
                value = None
                logger_debug("Defer size exceeded. "
                             "Skipping forward to next data element.")
                fp.seek(fp_tell() + length)
            else:
                value = (fp_read(length) if length > 0
                         else empty_value_for_VR(VR, raw=True))
                if debugging:
                    dotdot = "..." if length > 12 else "   "
                    displayed_value = value[:12] if value else b''
                    logger_debug("%08x: %-34s %s %r %s" %
                                 (value_tell, bytes2hex(displayed_value),
                                  dotdot, displayed_value, dotdot))

            # If the tag is (0008,0005) Specific Character Set, then store it
            if tag == BaseTag(0x00080005):
                from pydicom.values import convert_string
                encoding = convert_string(value or b'', is_little_endian)
                # Store the encoding value in the generator
                # for use with future elements (SQs)
                encoding = convert_encodings(encoding)

            yield RawDataElement(tag, VR, length, value, value_tell,
                                 is_implicit_VR, is_little_endian)

        # Second case: undefined length - must seek to delimiter,
        # unless is SQ type, in which case is easier to parse it, because
        # undefined length SQs and items of undefined lengths can be nested
        # and it would be error-prone to read to the correct outer delimiter
        else:
            # Try to look up type to see if is a SQ
            # if private tag, won't be able to look it up in dictionary,
            #   in which case just ignore it and read the bytes unless it is
            #   identified as a Sequence
            if VR is None:
                try:
                    VR = dictionary_VR(tag)
                except KeyError:
                    # Look ahead to see if it consists of items
                    # and is thus a SQ
                    next_tag = TupleTag(unpack(endian_chr + "HH", fp_read(4)))
                    # Rewind the file
                    fp.seek(fp_tell() - 4)
                    if next_tag == ItemTag:
                        VR = 'SQ'

            if VR == 'SQ':
                if debugging:
                    msg = "{0:08x}: Reading/parsing undefined length sequence"
                    logger_debug(msg.format(fp_tell()))
                seq = read_sequence(fp, is_implicit_VR,
                                    is_little_endian, length, encoding)
                if has_tag_set and tag not in tag_set:
                    continue
                yield DataElement(tag, VR, seq, value_tell,
                                  is_undefined_length=True)
            else:
                delimiter = SequenceDelimiterTag
                if debugging:
                    logger_debug("Reading undefined length data element")
                value = read_undefined_length_value(fp, is_little_endian,
                                                    delimiter, defer_size)

                # tags with undefined length are skipped after read
                if has_tag_set and tag not in tag_set:
                    continue
                yield RawDataElement(tag, VR, length, value, value_tell,
                                     is_implicit_VR, is_little_endian)


def _is_implicit_vr(fp, implicit_vr_is_assumed, is_little_endian, stop_when):
    """Check if the real VR is explicit or implicit.

    Parameters
    ----------
    fp : an opened file object
    implicit_vr_is_assumed : bool
        True if implicit VR is assumed.
        If this does not match with the real transfer syntax, a user warning
        will be issued.
    is_little_endian : bool
        True if file has little endian transfer syntax.
        Needed to interpret the first tag.
    stop_when : None, optional
        Optional call_back function which can terminate reading.
        Needed to check if the next tag still belongs to the read dataset.

    Returns
    -------
    True if implicit VR is used, False otherwise.
    """
    tag_bytes = fp.read(4)
    vr = fp.read(2)
    if len(vr) < 2:
        return implicit_vr_is_assumed

    # it is sufficient to check if the VR is in valid ASCII range, as it is
    # extremely unlikely that the tag length accidentally has such a
    # representation - this would need the first tag to be longer than 16kB
    # (e.g. it should be > 0x4141 = 16705 bytes)
    found_implicit = not (0x40 < vr[0] < 0x5B and 0x40 < vr[1] < 0x5B)

    if found_implicit != implicit_vr_is_assumed:
        # first check if the tag still belongs to the dataset if stop_when
        # is given - if not, the dataset is empty and we just return
        endian_chr = "<" if is_little_endian else ">"
        tag = TupleTag(unpack(endian_chr + "HH", tag_bytes))
        if stop_when is not None and stop_when(tag, vr, 0):
            return found_implicit

        # got to the real problem - warn or raise depending on config
        found_vr = 'implicit' if found_implicit else 'explicit'
        expected_vr = 'implicit' if not found_implicit else 'explicit'
        message = ('Expected {0} VR, but found {1} VR - using {1} VR for '
                   'reading'.format(expected_vr, found_vr))
        if config.enforce_valid_values:
            raise InvalidDicomError(message)
        warnings.warn(message, UserWarning)
    return found_implicit


def read_dataset(fp, is_implicit_VR, is_little_endian, bytelength=None,
                 stop_when=None, defer_size=None,
                 parent_encoding=default_encoding, specific_tags=None,
                 at_top_level=True):
    """Return a :class:`~pydicom.dataset.Dataset` instance containing the next
    dataset in the file.

    Parameters
    ----------
    fp : file-like
        An opened file-like object.
    is_implicit_VR : bool
        ``True`` if file transfer syntax is implicit VR.
    is_little_endian : bool
        ``True`` if file has little endian transfer syntax.
    bytelength : int, None, optional
        ``None`` to read until end of file or ItemDeliterTag, else a fixed
        number of bytes to read
    stop_when : None, optional
        Optional call_back function which can terminate reading. See help for
        :func:`data_element_generator` for details
    defer_size : int, None, optional
        Size to avoid loading large elements in memory. See :func:`dcmread` for
        more parameter info.
    parent_encoding :
        Optional encoding to use as a default in case (0008,0005) *Specific
        Character Set* isn't specified.
    specific_tags : list or None
        See :func:`dcmread` for parameter info.
    at_top_level: bool
        If dataset is top level (not within a sequence).
        Used to turn off explicit VR heuristic within sequences

    Returns
    -------
    dataset.Dataset
        A Dataset instance.

    See Also
    --------
    :class:`~pydicom.dataset.Dataset`
        A collection (dictionary) of DICOM
        :class:`~pydicom.dataelem.DataElement` instances.
    """
    raw_data_elements = dict()
    fp_start = fp.tell()
    if at_top_level:
        is_implicit_VR = _is_implicit_vr(
            fp, is_implicit_VR, is_little_endian, stop_when)
    fp.seek(fp_start)
    de_gen = data_element_generator(fp, is_implicit_VR, is_little_endian,
                                    stop_when, defer_size, parent_encoding,
                                    specific_tags)
    try:
        while (bytelength is None) or (fp.tell() - fp_start < bytelength):
            raw_data_element = next(de_gen)
            # Read data elements. Stop on some errors, but return what was read
            tag = raw_data_element.tag
            # Check for ItemDelimiterTag --dataset is an item in a sequence
            if tag == BaseTag(0xFFFEE00D):
                break
            raw_data_elements[tag] = raw_data_element
    except StopIteration:
        pass
    except EOFError as details:
        if config.enforce_valid_values:
            raise
        msg = str(details) + " in file " + getattr(fp, "name", "<no filename>")
        warnings.warn(msg, UserWarning)
    except NotImplementedError as details:
        logger.error(details)

    ds = Dataset(raw_data_elements)
    if 0x00080005 in raw_data_elements:
        char_set = DataElement_from_raw(raw_data_elements[0x00080005]).value
        encoding = convert_encodings(char_set)
    else:
        encoding = parent_encoding
    ds.set_original_encoding(is_implicit_VR, is_little_endian, encoding)
    return ds


def read_sequence(fp, is_implicit_VR, is_little_endian, bytelength, encoding,
                  offset=0):
    """Read and return a :class:`~pydicom.sequence.Sequence` -- i.e. a
    :class:`list` of :class:`Datasets<pydicom.dataset.Dataset>`.
    """

    seq = []  # use builtin list to start for speed, convert to Sequence at end
    is_undefined_length = False
    if bytelength != 0:  # SQ of length 0 possible (PS 3.5-2008 7.5.1a (p.40)
        if bytelength == 0xffffffff:
            is_undefined_length = True
            bytelength = None
        fp_tell = fp.tell  # for speed in loop
        fpStart = fp_tell()
        while (not bytelength) or (fp_tell() - fpStart < bytelength):
            file_tell = fp.tell()
            dataset = read_sequence_item(fp, is_implicit_VR, is_little_endian,
                                         encoding, offset)
            if dataset is None:  # None is returned if hit Sequence Delimiter
                break
            dataset.file_tell = file_tell + offset
            seq.append(dataset)
    seq = Sequence(seq)
    seq.is_undefined_length = is_undefined_length
    return seq


def read_sequence_item(fp, is_implicit_VR, is_little_endian, encoding,
                       offset=0):
    """Read and return a single :class:`~pydicom.sequence.Sequence` item, i.e.
    a :class:`~pydicom.dataset.Dataset`.
    """
    seq_item_tell = fp.tell() + offset
    if is_little_endian:
        tag_length_format = "<HHL"
    else:
        tag_length_format = ">HHL"
    try:
        bytes_read = fp.read(8)
        group, element, length = unpack(tag_length_format, bytes_read)
    except BaseException:
        raise IOError("No tag to read at file position "
                      "{0:05x}".format(fp.tell() + offset))
    tag = (group, element)
    if tag == SequenceDelimiterTag:  # No more items, time to stop reading
        logger.debug(
            "{0:08x}: {1}".format(fp.tell() - 8 + offset, "End of Sequence"))
        if length != 0:
            logger.warning("Expected 0x00000000 after delimiter, found 0x%x, "
                           "at position 0x%x" % (
                               length, fp.tell() - 4 + offset))
        return None
    if tag != ItemTag:
        logger.warning("Expected sequence item with tag %s at file position "
                       "0x%x" % (ItemTag, fp.tell() - 4 + offset))
    else:
        logger.debug("{0:08x}: {1}  Found Item tag (start of item)".format(
            fp.tell() - 4 + offset, bytes2hex(bytes_read)))
    if length == 0xFFFFFFFF:
        ds = read_dataset(fp, is_implicit_VR, is_little_endian,
                          bytelength=None, parent_encoding=encoding,
                          at_top_level=False)
        ds.is_undefined_length_sequence_item = True
    else:
        ds = read_dataset(fp, is_implicit_VR, is_little_endian, length,
                          parent_encoding=encoding,
                          at_top_level=False)
        ds.is_undefined_length_sequence_item = False
        logger.debug("%08x: Finished sequence item" % (fp.tell() + offset,))
    ds.seq_item_tell = seq_item_tell
    return ds


def _read_command_set_elements(fp):
    """Return a Dataset containing any Command Set (0000,eeee) elements
    in `fp`.

    Command Set elements are always Implicit VR Little Endian (DICOM Standard,
    Part 7, :dcm:`Section 6.3<part07/sect_6.3.html>`). Once any Command Set
    elements are read `fp` will be positioned at the start of the next group
    of elements.

    Parameters
    ----------
    fp : file-like
        The file-like positioned at the start of any command set elements.

    Returns
    -------
    dataset.Dataset
        The command set elements as a Dataset instance. May be empty if no
        command set elements are present.
    """

    def _not_group_0000(tag, VR, length):
        """Return True if the tag is not in group 0x0000, False otherwise."""
        return (tag.group != 0)

    command_set = read_dataset(fp, is_implicit_VR=True, is_little_endian=True,
                               stop_when=_not_group_0000)
    return command_set


def _read_file_meta_info(fp):
    """Return a Dataset containing any File Meta (0002,eeee) elements in `fp`.

    File Meta elements are always Explicit VR Little Endian (DICOM Standard,
    Part 10, :dcm:`Section 7<part10/chapter_7.html>`). Once any File Meta
    elements are read `fp` will be positioned at the start of the next group
    of elements.

    Parameters
    ----------
    fp : file-like
        The file-like positioned at the start of any File Meta Information
        group elements.

    Returns
    -------
    dataset.Dataset
        The File Meta elements as a Dataset instance. May be empty if no
        File Meta are present.
    """

    def _not_group_0002(tag, VR, length):
        """Return True if the tag is not in group 0x0002, False otherwise."""
        return tag.group != 2

    start_file_meta = fp.tell()
    file_meta = FileMetaDataset(
                    read_dataset(
                        fp, is_implicit_VR=False, is_little_endian=True,
                        stop_when=_not_group_0002
                    )
    )
    if not file_meta._dict:
        return file_meta

    # Test the file meta for correct interpretation by requesting the first
    #   data element: if it fails, retry loading the file meta with an
    #   implicit VR (issue #503)
    try:
        file_meta[list(file_meta.elements())[0].tag]
    except NotImplementedError:
        fp.seek(start_file_meta)
        file_meta = FileMetaDataset(
                        read_dataset(
                            fp, is_implicit_VR=True, is_little_endian=True,
                            stop_when=_not_group_0002
                        )
        )

    # Log if the Group Length doesn't match actual length
    if 'FileMetaInformationGroupLength' in file_meta:
        # FileMetaInformationGroupLength must be 12 bytes long and its value
        #   counts from the beginning of the next element to the end of the
        #   file meta elements
        length_file_meta = fp.tell() - (start_file_meta + 12)
        if file_meta.FileMetaInformationGroupLength != length_file_meta:
            logger.info("_read_file_meta_info: (0002,0000) 'File Meta "
                        "Information Group Length' value doesn't match the "
                        "actual File Meta Information length ({0} vs {1} "
                        "bytes)."
                        .format(file_meta.FileMetaInformationGroupLength,
                                length_file_meta))

    return file_meta


def read_file_meta_info(filename):
    """Read and return the DICOM file meta information only.

    This function is meant to be used in user code, for quickly going through
    a series of files to find one which is referenced to a particular SOP,
    without having to read the entire files.
    """
    with DicomFile(filename, 'rb') as fp:
        read_preamble(fp, False)  # if no header, raise exception
        return _read_file_meta_info(fp)


def read_preamble(fp, force):
    """Return the 128-byte DICOM preamble in `fp` if present.

    `fp` should be positioned at the start of the file-like. If the preamble
    and prefix are found then after reading `fp` will be positioned at the
    first byte after the prefix (byte offset 133). If either the preamble or
    prefix are missing and `force` is ``True`` then after reading `fp` will be
    positioned at the start of the file-like.

    Parameters
    ----------
    fp : file-like object
        The file-like to read the preamble from.
    force : bool
        Flag to force reading of a file even if no header is found.

    Returns
    -------
    preamble : str/bytes or None
        The 128-byte DICOM preamble will be returned if the appropriate prefix
        ('DICM') is found at byte offset 128. Returns ``None`` if the 'DICM'
        prefix is not found and `force` is ``True``.

    Raises
    ------
    InvalidDicomError
        If `force` is ``False`` and no appropriate header information found.

    Notes
    -----
    Also reads past the 'DICM' marker. Rewinds file to the beginning if
    no header found.
    """
    logger.debug("Reading File Meta Information preamble...")
    preamble = fp.read(128)
    if config.debugging:
        sample = bytes2hex(preamble[:8]) + "..." + bytes2hex(preamble[-8:])
        logger.debug("{0:08x}: {1}".format(fp.tell() - 128, sample))

    logger.debug("Reading File Meta Information prefix...")
    magic = fp.read(4)
    if magic != b"DICM" and force:
        logger.info(
            "File is not conformant with the DICOM File Format: 'DICM' "
            "prefix is missing from the File Meta Information header "
            "or the header itself is missing. Assuming no header and "
            "continuing.")
        preamble = None
        fp.seek(0)
    elif magic != b"DICM" and not force:
        raise InvalidDicomError("File is missing DICOM File Meta Information "
                                "header or the 'DICM' prefix is missing from "
                                "the header. Use force=True to force reading.")
    else:
        logger.debug("{0:08x}: 'DICM' prefix found".format(fp.tell() - 4))
    return preamble


def _at_pixel_data(tag, VR, length):
    return tag == (0x7fe0, 0x0010)


def read_partial(fileobj, stop_when=None, defer_size=None,
                 force=False, specific_tags=None):
    """Parse a DICOM file until a condition is met.

    Parameters
    ----------
    fileobj : a file-like object
        Note that the file will not close when the function returns.
    stop_when :
        Stop condition. See :func:`read_dataset` for more info.
    defer_size : int, str, None, optional
        See :func:`dcmread` for parameter info.
    force : bool
        See :func:`dcmread` for parameter info.
    specific_tags : list or None
        See :func:`dcmread` for parameter info.

    Notes
    -----
    Use :func:`dcmread` unless you need to stop on some condition other than
    reaching pixel data.

    Returns
    -------
    dataset.FileDataset or dicomdir.DicomDir
        The read dataset.

    See Also
    --------
    dcmread
        More generic file reading function.
    """
    # Read File Meta Information

    # Read preamble (if present)
    preamble = read_preamble(fileobj, force)
    # Read any File Meta Information group (0002,eeee) elements (if present)
    file_meta_dataset = _read_file_meta_info(fileobj)

    # Read Dataset

    # Read any Command Set group (0000,eeee) elements (if present)
    command_set = _read_command_set_elements(fileobj)

    # Check to see if there's anything left to read
    peek = fileobj.read(1)
    if peek != b'':
        fileobj.seek(-1, 1)

    # `filobj` should be positioned at the start of the dataset by this point.
    # Ensure we have appropriate values for `is_implicit_VR` and
    # `is_little_endian` before we try decoding. We assume an initial
    # transfer syntax of implicit VR little endian and correct it as necessary
    is_implicit_VR = True
    is_little_endian = True
    transfer_syntax = file_meta_dataset.get("TransferSyntaxUID")
    if peek == b'':  # EOF
        pass
    elif transfer_syntax is None:  # issue 258
        # If no TransferSyntaxUID element then we have to try and figure out
        #   the correct values for `is_little_endian` and `is_implicit_VR`.
        # Peek at the first 6 bytes to get the first element's tag group and
        #   (possibly) VR
        group, _, VR = unpack("<HH2s", fileobj.read(6))
        fileobj.seek(-6, 1)

        # Test the VR to see if it's valid, and if so then assume explicit VR
        from pydicom.values import converters
        VR = VR.decode(default_encoding)
        if VR in converters.keys():
            is_implicit_VR = False
            # Big endian encoding can only be explicit VR
            #   Big endian 0x0004 decoded as little endian will be 1024
            #   Big endian 0x0100 decoded as little endian will be 1
            # Therefore works for big endian tag groups up to 0x00FF after
            #   which it will fail, in which case we leave it as little endian
            #   and hope for the best (big endian is retired anyway)
            if group >= 1024:
                is_little_endian = False
    elif transfer_syntax == pydicom.uid.ImplicitVRLittleEndian:
        pass
    elif transfer_syntax == pydicom.uid.ExplicitVRLittleEndian:
        is_implicit_VR = False
    elif transfer_syntax == pydicom.uid.ExplicitVRBigEndian:
        is_implicit_VR = False
        is_little_endian = False
    elif transfer_syntax == pydicom.uid.DeflatedExplicitVRLittleEndian:
        # See PS3.5 section A.5
        # when written, the entire dataset following
        #     the file metadata was prepared the normal way,
        #     then "deflate" compression applied.
        #  All that is needed here is to decompress and then
        #     use as normal in a file-like object
        zipped = fileobj.read()
        # -MAX_WBITS part is from comp.lang.python answer:
        # groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
        unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
        fileobj = BytesIO(unzipped)  # a file-like object
        is_implicit_VR = False
    else:
        # Any other syntax should be Explicit VR Little Endian,
        #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE
        #        by Standard PS 3.5-2008 A.4 (p63)
        is_implicit_VR = False

    # Try and decode the dataset
    #   By this point we should be at the start of the dataset and have
    #   the transfer syntax (whether read from the file meta or guessed at)
    try:
        dataset = read_dataset(fileobj, is_implicit_VR, is_little_endian,
                               stop_when=stop_when, defer_size=defer_size,
                               specific_tags=specific_tags)
    except EOFError:
        if config.enforce_valid_values:
            raise
        # warning already logged in read_dataset

    # Add the command set elements to the dataset (if any)
    dataset.update(command_set._dict)

    class_uid = file_meta_dataset.get("MediaStorageSOPClassUID", None)
    if class_uid and class_uid.name == "Media Storage Directory Storage":
        dataset_class = DicomDir
    else:
        dataset_class = FileDataset
    new_dataset = dataset_class(fileobj, dataset, preamble, file_meta_dataset,
                                is_implicit_VR, is_little_endian)
    # save the originally read transfer syntax properties in the dataset
    new_dataset.set_original_encoding(is_implicit_VR, is_little_endian,
                                      dataset._character_set)
    return new_dataset


def dcmread(fp, defer_size=None, stop_before_pixels=False,
            force=False, specific_tags=None):
    """Read and parse a DICOM dataset stored in the DICOM File Format.

    Read a DICOM dataset stored in accordance with the :dcm:`DICOM File
    Format <part10/chapter_7.html>`. If the dataset is not stored in
    accordance with the File Format (i.e. the preamble and prefix are missing,
    there are missing required Type 1 *File Meta Information Group* elements
    or the entire *File Meta Information* is missing) then you will have to
    set `force` to ``True``.

    Parameters
    ----------
    fp : str or PathLike or file-like
        Either a file-like object, or a string containing the file name. If a
        file-like object, the caller is responsible for closing it.
    defer_size : int or str or None, optional
        If ``None`` (default), all elements are read into memory. If specified,
        then if a data element's stored value is larger than `defer_size`, the
        value is not read into memory until it is accessed in code. Specify an
        integer (bytes), or a string value with units, e.g. "512 KB", "2 MB".
    stop_before_pixels : bool, optional
        If ``False`` (default), the full file will be read and parsed. Set
        ``True`` to stop before reading (7FE0,0010) *Pixel Data* (and all
        subsequent elements).
    force : bool, optional
        If ``False`` (default), raises an
        :class:`~pydicom.errors.InvalidDicomError` if the file is
        missing the *File Meta Information* header. Set to ``True`` to force
        reading even if no *File Meta Information* header is found.
    specific_tags : list or None, optional
        If not ``None``, only the tags in the list are returned. The list
        elements can be tags or tag names. Note that the element (0008,0005)
        *Specific Character Set* is always returned if present - this ensures
        correct decoding of returned text values.

    Returns
    -------
    FileDataset
        An instance of :class:`~pydicom.dataset.FileDataset` that represents
        a parsed DICOM file.

    Raises
    ------
    InvalidDicomError
        If `force` is ``True`` and the file is not a valid DICOM file.

    See Also
    --------
    pydicom.dataset.FileDataset
        Data class that is returned.
    pydicom.filereader.read_partial
        Only read part of a DICOM file, stopping on given conditions.

    Examples
    --------
    Read and return a dataset stored in accordance with the DICOM File Format:

    >>> ds = pydicom.dcmread("rtplan.dcm")
    >>> ds.PatientName

    Read and return a dataset not in accordance with the DICOM File Format:

    >>> ds = pydicom.dcmread("rtplan.dcm", force=True)
    >>> ds.PatientName

    Use within a context manager:

    >>> with pydicom.dcmread("rtplan.dcm") as ds:
    >>>     ds.PatientName
    """
    # Open file if not already a file object
    caller_owns_file = True
    fp = path_from_pathlike(fp)
    if isinstance(fp, str):
        # caller provided a file name; we own the file handle
        caller_owns_file = False
        try:
            logger.debug(u"Reading file '{0}'".format(fp))
        except Exception:
            logger.debug("Reading file '{0}'".format(fp))
        fp = open(fp, 'rb')

    if config.debugging:
        logger.debug("\n" + "-" * 80)
        logger.debug("Call to dcmread()")
        msg = ("filename:'%s', defer_size='%s', "
               "stop_before_pixels=%s, force=%s, specific_tags=%s")
        logger.debug(msg % (fp.name, defer_size, stop_before_pixels,
                            force, specific_tags))
        if caller_owns_file:
            logger.debug("Caller passed file object")
        else:
            logger.debug("Caller passed file name")
        logger.debug("-" * 80)

    # Convert size to defer reading into bytes
    defer_size = size_in_bytes(defer_size)

    # Iterate through all items and store them --include file meta if present
    stop_when = None
    if stop_before_pixels:
        stop_when = _at_pixel_data
    try:
        dataset = read_partial(fp, stop_when, defer_size=defer_size,
                               force=force, specific_tags=specific_tags)
    finally:
        if not caller_owns_file:
            fp.close()
    # XXX need to store transfer syntax etc.
    return dataset


read_file = dcmread  # used read_file until pydicom 1.0. Kept for compatibility


def read_dicomdir(filename="DICOMDIR"):
    """Read a DICOMDIR file and return a :class:`~pydicom.dicomdir.DicomDir`.

    This is a wrapper around :func:`dcmread` which gives a default file name.

    Parameters
    ----------
    filename : str, optional
        Full path and name to DICOMDIR file to open

    Returns
    -------
    DicomDir

    Raises
    ------
    InvalidDicomError
        Raised if filename is not a DICOMDIR file.
    """
    # dcmread will return a DicomDir instance if file is one.

    # Read the file as usual.
    ds = dcmread(filename)
    # Here, check that it is in fact DicomDir
    if not isinstance(ds, DicomDir):
        msg = u"File '{0}' is not a Media Storage Directory file".format(
            filename)
        raise InvalidDicomError(msg)
    return ds


def data_element_offset_to_value(is_implicit_VR, VR):
    """Return number of bytes from start of data element to start of value"""
    if is_implicit_VR:
        offset = 8  # tag of 4 plus 4-byte length
    else:
        if VR in extra_length_VRs:
            offset = 12  # tag 4 + 2 VR + 2 reserved + 4 length
        else:
            offset = 8  # tag 4 + 2 VR + 2 length
    return offset


def read_deferred_data_element(fileobj_type, filename_or_obj, timestamp,
                               raw_data_elem):
    """Read the previously deferred value from the file into memory
    and return a raw data element.

    .. note:

        This is called internally by pydicom and will normally not be
        needed in user code.

    Parameters
    ----------
    fileobj_type : type
        The type of the original file object.
    filename_or_obj : str or file-like
        The filename of the original file if one exists, or the file-like
        object where the data element persists.
    timestamp : time or None
        The time the original file has been read, if not a file-like.
    raw_data_elem : dataelem.RawDataElement
        The raw data element with no value set.

    Returns
    -------
    dataelem.RawDataElement
        The data element with the value set.

    Raises
    ------
    IOError
        If `filename_or_obj` is ``None``.
    IOError
        If `filename_or_obj` is a filename and the corresponding file does
        not exist.
    ValueError
        If the VR or tag of `raw_data_elem` does not match the read value.
    """
    logger.debug("Reading deferred element %r" % str(raw_data_elem.tag))
    # If it wasn't read from a file, then return an error
    if filename_or_obj is None:
        raise IOError("Deferred read -- original filename not stored. "
                      "Cannot re-open")
    is_filename = isinstance(filename_or_obj, str)

    # Check that the file is the same as when originally read
    if is_filename and not os.path.exists(filename_or_obj):
        raise IOError(u"Deferred read -- original file "
                      "{0:s} is missing".format(filename_or_obj))
    if timestamp is not None:
        statinfo = os.stat(filename_or_obj)
        if statinfo.st_mtime != timestamp:
            warnings.warn("Deferred read warning -- file modification time "
                          "has changed.")

    # Open the file, position to the right place
    fp = (fileobj_type(filename_or_obj, 'rb')
          if is_filename else filename_or_obj)
    is_implicit_VR = raw_data_elem.is_implicit_VR
    is_little_endian = raw_data_elem.is_little_endian
    offset = data_element_offset_to_value(is_implicit_VR, raw_data_elem.VR)
    fp.seek(raw_data_elem.value_tell - offset)
    elem_gen = data_element_generator(fp, is_implicit_VR, is_little_endian,
                                      defer_size=None)

    # Read the data element and check matches what was stored before
    data_elem = next(elem_gen)
    fp.close()
    if data_elem.VR != raw_data_elem.VR:
        raise ValueError("Deferred read VR {0:s} does not match "
                         "original {1:s}".format(data_elem.VR,
                                                 raw_data_elem.VR))
    if data_elem.tag != raw_data_elem.tag:
        raise ValueError("Deferred read tag {0!r} does not match "
                         "original {1!r}".format(data_elem.tag,
                                                 raw_data_elem.tag))

    # Everything is ok, now this object should act like usual DataElement
    return data_elem
