# test_filereader.py
"""unittest tests for dicom.filereader module"""
# Copyright (c) 2010-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import sys
import os
import os.path
import unittest
from io import BytesIO

import shutil
# os.stat is only available on Unix and Windows   XXX Mac?
# Not sure if on other platforms the import fails, or the call to it??
stat_available = True
try:
    from os import stat  # NOQA
except:
    stat_available = False

have_numpy = True
try:
    import numpy  # NOQA
except:
    have_numpy = False
from dicom.filereader import read_file
from dicom.errors import InvalidDicomError
from dicom.tag import Tag, TupleTag
import dicom.valuerep
import gzip

from dicom.test.warncheck import assertWarns

from pkg_resources import Requirement, resource_filename
test_dir = resource_filename(Requirement.parse("pydicom"), "dicom/testfiles")

rtplan_name = os.path.join(test_dir, "rtplan.dcm")
rtdose_name = os.path.join(test_dir, "rtdose.dcm")
ct_name = os.path.join(test_dir, "CT_small.dcm")
mr_name = os.path.join(test_dir, "MR_small.dcm")
jpeg2000_name = os.path.join(test_dir, "JPEG2000.dcm")
jpeg_lossy_name = os.path.join(test_dir, "JPEG-lossy.dcm")
jpeg_lossless_name = os.path.join(test_dir, "JPEG-LL.dcm")
deflate_name = os.path.join(test_dir, "image_dfl.dcm")
rtstruct_name = os.path.join(test_dir, "rtstruct.dcm")
priv_SQ_name = os.path.join(test_dir, "priv_SQ.dcm")
nested_priv_SQ_name = os.path.join(test_dir, "nested_priv_SQ.dcm")
no_meta_group_length = os.path.join(test_dir, "no_meta_group_length.dcm")
gzip_name = os.path.join(test_dir, "zipMR.gz")

dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


def isClose(a, b, epsilon=0.000001):
    """Compare within some tolerance, to avoid machine roundoff differences"""
    try:
        a.append  # see if is a list
    except:  # (is not)
        return abs(a - b) < epsilon
    else:
        if len(a) != len(b):
            return False
        for ai, bi in zip(a, b):
            if abs(ai - bi) > epsilon:
                return False
        return True


