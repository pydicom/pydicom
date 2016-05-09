# filereader.py
"""Read a dicom media file"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom
from __future__ import absolute_import
# Need zlib and io.BytesIO for deflate-compressed file
import os.path
import warnings
import zlib
from io import BytesIO

from pydicom.tag import TupleTag
from pydicom.dataelem import RawDataElement
from pydicom.util.hexutil import bytes2hex
from pydicom.valuerep import extra_length_VRs
from pydicom.charset import default_encoding, convert_encodings
from pydicom.compat import in_py2
from pydicom import compat
from pydicom import config  # don't import datetime_conversion directly
from pydicom.config import logger

stat_available = True
try:
    from os import stat
except ImportError:
    stat_available = False

from pydicom.errors import InvalidDicomError
import pydicom.uid  # for Implicit/Explicit/Little/Big Endian transfer syntax UIDs
from pydicom.filebase import DicomFile
from pydicom.dataset import Dataset, FileDataset
from pydicom.dicomdir import DicomDir
from pydicom.datadict import dictionaryVR
from pydicom.dataelem import DataElement
from pydicom.tag import ItemTag, SequenceDelimiterTag
from pydicom.sequence import Sequence
from pydicom.fileutil import read_undefined_length_value
from struct import Struct, unpack
from sys import byteorder
sys_is_little_endian = (byteorder == 'little')


class DicomIter(object):
    """Iterator over DICOM data elements created from a file-like object
    """
    def __init__(self, fp, stop_when=None, force=False):
        """Read the preamble and meta info and prepare iterator for remainder of file.

        Parameters
        ----------
        fp : an open DicomFileLike object, at start of file
        force : boolean
            Force reading of data. See ``read_file`` for more parameter info.

        Adds flags to fp: Big/Little-endian and Implicit/Explicit VR
        """
        self.fp = fp
        self.stop_when = stop_when
        self.preamble = preamble = read_preamble(fp, force)
        self.has_header = has_header = (preamble is not None)
        self.file_meta_info = Dataset()
        if has_header:
            self.file_meta_info = file_meta_info = _read_file_meta_info(fp)
            transfer_syntax = file_meta_info.TransferSyntaxUID
            if transfer_syntax == pydicom.uid.ExplicitVRLittleEndian:
                self._is_implicit_VR = False
                self._is_little_endian = True
            elif transfer_syntax == pydicom.uid.ImplicitVRLittleEndian:
                self._is_implicit_VR = True
                self._is_little_endian = True
            elif transfer_syntax == pydicom.uid.ExplicitVRBigEndian:
                self._is_implicit_VR = False
                self._is_little_endian = False
            elif transfer_syntax == pydicom.uid.DeflatedExplicitVRLittleEndian:
                # See PS3.6-2008 A.5 (p 71) -- when written, the entire dataset
                #   following the file metadata was prepared the normal way,
                #   then "deflate" compression applied.
                #  All that is needed here is to decompress and then
                #      use as normal in a file-like object
                zipped = fp.read()
                # -MAX_WBITS part is from comp.lang.python answer:
                # groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
                unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
                fp = BytesIO(unzipped)  # a file-like object
                self.fp = fp  # point to new object
                self._is_implicit_VR = False
                self._is_little_endian = True
            else:
                # Any other syntax should be Explicit VR Little Endian,
                #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE
                #        by Standard PS 3.5-2008 A.4 (p63)
                self._is_implicit_VR = False
                self._is_little_endian = True
        else:  # no header -- make assumptions
            fp.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
            self._is_little_endian = True
            self._is_implicit_VR = True

        impl_expl = ("Explicit", "Implicit")[self._is_implicit_VR]
        big_little = ("Big", "Little")[self._is_little_endian]
        logger.debug("Using {0:s} VR, {1:s} Endian transfer syntax".format(
            impl_expl, big_little))

    def __iter__(self):
        tags = sorted(self.file_meta_info.keys())
        for tag in tags:
            yield self.file_meta_info[tag]

        for data_element in data_element_generator(self.fp,
                                                   self._is_implicit_VR, self._is_little_endian,
                                                   stop_when=self.stop_when):
            yield data_element


def data_element_generator(fp, is_implicit_VR, is_little_endian,
                           stop_when=None, defer_size=None, encoding=default_encoding):
    """Create a generator to efficiently return the raw data elements.

    Parameters
    ----------
    fp : file-like object
    is_implicit_VR : boolean
    is_little_endian : boolean
    stop_when : None, callable, optional
        If None (default), then the whole file is read.
        A callable which takes tag, VR, length,
        and returns True or False. If it returns True,
        read_data_element will just return.
    defer_size : int, str, None, optional
        See ``read_file`` for parameter info.
    encoding :
        Encoding scheme

    Returns
    -------
    VR : None if implicit VR, otherwise the VR read from the file
    length :
        the length as in the DICOM data element (could be
        DICOM "undefined length" 0xffffffffL)
    value_bytes :
        the raw bytes from the DICOM file
        (not parsed into python types)
    is_little_endian : boolean
        True if transfer syntax is little endian; else False.
    """
    # Summary of DICOM standard PS3.5-2008 chapter 7:
    # If Implicit VR, data element is:
    #    tag, 4-byte length, value.
    #       The 4-byte length can be FFFFFFFF (undefined length)*
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
            if not in_py2:
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
            if defer_size is not None and length > defer_size:
                # Flag as deferred by setting value to None, and skip bytes
                value = None
                logger_debug("Defer size exceeded. "
                             "Skipping forward to next data element.")
                fp.seek(fp_tell() + length)
            else:
                value = fp_read(length)
                if debugging:
                    dotdot = "   "
                    if length > 12:
                        dotdot = "..."
                    logger_debug("%08x: %-34s %s %r %s" % (value_tell,
                                                           bytes2hex(value[:12]), dotdot, value[:12], dotdot))

            # If the tag is (0008,0005) Specific Character Set, then store it
            if tag == (0x08, 0x05):
                from pydicom.values import convert_string
                encoding = convert_string(value, is_little_endian, encoding=default_encoding)
                # Store the encoding value in the generator for use with future elements (SQs)
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
                    VR = dictionaryVR(tag)
                except KeyError:
                    # Look ahead to see if it consists of items and is thus a SQ
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
                yield DataElement(tag, VR, seq, value_tell,
                                  is_undefined_length=True)
            else:
                delimiter = SequenceDelimiterTag
                if debugging:
                    logger_debug("Reading undefined length data element")
                value = read_undefined_length_value(fp, is_little_endian,
                                                    delimiter, defer_size)

                # If the tag is (0008,0005) Specific Character Set, then store it
                if tag == (0x08, 0x05):
                    from pydicom.values import convert_string
                    encoding = convert_string(value, is_little_endian, encoding=default_encoding)
                    # Store the encoding value in the generator for use with future elements (SQs)
                    encoding = convert_encodings(encoding)

                yield RawDataElement(tag, VR, length, value, value_tell,
                                     is_implicit_VR, is_little_endian)


def read_dataset(fp, is_implicit_VR, is_little_endian, bytelength=None,
                 stop_when=None, defer_size=None, parent_encoding=default_encoding):
    """Return a Dataset instance containing the next dataset in the file.

    Parameters
    ----------
    fp : an opened file object
    is_implicit_VR : boolean
        True if file transfer syntax is implicit VR.
    is_little_endian : boolean
        True if file has little endian transfer syntax.
    bytelength : int, None, optional
        None to read until end of file or ItemDeliterTag, else
        a fixed number of bytes to read
    stop_when : None, optional
        optional call_back function which can terminate reading.
        See help for data_element_generator for details
    defer_size : int, None, optional
        Size to avoid loading large elements in memory.
        See ``read_file`` for more parameter info.
    parent_encoding :
        optional encoding to use as a default in case
        a Specific Character Set (0008,0005) isn't specified

    Returns
    -------
    a Dataset instance

    See Also
    --------
    pydicom.dataset.Dataset
        A collection (dictionary) of Dicom `DataElement` instances.
    """
    raw_data_elements = dict()
    fpStart = fp.tell()
    de_gen = data_element_generator(fp, is_implicit_VR, is_little_endian,
                                    stop_when, defer_size, parent_encoding)
    try:
        while (bytelength is None) or (fp.tell() - fpStart < bytelength):
            raw_data_element = next(de_gen)
            # Read data elements. Stop on some errors, but return what was read
            tag = raw_data_element.tag
            # Check for ItemDelimiterTag --dataset is an item in a sequence
            if tag == (0xFFFE, 0xE00D):
                break
            raw_data_elements[tag] = raw_data_element
    except StopIteration:
        pass
    except EOFError as details:
        # XXX is this error visible enough to user code with just logging?
        logger.error(str(details) + " in file " +
                     getattr(fp, "name", "<no filename>"))
    except NotImplementedError as details:
        logger.error(details)

    return Dataset(raw_data_elements)


def read_sequence(fp, is_implicit_VR, is_little_endian, bytelength, encoding,
                  offset=0):
    """Read and return a Sequence -- i.e. a list of Datasets"""

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


def read_sequence_item(fp, is_implicit_VR, is_little_endian, encoding, offset=0):
    """Read and return a single sequence item, i.e. a Dataset"""
    seq_item_tell = fp.tell() + offset
    if is_little_endian:
        tag_length_format = "<HHL"
    else:
        tag_length_format = ">HHL"
    try:
        bytes_read = fp.read(8)
        group, element, length = unpack(tag_length_format, bytes_read)
    except:
        raise IOError("No tag to read at file position "
                      "{0:05x}".format(fp.tell() + offset))
    tag = (group, element)
    if tag == SequenceDelimiterTag:  # No more items, time to stop reading
        logger.debug("{0:08x}: {1}".format(fp.tell() - 8 + offset, "End of Sequence"))
        if length != 0:
            logger.warning("Expected 0x00000000 after delimiter, found 0x%x, "
                           "at position 0x%x" % (length, fp.tell() - 4 + offset))
        return None
    if tag != ItemTag:
        logger.warning("Expected sequence item with tag %s at file position "
                       "0x%x" % (ItemTag, fp.tell() - 4 + offset))
    else:
        logger.debug("{0:08x}: {1}  Found Item tag (start of item)".format(
            fp.tell() - 4 + offset, bytes2hex(bytes_read)))
    if length == 0xFFFFFFFF:
        ds = read_dataset(fp, is_implicit_VR, is_little_endian,
                          bytelength=None, parent_encoding=encoding)
        ds.is_undefined_length_sequence_item = True
    else:
        ds = read_dataset(fp, is_implicit_VR, is_little_endian, length,
                          parent_encoding=encoding)
        ds.is_undefined_length_sequence_item = False
        logger.debug("%08x: Finished sequence item" % (fp.tell() + offset,))
    ds.seq_item_tell = seq_item_tell
    return ds


def not_group2(tag, VR, length):
    return (tag.group != 2)


def _read_file_meta_info(fp):
    """Return the file meta information.
    fp must be set after the 128 byte preamble and 'DICM' marker
    """
    # File meta info always LittleEndian, Explicit VR. After will change these
    #    to the transfer syntax values set in the meta info

    # Get group length data element, whose value is the length of the meta_info
    fp_save = fp.tell()  # in case need to rewind
    debugging = config.debugging
    if debugging:
        logger.debug("Try to read group length info...")
    bytes_read = fp.read(8)
    group, elem, VR, length = unpack("<HH2sH", bytes_read)
    if debugging:
        debug_msg = "{0:08x}: {1}".format(fp.tell() - 8, bytes2hex(bytes_read))
    if not in_py2:
        VR = VR.decode(default_encoding)
    if VR in extra_length_VRs:
        bytes_read = fp.read(4)
        length = unpack("<L", bytes_read)[0]
        if debugging:
            debug_msg += " " + bytes2hex(bytes_read)
    if debugging:
        debug_msg = "{0:<47s}  ({1:04x}, {2:04x}) {3:2s} Length: {4:d}".format(
            debug_msg, group, elem, VR, length)
        logger.debug(debug_msg)

    # Store meta group length if it exists, then read until not group 2
    if group == 2 and elem == 0:
        bytes_read = fp.read(length)
        if debugging:
            logger.debug("{0:08x}: {1}".format(fp.tell() - length,
                                               bytes2hex(bytes_read)))
        group_length = unpack("<L", bytes_read)[0]
        expected_ds_start = fp.tell() + group_length
        if debugging:
            msg = "value (group length) = {0:d}".format(group_length)
            msg += "  regular dataset should start at {0:08x}".format(
                expected_ds_start)
            logger.debug(" " * 10 + msg)
    else:
        expected_ds_start = None
        if debugging:
            logger.debug(" " * 10 + "(0002,0000) Group length not found.")

    # Changed in pydicom 0.9.7 -- don't trust the group length, just read
    #    until no longer group 2 data elements. But check the length and
    #    give a warning if group 2 ends at different location.
    # Rewind to read the first data element as part of the file_meta dataset
    if debugging:
        logger.debug("Rewinding and reading whole dataset "
                     "including this first data element")
    fp.seek(fp_save)
    file_meta = read_dataset(fp, is_implicit_VR=False,
                             is_little_endian=True, stop_when=not_group2)
    fp_now = fp.tell()
    if expected_ds_start and fp_now != expected_ds_start:
        logger.info("*** Group length for file meta dataset "
                    "did not match end of group 2 data ***")
    else:
        if debugging:
            logger.debug("--- End of file meta data found "
                         "as expected ---------")
    return file_meta


def read_file_meta_info(filename):
    """Read and return the DICOM file meta information only.

    This function is meant to be used in user code, for quickly going through
    a series of files to find one which is referenced to a particular SOP,
    without having to read the entire files.
    """
    fp = DicomFile(filename, 'rb')
    read_preamble(fp, False)  # if no header, raise exception
    return _read_file_meta_info(fp)


def read_preamble(fp, force):
    """Read and return the DICOM preamble.

    Parameters
    ----------
    fp : file-like object
    force : boolean
        Flag to force reading of a file even if no header is found.

    Returns
    -------
    preamble : DICOM preamble, None
        The DICOM preamble will be returned if appropriate
        header ('DICM') is found. Returns None if no header
        is found.

    Raises
    ------
    InvalidDicomError
        If force flag is false and no appropriate header information
        found.

    Notes
    -----
    Also reads past the 'DICM' marker. Rewinds file to the beginning if
    no header found.
    """
    logger.debug("Reading preamble...")
    preamble = fp.read(0x80)
    if config.debugging:
        sample = bytes2hex(preamble[:8]) + "..." + bytes2hex(preamble[-8:])
        logger.debug("{0:08x}: {1}".format(fp.tell() - 0x80, sample))
    magic = fp.read(4)
    if magic != b"DICM":
        if force:
            logger.info("File is not a standard DICOM file; 'DICM' header is "
                        "missing. Assuming no header and continuing")
            preamble = None
            fp.seek(0)
        else:
            raise InvalidDicomError("File is missing 'DICM' marker. "
                                    "Use force=True to force reading")
    else:
        logger.debug("{0:08x}: 'DICM' marker found".format(fp.tell() - 4))
    return preamble


def _at_pixel_data(tag, VR, length):
    return tag == (0x7fe0, 0x0010)


def read_partial(fileobj, stop_when=None, defer_size=None, force=False):
    """Parse a DICOM file until a condition is met.

    Parameters
    ----------
    fileobj : a file-like object
        Note that the file will not close when the function returns.
    stop_when :
        Stop condition. See ``read_dataset`` for more info.
    defer_size : int, str, None, optional
        See ``read_file`` for parameter info.
    force : boolean
        See ``read_file`` for parameter info.

    Notes
    -----
    Use ``read_file`` unless you need to stop on some condition
    other than reaching pixel data.

    Returns
    -------
    FileDataset instance or DicomDir instance.

    See Also
    --------
    read_file
        More generic file reading function.
    """
    # Read preamble -- raise an exception if missing and force=False
    preamble = read_preamble(fileobj, force)
    file_meta_dataset = Dataset()
    # Assume a transfer syntax, correct it as necessary
    is_implicit_VR = True
    is_little_endian = True
    if preamble:
        file_meta_dataset = _read_file_meta_info(fileobj)
        transfer_syntax = file_meta_dataset.get("TransferSyntaxUID")
        if transfer_syntax is None:  # issue 258
            pass
        elif transfer_syntax == pydicom.uid.ImplicitVRLittleEndian:
            pass
        elif transfer_syntax == pydicom.uid.ExplicitVRLittleEndian:
            is_implicit_VR = False
        elif transfer_syntax == pydicom.uid.ExplicitVRBigEndian:
            is_implicit_VR = False
            is_little_endian = False
        elif transfer_syntax == pydicom.uid.DeflatedExplicitVRLittleEndian:
            # See PS3.6-2008 A.5 (p 71)
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
    else:  # no header -- use the is_little_endian, implicit assumptions
        file_meta_dataset.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian
        endian_chr = "<"
        element_struct = Struct(endian_chr + "HH2sH")
        # Try reading first 8 bytes
        group, elem, VR, length = element_struct.unpack(fileobj.read(8))
        # Rewind file object
        fileobj.seek(0)
        # If the VR is a valid VR, assume Explicit VR transfer systax
        from pydicom.values import converters
        if not in_py2:
            VR = VR.decode(default_encoding)
        if VR in converters.keys():
            is_implicit_VR = False
            # Determine if group in low numbered range (Little vs Big Endian)
            if group == 0:  # got (0,0) group length. Not helpful.
                # XX could use similar to http://www.dclunie.com/medical-image-faq/html/part2.html code example
                msg = ("Not able to guess transfer syntax when first item "
                       "is group length")
                raise NotImplementedError(msg)
            if group < 2000:
                file_meta_dataset.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
            else:
                file_meta_dataset.TransferSyntaxUID = pydicom.uid.ExplicitVRBigEndian
                is_little_endian = False

    try:
        dataset = read_dataset(fileobj, is_implicit_VR, is_little_endian,
                               stop_when=stop_when, defer_size=defer_size)
    except EOFError:
        pass  # error already logged in read_dataset

    class_uid = file_meta_dataset.get("MediaStorageSOPClassUID", None)
    if class_uid and class_uid == "Media Storage Directory Storage":
        return DicomDir(fileobj, dataset, preamble, file_meta_dataset,
                        is_implicit_VR, is_little_endian)
    else:
        return FileDataset(fileobj, dataset, preamble, file_meta_dataset,
                           is_implicit_VR, is_little_endian)


def read_file(fp, defer_size=None, stop_before_pixels=False, force=False):
    """Read and parse a DICOM file.

    Parameters
    ----------
    fp : file-like object, str
        Either a file-like object, or a string containing the file name.
        If a file-like object, the caller is responsible for closing it.
    defer_size : int, str, None, optional
        If None (default), all elements read into memory.
        If specified, if a data element value is larger than defer_size,
        then the value is not read into memory until it is accessed in code.
        Specify an integer (bytes), or a string value with units, e.g.
        "512 KB", "2 MB".
    stop_before_pixels : boolean, optional
        If False (default), the full file will be read and parsed.
        Set True to stop before reading pixels (and anything after them).
    force : boolean, optional
        If False (default), raises an InvalidDicomError if the file
        is not valid DICOM.
        Set to True to force reading even if no header is found.

    Returns
    -------
    FileDataset
        An instance of FileDataset that represents a parsed DICOM file.

    Raises
    ------
    InvalidDicomError
        If the force flag is True and the file is not a valid DICOM file.

    See Also
    --------
    pydicom.dataset.FileDataset
        Data class that is returned.
    pydicom.filereader.read_partial
        Only read part of a DICOM file, stopping on given conditions.

    Examples
    --------
    Read file and return file dataset:
    >>> rtplan = pydicom.read_file("rtplan.dcm")
    >>> rtplan.PatientName

    Use within a context manager:
    >>> with pydicom.read_file("rtplan.dcm") as rtplan:
    >>>     rtplan.PatientName
    """
    # Open file if not already a file object
    caller_owns_file = True
    if isinstance(fp, compat.string_types):
        # caller provided a file name; we own the file handle
        caller_owns_file = False
        try:
            logger.debug(u"Reading file '{0}'".format(fp))
        except Exception:
            logger.debug("Reading file '{0}'".format(fp))
        fp = open(fp, 'rb')

    if config.debugging:
        logger.debug("\n" + "-" * 80)
        logger.debug("Call to read_file()")
        msg = ("filename:'%s', defer_size='%s', "
               "stop_before_pixels=%s, force=%s")
        logger.debug(msg % (fp.name, defer_size, stop_before_pixels, force))
        if caller_owns_file:
            logger.debug("Caller passed file object")
        else:
            logger.debug("Caller passed file name")
        logger.debug("-" * 80)

    # Convert size to defer reading into bytes, and store in file object
    # if defer_size is not None:
    #    defer_size = size_in_bytes(defer_size)
    # fp.defer_size = defer_size

    # Iterate through all items and store them --include file meta if present
    stop_when = None
    if stop_before_pixels:
        stop_when = _at_pixel_data
    try:
        dataset = read_partial(fp, stop_when, defer_size=defer_size,
                               force=force)
    finally:
        if not caller_owns_file:
            fp.close()
    # XXX need to store transfer syntax etc.
    return dataset


def read_dicomdir(filename="DICOMDIR"):
    """Read a DICOMDIR file and return a DicomDir instance.

    This is a wrapper around read_file, which gives a default file name.

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
    # read_file will return a DicomDir instance if file is one.

    # Read the file as usual.
    ds = read_file(filename)
    # Here, check that it is in fact DicomDir
    if not isinstance(ds, DicomDir):
        msg = u"File '{0}' is not a Media Storage Directory file".format(filename)
        raise InvalidDicomError(msg)
    return ds


