# fileiter.py
"""Read a DICOM file one data element at a time"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import zlib
from StringIO import StringIO # tried cStringIO but wouldn't let me derive class from it.
import logging
logger = logging.getLogger('pydicom')

from dicom.UID import UID, UID_dictionary
from dicom.UID import DeflatedExplicitVRLittleEndian, ExplicitVRLittleEndian
from dicom.UID import ImplicitVRLittleEndian, ExplicitVRBigEndian
from dicom.filereader import read_data_element, _read_fileMetaInfo
from dicom.filebase import DicomFile, DicomStringIO

class DicomIter(object):
    """Parse a DICOM file one Data Element at a time
    Use like:
    from dicom.fileiter import DicomIter
    from dicom.dataset import Dataset
    ds = Dataset()
    for data_element in DicomIter:
        if meets_some_condition(data_element):
            ds.Add(data_element)
        if some_other_condition(data_element):
            break
    You can generalize this function to examine the elements as they come,
    or to only read to a certain point and then stop
    """
    def __init__(self, filename):
        """Open DICOM file filename and read the preamble, prepare to read
        the dataset"""
        self.fp = DicomFile(filename,'rb')
        logger.debug("Opening file '%s' and reading preamble" % self.fp)

        self.has_header = True
        self.fp.seek(0x80)
        magic = self.fp.read(4)
        if magic != "DICM":
            logger.info("File is not a standard DICOM file; 'DICM' header is missing. Assuming no header and continuing")
            self.has_header = False
        self.fp.seek(0)
    
        self.FileMetaInfo = dict()
        if self.has_header:
            logger.debug("Reading preamble")
            preamble = self.fp.read(0x80)
            self.FileMetaInfo = _read_fileMetaInfo(self.fp)
        
            TransferSyntax = self.FileMetaInfo.TransferSyntaxUID
            if TransferSyntax == ExplicitVRLittleEndian:
                self.fp.isExplicitVR = True
            elif TransferSyntax == ImplicitVRLittleEndian:
                self.fp.isImplicitVR = True
            elif TransferSyntax == ExplicitVRBigEndian:
                self.fp.isExplicitVR = True
                self.fp.isBigEndian = True
            elif TransferSyntax == DeflatedExplicitVRLittleEndian:
                # See PS3.6-2008 A.5 (p 71) -- when written, the entire dataset following 
                #     the file metadata was prepared the normal way, then "deflate" compression applied.
                #  All that is needed here is to decompress and then use as normal in a file-like object
                zipped = self.fp.read()            
                # -MAX_WBITS part is from comp.lang.python answer:  http://groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
                unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
                self.fp = DicomStringIO(unzipped) # a file-like object that usual code can use as normal
                self.fp.isExplicitVR = True
                self.fp.isLittleEndian = True
            else:
                # Any other syntax should be Explicit VR Little Endian,
                #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE by Standard PS 3.5-2008 A.4 (p63)
                self.fp.isExplicitVR = True
                self.fp.isLittleEndian = True
        else: # no header -- make assumptions
            self.fp.isLittleEndian = True
            self.fp.isImplicitVR = True
        
        logger.debug("Using %s VR, %s Endian transfer syntax" %(("Explicit", "Implicit")[self.fp.isImplicitVR], ("Big", "Little")[self.fp.isLittleEndian]))
        # Return the rest of the file, including what we have already read
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
 
if __name__ == "__main__":
    # EXAMPLE use of iterating through the file. Needs python2.5 for "all"
    #     or see http://docs.python.org/library/functions.html?highlight=all#all
    filename = r"c:\svnwork\pydicom\source\dicom\testfiles\CT_small.dcm"
    need_items = ["Patient's Name", "Patient ID", 
                  "Study Date", "Study Description"]
    have_items = dict([(name,False) for name in need_items])
    for data_elem in DicomIter(filename):
        if data_elem.description() in need_items:
            print "***", data_elem
            have_items[data_elem.description()] = True
            if all(have_items.values()):
                break # got everything we care about so stop reading
        else:
            print data_elem.tag
