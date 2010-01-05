# filereader.py
"""Read a dicom media file"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

# Need zlib and cStringIO for deflate-compressed file
import zlib
from StringIO import StringIO # tried cStringIO but wouldn't let me derive class from it.
import logging
from dicom.tag import TupleTag

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
from dicom.dataelem import DataElement, DeferredDataElement
from dicom.tag import Tag, ItemTag, ItemDelimiterTag, SequenceDelimiterTag
from dicom.sequence import Sequence
from dicom.readers import readers, read_VR
from dicom.misc import size_in_bytes
from dicom.fileutil import absorb_delimiter_item, length_of_undefined_length
from struct import unpack, Struct
from sys import byteorder
sys_isLittleEndian = (byteorder == 'little')

def open_dicom(filename):
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

    return DicomIter(DicomFile(filename,'rb'))
    
class DicomIter(object):
    """Iterator over DICOM data elements created from a file-like object
    """
    def __init__(self, fp, stop_when=None):
        """Read the preambleand meta info, prepare iterator for remainder
        
        fp -- an open DicomFileLike object, at start of file
        
        Adds flags to fp: Big/Little-endian and Implicit/Explicit VR
        """
        self.fp = fp
        self.stop_when = stop_when
        self.preamble = preamble = read_preamble(fp)
        self.has_header = has_header = (preamble is not None)
        self.file_meta_info = {}
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
                fp = DicomStringIO(unzipped) # a file-like object that usual code can use as normal
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
                
def data_element_generator(fp, is_implicit_VR, is_little_endian, stop_when=None):
    """Create a generator to efficiently return the raw data elements
    Specifically, returns (VR, length, raw_bytes, value_tell, is_little_endian),
    where: 
    VR -- None if implicit VR, otherwise the VR read from the file
    length -- the length as in the DICOM data element (could be 
        DICOM "undefined length" 0xffffffffL),
    value_bytes -- the raw bytes from the DICOM file (not parsed into python types)
    is_little_endian -- True if transfer syntax is little endian; else False
    """
    # With a generator, state is stored, so we can break down
    #    into the individual cases, and not have to check them again for each
    #    data element
    
    # XXX need to handle case of stopping on Sequence Item Delimiter
    
    # Make local variables so have faster lookup
    fp_read = fp.read 
    fp_tell = fp.tell
    if is_implicit_VR:
        VR = None # save time on read -- look it up in dictionary later
        if is_little_endian:
            unpack_format = "<HHL" # XXX in python >=2.5, can do struct.Struct to save time 
        else:
            unpack_format = ">HHL"
            
        while True:
            bytes = fp_read(8)
            if len(bytes) == 0:
                raise StopIteration # at end of file
            group, elem, length = unpack(unpack_format, bytes)
            tag = (group, elem)
            if stop_when is not None: # could move to its own case too
                if stop_when(tag, VR, length): # XXX Note VR is None here!! Should make stop_when just take tag?
                    raise StopIteration
            if length != 0xFFFFFFFFL: # undefined length
                value = fp_read(length)
                value_tell = fp_tell()
                # print "%6x: (%04x, %04x) %4s %04x %30s " % (value_tell, group, elem, VR, length, value[:30])
                yield tag, (VR, length, value, fp_tell(), is_little_endian)
            else:
                # find length_of_undefined_length and read it
                if VR == "SQ":
                    seq = read_sequence(fp, is_implicit_VR, is_little_endian, length)
                    yield tag, (VR, length, seq, value_tell, is_little_endian)
                else:        
                    if VR == "OB":
                        delimiter = SequenceDelimiterTag
                    else:
                        delimiter = ItemDelimiterTag
                    length = length_of_undefined_length(fp, is_little_endian,
                                                 delimiter)
                    absorb_delimiter_item(fp, is_little_endian, delimiter)
                    yield tag, (VR, length, fp_read(length), value_tell,
                                is_little_endian)
    else: # Explicit VR
        if is_little_endian:
            unpack_format = "<HH2s"
            long_length_format = "<2sL"
            short_length_format = "<H"
        else:
            unpack_format = ">HH2s"
            long_length_format = ">2sL"
            short_length_format = ">H"
        while True:
            bytes = fp_read(6)
            if len(bytes) == 0:
                raise StopIteration # at end of file
            group, elem, VR = unpack(unpack_format, bytes)
            value_tell = fp_tell()
            tag = (group, elem)
            if VR in ('OB','OW','SQ','UN', 'UT'):
                reserved, length = unpack(long_length_format, fp_read(6)) 
            else:
                length = unpack(short_length_format, fp_read(2))[0]
            if stop_when is not None: # could move to its own case too
                if stop_when(tag, VR, length):
                    raise StopIteration
            if length != 0xFFFFFFFFL:
                # print "(%04x, %04x): %r %r" % (group, elem, VR, length)
                yield tag, (VR, length, fp_read(length), value_tell,
                            is_little_endian)
            else:
                # find length_of_undefined_length and read it
                if VR == "SQ":
                    seq = read_sequence(fp, is_implicit_VR, is_little_endian, length)
                    yield tag, (VR, length, seq, value_tell, is_little_endian)
                else: 
                    if VR == "OB":
                        delimiter = SequenceDelimiterTag
                    else:
                        delimiter = ItemDelimiterTag
                    length = length_of_undefined_length(fp, is_little_endian,
                                                 delimiter)
                    absorb_delimiter_item(fp, is_little_endian, delimiter)
                    yield tag, (VR, length, fp_read(length), value_tell,
                                is_little_endian)

            
def read_dataset(fp, is_implicit_VR, is_little_endian, bytelength=None, stop_when=None):
    """Return a dictionary containing raw data elements of the form:
    tag -> (VR, length, value, value_tell)
    where length is original length (could be "undefined length")
    and value_tell is the file position where the value bytes start.
    """
    raw_data_elements = dict()
    fpStart = fp.tell()

    try:
        for tag, raw_data in data_element_generator(fp, is_implicit_VR, is_little_endian, stop_when):
            if (bytelength is not None) and (fp.tell()-fpStart >= bytelength):
                
                break
            # Read data elements. Stop on certain errors, but return what was already read     
            if tag == (0xFFFE, 0xE00D): #ItemDelimiterTag --dataset is an item in a sequence
                break
            raw_data_elements[TupleTag(tag)] = raw_data   
            
    except EOFError, details:
        logger.error(str(details) + " in file " + 
                    getattr(fp, "name", "<no filename>")) # XXX is this visible enough to user code?
    except NotImplementedError, details:
        logger.error(details)           
 
    return Dataset(raw_data_elements)

def read_sequence(fp, is_implicit_VR, is_little_endian, bytelength):
    """Read and return a Sequence -- i.e. a list of Datasets"""
    seq = [] # use builtin list to start for speed, convert to Sequence at end
    isUndefinedLength = False
    if bytelength != 0:  # Sequence of length 0 is possible (PS 3.5-2008 7.5.1a (p.40)        
        if bytelength == 0xffffffffL:
            isUndefinedLength = True
            bytelength = None
        fp_tell = fp.tell # for speed in loop
        fpStart = fp_tell()
        while (not bytelength) or (fp_tell()-fpStart < bytelength):
            dataset = read_sequence_item(fp, is_implicit_VR, is_little_endian)
            if dataset is None:  # None is returned if get to Sequence Delimiter
                break
            seq.append(dataset)
    seq = Sequence(seq)
    seq.isUndefinedLength = isUndefinedLength
    return seq

# Add sequence reader here to avoid circular import of dicom.readers
readers['SQ'] = read_sequence

def read_sequence_item(fp, is_implicit_VR, is_little_endian):
    """Read and return a single sequence item, i.e. a Dataset"""
    if is_little_endian:
        tag_length_struct = Struct("<HHL")
    else:
        tag_length_struct = Struct(">HHL")
    group, element, length = tag_length_struct.unpack(fp.read(8))

    tag = (group, element)
    if tag == SequenceDelimiterTag: # No more items, time to stop reading
        data_element = DataElement(tag, None, None, fp.tell()-4)
        logger.debug("%04x: %s", fp.tell()-4, str(data_element))
        if length != 0:
            logger.warning("Expected 0x00000000 after delimiter, found 0x%x, at position 0x%x", length, fp.tell()-4)
        return None
    if tag != ItemTag:
        logger.warning("Expected sequence item with tag %s at file position 0x%x", (ItemTag, fp.tell()-4))
    else:
        logger.debug("%04x: Found Item tag (start of item)", fp.tell()-4)
    isUndefinedLength = False
    if length == 0xFFFFFFFFL:
        isUndefinedLength = True
        length = None # length_of_undefined_length(fp, ItemDelimiterTag)
    ds = read_dataset(fp, is_implicit_VR, is_little_endian, length)
    # XXX need this back in somewhere -- ds.isUndefinedLengthSequenceItem = isUndefinedLength
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
    preamble = read_preamble(fp)
    return _read_file_meta_info(fp)
    
def read_preamble(fp):
    """Read and return the DICOM preamble and read past the 'DICM' marker. 
    If 'DICM' does not exist, assume no preamble, return None, and 
    rewind file to the beginning..
    """
    logger.debug("Reading preamble")
    preamble = fp.read(0x80)
    magic = fp.read(4)
    if magic != "DICM":
        logger.info("File is not a standard DICOM file; 'DICM' header is missing. Assuming no header and continuing")
        preamble = None
        fp.seek(0)
    return preamble

def _at_pixel_data(tag, VR, length):
    return tag == (0x7fe0, 0x0010)

def read_partial(fileobj, stop_when=None):
    """Parse a DICOM file until a condition is met; return partial dataset
    fileobj -- a file-like object. This function does not close it.
    stop_when -- a function which takes tag, VR, length, and returns True or False.
        A True value means read_data_element will raise StopIteration.
        if None, then the whole file is read.
    """
    preamble = read_preamble(fileobj)
    file_meta_dataset = {}
    # Assume a transfer syntax, correct it as necessary
    is_implicit_VR = True
    is_little_endian = True
    if preamble:
        file_meta_dataset = _read_file_meta_info(fileobj)
        transfer_syntax = file_meta_dataset[(0x0002, 0x0010)] # XXX should make this work with named attribute .TransferSyntaxUID
        if transfer_syntax == dicom.UID.ExplicitVRLittleEndian:
            is_implicit_VR = False
        elif transfer_syntax == dicom.UID.ExplicitVRBigEndian:
            is_implicit_VR = False
            is_little_endian = False
        elif transfer_syntax == dicom.UID.DeflatedExplicitVRLittleEndian:
            # See PS3.6-2008 A.5 (p 71) -- when written, the entire dataset following 
            #     the file metadata was prepared the normal way, then "deflate" compression applied.
            #  All that is needed here is to decompress and then use as normal in a file-like object
            zipped = fp.read()            
            # -MAX_WBITS part is from comp.lang.python answer:  http://groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
            unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
            fp = DicomStringIO(unzipped) # a file-like object that usual code can use as normal
            self.fp = fp #point to new object
            is_implicit_VR = False
        else:
            # Any other syntax should be Explicit VR Little Endian,
            #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE by Standard PS 3.5-2008 A.4 (p63)
            is_implicit_VR = False
    else: # no header -- use the little_endian, implicit assumptions
        transfer_syntax = dicom.UID.ImplicitVRLittleEndian
         
    try:
        dataset = read_dataset(fileobj, is_implicit_VR, is_little_endian, stop_when)
    except EOFError, e:
        pass  # error already logged in read_dataset
    return FileDataset(dataset, file_meta_dataset, is_implicit_VR,
                        is_little_endian)

def read_file(fp, defer_size=None, stop_before_pixels=False):
    """Return a Dataset containing the contents of the Dicom file
    
    fp -- either a file-like object, or a string containing the file name.
    defer_size -- if a data element value is larger than defer_size,
        then the value is not read into memory until it is accessed in code.
        Specify an integer (bytes), or a string value with units: e.g. "512 KB", "2 MB".
        Default None means all elements read into memory.
    stop_before_pixels -- Set False to stop before reading pixels (and anything after them).
                   If False, a partial dataset will be returned.
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
        dataset = read_partial(fp, stop_when)
    finally: 
        if not caller_owns_file:
            fp.close()
    # XXX need to store transfer syntax etc.
    return dataset
            
ReadFile = read_file    # For backwards compatibility pydicom version <=0.9.2
readfile = read_file    # forgive a missing underscore

if __name__ == "__main__":
    ds = read_file("testfiles/CT_small.dcm")