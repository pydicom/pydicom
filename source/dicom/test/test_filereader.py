# test_filereader.py
"""unittest tests for dicom.filereader module"""
# Copyright (c) 2010 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import sys
import os
import os.path
import unittest
from cStringIO import StringIO

import shutil
# os.stat is only available on Unix and Windows   XXX Mac?
# Not sure if on other platforms the import fails, or the call to it??
stat_available = True
try:
    from os import stat
except:
    stat_available = False

have_numpy = True
try:
    import numpy
except:
    have_numpy = False
from dicom.filereader import read_file, data_element_generator, InvalidDicomError
from dicom.values import convert_value
from dicom.tag import Tag
from dicom.sequence import Sequence

from warncheck import assertWarns

from pkg_resources import Requirement, resource_filename
test_dir = resource_filename(Requirement.parse("pydicom"),"dicom/testfiles")

rtplan_name = os.path.join(test_dir, "rtplan.dcm")
rtdose_name = os.path.join(test_dir, "rtdose.dcm")
ct_name     = os.path.join(test_dir, "CT_small.dcm")
mr_name     = os.path.join(test_dir, "MR_small.dcm")
jpeg2000_name   = os.path.join(test_dir, "JPEG2000.dcm")
jpeg_lossy_name   = os.path.join(test_dir, "JPEG-lossy.dcm")
jpeg_lossless_name   = os.path.join(test_dir, "JPEG-LL.dcm")
deflate_name = os.path.join(test_dir, "image_dfl.dcm")
rtstruct_name = os.path.join(test_dir, "rtstruct.dcm")
priv_SQ_name = os.path.join(test_dir, "priv_SQ.dcm")
no_meta_group_length = os.path.join(test_dir, "no_meta_group_length.dcm")

dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()

def isClose(a, b, epsilon=0.000001):
    """Compare within some tolerance, to avoid machine roundoff differences"""
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
        """Returns correct values for sample data elements in test CT file...."""
        ct = read_file(ct_name)
        self.assertEqual(ct.file_meta.ImplementationClassUID, '1.3.6.1.4.1.5962.2',
                "ImplementationClassUID not the expected value")
        self.assertEqual(ct.file_meta.ImplementationClassUID,
                        ct.file_meta[0x2, 0x12].value,
                "ImplementationClassUID does not match the value accessed by tag number")
        # (0020, 0032) Image Position (Patient)  [-158.13580300000001, -179.035797, -75.699996999999996]
        imagepos = ct.ImagePositionPatient
        self.assert_(isClose(imagepos, [-158.135803, -179.035797, -75.699997]),
                "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.Rows, 128, "Rows not 128")
        self.assertEqual(ct.Columns, 128, "Columns not 128")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 128*128*2, "Pixel data not expected length")
        
        # Also test private elements name can be resolved:
        expected = "[Duration of X-ray on]"
        got = ct[(0x0043,0x104e)].name
        msg = "Mismatch in private tag name, expected '%s', got '%s'"
        self.assertEqual(expected, got, msg % (expected, got))
        
        # Check that can read pixels - get last one in array
        if have_numpy:
            expected = 909
            got = ct.pixel_array[-1][-1]
            msg = "Did not get correct value for last pixel: expected %d, got %r" % (expected, got)
            self.assertEqual(expected, got, msg)
        else:
            print "**Numpy not available -- pixel array test skipped**"
    def testNoForce(self):
        """Raises exception if missing DICOM header and force==False..........."""
        self.assertRaises(InvalidDicomError, read_file, rtstruct_name)
        
    def testRTstruct(self):
        """Returns correct values for sample elements in test RTSTRUCT file...."""
        # RTSTRUCT test file has complex nested sequences -- see rtstruct.dump file
        # Also has no DICOM header ... so tests 'force' argument of read_file
        
        rtss = read_file(rtstruct_name, force=True)
        expected = '1.2.840.10008.1.2' # implVR little endian
        got = rtss.file_meta.TransferSyntaxUID
        msg = "Expected transfer syntax %r, got %r" % (expected, got)
        self.assertEqual(expected, got, msg)
        frame_of_ref = rtss.ReferencedFrameofReferences[0]
        study = frame_of_ref.RTReferencedStudies[0]
        uid = study.RTReferencedSeries[0].SeriesInstanceUID
        expected = "1.2.826.0.1.3680043.8.498.2010020400001.2.1.1"
        msg = "Expected Reference Series UID '%s', got '%s'" % (expected, uid)
        self.assertEqual(expected, uid, msg)
        
        got = rtss.ROIContours[0].Contours[2].ContourNumber
        expected = 3
        msg = "Expected Contour Number %d, got %r" % (expected, got)
        self.assertEqual(expected, got, msg)
        
        got = rtss.RTROIObservations[0].ROIPhysicalProperties[0].ROIPhysicalProperty
        expected = 'REL_ELEC_DENSITY'
        msg = "Expected Physical Property '%s', got %r" % (expected, got)
        self.assertEqual(expected, got, msg)
        
    def testMR(self):
        """Returns correct values for sample data elements in test MR file....."""
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
        ctpartial_tags = sorted(ctpartial.keys())
        ctfull = read_file(ct_name)
        ctfull_tags = sorted(ctfull.keys())
        msg = "Tag list of partial CT read (except pixel tag and padding) did not match full read"
        msg += "\nExpected: %r\nGot %r" % (ctfull_tags[:-2], ctpartial_tags)
        missing = [Tag(0x7fe0, 0x10), Tag(0xfffc, 0xfffc)]
        self.assertEqual(ctfull_tags, ctpartial_tags+missing, msg)
    def testPrivateSQ(self):
        """Can read private undefined length SQ without error...................."""
        # From issues 91, 97, 98. Bug introduced by fast reading, due to VR=None
        #    in raw data elements, then an undefined length private item VR is looked up,
        #    and there is no such tag, generating an exception
        
        # Simply read the file, in 0.9.5 this generated an exception
        priv_SQ = read_file(priv_SQ_name)
    def testNoMetaGroupLength(self):
        """Read file with no group length in file meta..........................."""
        # Issue 108 -- iView example file with no group length (0002,0002)
        # Originally crashed, now check no exception, but also check one item
        #     in file_meta, and second one in followinsg dataset
        ds = read_file(no_meta_group_length)
        got = ds.InstanceCreationDate
        expected = "20111130"
        self.assertEqual(got, expected, "Sample data element after file meta with no group length failed, expected '%s', got '%s'" % (expected, got))
        

