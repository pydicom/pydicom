# test_filereader.py
"""unittest tests for dicom.filereader module"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import sys
import os
import os.path
import unittest

import shutil
# os.stat is only available on Unix and Windows
# Not sure if on other platforms the import fails, or the call to it??
stat_available = True
try:
    from os import stat
except:
    stat_available = False
from dicom.filereader import read_file, DicomStringIO, data_element_generator
from dicom.tag import Tag
from dicom.sequence import Sequence

from warncheck import assertWarns

rtplan_name = "rtplan.dcm"
rtdose_name = "rtdose.dcm"
ct_name     = "CT_small.dcm"
mr_name     = "MR_small.dcm"
jpeg2000_name   = "JPEG2000.dcm"
jpeg_lossy_name   = "JPEG-lossy.dcm"
jpeg_lossless_name   = "JPEG-LL.dcm"
deflate_name = "image_dfl.dcm"
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()

def isClose(a, b, epsilon=0.000001): # compare within some tolerance, to avoid machine roundoff differences
    try:
        a.append  # see if is a list
    except: # (is not)
        return abs(a-b) < epsilon
    else:
        if len(a) != len(b): 
            return False
        for ai, bi in zip(a, b):
            if abs(ai-bi) > epsilon: 
                return False
        return True

class ReaderTests(unittest.TestCase):
    def testRTPlan(self):
        """Returns correct values for sample data elements in test RT Plan file"""
        plan = read_file(rtplan_name)
        beam = plan.Beams[0]
        cp0, cp1 = beam.ControlPoints # if not two controlpoints, then this would raise exception
        
        self.assertEqual(beam.TreatmentMachineName, "unit001", "Incorrect unit name")
        self.assertEqual(beam.TreatmentMachineName, beam[0x300a, 0x00b2].value,
                "beam TreatmentMachineName does not match the value accessed by tag number")
        
        cumDoseRef = cp1.ReferencedDoseReferences[0].CumulativeDoseReferenceCoefficient
        self.assert_(isClose(cumDoseRef, 0.9990268),
                "Cum Dose Ref Coeff not the expected value (CP1, Ref'd Dose Ref")
        JawX = cp0.BLDPositions[0].LeafJawPositions
        self.assert_(isClose(JawX[0], -100.0) and isClose(JawX[1], 100.0),
                "X jaws not as expected (control point 0)")
    def testRTDose(self):
        """Returns correct values for sample data elements in test RT Dose file"""
        dose = read_file(rtdose_name)
        self.assertEqual(dose.FrameIncrementPointer, Tag((0x3004, 0x000c)),
                "Frame Increment Pointer not the expected value")
        self.assertEqual(dose.FrameIncrementPointer, dose[0x28, 9].value,
                "FrameIncrementPointer does not match the value accessed by tag number")
        
        # try a value that is nested the deepest (so deep I break it into two steps!)
        fract = dose.ReferencedRTPlans[0].ReferencedFractionGroups[0]
        beamnum = fract.ReferencedBeams[0].ReferencedBeamNumber
        self.assertEqual(beamnum, 1, "Beam number not the expected value")
    def testCT(self):
        """Returns correct values for sample data elements in test CT file"""
        ct = read_file(ct_name)
        self.assertEqual(ct.ImplementationClassUID, '1.3.6.1.4.1.5962.2',
                "ImplementationClassUID not the expected value")
        self.assertEqual(ct.ImplementationClassUID, ct[0x2, 0x12].value,
                "ImplementationClassUID does not match the value accessed by tag number")
        # (0020, 0032) Image Position (Patient)  [-158.13580300000001, -179.035797, -75.699996999999996]
        imagepos = ct.ImagePositionPatient
        self.assert_(isClose(imagepos, [-158.135803, -179.035797, -75.699997]),
                "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.Rows, 128, "Rows not 128")
        self.assertEqual(ct.Columns, 128, "Columns not 128")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 128*128*2, "Pixel data not expected length")
    def testMR(self):
        """Returns correct values for sample data elements in test MR file"""
        mr = read_file(mr_name)
        # (0010, 0010) Patient's Name           'CompressedSamples^MR1'
        self.assertEqual(mr.PatientsName, 'CompressedSamples^MR1', "Wrong patient name")
        self.assertEqual(mr.PatientsName, mr[0x10,0x10].value,
                "Name does not match value found when accessed by tag number")
        self.assert_(isClose(mr.PixelSpacing, [0.3125, 0.3125]), "Wrong pixel spacing")
    def testDeflate(self):
        """Returns correct values for sample data elements in test compressed (zlib deflate) file"""
        # Everything after group 2 is compressed. If we can read anything else, the decompression must have been ok.
        ds = read_file(deflate_name)
        got = ds.ConversionType
        expected = "WSD"
        self.assertEqual(got, expected, "Attempted to read deflated file data element Conversion Type, expected '%s', got '%s'" % (expected, got))
    def testNoPixelsRead(self):
        """Returns all data elements before pixels using stop_before_pixels=False"""
        # Just check the tags, and a couple of values
        ctpartial = read_file(ct_name, stop_before_pixels=True)
        ctpartial_tags = ctpartial.keys()
        ctpartial_tags.sort()
        ctfull = read_file(ct_name)
        ctfull_tags = ctfull.keys()
        ctfull_tags.sort()
        msg = "Tag list of partial CT read (except pixel tag and padding) did not match full read"
        missing = [Tag(0x7fe0, 0x10), Tag(0xfffc, 0xfffc)]
        self.assertEqual(ctfull_tags, ctpartial_tags+missing, msg)


class JPEG2000Tests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg2000_name)
    def testJPEG2000(self):
        """JPEG2000: Returns correct values for sample data elements..........."""
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)] # XX also tests multiple-valued AT data element
        got = self.jpeg.FrameIncrementPointer
        self.assertEqual(got, expected, "JPEG2000 file, Frame Increment Pointer: expected %s, got %s" % (expected, got))

        got = self.jpeg.DerivationCodes[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG200 file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEG2000PixelArray(self):
        """JPEG2000: Fails gracefully when uncompressed data is asked for..."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)
    
class JPEGlossyTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg_lossy_name)
    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements........."""
        got = self.jpeg.DerivationCodes[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG-lossy file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEGlossyPixelArray(self):
        """JPEG-lossy: Fails gracefully when uncompressed data is asked for."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)
        
class JPEGlosslessTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg_lossless_name)
    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements..........."""
        got = self.jpeg.SourceImages[0].PurposeofReferenceCodes[0].CodeMeaning
        expected = 'Uncompressed predecessor'
        self.assertEqual(got, expected, "JPEG-lossless file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data is asked for..."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)        

class SequenceTests(unittest.TestCase):
    def testEmptyItem(self):
        """Read sequence with a single empty item................................"""
        # This is fix for issue 27
        bytes = "\x08\x00\x32\x10\x08\x00\x00\x00\xfe\xff\x00\xe0\x00\x00\x00\x00" # from issue 27, procedure code sequence (0008,1032)
        bytes += "\x08\x00\x3e\x10\x0c\x00\x00\x00\x52\x20\x41\x44\x44\x20\x56\x49\x45\x57\x53\x20" # data element following
        # create an in-memory fragment of a DICOM
        fp = DicomStringIO(bytes) 
        fp.isLittleEndian = True
        fp.isImplicitVR = True
        gen = data_element_generator(fp, is_implicit_VR=True, is_little_endian=True)
        data_element = gen.next()
        seq = data_element.value
        self.assert_(isinstance(seq, Sequence) and len(seq[0])==0, "Expected Sequence with single empty item, got item %s" % repr(seq[0]))
        elem2 = gen.next()
        self.assertEqual(elem2.tag, 0x0008103e, "Expected a data element after empty sequence item")

class DeferredReadTests(unittest.TestCase):
    """Test that deferred data element reading (for large size)
    works as expected
    """
    # Copy one of test files and use temporarily, then later remove.
    def setUp(self):
        self.testfile_name = ct_name + ".tmp"
        shutil.copyfile(ct_name, self.testfile_name)
    def testTimeCheck(self):
        """Deferred read warns if file has been modified..........."""
        if stat_available:
            ds = read_file(self.testfile_name, defer_size=2000)
            from time import sleep
            sleep(1)
            open(self.testfile_name, "r+").write('\0') # "touch" the file
            warning_start = "Deferred read warning -- file modification time "
            data_elem = ds.data_element('PixelData')
            assertWarns(self, warning_start, data_elem.read_value)
    def testFileExists(self):
        """Deferred read raises error if file no longer exists....."""
        ds = read_file(self.testfile_name, defer_size=2000)
        os.remove(self.testfile_name)
        data_elem = ds.data_element('PixelData')
        self.assertRaises(IOError, data_elem.read_value)
    def testValuesIdentical(self):
        """Deferred values exactly matches normal read..............."""
        ds_norm = read_file(self.testfile_name)
        ds_defer = read_file(self.testfile_name, defer_size=2000)
        for data_elem in ds_norm:
            tag = data_elem.tag
            self.assertEqual(data_elem.value, ds_defer[tag].value, "Mismatched value for tag %r" % tag)
        
    def tearDown(self):
        if os.path.exists(self.testfile_name):
            os.remove(self.testfile_name)
        
        
if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are, then need to switch there
    dir_name = os.path.dirname(sys.argv[0])
    save_dir = os.getcwd()
    if dir_name:
        os.chdir(dir_name)
    os.chdir("../testfiles")
    unittest.main()
    os.chdir(save_dir)
