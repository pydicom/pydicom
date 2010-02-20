# filereader.py
"""Read a dicom media file"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

# Need zlib and cStringIO for deflate-compressed file
import os.path
import warnings
import zlib
from cStringIO import StringIO # tried cStringIO but wouldn't let me derive class from it.
import logging
from dicom.tag import TupleTag
from dicom.dataelem import RawDataElement

logger = logging.getLogger('pydicom')

stat_available = True
try:
    from os import stat
except:
    stat_available = False
try:
    from os import SEEK_CUR
except ImportError: # SEEK_CUR not available in python < 2.5
    SEEK_CUR = 1

import dicom.UID # for Implicit/Explicit / Little/Big Endian transfer syntax UIDs
from dicom.filebase import DicomFile, DicomFileLike
from dicom.filebase import DicomIO, DicomStringIO
from dicom.dataset import Dataset, FileDataset
from dicom.datadict import dictionaryVR
from dicom.dataelem import DataElement, DeferredDataElement
from dicom.tag import Tag, ItemTag, ItemDelimiterTag, SequenceDelimiterTag
from dicom.sequence import Sequence
from dicom.misc import size_in_bytes
from dicom.fileutil import absorb_delimiter_item, read_undefined_length_value
from dicom.fileutil import length_of_undefined_length
from struct import unpack
from sys import byteorder
sys_is_little_endian = (byteorder == 'little')

class InvalidDicomError(Exception):
    """Exception that is raised when the the file does not seem
    to be a valid dicom file. This is the case when the three
    characters "DICM" are not present at position 128 in the file.
    (According to the dicom specification, each dicom file should 
    have this.)
    
    To force reading the file (because maybe it is a dicom file without
    a header), use read_file(..., force=True).
    """
    def __init__(self, *args):
        if not args:
            args = ('The specified file is not a valid DICOM file.',)
        Exception.__init__(self, *args)

def open_dicom(filename, force=False):
    """Return an iterator for DICOM file data elements.

    Similar to opening a file using python open() and iterating by line

    Use like:

    from dicom.filereader import open_dicom
    from dicom.dataset import Dataset
    ds = Dataset()
    for data_element in open_dicom("CT_small.dcm"):
        if meets_some_condition(data_element):
            ds.Add(data_element)
        if some_other_condition(data_element):
            break
    You can generalize this function to examine the elements as they come,
    or to only read to a certain point and then stop
    """

    return DicomIter(DicomFile(filename,'rb'), force=force)

class DicomIter(object):
    """Iterator over DICOM data elements created from a file-like object
    """
    def __init__(self, fp, stop_when=None, force=False):
        """Read the preambleand meta info, prepare iterator for remainder

        fp -- an open DicomFileLike object, at start of file

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
            if transfer_syntax == dicom.UID.ExplicitVRLittleEndian:
                is_explicit_VR = True
            elif transfer_syntax == dicom.UID.ImplicitVRLittleEndian:
                is_implicit_VR = True
            elif transfer_syntax == dicom.UID.ExplicitVRBigEndian:
                is_explicit_VR = True
                is_big_endian = True
            elif transfer_syntax == dicom.UID.DeflatedExplicitVRLittleEndian:
                # See PS3.6-2008 A.5 (p 71) -- when written, the entire dataset following
                #     the file metadata was prepared the normal way, then "deflate" compression applied.
                #  All that is needed here is to decompress and then use as normal in a file-like object
                zipped = fp.read()
                # -MAX_WBITS part is from comp.lang.python answer:  http://groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
                unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
                fp = StringIO(unzipped) # a file-like object that usual code can use as normal
                self.fp = fp #point to new object
                is_explicit_VR = True
                is_little_endian = True
            else:
                # Any other syntax should be Explicit VR Little Endian,
                #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE by Standard PS 3.5-2008 A.4 (p63)
                is_explicit_VR = True
                is_little_endian = True
        else: # no header -- make assumptions
            fp.TransferSyntaxUID = dicom.UID.ImplicitVRLittleEndian
            is_little_endian = True
            is_implicit_VR = True

        logger.debug("Using %s VR, %s Endian transfer syntax" %(("Explicit", "Implicit")[is_implicit_VR], ("Big", "Little")[is_little_endian]))

    def __iter__(self):
        tags = self.file_meta_info.keys()
        tags.sort()
        for tag in tags:
            yield self.file_meta_info[tag]

        for data_element in data_element_generator(self.fp, stop_when=self.stop_when):
            yield data_element

