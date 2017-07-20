# test_filereader.py
# -*- coding: utf-8 -*-
"""unittest tests for pydicom.filereader module"""
# Copyright (c) 2010-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom

import gzip
from io import BytesIO
import os
import os.path
import shutil
import sys
import tempfile
import unittest
from pydicom.util.testing.warncheck import assertWarns
from pydicom.dataset import Dataset, FileDataset
from pydicom.dataelem import DataElement
from pydicom.filereader import read_file
from pydicom.errors import InvalidDicomError
from pydicom.tag import Tag, TupleTag
from pydicom.uid import ImplicitVRLittleEndian
import pydicom.valuerep
import pydicom.config
try:
    unittest.skipUnless
except AttributeError:
    try:
        import unittest2 as unittest
    except ImportError:
        print("unittest2 is required for testing in python2.6")
have_gdcm_handler = True
try:
    import pydicom.pixel_data_handlers.gdcm_handler as gdcm_handler
except ImportError as e:
    have_gdcm_handler = False
# os.stat is only available on Unix and Windows   XXX Mac?
# Not sure if on other platforms the import fails, or the call to it??
try:
    from os import stat  # NOQA
except ImportError:
    stat = None

try:
    import numpy  # NOQA
except ImportError:
    numpy = None

try:
    import jpeg_ls
except ImportError:
    jpeg_ls = None

try:
    from PIL import Image as PILImg
except ImportError:
    # If that failed, try the alternate import syntax for PIL.
    try:
        import Image as PILImg
    except ImportError:
        # Neither worked, so it's likely not installed.
        PILImg = None

have_numpy = numpy is not None
have_jpeg_ls = jpeg_ls is not None
have_pillow = PILImg is not None

test_dir = os.path.dirname(__file__)
test_files = os.path.join(test_dir, 'test_files')

empty_number_tags_name = os.path.join(test_files,
                                      "reportsi_with_empty_number_tags.dcm")
rtplan_name = os.path.join(test_files, "rtplan.dcm")
rtdose_name = os.path.join(test_files, "rtdose.dcm")
ct_name = os.path.join(test_files, "CT_small.dcm")
mr_name = os.path.join(test_files, "MR_small.dcm")
truncated_mr_name = os.path.join(test_files, "MR_truncated.dcm")
jpeg2000_name = os.path.join(test_files, "JPEG2000.dcm")
jpeg2000_lossless_name = os.path.join(test_files, "MR_small_jp2klossless.dcm")
jpeg_ls_lossless_name = os.path.join(test_files,
                                     "MR_small_jpeg_ls_lossless.dcm")
jpeg_lossy_name = os.path.join(test_files, "JPEG-lossy.dcm")
jpeg_lossless_name = os.path.join(test_files, "JPEG-LL.dcm")
deflate_name = os.path.join(test_files, "image_dfl.dcm")
rtstruct_name = os.path.join(test_files, "rtstruct.dcm")
priv_SQ_name = os.path.join(test_files, "priv_SQ.dcm")
nested_priv_SQ_name = os.path.join(test_files, "nested_priv_SQ.dcm")
meta_missing_tsyntax_name = os.path.join(test_files,
                                         "meta_missing_tsyntax.dcm")
no_meta_group_length = os.path.join(test_files, "no_meta_group_length.dcm")
gzip_name = os.path.join(test_files, "zipMR.gz")
color_px_name = os.path.join(test_files, "color-px.dcm")
color_pl_name = os.path.join(test_files, "color-pl.dcm")
explicit_vr_le_no_meta = os.path.join(test_files, "ExplVR_LitEndNoMeta.dcm")
explicit_vr_be_no_meta = os.path.join(test_files, "ExplVR_BigEndNoMeta.dcm")
emri_name = os.path.join(test_files, "emri_small.dcm")
emri_big_endian_name = os.path.join(test_files, "emri_small_big_endian.dcm")
emri_jpeg_ls_lossless = os.path.join(test_files,
                                     "emri_small_jpeg_ls_lossless.dcm")
emri_jpeg_2k_lossless = os.path.join(test_files,
                                     "emri_small_jpeg_2k_lossless.dcm")
color_3d_jpeg_baseline = os.path.join(test_files, "color3d_jpeg_baseline.dcm")
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


def isClose(a, b, epsilon=0.000001):
    """Compare within some tolerance, to avoid machine roundoff differences"""
    try:
        a.append  # see if is a list
    except BaseException:  # (is not)
        return abs(a - b) < epsilon
    else:
        if len(a) != len(b):
            return False
        for ai, bi in zip(a, b):
            if abs(ai - bi) > epsilon:
                return False
        return True


