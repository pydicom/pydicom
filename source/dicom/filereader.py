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
from dicom.datadict import dictionaryVR
from dicom.dataset import Dataset
from dicom.dataelem import DataElement, DeferredDataElement
from dicom.tag import Tag, ItemTag, ItemDelimiterTag, SequenceDelimiterTag
from dicom.sequence import Sequence
from dicom.readers import readers, read_VR
from dicom.misc import size_in_bytes

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
    def __init__(self, fp):
        """Read the preambleand meta info, prepare iterator for remainder
        
        fp -- an open DicomFileLike object, at start of file
        
        Adds flags to fp: Big/Little-endian and Implicit/Explicit VR
        """
        self.fp = fp
        fp.preamble = preamble = read_preamble(fp)
        fp.has_header = has_header = (preamble is not None)
        if has_header:
            self.FileMetaInfo = FileMetaInfo = _read_file_meta_info(fp)    
            TransferSyntax = FileMetaInfo.TransferSyntaxUID
            if TransferSyntax == dicom.UID.ExplicitVRLittleEndian:
                fp.isExplicitVR = True
            elif TransferSyntax == dicom.UID.ImplicitVRLittleEndian:
                fp.isImplicitVR = True
            elif TransferSyntax == dicom.UID.ExplicitVRBigEndian:
                fp.isExplicitVR = True
                fp.isBigEndian = True
            elif TransferSyntax == dicom.UID.DeflatedExplicitVRLittleEndian:
                # See PS3.6-2008 A.5 (p 71) -- when written, the entire dataset following 
                #     the file metadata was prepared the normal way, then "deflate" compression applied.
                #  All that is needed here is to decompress and then use as normal in a file-like object
                zipped = fp.read()            
                # -MAX_WBITS part is from comp.lang.python answer:  http://groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
                unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
                fp = DicomStringIO(unzipped) # a file-like object that usual code can use as normal
                self.fp = fp #point to new object
                fp.isExplicitVR = True
                fp.isLittleEndian = True
            else:
                # Any other syntax should be Explicit VR Little Endian,
                #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE by Standard PS 3.5-2008 A.4 (p63)
                fp.isExplicitVR = True
                fp.isLittleEndian = True
        else: # no header -- make assumptions
            fp.TransferSyntaxUID = dicom.UID.ImplicitVRLittleEndian
            fp.isLittleEndian = True
            fp.isImplicitVR = True
    
        logger.debug("Using %s VR, %s Endian transfer syntax" %(("Explicit", "Implicit")[fp.isImplicitVR], ("Big", "Little")[fp.isLittleEndian]))

    def __iter__(self):
        tags = self.FileMetaInfo.keys()
        tags.sort()
        for tag in tags:
            yield self.FileMetaInfo[tag]
        
        data_element = True
        while data_element:
            data_element = read_data_element(self.fp)
            if data_element:
                yield data_element

def read_data_element(fp, length=None):
    """Read and return the next data element"""
    data_element_tell = fp.tell()

    try:
        tag = fp.read_tag()
    except EOFError: # sometimes don't know are done until read next data element and at end-of-file
        return None  # don't re-raise the error. Should be okay
    
    if tag==ItemDelimiterTag or tag==SequenceDelimiterTag:
        length = fp.read_UL()
        if length != 0:
            logger.warning("Expected 0x00000000 after delimiter, found 0x%x, at position 0x%x", length, fp.tell()-4)
        data_element = DataElement(tag, None, None, data_element_tell)
        logger.debug("%04x: %s", data_element_tell, str(data_element))
        return data_element
        
    # Get the value representation VR
    if fp.isImplicitVR:
        try:
            VR = dictionaryVR(tag)
        except KeyError:
            if tag.is_private:
                VR = 'OB'  # just read the bytes, no way to know what they mean
            elif tag.element == 0:  # group length tag implied in versions < 3.0
                VR = 'UL'
            else:
                raise KeyError, "Unknown DICOM tag %s - can't look up VR" % str(tag)
    else:
        VR = read_VR(fp)

    if VR not in readers:
        raise NotImplementedError, "Unknown Value Representation '%s' in tag %s" % (VR, tag)

    # Get the length field of the data element
    if fp.isExplicitVR:
        if VR in ['OB','OW','SQ','UN', 'UT']:
            reserved = fp.read(2)
            length = fp.read_UL()
        else:
            length = fp.read_US()
    else: # Implicit VR
        length = fp.read_UL()

    isUndefinedLength = (length == 0xFFFFFFFFL)
    value_tell = fp.tell() # store file location and size
    length_original = length
    
    # For debugging only, log info about a sequence element
    if VR == "SQ":
        temp_data_element = DataElement(tag,VR, Sequence(), data_element_tell)
        logger.debug("%04x: %s", data_element_tell, temp_data_element)
        logger.debug("                         -------> SQ is using %s", ["explicit length", "Undefined Length"][isUndefinedLength])

    # Look up a reader function which will get the data element value
    # Dispatch two cases: a plain reader, or a number one which needs a format string
    # Readers are defined in dictionary 'readers'  in readers.py
    if isinstance(readers[VR], tuple):
        reader, num_format = readers[VR]
    else:
        reader = readers[VR]
        num_format = None

    # Call the reader, or delay reading until later if has been requested
    if fp.defer_size is not None and length > fp.defer_size and VR != "SQ":
        file_mtime = None
        if stat_available:
            file_mtime = stat(fp.name).st_mtime
        logger.debug("Deferring read for data element %s" % str(tag))
        
        # Read to start of next data item
        if isUndefinedLength:
            length = length_of_undefined_length(fp, SequenceDelimiterTag, rewind=False)
        else:
            fp.seek(length, SEEK_CUR)
        
        # Create the deferred data element
        data_element = DeferredDataElement(tag, VR, fp, file_mtime, data_element_tell, length)
    else:
        value = reader(fp, length, num_format)
        data_element = DataElement(tag, VR, value, value_tell)

    data_element.isUndefinedLength = isUndefinedLength # store this to write back data element in same way was read
    if data_element.VR != "SQ":
        logger.debug("%04x: %s", data_element_tell, str(data_element))
    return data_element