def data_element_generator(fp, is_implicit_VR, is_little_endian, stop_when=None, 
                            defer_size=None):
    """Create a generator to efficiently return the raw data elements
    Specifically, returns (VR, length, raw_bytes, value_tell, is_little_endian),
    where:
    VR -- None if implicit VR, otherwise the VR read from the file
    length -- the length as in the DICOM data element (could be
        DICOM "undefined length" 0xffffffffL),
    value_bytes -- the raw bytes from the DICOM file (not parsed into python types)
    is_little_endian -- True if transfer syntax is little endian; else False
    """
    # Summary of DICOM standard PS3.5-2008 chapter 7:
    # If Implicit VR, data element is:
    #    tag, 4-byte length, value.
    #       The 4-byte length can be FFFFFFFF (undefined length)*
    # If Explicit VR:
    #    if OB, OW, OF, SQ, UN, or UT:
    #       tag, VR, 2-bytes reserved (both zero), 4-byte length, value
    #           for all but UT, the length can be FFFFFFFF (undefined length)*
    #   else: (any other VR)
    #       tag, VR, (2 byte length), value
    # * for undefined length, a Sequence Delimitation Item marks the end
    #        of the Value Field.

    # With a generator, state is stored, so we can break down
    #    into the individual cases, and not have to check them again for each
    #    data element

    # Make local variables so have faster lookup
    fp_read = fp.read
    fp_tell = fp.tell
    logger_debug = logger.debug
    debugging = dicom.debugging
    
    if is_little_endian:
        endian_chr = "<"
    else:
        endian_chr = ">"
    if is_implicit_VR:
        unpack_format = endian_chr + "HHL" # XXX in python >=2.5, can do struct.Struct to save time
    else: # Explicit VR
        unpack_format = endian_chr + "HH2s"
        long_length_format = endian_chr + "2sL"
        short_length_format = endian_chr + "H"

    while True:
        # Read tag, VR, length, get ready to read value
        if is_implicit_VR:
            VR = None # must reset each time -- may have looked up on last iteration (e.g. SQ)
            bytes = fp_read(8)
            if len(bytes) < 8:
                raise StopIteration # at end of file
            group, elem, length = unpack(unpack_format, bytes)
        else: # explicit VR
            bytes = fp_read(6)
            if len(bytes) < 6:
                raise StopIteration # at end of file
            group, elem, VR = unpack(unpack_format, bytes)
            if debugging:
                logger_debug("%04x: (%04x, %04x) ExplVR='%s'" % (fp_tell()-6, group, elem , VR))
            if VR in ('OB','OW','OF','SQ','UN', 'UT'):
                reserved, length = unpack(long_length_format, fp_read(6))
            else:
                length = unpack(short_length_format, fp_read(2))[0]

        # Now are positioned to read the value, but may not want to -- check stop_when
        value_tell = fp_tell()
        # logger.debug("%04x: start of value of length %d" % (value_tell, length))
        tag = TupleTag((group, elem))
        if stop_when is not None:
            if stop_when(tag, VR, length): # XXX Note VR may be None here!! Should make stop_when just take tag?
                raise StopIteration

        # Reading the value
        # First case (most common): reading a value with a defined length
        if length != 0xFFFFFFFFL:
            if defer_size is not None and length > defer_size:
                # Flag as deferred read by setting value to None, and skip bytes
                value = None
                fp.seek(fp_tell()+length)
            else:
                value = fp_read(length)
                if debugging:
                    logger_debug("%04x: (%04x, %04x) %4s %04x %30r " % (value_tell, group, elem, VR, length, value[:30]))
            yield RawDataElement(tag, VR, length, value, value_tell, 
                                     is_implicit_VR, is_little_endian)

        # Second case: undefined length - must seek to delimiter,
        #  ... unless is SQ type, in which case is easier to parse it, because
        #      undefined length SQs and items of undefined lengths can be nested
        #      and it would be error-prone to read to the correct outer delimiter 
        else:
            if VR is None:
                VR = dictionaryVR(tag)
            if VR == 'SQ':
                if debugging:
                    logger_debug("%04x: Reading and parsing undefined length sequence"
                                % fp_tell())
                seq = read_sequence(fp, is_implicit_VR, is_little_endian, length)
                yield DataElement(tag, VR, seq, value_tell, is_undefined_length=True)
            else:
                delimiter = SequenceDelimiterTag
                if debugging:
                    logger_debug("Reading undefined length data element")
                value = read_undefined_length_value(fp, is_little_endian, delimiter,
                                        defer_size)
                yield RawDataElement(tag, VR, length, value, value_tell,
                                is_implicit_VR, is_little_endian)

