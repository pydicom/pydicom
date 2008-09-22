# filereader.py
"""Read a dicom media file"""
#
# Copyright 2004, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details 

from struct import unpack, calcsize
# Need zlib and cStringIO for deflate-compressed file
import zlib
from StringIO import StringIO

from UIDs import UID_dictionary, DeflatedExplicitVRLittleEndian, ExplicitVRLittleEndian, ImplicitVRLittleEndian
from dicom.filebase import DicomFile, DicomStringIO
from dicom.datadict import dictionaryVR
from dicom.dataset import Dataset
from dicom.attribute import Attribute
from dicom.tag import Tag
from dicom.sequence import Sequence

# Use Boolean values if Python version has them, else make our own
try:
    True
except:
    False = 0; True = not False

class MultiValue(list):
    """MutliValue is a special list, derived to overwrite the __str__ method
    to display the multi-value list more nicely. Used for Dicom values of
    multiplicity > 1, i.e. strings with the "\" delimiter inside.
    """
    def __str__(self):
        lines = [str(x) for x in self]
        return "[" + ", ".join(lines) + "]"
    __repr__ = __str__
    
def read_VR(fp):
    """Return the two character Value Representation string"""
    return unpack("2s", fp.read(2))[0]

def read_numbers(fp, length, format):
    """Read a "value" of type format from the dicom file. "Value" can be more than one number"""
    endianChar = '><'[fp.isLittleEndian]
    bytes_per_value = calcsize(format)
    data = fp.read(length)

    format_string = "%c%u%c" % (endianChar, length/bytes_per_value, format) 
    value = unpack(format_string, data)
    if len(value) == 1:
        return value[0]
    else:        
        return list(value)  # convert from tuple to a list so can modify if need to

def read_OBvalue(fp, length):
    return fp.read(length)

def read_OWvalue(fp, length):
    # NO!:  """Return an "Other word" attribute as a tuple of short integers,
    #         with the proper byte swapping done"""

    # XXX for now just return the raw bytes and let the caller decide what to do with them
    return fp.read(length)

def read_UI(fp, length):
    value = fp.read(length)
    # Strip off 0-byte padding for even length (if there)
    if value and value[-1] == '\0':
        value = value[:-1]
    return MultiString(value)

def MultiString(val):
    """Split a string by delimiters if there are any"""
    # Remove trailing blank used to pad to even length
    # 2005.05.25: also check for trailing 0, error made in PET files we are converting
    if val and (val[-1] == ' ' or val[-1] == '\x00'):
        val = val[:-1]

    splitup = val.split("\\")
    if len(splitup) == 1:
        return splitup[0]
    else:
        return MultiValue(splitup)

def read_String(fp, length):
    return MultiString(fp.read(length))

def read_SingleString(fp, length):
    """Read a single string; the backslash used to separate values in multi-strings
    has no meaning here"""
    val = fp.read(length)
    if val and val[-1]==' ':
        val = val[:-1]
    return val

def ReadAttribute(fp, length=None):
    try:
        tag = fp.read_tag()
    except EOFError:
        return None

    # 2006.10.20 DM: if find SQ delimiter tag, ignore it. Kludge to handle XiO dicom files
    if tag==Tag((0xfffe, 0xe00d)) or tag==Tag((0xfffe, 0xe000)) or tag==Tag((0xfffe, 0xe0dd)):
        fp.seek(fp.tell()-4)
        AbsorbDelimiterItem(fp, tag)
        return ReadAttribute(fp, length)
    
    # Get the value representation VR
    if fp.isImplicitVR:
        try:
            VR = dictionaryVR(tag)
        except KeyError:
            if tag.isPrivate:
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

    value_tell = fp.tell() # store file location and size, for programs like anonymizers
    length_original = length
    try:
        readers[VR][0] # if reader is a tuple, then need to pass a number format
    except TypeError:
        value = readers[VR](fp, length) # call the function to read that kind of item
    else:
        value = readers[VR][0](fp, length, readers[VR][1])
    #  print Attribute(tag, VR, value)
    if tag == 0x00280103: # This flags whether pixel values are US (val=0) or SS (val = 1)
        fp.isSSpixelRep = value # XXX This is not used anywhere else in code?
    attr = Attribute(tag, VR, value, value_tell)
    # print attr    # Use for debugging file reading errors
    return attr

def ReadDataset(fp, bytelength=None):
    """Return a Dataset dictionary containing Attributes starting from
    the current file position through the following bytelength bytes
    The dictionary key is the Dicom (group, element) tag, and the dictionary
    value is the Attribute class instance
    """
    ds = Dataset()
    fpStart = fp.tell()
    while (bytelength is None) or (fp.tell() - fpStart < bytelength):  
        attribute = ReadAttribute(fp)
        if not attribute:
           break        # a is None if end-of-file
        # print attribute # XXX
        ds.Add(attribute)
    # XXX should test that fp.tell() exactly number of bytes expected?
    return ds