class JPEG2000Tests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg2000_name)
    def testJPEG2000(self):
        """JPEG2000: Returns correct values for sample data elements............"""
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)] # XX also tests multiple-valued AT data element
        got = self.jpeg.FrameIncrementPointer
        self.assertEqual(got, expected, "JPEG2000 file, Frame Increment Pointer: expected %s, got %s" % (expected, got))

        got = self.jpeg.DerivationCodes[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG200 file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEG2000PixelArray(self):
        """JPEG2000: Fails gracefully when uncompressed data is asked for......."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)

class JPEGlossyTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg_lossy_name)
    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements.........."""
        got = self.jpeg.DerivationCodes[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG-lossy file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEGlossyPixelArray(self):
        """JPEG-lossy: Fails gracefully when uncompressed data is asked for....."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)

class JPEGlosslessTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg_lossless_name)
    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements........"""
        got = self.jpeg.SourceImages[0].PurposeofReferenceCodes[0].CodeMeaning
        expected = 'Uncompressed predecessor'
        self.assertEqual(got, expected, "JPEG-lossless file, Code Meaning got %s, expected %s" % (got, expected))
    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data is asked for..."""
        self.assertRaises(NotImplementedError, self.jpeg._getPixelArray)

        # create an in-memory fragment
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
            def read_value():
                data_elem = ds.PixelData
            assertWarns(self, warning_start, read_value)
    def testFileExists(self):
        """Deferred read raises error if file no longer exists....."""
        ds = read_file(self.testfile_name, defer_size=2000)
        os.remove(self.testfile_name)
        def read_value():
            data_elem = ds.PixelData
        self.assertRaises(IOError, read_value)
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

class FileLikeTests(unittest.TestCase):
    """Test that can read DICOM files with file-like object rather than filename"""
    def testReadFileGivenFileObject(self):
        """filereader: can read using already opened file............"""
        f = open(ct_name, 'rb')
        ct = read_file(f)
        # Tests here simply repeat testCT -- perhaps should collapse the code together?

        self.assertEqual(ct.file_meta.ImplementationClassUID, '1.3.6.1.4.1.5962.2',
                "ImplementationClassUID not the expected value")
        self.assertEqual(ct.file_meta.ImplementationClassUID,
                        ct.file_meta[0x2, 0x12].value,
                "ImplementationClassUID does not match the value accessed by tag number")
        # (0020, 0032) Image Position (Patient)  [-158.13580300000001, -179.035797, -75.699996999999996]
        imagepos = ct.ImagePositionPatient
        self.assert_(isClose(imagepos, [-158.135803, -179.035797, -75.699997]),
                "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.Rows, 128, "Rows not 128")
        self.assertEqual(ct.Columns, 128, "Columns not 128")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 128*128*2, "Pixel data not expected length")
        # Should also be able to close the file ourselves without exception raised:
        f.close()
    def testReadFileGivenFileLikeObject(self):
        """filereader: can read using a file-like (StringIO) file...."""
        file_like = StringIO(open(ct_name, 'rb').read())
        ct = read_file(file_like)
        # Tests here simply repeat some of testCT test
        imagepos = ct.ImagePositionPatient
        self.assert_(isClose(imagepos, [-158.135803, -179.035797, -75.699997]),
                "ImagePosition(Patient) values not as expected")
        self.assertEqual(len(ct.PixelData), 128*128*2, "Pixel data not expected length")
        # Should also be able to close the file ourselves without exception raised:
        file_like.close()

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