def read_dataset(fp, is_implicit_VR, is_little_endian, bytelength=None, 
                    stop_when=None, defer_size=None):
    """Return a dictionary containing raw data elements of the form:
    tag -> (VR, length, value, value_tell)
    where length is original length (could be "undefined length")
    and value_tell is the file position where the value bytes start.
    """
    raw_data_elements = dict()
    fpStart = fp.tell()
    de_gen = data_element_generator(fp, is_implicit_VR, is_little_endian, 
                                    stop_when, defer_size)
    try:
        while (bytelength is None) or (fp.tell()-fpStart < bytelength):
            raw_data_element = de_gen.next()
            # Read data elements. Stop on certain errors, but return what was already read
            tag = raw_data_element.tag
            if tag == (0xFFFE, 0xE00D): #ItemDelimiterTag --dataset is an item in a sequence
                break
            raw_data_elements[tag] = raw_data_element

    except StopIteration:
        pass
    except EOFError, details:
        logger.error(str(details) + " in file " +
                    getattr(fp, "name", "<no filename>")) # XXX is this visible enough to user code?
    except NotImplementedError, details:
        logger.error(details)

    return Dataset(raw_data_elements)

def read_sequence(fp, is_implicit_VR, is_little_endian, bytelength):
    """Read and return a Sequence -- i.e. a list of Datasets"""
    seq = [] # use builtin list to start for speed, convert to Sequence at end
    is_undefined_length = False
    if bytelength != 0:  # Sequence of length 0 is possible (PS 3.5-2008 7.5.1a (p.40)
        if bytelength == 0xffffffffL:
            is_undefined_length = True
            bytelength = None
        fp_tell = fp.tell # for speed in loop
        fpStart = fp_tell()
        while (not bytelength) or (fp_tell()-fpStart < bytelength):
            dataset = read_sequence_item(fp, is_implicit_VR, is_little_endian)
            if dataset is None:  # None is returned if get to Sequence Delimiter
                break
            seq.append(dataset)
    seq = Sequence(seq)
    seq.is_undefined_length = is_undefined_length
    return seq

def read_sequence_item(fp, is_implicit_VR, is_little_endian):
    """Read and return a single sequence item, i.e. a Dataset"""
    if is_little_endian:
        tag_length_format = "<HHL"
    else:
        tag_length_format = ">HHL"
    try:
        group, element, length = unpack(tag_length_format, fp.read(8))
    except:
        raise IOError, "No tag to read at file position %05x" % fp.tell()

    tag = (group, element)
    if tag == SequenceDelimiterTag: # No more items, time to stop reading
        data_element = DataElement(tag, None, None, fp.tell()-4)
        logger.debug("%04x: %s" % (fp.tell()-4, "End of Sequence"))
        if length != 0:
            logger.warning("Expected 0x00000000 after delimiter, found 0x%x, at position 0x%x" % (length, fp.tell()-4))
        return None
    if tag != ItemTag:
        logger.warning("Expected sequence item with tag %s at file position 0x%x" % (ItemTag, fp.tell()-4))
    else:
        logger.debug("%04x: Found Item tag (start of item)" % (fp.tell()-4,))
    is_undefined_length = False
    if length == 0xFFFFFFFFL:
        ds = read_dataset(fp, is_implicit_VR, is_little_endian, bytelength=None)
        ds.is_undefined_length_sequence_item = True
    else:
        ds = read_dataset(fp, is_implicit_VR, is_little_endian, length)
    logger.debug("%04x: Finished sequence item" % fp.tell())
    return ds

def _read_file_meta_info(fp):
    """Return the file meta information.
    fp must be set after the 128 byte preamble and 'DICM' marker
    """
    # File meta info is always LittleEndian, Explicit VR. After will change these
    #    to the transfer syntax values set in the meta info

    # Get group length data element, whose value is the length of the meta_info
    group, elem, VR, length = unpack("<HH2sH", fp.read(8))
    group_length = unpack("<L", fp.read(length))[0] # XXX should prob check (gp, el), VR before read
    file_meta = read_dataset(fp, is_implicit_VR=False,
                        is_little_endian=True, bytelength=group_length)
    # ds = Dataset(raw_file_meta)
    return file_meta

def read_file_meta_info(filename):
    """Read and return the DICOM file meta information only.

    This function is meant to be used in user code, for quickly going through
    a series of files to find one which is referenced to a particular SOP,
    without having to read the entire files.
    """
    fp = DicomFile(filename, 'rb')
    preamble = read_preamble(fp, False) # if no header, raise exception
    return _read_file_meta_info(fp)