class ReaderTests(unittest.TestCase):
    def testEmptyNumbersTag(self):
        """Tests that an empty tag with a number VR (FL, UL, SL, US,
        SS, FL, FD, OF) reads as an empty string"""
        empty_number_tags_ds = read_file(empty_number_tags_name)
        self.assertEqual(empty_number_tags_ds.ExaminedBodyThickness, '')
        self.assertEqual(empty_number_tags_ds.SimpleFrameList, '')
        self.assertEqual(empty_number_tags_ds.ReferencePixelX0, '')
        self.assertEqual(empty_number_tags_ds.PhysicalUnitsXDirection, '')
        self.assertEqual(empty_number_tags_ds.TagAngleSecondAxis, '')
        self.assertEqual(empty_number_tags_ds.TagSpacingSecondDimension, '')
        self.assertEqual(empty_number_tags_ds.VectorGridData, '')

    def testUTF8FileName(self):
        utf8_filename = os.path.join(tempfile.gettempdir(), "ДИКОМ.dcm")
        shutil.copyfile(rtdose_name, utf8_filename)
        ds = read_file(utf8_filename)
        os.remove(utf8_filename)
        self.assertTrue(ds is not None)

    def testRTPlan(self):
        """Returns correct values for sample data elements in test
        RT Plan file.
        """
        plan = read_file(rtplan_name)
        beam = plan.BeamSequence[0]
        # if not two controlpoints, then this would raise exception
        cp0, cp1 = beam.ControlPointSequence

        self.assertEqual(beam.TreatmentMachineName, "unit001",
                         "Incorrect unit name")
        self.assertEqual(beam.TreatmentMachineName, beam[0x300a, 0x00b2].value,
                         "beam TreatmentMachineName does not match "
                         "the value accessed by tag number")

        got = cp1.ReferencedDoseReferenceSequence[
            0].CumulativeDoseReferenceCoefficient
        DS = pydicom.valuerep.DS
        expected = DS('0.9990268')
        self.assertTrue(got == expected,
                        "Cum Dose Ref Coeff not the expected value "
                        "(CP1, Ref'd Dose Ref")
        got = cp0.BeamLimitingDevicePositionSequence[0].LeafJawPositions
        self.assertTrue(got[0] == DS('-100') and got[1] == DS('100.0'),
                        "X jaws not as expected (control point 0)")

    def testRTDose(self):
        """Returns correct values for sample data elements in test
        RT Dose file"""
        dose = read_file(rtdose_name)
        self.assertEqual(dose.FrameIncrementPointer, Tag((0x3004, 0x000c)),
                         "Frame Increment Pointer not the expected value")
        self.assertEqual(dose.FrameIncrementPointer, dose[0x28, 9].value,
                         "FrameIncrementPointer does not match the value "
                         "accessed by tag number")

        # try a value that is nested the deepest
        # (so deep I break it into two steps!)
        fract = \
            dose.ReferencedRTPlanSequence[0].ReferencedFractionGroupSequence[0]
        beamnum = fract.ReferencedBeamSequence[0].ReferencedBeamNumber
        self.assertEqual(beamnum, 1, "Beam number not the expected value")

    def testCT(self):
        """Returns correct values for sample data elements in test CT file."""
        ct = read_file(ct_name)
        self.assertEqual(ct.file_meta.ImplementationClassUID,
                         '1.3.6.1.4.1.5962.2',
                         "ImplementationClassUID not the expected value")
        self.assertEqual(ct.file_meta.ImplementationClassUID,
                         ct.file_meta[0x2, 0x12].value,
                         "ImplementationClassUID does not match the value "
                         "accessed by tag number")
        # (0020, 0032) Image Position (Patient)
        # [-158.13580300000001, -179.035797, -75.699996999999996]
        got = ct.ImagePositionPatient
        DS = pydicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        self.assertTrue(got == expected,
                        "ImagePosition(Patient) values not as expected."
                        "got {0}, expected {1}".format(got, expected))

        self.assertEqual(ct.Rows, 128, "Rows not 128")
        self.assertEqual(ct.Columns, 128, "Columns not 128")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 128 * 128 * 2,
                         "Pixel data not expected length")

        # Also test private elements name can be resolved:
        expected = "[Duration of X-ray on]"
        got = ct[(0x0043, 0x104e)].name
        msg = "Mismatch in private tag name, expected '%s', got '%s'"
        self.assertEqual(expected, got, msg % (expected, got))

    @unittest.skipUnless(have_numpy, "Numpy not installed")
    def testCTPixelData(self):
        """Check that we can read pixel data.
        Tests that we get last one in array.
        """
        ct = read_file(ct_name)
        expected = 909
        got = ct.pixel_array[-1][-1]
        msg = ("Did not get correct value for last pixel: "
               "expected %d, got %r" % (expected, got))
        self.assertEqual(expected, got, msg)

    def testNoForce(self):
        """Raises exception if missing DICOM header and force==False."""
        self.assertRaises(InvalidDicomError, read_file, rtstruct_name)

    def testRTstruct(self):
        """Returns correct values for sample elements in test RTSTRUCT file."""
        # RTSTRUCT test file has complex nested sequences
        # -- see rtstruct.dump file
        # Also has no DICOM header ... so tests 'force' argument of read_file

        rtss = read_file(rtstruct_name, force=True)
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
        """Returns correct dir attributes for both Dataset and DICOM names
        (python >= 2.6).."""
        # Only python >= 2.6 calls __dir__ for dir() call
        rtss = read_file(rtstruct_name, force=True)
        # sample some expected 'dir' values
        got_dir = dir(rtss)
        expect_in_dir = ['pixel_array', 'add_new', 'ROIContourSequence',
                         'StructureSetDate']
        for name in expect_in_dir:
            self.assertTrue(name in got_dir,
                            "Expected name '%s' in dir()" % name)

        # Now check for some items in dir() of a nested item
        roi0 = rtss.ROIContourSequence[0]
        got_dir = dir(roi0)
        expect_in_dir = ['pixel_array', 'add_new', 'ReferencedROINumber',
                         'ROIDisplayColor']
        for name in expect_in_dir:
            self.assertTrue(name in got_dir,
                            "Expected name '%s' in dir()" % name)

    def testMR(self):
        """Returns correct values for sample data elements in test MR file."""
        mr = read_file(mr_name)
        # (0010, 0010) Patient's Name           'CompressedSamples^MR1'
        mr.decode()
        self.assertEqual(mr.PatientName, 'CompressedSamples^MR1',
                         "Wrong patient name")
        self.assertEqual(mr.PatientName, mr[0x10, 0x10].value,
                         "Name does not match value found when "
                         "accessed by tag number")
        got = mr.PixelSpacing
        DS = pydicom.valuerep.DS
        expected = [DS('0.3125'), DS('0.3125')]
        self.assertTrue(got == expected, "Wrong pixel spacing")

    def testDeflate(self):
        """Returns correct values for sample data elements in test compressed
         (zlib deflate) file
         """
        # Everything after group 2 is compressed.
        # If we can read anything else, the decompression must have been ok.
        ds = read_file(deflate_name)
        got = ds.ConversionType
        expected = "WSD"
        self.assertEqual(got, expected,
                         "Attempted to read deflated file data element "
                         "Conversion Type, expected '%s', got '%s'" % (
                             expected, got))

    def testNoPixelsRead(self):
        """Returns all data elements before pixels using
        stop_before_pixels=False.
        """
        # Just check the tags, and a couple of values
        ctpartial = read_file(ct_name, stop_before_pixels=True)
        ctpartial_tags = sorted(ctpartial.keys())
        ctfull = read_file(ct_name)
        ctfull_tags = sorted(ctfull.keys())
        msg = ("Tag list of partial CT read (except pixel tag and padding) "
               "did not match full read")
        msg += "\nExpected: %r\nGot %r" % (ctfull_tags[:-2], ctpartial_tags)
        missing = [Tag(0x7fe0, 0x10), Tag(0xfffc, 0xfffc)]
        self.assertEqual(ctfull_tags, ctpartial_tags + missing, msg)

    def testPrivateSQ(self):
        """Can read private undefined length SQ without error."""
        # From issues 91, 97, 98. Bug introduced by fast reading, due to
        #    VR=None in raw data elements, then an undefined length private
        #    item VR is looked up, and there is no such tag,
        #    generating an exception

        # Simply read the file, in 0.9.5 this generated an exception
        read_file(priv_SQ_name)

    def testNestedPrivateSQ(self):
        """Can successfully read a private SQ which contains additional SQs."""
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
                        "Entire dataset was not parsed properly. "
                        "PixelData is not present")

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
        """Read file with no group length in file meta."""
        # Issue 108 -- iView example file with no group length (0002,0002)
        # Originally crashed, now check no exception, but also check one item
        #     in file_meta, and second one in followinsg dataset
        ds = read_file(no_meta_group_length)
        got = ds.InstanceCreationDate
        expected = "20111130"
        self.assertEqual(got, expected,
                         "Sample data element after file meta with no "
                         "group length failed, expected '%s', got '%s'" % (
                             expected, got))

    def testNoTransferSyntaxInMeta(self):
        """Read file with file_meta, but has no TransferSyntaxUID in it."""
        # From issue 258: if file has file_meta but no TransferSyntaxUID in it,
        #   should assume default transfer syntax
        ds = read_file(
            meta_missing_tsyntax_name)  # is dicom default transfer syntax

        # Repeat one test from nested private sequence test to maker sure
        #    file was read correctly
        pixel_data_tag = TupleTag((0x7fe0, 0x10))
        self.assertTrue(pixel_data_tag in ds,
                        "Failed to properly read a file with no "
                        "Transfer Syntax in file_meta")

    def testExplicitVRLittleEndianNoMeta(self):
        """Read file without file meta with Little Endian Explicit VR dataset.
        """
        # Example file from CMS XiO 5.0 and above
        # Still need to force read data since there is no 'DICM' marker present
        ds = read_file(explicit_vr_le_no_meta, force=True)
        got = ds.InstanceCreationDate
        expected = "20150529"
        self.assertEqual(got, expected,
                         "Sample data element from dataset failed, "
                         "expected '%s', got '%s'" % (expected, got))

    def testExplicitVRBigEndianNoMeta(self):
        """Read file without file meta with Big Endian Explicit VR dataset."""
        # Example file from CMS XiO 5.0 and above
        # Still need to force read data since there is no 'DICM' marker present
        ds = read_file(explicit_vr_be_no_meta, force=True)
        got = ds.InstanceCreationDate
        expected = "20150529"
        self.assertEqual(got, expected,
                         "Sample data element from dataset failed, "
                         "expected '%s', got '%s'" % (expected, got))

    def testPlanarConfig(self):
        px_data_ds = read_file(color_px_name)
        pl_data_ds = read_file(color_pl_name)
        assert px_data_ds.PlanarConfiguration != pl_data_ds.PlanarConfiguration
        if have_numpy:
            px_data = px_data_ds.pixel_array
            pl_data = pl_data_ds.pixel_array
            self.assertTrue(numpy.all(px_data == pl_data))

    def test_correct_ambiguous_vr(self):
        """Test correcting ambiguous VR elements read from file"""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.add(DataElement(0x00280108, 'US', 10))
        ds.add(DataElement(0x00280109, 'US', 500))

        fp = BytesIO()
        file_ds = FileDataset(fp, ds)
        file_ds.is_implicit_VR = True
        file_ds.is_little_endian = True
        file_ds.save_as(fp)

        ds = read_file(fp, force=True)
        self.assertEqual(ds[0x00280108].VR, 'US')
        self.assertEqual(ds.SmallestPixelValueInSeries, 10)

    def test_correct_ambiguous_vr_compressed(self):
        """Test correcting compressed Pixel Data read from file"""
        # Create an implicit VR compressed dataset
        ds = read_file(jpeg_lossless_name)
        fp = BytesIO()
        file_ds = FileDataset(fp, ds)
        file_ds.is_implicit_VR = True
        file_ds.is_little_endian = True
        file_ds.save_as(fp)

        ds = read_file(fp, force=True)
        self.assertEqual(ds[0x7fe00010].VR, 'OB')

    def test_long_specific_char_set(self):
        """Test that specific character set is read even if it is longer
         than defer_size"""
        ds = Dataset()

        long_specific_char_set_value = ['ISO 2022IR 100'] * 9
        ds.add(DataElement(0x00080005, 'CS', long_specific_char_set_value))

        fp = BytesIO()
        file_ds = FileDataset(fp, ds)
        file_ds.save_as(fp)

        ds = read_file(fp, defer_size=65, force=True)
        self.assertEqual(ds[0x00080005].value, long_specific_char_set_value)

    def test_no_preamble_file_meta_dataset(self):
        """Test correct read of group 2 elements with no preamble."""
        bytestream = (b'\x02\x00\x02\x00\x55\x49\x16\x00\x31\x2e\x32\x2e'
                      b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e'
                      b'\x31\x2e\x31\x2e\x39\x00\x02\x00\x10\x00\x55\x49'
                      b'\x12\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
                      b'\x30\x30\x38\x2e\x31\x2e\x32\x00\x20\x20\x10\x00'
                      b'\x02\x00\x00\x00\x01\x00\x20\x20\x20\x00\x06\x00'
                      b'\x00\x00\x4e\x4f\x52\x4d\x41\x4c')

        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertTrue('MediaStorageSOPClassUID' in ds.file_meta)
        self.assertEqual(ds.file_meta.TransferSyntaxUID,
                         ImplicitVRLittleEndian)
        self.assertEqual(ds.Polarity, 'NORMAL')
        self.assertEqual(ds.ImageBoxPosition, 1)

    def test_no_preamble_command_group_dataset(self):
        """Test correct read of group 0 and 2 elements with no preamble."""
        bytestream = (b'\x02\x00\x02\x00\x55\x49\x16\x00\x31\x2e\x32\x2e'
                      b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e'
                      b'\x31\x2e\x31\x2e\x39\x00\x02\x00\x10\x00\x55\x49'
                      b'\x12\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
                      b'\x30\x30\x38\x2e\x31\x2e\x32\x00'
                      b'\x20\x20\x10\x00\x02\x00\x00\x00\x01\x00\x20\x20'
                      b'\x20\x00\x06\x00\x00\x00\x4e\x4f\x52\x4d\x41\x4c'
                      b'\x00\x00\x10\x01\x02\x00\x00\x00\x03\x00')

        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertTrue('MediaStorageSOPClassUID' in ds.file_meta)
        self.assertEqual(ds.file_meta.TransferSyntaxUID,
                         ImplicitVRLittleEndian)
        self.assertEqual(ds.Polarity, 'NORMAL')
        self.assertEqual(ds.ImageBoxPosition, 1)
        self.assertEqual(ds.MessageID, 3)

    def test_group_length_wrong(self):
        """Test file is read correctly even if FileMetaInformationGroupLength
        is incorrect.
        """
        bytestream = (b'\x02\x00\x00\x00\x55\x4C\x04\x00\x0A\x00\x00\x00'
                      b'\x02\x00\x02\x00\x55\x49\x16\x00\x31\x2e\x32\x2e'
                      b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e'
                      b'\x31\x2e\x31\x2e\x39\x00\x02\x00\x10\x00\x55\x49'
                      b'\x12\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
                      b'\x30\x30\x38\x2e\x31\x2e\x32\x00'
                      b'\x20\x20\x10\x00\x02\x00\x00\x00\x01\x00\x20\x20'
                      b'\x20\x00\x06\x00\x00\x00\x4e\x4f\x52\x4d\x41\x4c')
        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertFalse(len(
            bytestream) - 12 == ds.file_meta.FileMetaInformationGroupLength)
        self.assertTrue(ds.file_meta.FileMetaInformationGroupLength == 10)
        self.assertTrue('MediaStorageSOPClassUID' in ds.file_meta)
        self.assertEqual(ds.file_meta.TransferSyntaxUID,
                         ImplicitVRLittleEndian)
        self.assertEqual(ds.Polarity, 'NORMAL')
        self.assertEqual(ds.ImageBoxPosition, 1)

    def test_preamble_command_meta_no_dataset(self):
        """Test reading only preamble, command and meta elements"""
        preamble = b'\x00' * 128
        prefix = b'DICM'
        command = (b'\x00\x00\x00\x00\x04\x00\x00\x00\x38'
                   b'\x00\x00\x00\x00\x00\x02\x00\x12\x00\x00'
                   b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31'
                   b'\x30\x30\x30\x38\x2e\x31\x2e\x31\x00\x00'
                   b'\x00\x00\x01\x02\x00\x00\x00\x30\x00\x00'
                   b'\x00\x10\x01\x02\x00\x00\x00\x07\x00\x00'
                   b'\x00\x00\x08\x02\x00\x00\x00\x01\x01')
        meta = (b'\x02\x00\x00\x00\x55\x4C\x04\x00\x0A\x00\x00\x00'
                b'\x02\x00\x02\x00\x55\x49\x16\x00\x31\x2e\x32\x2e'
                b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e'
                b'\x31\x2e\x31\x2e\x39\x00\x02\x00\x10\x00\x55\x49'
                b'\x12\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
                b'\x30\x30\x38\x2e\x31\x2e\x32\x00')

        bytestream = preamble + prefix + meta + command
        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertTrue('TransferSyntaxUID' in ds.file_meta)
        self.assertTrue('MessageID' in ds)

    def test_preamble_meta_no_dataset(self):
        """Test reading only preamble and meta elements"""
        preamble = b'\x00' * 128
        prefix = b'DICM'
        meta = (b'\x02\x00\x00\x00\x55\x4C\x04\x00\x0A\x00\x00\x00'
                b'\x02\x00\x02\x00\x55\x49\x16\x00\x31\x2e\x32\x2e'
                b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e'
                b'\x31\x2e\x31\x2e\x39\x00\x02\x00\x10\x00\x55\x49'
                b'\x12\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
                b'\x30\x30\x38\x2e\x31\x2e\x32\x00')

        bytestream = preamble + prefix + meta
        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertEqual(ds.preamble, b'\x00' * 128)
        self.assertTrue('TransferSyntaxUID' in ds.file_meta)
        self.assertEqual(ds[:], Dataset())

    def test_preamble_commandset_no_dataset(self):
        """Test reading only preamble and command set"""
        preamble = b'\x00' * 128
        prefix = b'DICM'
        command = (b'\x00\x00\x00\x00\x04\x00\x00\x00\x38'
                   b'\x00\x00\x00\x00\x00\x02\x00\x12\x00\x00'
                   b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31'
                   b'\x30\x30\x30\x38\x2e\x31\x2e\x31\x00\x00'
                   b'\x00\x00\x01\x02\x00\x00\x00\x30\x00\x00'
                   b'\x00\x10\x01\x02\x00\x00\x00\x07\x00\x00'
                   b'\x00\x00\x08\x02\x00\x00\x00\x01\x01')
        bytestream = preamble + prefix + command

        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertTrue('MessageID' in ds)
        self.assertEqual(ds.file_meta, Dataset())

    def test_meta_no_dataset(self):
        """Test reading only meta elements"""
        bytestream = (b'\x02\x00\x00\x00\x55\x4C\x04\x00\x0A\x00\x00\x00'
                      b'\x02\x00\x02\x00\x55\x49\x16\x00\x31\x2e\x32\x2e'
                      b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e'
                      b'\x31\x2e\x31\x2e\x39\x00\x02\x00\x10\x00\x55\x49'
                      b'\x12\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
                      b'\x30\x30\x38\x2e\x31\x2e\x32\x00')
        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertTrue('TransferSyntaxUID' in ds.file_meta)
        self.assertEqual(ds[:], Dataset())

    def test_commandset_no_dataset(self):
        """Test reading only command set elements"""
        bytestream = (b'\x00\x00\x00\x00\x04\x00\x00\x00\x38'
                      b'\x00\x00\x00\x00\x00\x02\x00\x12\x00\x00'
                      b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31'
                      b'\x30\x30\x30\x38\x2e\x31\x2e\x31\x00\x00'
                      b'\x00\x00\x01\x02\x00\x00\x00\x30\x00\x00'
                      b'\x00\x10\x01\x02\x00\x00\x00\x07\x00\x00'
                      b'\x00\x00\x08\x02\x00\x00\x00\x01\x01')
        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertTrue('MessageID' in ds)
        self.assertTrue(ds.preamble is None)
        self.assertEqual(ds.file_meta, Dataset())

    def test_no_dataset(self):
        """Test reading no elements or preamble produces empty Dataset"""
        bytestream = b''
        fp = BytesIO(bytestream)
        ds = read_file(fp, force=True)
        self.assertTrue(ds.preamble is None)
        self.assertEqual(ds.file_meta, Dataset())
        self.assertEqual(ds[:], Dataset())