def ReadSequence(fp, length):
    """Return a Sequence list of Datasets"""
    seq = Sequence()
    isUndefinedLength = 0
    if length == 0xffffffffL:
        isUndefinedLength = 1
        length = LengthOfUndefinedLength(fp, 0xfffee0dd)
        # raise NotImplementedError, "This code does not handle delimited sequences yet"
    fpStart = fp.tell()            
    while fp.tell() - fpStart < length:
        seq.append(ReadSequenceItem(fp))
    if isUndefinedLength:
        AbsorbDelimiterItem(fp, Tag(0xfffee0dd))
    return seq

def ReadSequenceItem(fp):
    tag = fp.read_tag()
    assert tag == (0xfffe, 0xe000), "Expected sequence item with tag (FFFE, E000)"
    length = fp.read_UL()
    isUndefinedLength = 0
    if length == 0xFFFFFFFFL:
        isUndefinedLength = 1
        length = LengthOfUndefinedLength(fp, 0xfffee00d)
        # raise NotImplementedError, "This code does not handle Undefined Length sequence items"
    ds = ReadDataset(fp, length)
    if isUndefinedLength:
        AbsorbDelimiterItem(fp, Tag(0xfffee00d))
    return ds

def AbsorbDelimiterItem(fp, delimiter):
    """Used to read (and ignore) undefined length sequence or item terminators."""
    tag = fp.read_tag()
    # added 2006.10.20 DM: problem with XiO plan file not having SQ delimiters
    # Catch the missing delimiter exception and ignore the missing delimiter
    try:
        assert tag == delimiter, "Did not find expected delimiter %x, found %s" % (delimiter, str(tag))
        length = fp.read_UL() # 4 bytes for 'length', all 0's
    except AssertionError, e: 
        fp.seek(fp.tell()-4)

def LengthOfUndefinedLength(fp, delimiter):
    """Search through the file to find the delimiter, return the length of the data
    element value that the dicom file writer was too lazy to figure out for us.
    Return the file to the start of the data, ready to read it.
    Note the data element that the delimiter starts is not read here, the calling
    routine must handle that.
    delimiter must be 4 bytes long"""
    chunk = 0
    data_start = fp.tell()
    while chunk != delimiter:
        chunk = fp.read_tag()
        fp.seek(fp.tell()-3) # move only one byte forward
    length = fp.tell() - data_start - 4  # subtract off the last 4 we just read
    fp.seek(data_start)
    return length

def ReadDelimiterItem(fp, delimiter):
    found = fp.read(4)
    assert found==delimiter, "Expected delimitor %s, got %s" % (Tag(delimiter), Tag(found))
    length = fp.read_UL()
    assert length==0, "Expected delimiter item to have length 0, got %d" % length
    
def read_UN(fp, length):
    """Return a byte string for an Attribute of value 'UN' (unknown)"""
    if length == 0xFFFFFFFFL:
        raise NotImplementedError, "This code has not been tested for 'UN' with unknown length"
        delimiter = 0xFFFEE00DL
        length = LengthOfUndefinedLength(fp, delimiter)
        data_value = fp.read(length)
        ReadDelimiterItem(fp, delimiter)
        return data_value
    else:
        return fp.read(length)

def read_ATvalue(fp, length):
    """Return a attribute tag as the value of the current Dicom attribute being read"""
    assert length == 4, "Expected length 4 for Dicom attribute of value representation 'AT', got %d" % length
    return fp.read_tag()

def _ReadFileMetaInfo(fp):
    """Return the file meta information.
    fp must be set after the 128 byte preamble"""
    magic = fp.read(4)
    if magic != "DICM":
        raise IOError, 'File does not appear to be a Dicom file; "DICM" is missing. Try ReadFile with has_header=False'

    # File meta info is always LittleEndian, Explicit VR. After will change these
    #    to the transfer syntax values set in the meta info
    fp.isLittleEndian = True
    fp.isImplicitVR = False

    GroupLength = ReadAttribute(fp)
    return ReadDataset(fp, GroupLength.value)

def ReadFileMetaInfo(filename):
    """Just get the basic file meta information. Useful for going through
    a series of files to find one which is referenced to a particular SOP."""
    fp = DicomFile(filename, 'rb')
    preamble = fp.read(0x80)
    return _ReadFileMetaInfo(fp)

def ReadImageFile(fp):
    raise NotImplementedError