class ReaderTests(unittest.TestCase):
    def testRTPlan(self):
        """Returns correct values for sample data elements in test RT Plan file"""
        plan = read_file(rtplan_name)
        beam = plan.BeamSequence[0]
        cp0, cp1 = beam.ControlPointSequence  # if not two controlpoints, then this would raise exception

        self.assertEqual(beam.TreatmentMachineName, "unit001", "Incorrect unit name")
        self.assertEqual(beam.TreatmentMachineName, beam[0x300a, 0x00b2].value,
                         "beam TreatmentMachineName does not match the value accessed by tag number")

        got = cp1.ReferencedDoseReferenceSequence[0].CumulativeDoseReferenceCoefficient
        DS = dicom.valuerep.DS
        expected = DS('0.9990268')
        self.assertTrue(got == expected,
                        "Cum Dose Ref Coeff not the expected value (CP1, Ref'd Dose Ref")
        got = cp0.BeamLimitingDevicePositionSequence[0].LeafJawPositions
        self.assertTrue(got[0] == DS('-100') and got[1] == DS('100.0'),
                        "X jaws not as expected (control point 0)")

    def testRTDose(self):
        """Returns correct values for sample data elements in test RT Dose file"""
        dose = read_file(rtdose_name)
        self.assertEqual(dose.FrameIncrementPointer, Tag((0x3004, 0x000c)),
                         "Frame Increment Pointer not the expected value")
        self.assertEqual(dose.FrameIncrementPointer, dose[0x28, 9].value,
                         "FrameIncrementPointer does not match the value accessed by tag number")

        # try a value that is nested the deepest (so deep I break it into two steps!)
        fract = dose.ReferencedRTPlanSequence[0].ReferencedFractionGroupSequence[0]
        beamnum = fract.ReferencedBeamSequence[0].ReferencedBeamNumber
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
        got = ct.ImagePositionPatient
        DS = dicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        self.assertTrue(got == expected, "ImagePosition(Patient) values not as expected."
                        "got {0}, expected {1}".format(got, expected))

        self.assertEqual(ct.Rows, 128, "Rows not 128")
        self.assertEqual(ct.Columns, 128, "Columns not 128")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 128 * 128 * 2, "Pixel data not expected length")

        # Also test private elements name can be resolved:
        expected = "[Duration of X-ray on]"
        got = ct[(0x0043, 0x104e)].name
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
        expected = '1.2.840.10008.1.2'  # implVR little endian
        got = rtss.file_meta.TransferSyntaxUID
        msg = "Expected transfer syntax %r, got %r" % (expected, got)
        self.assertEqual(expected, got, msg)
        frame_of_ref = rtss.ReferencedFrameOfReferenceSequence[0]
        study = frame_of_ref.RTReferencedStudySequence[0]
        uid = study.RTReferencedSeriesSequence[0].SeriesInstanceUID
        expected = "1.2.826.0.1.3680043.8.498.2010020400001.2.1.1"
        msg = "Expected Reference Series UID '%s', got '%s'" % (expected, uid)
        self.assertEqual(expected, uid, msg)

        got = rtss.ROIContourSequence[0].ContourSequence[2].ContourNumber
        expected = 3
        msg = "Expected Contour Number %d, got %r" % (expected, got)
        self.assertEqual(expected, got, msg)

        obs_seq0 = rtss.RTROIObservationsSequence[0]
        got = obs_seq0.ROIPhysicalPropertiesSequence[0].ROIPhysicalProperty
        expected = 'REL_ELEC_DENSITY'
        msg = "Expected Physical Property '%s', got %r" % (expected, got)
        self.assertEqual(expected, got, msg)

    def testDir(self):
        """Returns correct dir attributes for both Dataset and DICOM names (python >= 2.6).."""
        # Only python >= 2.6 calls __dir__ for dir() call
        rtss = read_file(rtstruct_name, force=True)
        # sample some expected 'dir' values
        got_dir = dir(rtss)
        expect_in_dir = ['pixel_array', 'add_new', 'ROIContourSequence',
                         'StructureSetDate', '__sizeof__']
        expect_not_in_dir = ['RemovePrivateTags', 'AddNew', 'GroupDataset']  # remove in v1.0
        for name in expect_in_dir:
            self.assertTrue(name in got_dir, "Expected name '%s' in dir()" % name)
        for name in expect_not_in_dir:
            self.assertTrue(name not in got_dir, "Unexpected name '%s' in dir()" % name)
        # Now check for some items in dir() of a nested item
        roi0 = rtss.ROIContourSequence[0]
        got_dir = dir(roi0)
        expect_in_dir = ['pixel_array', 'add_new', 'ReferencedROINumber',
                         'ROIDisplayColor', '__sizeof__']
        for name in expect_in_dir:
            self.assertTrue(name in got_dir, "Expected name '%s' in dir()" % name)

    def testMR(self):
        """Returns correct values for sample data elements in test MR file....."""
        mr = read_file(mr_name)
        # (0010, 0010) Patient's Name           'CompressedSamples^MR1'
        mr.decode()
        self.assertEqual(mr.PatientName, 'CompressedSamples^MR1', "Wrong patient name")
        self.assertEqual(mr.PatientName, mr[0x10, 0x10].value,
                         "Name does not match value found when accessed by tag number")
        got = mr.PixelSpacing
        DS = dicom.valuerep.DS
        expected = [DS('0.3125'), DS('0.3125')]
        self.assertTrue(got == expected, "Wrong pixel spacing")

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
        self.assertEqual(ctfull_tags, ctpartial_tags + missing, msg)

    def testPrivateSQ(self):
        """Can read private undefined length SQ without error...................."""
        # From issues 91, 97, 98. Bug introduced by fast reading, due to VR=None
        #    in raw data elements, then an undefined length private item VR is looked up,
        #    and there is no such tag, generating an exception

        # Simply read the file, in 0.9.5 this generated an exception
        read_file(priv_SQ_name)

    def testNestedPrivateSQ(self):
        """Can successfully read a private SQ which contains additional SQ's....."""
        # From issue 113. When a private SQ of undefined length is used, the
        #   sequence is read in and the length of the SQ is determined upon
        #   identification of the SQ termination sequence. When using nested
        #   Sequences, the first termination sequence encountered actually
        #   belongs to the nested Sequence not the parent, therefore the
        #   remainder of the file is not read in properly
        ds = read_file(nested_priv_SQ_name)

        # Make sure that the entire dataset was read in
        pixel_data_tag = TupleTag((0x7fe0, 0x10))
        self.assertTrue(pixel_data_tag in ds,
                        "Entire dataset was not parsed properly. PixelData is not present")

        # Check that the DataElement is indeed a Sequence
        tag = TupleTag((0x01, 0x01))
        seq0 = ds[tag]
        self.assertEqual(seq0.VR, 'SQ',
                         "First level sequence not parsed properly")

        # Now verify the presence of the nested private SQ
        seq1 = seq0[0][tag]
        self.assertEqual(seq1.VR, 'SQ',
                         "Second level sequence not parsed properly")

        # Now make sure the values that are parsed are correct
        got = seq1[0][tag].value
        expected = b'Double Nested SQ'
        self.assertEqual(got, expected,
                         "Expected a value of %s, got %s'" % (expected, got))

        got = seq0[0][0x01, 0x02].value
        expected = b'Nested SQ'
        self.assertEqual(got, expected,
                         "Expected a value of %s, got %s'" % (expected, got))

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
        expected = [Tag(0x0054, 0x0010), Tag(0x0054, 0x0020)]  # XX also tests multiple-valued AT data element
        got = self.jpeg.FrameIncrementPointer
        self.assertEqual(got, expected, "JPEG2000 file, Frame Increment Pointer: expected %s, got %s" % (expected, got))

        got = self.jpeg.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG200 file, Code Meaning got %s, expected %s" % (got, expected))

    def testJPEG2000PixelArray(self):
        """JPEG2000: Fails gracefully when uncompressed data is asked for......."""
        self.assertRaises(NotImplementedError, self.jpeg._get_pixel_array)