class ReadDataElementTests(unittest.TestCase):
    def setUp(self):
        ds = Dataset()
        ds.DoubleFloatPixelData = (b'\x00\x01\x02\x03\x04\x05\x06\x07'
                                   b'\x01\x01\x02\x03\x04\x05\x06\x07')  # OD
        ds.SelectorOLValue = (b'\x00\x01\x02\x03\x04\x05\x06\x07'
                              b'\x01\x01\x02\x03')  # VR of OL
        ds.PotentialReasonsForProcedure = ['A', 'B',
                                           'C']  # VR of UC, odd length
        ds.StrainDescription = 'Test'  # Even length
        ds.URNCodeValue = 'http://test.com'  # VR of UR
        ds.RetrieveURL = 'ftp://test.com  '  # Test trailing spaces ignored
        ds.DestinationAE = '    TEST  12    '  # 16 characters max for AE

        self.fp = BytesIO()  # Implicit little
        file_ds = FileDataset(self.fp, ds)
        file_ds.is_implicit_VR = True
        file_ds.is_little_endian = True
        file_ds.save_as(self.fp)

        self.fp_ex = BytesIO()  # Explicit little
        file_ds = FileDataset(self.fp_ex, ds)
        file_ds.is_implicit_VR = False
        file_ds.is_little_endian = True
        file_ds.save_as(self.fp_ex)

    def test_read_OD_implicit_little(self):
        """Check creation of OD DataElement from byte data works correctly."""
        ds = read_file(self.fp, force=True)
        ref_elem = ds.get(0x7fe00009)
        elem = DataElement(0x7fe00009, 'OD',
                           b'\x00\x01\x02\x03\x04\x05\x06\x07'
                           b'\x01\x01\x02\x03\x04\x05\x06\x07')
        self.assertEqual(ref_elem, elem)

    def test_read_OD_explicit_little(self):
        """Check creation of OD DataElement from byte data works correctly."""
        ds = read_file(self.fp_ex, force=True)
        ref_elem = ds.get(0x7fe00009)
        elem = DataElement(0x7fe00009, 'OD',
                           b'\x00\x01\x02\x03\x04\x05\x06\x07'
                           b'\x01\x01\x02\x03\x04\x05\x06\x07')
        self.assertEqual(ref_elem, elem)

    def test_read_OL_implicit_little(self):
        """Check creation of OL DataElement from byte data works correctly."""
        ds = read_file(self.fp, force=True)
        ref_elem = ds.get(0x00720075)
        elem = DataElement(0x00720075, 'OL',
                           b'\x00\x01\x02\x03\x04\x05\x06\x07'
                           b'\x01\x01\x02\x03')
        self.assertEqual(ref_elem, elem)

    def test_read_OL_explicit_little(self):
        """Check creation of OL DataElement from byte data works correctly."""
        ds = read_file(self.fp_ex, force=True)
        ref_elem = ds.get(0x00720075)
        elem = DataElement(0x00720075, 'OL',
                           b'\x00\x01\x02\x03\x04\x05\x06\x07'
                           b'\x01\x01\x02\x03')
        self.assertEqual(ref_elem, elem)

    def test_read_UC_implicit_little(self):
        """Check creation of DataElement from byte data works correctly."""
        ds = read_file(self.fp, force=True)
        ref_elem = ds.get(0x00189908)
        elem = DataElement(0x00189908, 'UC', ['A', 'B', 'C'])
        self.assertEqual(ref_elem, elem)

        ds = read_file(self.fp, force=True)
        ref_elem = ds.get(0x00100212)
        elem = DataElement(0x00100212, 'UC', 'Test')
        self.assertEqual(ref_elem, elem)

    def test_read_UC_explicit_little(self):
        """Check creation of DataElement from byte data works correctly."""
        ds = read_file(self.fp_ex, force=True)
        ref_elem = ds.get(0x00189908)
        elem = DataElement(0x00189908, 'UC', ['A', 'B', 'C'])
        self.assertEqual(ref_elem, elem)

        ds = read_file(self.fp_ex, force=True)
        ref_elem = ds.get(0x00100212)
        elem = DataElement(0x00100212, 'UC', 'Test')
        self.assertEqual(ref_elem, elem)

    def test_read_UR_implicit_little(self):
        """Check creation of DataElement from byte data works correctly."""
        ds = read_file(self.fp, force=True)
        ref_elem = ds.get(0x00080120)  # URNCodeValue
        elem = DataElement(0x00080120, 'UR', 'http://test.com')
        self.assertEqual(ref_elem, elem)

        # Test trailing spaces ignored
        ref_elem = ds.get(0x00081190)  # RetrieveURL
        elem = DataElement(0x00081190, 'UR', 'ftp://test.com')
        self.assertEqual(ref_elem, elem)

    def test_read_UR_explicit_little(self):
        """Check creation of DataElement from byte data works correctly."""
        ds = read_file(self.fp_ex, force=True)
        ref_elem = ds.get(0x00080120)  # URNCodeValue
        elem = DataElement(0x00080120, 'UR', 'http://test.com')
        self.assertEqual(ref_elem, elem)

        # Test trailing spaces ignored
        ref_elem = ds.get(0x00081190)  # RetrieveURL
        elem = DataElement(0x00081190, 'UR', 'ftp://test.com')
        self.assertEqual(ref_elem, elem)

    def test_read_AE(self):
        """Check creation of AE DataElement from byte data works correctly."""
        ds = read_file(self.fp, force=True)
        self.assertEqual(ds.DestinationAE, 'TEST  12')


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
        if stat is not None:
            ds = read_file(self.testfile_name, defer_size='2 kB')
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
            self.assertEqual(data_elem.value, ds_defer[tag].value,
                             "Mismatched value for tag %r" % tag)

    def testZippedDeferred(self):
        """Deferred values from a gzipped file works.............."""
        # Arose from issue 103 "Error for defer_size read of gzip file object"
        fobj = gzip.open(gzip_name)
        ds = read_file(fobj, defer_size=1)
        fobj.close()
        # before the fix, this threw an error as file reading was not in
        # the right place, it was re-opened as a normal file, not a zip file
        ds.InstanceNumber

    def tearDown(self):
        if os.path.exists(self.testfile_name):
            os.remove(self.testfile_name)