def ReadFile(fp, has_header=True):
    """Return a Dataset containing the contents of the Dicom file
    
    fp is either a DicomFile object, or a string containing the file name.
    
    has_header -- a non-compliant file might skip the 128-byte preamble and 
    group 2 information. Set this False to not try to read these."""

    if type(fp) is type(""):
        fp = DicomFile(fp,'rb')
    if has_header:
        preamble = fp.read(0x80)
        FileMetaInfo = _ReadFileMetaInfo(fp)
    
        TransferSyntax = FileMetaInfo.TransferSyntaxUID
        if TransferSyntax == ExplicitVRLittleEndian:
            fp.isExplicitVR = True
        elif TransferSyntax == ImplicitVRLittleEndian:
            fp.isImplicitVR = True
        elif TransferSyntax == DeflatedExplicitVRLittleEndian:
            # See PS3.6-2008 A.5 (p 71) -- when written, the entire dataset following 
            #     the file metadata was prepared the normal way, then "deflate" compression applied.
            #  All that is needed here is to decompress and then use as normal in a file-like object
            zipped = fp.read()            
            # -MAX_WBITS part is from comp.lang.python answer:  http://groups.google.com/group/comp.lang.python/msg/e95b3b38a71e6799
            unzipped = zlib.decompress(zipped, -zlib.MAX_WBITS)
            fp = DicomStringIO(unzipped) # a file-like object that usual code can use as normal
            fp.isExplicitVR = True
            fp.isLittleEndian = True
        else:
            raise NotImplementedError, "This code can only read Explicit or Implicit VR Little Endian transfer syntax, found %s" % ("'" + FileMetaInfo.TransferSyntaxUID + "'")
    else: # no header -- make assumptions
        fp.isLittleEndian = True
        fp.isImplicitVR = True
        
    # Return the rest of the file, including what we have already read
    ds = ReadDataset(fp)
    if has_header:
        ds.update(FileMetaInfo) # put in tags from FileMetaInfo
        # Find the names added to the FileMetaInfo Dataset instance...
        #   XXX is this still necessary now that Dataset has its own update() method?
        metaNamedMembers = [x for x in dir(FileMetaInfo) if x not in dir(Dataset)]
        # ...and put them into the Dataset instance we will return:
        for namedMember in metaNamedMembers:
            ds.__dict__[namedMember] = FileMetaInfo.__dict__[namedMember]
    ds.isLittleEndian = fp.isLittleEndian
    ds.isExplicitVR = fp.isExplicitVR
    if has_header:
        ds.preamble = preamble  # save so can write same preamble if re-write file
    fp.close()
    return ds
        
# readers map a VR to the function to read the value(s)
# for read_numbers, the reader maps to a tuple (function, number format (struct module style))
readers = {'UL':(read_numbers,'L'), 'SL':(read_numbers,'l'),
           'US':(read_numbers,'H'), 'SS':(read_numbers, 'h'),
           'FL':(read_numbers,'f'), 'FD':(read_numbers, 'd'),
           'OF':(read_numbers,'f'),
           'OB':read_OBvalue, 'UI':read_UI,
           'SH':read_String,  'DA':read_String, 'TM': read_String,
           'CS':read_String,  'PN':read_String, 'LO': read_String,
           'IS':read_String,  'DS':read_String, 'AE': read_String,
           'AS':read_String,
           'LT':read_SingleString,
           'SQ':ReadSequence,
           'UN':read_UN,
           'AT':read_ATvalue,
           'ST':read_String,
           'OW':read_OWvalue,
           'OW/OB':read_OBvalue,# note OW/OB depends on other items, which we don't know at read time
           'OB/OW':read_OBvalue,
           'US or SS':read_OWvalue,
           'US or SS or OW':read_OWvalue,
           'US\US or SS\US':read_OWvalue,
           'DT':read_String,
           'UT':read_SingleString,          
           } 


#def RemoveAttribute(filename, attribute, datasetList):
#    """taglist specifies all the tags (sequences) leading to the item to remove (last in the list).
#    The attribute will be removed and length fields of 'parent' items adjusted.
#    The file must be small enough to completely read into memory.
#    This does NOT handle removing a dataset from a sequence."""
#    ds = ReadFile(filename)  # read in all attribute tree
#    attributes = []
#    lastds = ds
#    for tag in taglist:
#        attr = lastds[tag]
#        attributes.append(attr)
#        lastds = attr.value  # must be a SQ
    
if __name__ == "__main__":
    import sys, os.path
    here = os.path.dirname(sys.argv[0])
    filename = os.path.join(here, "test", "plan.dcm")
    ds = ReadFile(filename)
    print
    print "Transfer Syntax..:",
    tUID = ds.TransferSyntaxUID
    if tUID==ExplicitVRLittleEndian:
        print "Explicit VR Little Endian"
    elif tUID==ImplicitVRLittleEndian:
        print "Implicit VR Little Endian"
    else:
        print "Transfer syntax not known to this present program"

    print "Modality:", ds.Modality
    print "Patient's name, id: '%s', '%s'" % (ds.PatientsName, ds.PatientsID)
    print "Patient's Birth Date:", ds.PatientsBirthDate
    print "RT Plan Label:", ds.RTPlanLabel
    print "Number of beams:", len(ds.Beams)
    beam=ds.Beams[0]
    print "First beam number: %d, name: '%s'" % (beam.BeamNumber, beam.BeamName)
    print "Collimator angle of that beam:", beam.ControlPoints[0].BLDAngle