def read_preamble(fp, force):
    """Read and return the DICOM preamble and read past the 'DICM' marker.
    If 'DICM' does not exist, assume no preamble, return None, and
    rewind file to the beginning..
    """
    logger.debug("Reading preamble")
    preamble = fp.read(0x80)
    magic = fp.read(4)
    if magic != "DICM":
        if force:
            logger.info("File is not a standard DICOM file; 'DICM' header is missing. Assuming no header and continuing")
            preamble = None
            fp.seek(0)
        else:
            raise InvalidDicomError
    return preamble

def _at_pixel_data(tag, VR, length):
    return tag == (0x7fe0, 0x0010)

def read_partial(fileobj, stop_when=None, defer_size=None, force=False):
    """Parse a DICOM file until a condition is met; return partial dataset
    fileobj -- a file-like object. This function does not close it.
    stop_when -- a function which takes tag, VR, length, and returns True or False.
        A True value means read_data_element will raise StopIteration.
        if None, then the whole file is read.
    """
    preamble = read_preamble(fileobj, force) # raises an exception if force=False
    file_meta_dataset = Dataset()
    # Assume a transfer syntax, correct it as necessary
    is_implicit_VR = True
    is_little_endian = True
    if preamble:
        file_meta_dataset = _read_file_meta_info(fileobj)
        transfer_syntax = file_meta_dataset.TransferSyntaxUID
        if transfer_syntax == dicom.UID.ImplicitVRLittleEndian:
            pass
        elif transfer_syntax == dicom.UID.ExplicitVRLittleEndian:
            is_implicit_VR = False
        elif transfer_syntax == dicom.UID.ExplicitVRBigEndian:
            is_implicit_VR = False
            is_little_endian = False
        elif transfer_syntax == dicom.UID.DeflatedExplicitVRLittleEndian:
            # See PS3.6-2008 A.5 (p 71) -- when written, the entire dataset following
            #     the file metadata was prepared the normal way, then "deflate" compression applied.
            #  All that is needed here is to decompress and then use as normal in a file-like object
            zipped = fileobj.read()
            # -MAX_WBITS part is from comp.lang.python answer:  http://groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
            unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
            fileobj = StringIO(unzipped) # a file-like object that usual code can use as normal
            is_implicit_VR = False
        else:
            # Any other syntax should be Explicit VR Little Endian,
            #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE by Standard PS 3.5-2008 A.4 (p63)
            is_implicit_VR = False
    else: # no header -- use the is_little_endian, implicit assumptions
        file_meta_dataset.TransferSyntaxUID = dicom.UID.ImplicitVRLittleEndian

    try:
        dataset = read_dataset(fileobj, is_implicit_VR, is_little_endian, 
                            stop_when=stop_when, defer_size=defer_size)
    except EOFError, e:
        pass  # error already logged in read_dataset
    return FileDataset(fileobj, dataset, preamble, file_meta_dataset, is_implicit_VR,
                        is_little_endian)

def read_file(fp, defer_size=None, stop_before_pixels=False, force=False):
    """Return a Dataset containing the contents of the Dicom file

    fp -- either a file-like object, or a string containing the file name.
    defer_size -- if a data element value is larger than defer_size,
        then the value is not read into memory until it is accessed in code.
        Specify an integer (bytes), or a string value with units: e.g. "512 KB", "2 MB".
        Default None means all elements read into memory.
    stop_before_pixels -- Set False to stop before reading pixels (and anything after them).
                   If False, a partial dataset will be returned.
    force -- Set to True to force reading the file even if no header is found.
                   If False, a dicom.filereader.InvalidDicomError is raised when the file is not valid DICOM.
    """
    # Open file if not already a file object
    caller_owns_file = True
    if isinstance(fp, basestring):
        # caller provided a file name; we own the file handle
        caller_owns_file = False
        logger.debug("Reading file '%s'" % fp)
        fp = open(fp, 'rb')

    # Convert size to defer reading into bytes, and store in file object
    # if defer_size is not None:
    #    defer_size = size_in_bytes(defer_size)
    # fp.defer_size = defer_size

    # Iterate through all items and store them --includes file meta info if present
    stop_when = None
    if stop_before_pixels:
        stop_when = _at_pixel_data
    try:
        dataset = read_partial(fp, stop_when, defer_size=defer_size, force=force)
    finally:
        if not caller_owns_file:
            fp.close()
    # XXX need to store transfer syntax etc.
    return dataset

ReadFile = read_file    # For backwards compatibility pydicom version <=0.9.2
readfile = read_file    # forgive a missing underscore