def data_element_offset_to_value(is_implicit_VR, VR):
    """Return number of bytes from start of data element to start of value"""
    if is_implicit_VR:
        offset = 8   # tag of 4 plus 4-byte length
    else:
        if VR in extra_length_VRs:
            offset = 12  # tag 4 + 2 VR + 2 reserved + 4 length
        else:
            offset = 8  # tag 4 + 2 VR + 2 length
    return offset


def read_deferred_data_element(fileobj_type, filename, timestamp,
                               raw_data_elem):
    """Read the previously deferred value from the file into memory
    and return a raw data element"""
    logger.debug("Reading deferred element %r" % str(raw_data_elem.tag))
    # If it wasn't read from a file, then return an error
    if filename is None:
        raise IOError("Deferred read -- original filename not stored. "
                      "Cannot re-open")
    # Check that the file is the same as when originally read
    if not os.path.exists(filename):
        raise IOError(u"Deferred read -- original file "
                      "{0:s} is missing".format(filename))
    if stat_available and (timestamp is not None):
        statinfo = os.stat(filename)
        if statinfo.st_mtime != timestamp:
            warnings.warn("Deferred read warning -- file modification time "
                          "has changed.")

    # Open the file, position to the right place
    # fp = self.typefileobj(self.filename, "rb")
    fp = fileobj_type(filename, 'rb')
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
                         "original {1:s}".format(data_elem.VR, raw_data_elem.VR))
    if data_elem.tag != raw_data_elem.tag:
        raise ValueError("Deferred read tag {0!r} does not match "
                         "original {1!r}".format(data_elem.tag, raw_data_elem.tag))

    # Everything is ok, now this object should act like usual DataElement
    return data_elem