def read_dataset(fp, bytelength=None):
    """Return a Dataset dictionary containing DataElements starting from
    the current file position through the following bytelength bytes
    The dictionary key is the Dicom (group, element) tag, and the dictionary
    value is the DataElement class instance
    """
    ds = Dataset()
    fpStart = fp.tell()
    while (bytelength is None) or (fp.tell()-fpStart < bytelength):
        # Read data elements. Stop on certain errors, but return what was already read
        try:
            data_element = read_data_element(fp)
        except EOFError, details:
            logger.error(str(details) + " in file " + fp.name) # XXX is this visible enough to user code?
            break
        except NotImplementedError, details:
            logger.error(details)
            break
        
        if data_element is None: # None if end-of-file
            break        
        if data_element.tag == ItemDelimiterTag: # dataset is an item in a sequence
            break
        ds.Add(data_element)
    
    return ds

def read_sequence(fp, bytelength, format=None):
    """Read and return a Sequence -- i.e. a list of Datasets"""
    seq = Sequence()
    if bytelength == 0:  # Sequence of length 0 is possible (PS 3.5-2008 7.5.1a (p.40)
        return seq
    seq.isUndefinedLength = False
    if bytelength == 0xffffffffL:
        seq.isUndefinedLength = True
        bytelength = None
    fpStart = fp.tell()            
    while (not bytelength) or (fp.tell()-fpStart < bytelength):
        dataset = read_sequence_item(fp)
        if dataset is None:  # None is returned if get to Sequence Delimiter
            break
        seq.append(dataset)
    return seq

# Add sequence reader here to avoid circular import of dicom.readers
readers['SQ'] = read_sequence

def read_sequence_item(fp):
    """Read and return a single sequence item, i.e. a Dataset"""
    tag = fp.read_tag()
    if tag == SequenceDelimiterTag: # No more items, time to stop reading
        data_element = DataElement(tag, None, None, fp.tell()-4)
        logger.debug("%04x: %s", fp.tell()-4, str(data_element))
        length = fp.read_UL()
        if length != 0:
            logger.warning("Expected 0x00000000 after delimiter, found 0x%x, at position 0x%x", length, fp.tell()-4)
        return None
    if tag != ItemTag:
        logger.warning("Expected sequence item with tag %s at file position 0x%x", (ItemTag, fp.tell()-4))
    else:
        logger.debug("%04x: Found Item tag (start of item)", fp.tell()-4)
    length = fp.read_UL()
    isUndefinedLength = False
    if length == 0xFFFFFFFFL:
        isUndefinedLength = True
        length = None # length_of_undefined_length(fp, ItemDelimiterTag)
    ds = read_dataset(fp, length)
    ds.isUndefinedLengthSequenceItem = isUndefinedLength
    return ds
    
def _read_file_meta_info(fp):
    """Return the file meta information.
    fp must be set after the 128 byte preamble and 'DICM' marker
    """
    # File meta info is always LittleEndian, Explicit VR. After will change these
    #    to the transfer syntax values set in the meta info
    fp.isLittleEndian = True
    fp.isImplicitVR = False

    GroupLength = read_data_element(fp)
    return read_dataset(fp, GroupLength.value)

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
    
def read_file(fp, defer_size=None):
    """Return a Dataset containing the contents of the Dicom file
    
    fp -- either a file-like object, or a string containing the file name.
    defer_size -- if a data element value is larger than defer_size,
        then the value is not read into memory until it is accessed in code.
        Specify an integer (bytes), or a string value with units: e.g. "512 KB", "2 MB".
        Default None means all elements read into memory.
    
    """
    # Open file if not already a file object
    caller_owns_file = True
    if isinstance(fp, basestring):
        # caller provided a file name; we own the file handle
        caller_owns_file = False
        logger.debug("Reading file '%s'" % fp)
        fp = DicomFile(fp, 'rb')
    elif not isinstance(fp, DicomIO):
        # convert a "normal" file into DicomFileLike, so handle big/little endian, tag reading, etc
        if fp.mode[-1] != 'b':
            raise IOError, "File mode must be opened in binary mode"
        fp = DicomFileLike(fp)
    
    try:
        # Convert size to defer reading into bytes, and store in file object
        if defer_size is not None:
            defer_size = size_in_bytes(defer_size)
        fp.defer_size = defer_size
            
        # Iterate through all items and store them all --includes file meta info if present
        try:
            ds = Dataset()
            for data_element in DicomIter(fp):
                ds.Add(data_element)
        except EOFError, e:
            pass  # error already logged in read_dataset
    finally: 
        if not caller_owns_file:
            fp.close()
    
    # Store file info (Big/Little Endian, Expl/Impl VR; preamble) into dataset
    #    so can be used to rewrite same way if desired
    ds.preamble = fp.preamble
    ds.has_header = fp.has_header

    if not ds.has_header:
        ds.TransferSyntaxUID = fp.TransferSyntaxUID # need to store this for PixelArray checks
    ds.isLittleEndian = fp.isLittleEndian
    ds.isExplicitVR = fp.isExplicitVR

    return ds
        
ReadFile = read_file    # For backwards compatibility pydicom version <=0.9.2
readfile = read_file    # forgive a missing underscore