def data_element_offset_to_value(is_implicit_VR, VR):
    """Return number of bytes from start of data element to start of value"""
    if is_implicit_VR:
        offset = 8   # tag of 4 plus 4-byte length
    else:
        if VR in ('OB','OW','OF','SQ','UN','UT'):
            offset = 12 # tag 4 + 2 VR + 2 reserved + 4 length
        else: 
            offset = 8  # tag 4 + 2 VR + 2 length
    return offset

def read_deferred_data_element(filename, timestamp, raw_data_elem):
    """Read the previously deferred value from the file into memory
    and return a raw data element"""
    logger.debug("Reading deferred element %r" % str(raw_data_elem.tag))
    # If it wasn't read from a file, then return an error
    if filename is None:
        raise IOError, "Deferred read -- original filename not stored. Cannot re-open"
    # Check that the file is the same as when originally read
    if not os.path.exists(filename):
        raise IOError, "Deferred read -- original file '%s' is missing" % filename
    if stat_available and timestamp is not None:
        statinfo = stat(filename)
        if statinfo.st_mtime != timestamp:
            warnings.warn("Deferred read warning -- file modification time has changed.")

    # Open the file, position to the right place
    fp = open(filename, 'rb')
    is_implicit_VR = raw_data_elem.is_implicit_VR
    is_little_endian = raw_data_elem.is_little_endian
    offset = data_element_offset_to_value(is_implicit_VR, raw_data_elem.VR)
    fp.seek(raw_data_elem.value_tell - offset)
    elem_gen = data_element_generator(fp, is_implicit_VR, is_little_endian, 
                                        defer_size=None)

    # Read the data element and check matches what was stored before
    data_elem = elem_gen.next()
    fp.close()
    if data_elem.VR != raw_data_elem.VR:
        raise ValueError, "Deferred read VR '%s' does not match original '%s'" % (data_elem.VR, raw_data_elem.VR)
    if data_elem.tag != raw_data_elem.tag:
        raise ValueError, "Deferred read tag %r does not match original %r" % (data_elem.tag, raw_data_elem.tag)

    # Everything is ok, now this object should act like usual DataElement
    return data_elem

if __name__ == "__main__":
    def hex2str(hexstr):
        """Return a bytestring rep of a string of hex rep of bytes separated by spaces"""
        return "".join([chr(int(x,16)) for x in hexstr.split()])  # after python 2.3 can be a () generator rather than a list
    
    filename = "/Users/darcy/hg/pydicom/source/dicom/testfiles/rtss.dcm"
    ds = read_file(filename)
    from dicom.util.dump import PrettyPrint
    # print ds.items()
    PrettyPrint(ds)
    # print ds
    STOP
    seq_str = (
    " 06 30 10 00"   # Referenced Frame of Reference Sequence   1 item(s) ---- 
    " ff ff ff ff"   #   undefined length
        " fe ff 00 e0"   # Sequence Item 
        " ff ff ff ff"  #   of undefined length 
            " 20 00 52 00"    # (0020, 0052) Frame of Reference UID 
            " 04 00 00 00"    # length 4
            " 32 2e 31 36"    # 2.16  -- rest left out to simplify
            " 06 30 12 00"    # RT Referenced Study Sequence  
            " ff ff ff ff"      #   undefined length
                " fe ff 00 e0"  # Sequence Item
                " ff ff ff ff"  #   of undefined length
                    " 08 00 50 11"  # (0008, 1150) Referenced SOP Class UID 
                    " 04 00 00 00"  # length 4
                    " 31 2e 32 2e"  # 1.2.          
                    " 08 00 55 11"  # (0008, 1155) Referenced SOP Instance UID 
                    " 04 00 00 00"  # length 4
                    " 32 2e 31 36"  # 2.16
                    " 06 30 14 00"  # (3006, 0014)  RT Referenced Series Sequence
                    " ff ff ff ff"  # undefined length
                        " fe ff 00 e0"  # Sequence Item
                        " ff ff ff ff"  # undefined length
                            " 20 00 0e 00"  # (0020, 000e) Series Instance UID  
                            " 04 00 00 00"  # length 4
                            " 32 2e 31 36"  # 2.16
                        " fe ff 0d e0 00 00 00 00" # Item Delimiter Tag                     
                    " fe ff dd e0 00 00 00 00" # Sequence Delimiter Tag
                " fe ff 0d e0 00 00 00 00" # Item Delimiter Tag
            " fe ff dd e0 00 00 00 00" # Sequence Delimiter Tag
        " fe ff 0d e0 00 00 00 00" # Item Delimiter Tag
    " fe ff dd e0 00 00 00 00"  # Sequence Delimiter Tag
    )
    infile = StringIO(hex2str(seq_str))
    ds = read_file(infile)
    from dicom.util import PrettyPrint
    PrettyPrint(ds)
    