class ReadTruncatedFileTests(unittest.TestCase):
    def testReadFileWithMissingPixelData(self):
        mr = read_file(truncated_mr_name)
        mr.decode()
        self.assertEqual(mr.PatientName, 'CompressedSamples^MR1',
                         "Wrong patient name")
        self.assertEqual(mr.PatientName, mr[0x10, 0x10].value,
                         "Name does not match value found when "
                         "accessed by tag number")
        got = mr.PixelSpacing
        DS = pydicom.valuerep.DS
        expected = [DS('0.3125'), DS('0.3125')]
        self.assertTrue(got == expected, "Wrong pixel spacing")

    @unittest.skipUnless(
        have_numpy and not have_gdcm_handler,
        "Numpy not installed or gdcm is installed, "
        "gdcm fixes truncated data??")
    def testReadFileWithMissingPixelDataArray(self):
        mr = read_file(truncated_mr_name)
        mr.decode()
        msg = r"(Amount of pixel data.*" \
            "does not match the expected data|" \
            "Unexpected end of file. Read.*bytes of.*expected|" \
            "'str' object has no attribute 'reshape'|" \
            "'bytes' object has no attribute 'reshape')"
        with self.assertRaisesRegexp(AttributeError, msg):
            mr.pixel_array


class FileLikeTests(unittest.TestCase):
    """Test that can read DICOM files with file-like object rather than
    filename
    """

    def testReadFileGivenFileObject(self):
        """filereader: can read using already opened file............"""
        f = open(ct_name, 'rb')
        ct = read_file(f)
        # Tests here simply repeat testCT -- perhaps should collapse
        # the code together?
        got = ct.ImagePositionPatient
        DS = pydicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        self.assertTrue(got == expected,
                        "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.file_meta.ImplementationClassUID,
                         '1.3.6.1.4.1.5962.2',
                         "ImplementationClassUID not the expected value")
        self.assertEqual(ct.file_meta.ImplementationClassUID,
                         ct.file_meta[0x2, 0x12].value,
                         "ImplementationClassUID does not match the "
                         "value accessed by tag number")
        # (0020, 0032) Image Position (Patient)
        # [-158.13580300000001, -179.035797, -75.699996999999996]
        got = ct.ImagePositionPatient
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        self.assertTrue(got == expected,
                        "ImagePosition(Patient) values not as expected")
        self.assertEqual(ct.Rows, 128, "Rows not 128")
        self.assertEqual(ct.Columns, 128, "Columns not 128")
        self.assertEqual(ct.BitsStored, 16, "Bits Stored not 16")
        self.assertEqual(len(ct.PixelData), 128 * 128 * 2,
                         "Pixel data not expected length")
        # Should also be able to close the file ourselves without
        # exception raised:
        f.close()

    def testReadFileGivenFileLikeObject(self):
        """filereader: can read using a file-like (BytesIO) file...."""
        with open(ct_name, 'rb') as f:
            file_like = BytesIO(f.read())
        ct = read_file(file_like)
        # Tests here simply repeat some of testCT test
        got = ct.ImagePositionPatient
        DS = pydicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        self.assertTrue(got == expected,
                        "ImagePosition(Patient) values not as expected")
        self.assertEqual(len(ct.PixelData), 128 * 128 * 2,
                         "Pixel data not expected length")
        # Should also be able to close the file ourselves without
        # exception raised:
        file_like.close()


if __name__ == "__main__":
    # This is called if run alone, but not if loaded through run_tests.py
    # If not run from the directory where the sample images are, then need
    # to switch there
    unittest.main()