class JPEGlossyTests(unittest.TestCase):

    def setUp(self):
        self.jpeg = read_file(jpeg_lossy_name)

    def testJPEGlossy(self):
        """JPEG-lossy: Returns correct values for sample data elements.........."""
        got = self.jpeg.DerivationCodeSequence[0].CodeMeaning
        expected = 'Lossy Compression'
        self.assertEqual(got, expected, "JPEG-lossy file, Code Meaning got %s, expected %s" % (got, expected))

    def testJPEGlossyPixelArray(self):
        """JPEG-lossy: Fails gracefully when uncompressed data is asked for....."""
        self.assertRaises(NotImplementedError, self.jpeg._get_pixel_array)


class JPEGlosslessTests(unittest.TestCase):
    def setUp(self):
        self.jpeg = read_file(jpeg_lossless_name)

    def testJPEGlossless(self):
        """JPEGlossless: Returns correct values for sample data elements........"""
        got = self.jpeg.SourceImageSequence[0].PurposeOfReferenceCodeSequence[0].CodeMeaning
        expected = 'Uncompressed predecessor'
        self.assertEqual(got, expected, "JPEG-lossless file, Code Meaning got %s, expected %s" % (got, expected))

    def testJPEGlosslessPixelArray(self):
        """JPEGlossless: Fails gracefully when uncompressed data is asked for..."""
        self.assertRaises(NotImplementedError, self.jpeg._get_pixel_array)

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
            with open(self.testfile_name, "r+") as f:
                f.write('\0')  # "touch" the file
            warning_start = "Deferred read warning -- file modification time "

            def read_value():
                ds.PixelData

            assertWarns(self, warning_start, read_value)

    def testFileExists(self):
        """Deferred read raises error if file no longer exists....."""
        ds = read_file(self.testfile_name, defer_size=2000)
        os.remove(self.testfile_name)

        def read_value():
            ds.PixelData

        self.assertRaises(IOError, read_value)

    def testValuesIdentical(self):
        """Deferred values exactly matches normal read..............."""
        ds_norm = read_file(self.testfile_name)
        ds_defer = read_file(self.testfile_name, defer_size=2000)
        for data_elem in ds_norm:
            tag = data_elem.tag
            self.assertEqual(data_elem.value, ds_defer[tag].value, "Mismatched value for tag %r" % tag)

    def testZippedDeferred(self):
        """Deferred values from a gzipped file works.............."""
        # Arose from issue 103 "Error for defer_size read of gzip file object"
        fobj = gzip.open(gzip_name)
        ds = read_file(fobj, defer_size=1)
        fobj.close()
        # before the fix, this threw an error as file reading was not in right place,
        #    it was re-opened as a normal file, not zip file
        ds.InstanceNumber

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
        got = ct.ImagePositionPatient
        DS = dicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        self.assertTrue(got == expected, "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.file_meta.ImplementationClassUID, '1.3.6.1.4.1.5962.2',
                         "ImplementationClassUID not the expected value")
        self.assertEqual(ct.file_meta.ImplementationClassUID,
                         ct.file_meta[0x2, 0x12].value,
                         "ImplementationClassUID does not match the value accessed by tag number")
        # (0020, 0032) Image Position (Patient)  [-158.13580300000001, -179.035797, -75.699996999999996]
        got = ct.ImagePositionPatient
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        self.assertTrue(got == expected, "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.Rows, 128, "Rows not 128")
        self.assertEqual(ct.Columns, 128, "Columns not 128")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 128 * 128 * 2, "Pixel data not expected length")
        # Should also be able to close the file ourselves without exception raised:
        f.close()

    def testReadFileGivenFileLikeObject(self):
        """filereader: can read using a file-like (BytesIO) file...."""
        with open(ct_name, 'rb') as f:
            file_like = BytesIO(f.read())
        ct = read_file(file_like)
        # Tests here simply repeat some of testCT test
        got = ct.ImagePositionPatient
        DS = dicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        self.assertTrue(got == expected, "ImagePosition(Patient) values not as expected")
        self.assertEqual(len(ct.PixelData), 128 * 128 * 2, "Pixel data not expected length")
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
