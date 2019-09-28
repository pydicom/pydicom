# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
# -*- coding: utf-8 -*-
"""Unit tests for the pydicom.filereader module."""

import gzip
import io
from io import BytesIO
import os
import shutil
from struct import unpack
import sys
import tempfile

import pytest

import pydicom.config
from pydicom import config
from pydicom.dataset import Dataset, FileDataset
from pydicom.data import get_testdata_files
from pydicom.filereader import dcmread, read_dataset
from pydicom.dataelem import DataElement, DataElement_from_raw
from pydicom.errors import InvalidDicomError
from pydicom.filebase import DicomBytesIO
from pydicom.filereader import data_element_generator
from pydicom.tag import Tag, TupleTag
from pydicom.uid import ImplicitVRLittleEndian
import pydicom.valuerep


from pydicom.pixel_data_handlers import gdcm_handler
have_gdcm_handler = gdcm_handler.is_available()

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

empty_number_tags_name = get_testdata_files(
    "reportsi_with_empty_number_tags.dcm")[0]
rtplan_name = get_testdata_files("rtplan.dcm")[0]
rtdose_name = get_testdata_files("rtdose.dcm")[0]
ct_name = get_testdata_files("CT_small.dcm")[0]
mr_name = get_testdata_files("MR_small.dcm")[0]
truncated_mr_name = get_testdata_files("MR_truncated.dcm")[0]
jpeg2000_name = get_testdata_files("JPEG2000.dcm")[0]
jpeg2000_lossless_name = get_testdata_files("MR_small_jp2klossless.dcm")[0]
jpeg_ls_lossless_name = get_testdata_files("MR_small_jpeg_ls_lossless.dcm")[0]
jpeg_lossy_name = get_testdata_files("JPEG-lossy.dcm")[0]
jpeg_lossless_name = get_testdata_files("JPEG-LL.dcm")[0]
deflate_name = get_testdata_files("image_dfl.dcm")[0]
rtstruct_name = get_testdata_files("rtstruct.dcm")[0]
priv_SQ_name = get_testdata_files("priv_SQ.dcm")
# be sure that we don't pick up the nested_priv_sq
priv_SQ_name = [filename
                for filename in priv_SQ_name
                if 'nested' not in filename]
priv_SQ_name = priv_SQ_name[0]
nested_priv_SQ_name = get_testdata_files("nested_priv_SQ.dcm")[0]
meta_missing_tsyntax_name = get_testdata_files("meta_missing_tsyntax.dcm")[0]
no_meta_group_length = get_testdata_files("no_meta_group_length.dcm")[0]
gzip_name = get_testdata_files("zipMR.gz")[0]
color_px_name = get_testdata_files("color-px.dcm")[0]
color_pl_name = get_testdata_files("color-pl.dcm")[0]
explicit_vr_le_no_meta = get_testdata_files("ExplVR_LitEndNoMeta.dcm")[0]
explicit_vr_be_no_meta = get_testdata_files("ExplVR_BigEndNoMeta.dcm")[0]
emri_name = get_testdata_files("emri_small.dcm")[0]
emri_big_endian_name = get_testdata_files("emri_small_big_endian.dcm")[0]
emri_jpeg_ls_lossless = get_testdata_files(
    "emri_small_jpeg_ls_lossless.dcm")[0]
emri_jpeg_2k_lossless = get_testdata_files(
    "emri_small_jpeg_2k_lossless.dcm")[0]
color_3d_jpeg_baseline = get_testdata_files("color3d_jpeg_baseline.dcm")[0]
dir_name = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()


class TestReader(object):
    def test_empty_numbers_tag(self):
        """Test that an empty tag with a number VR (FL, UL, SL, US,
        SS, FL, FD, OF) reads as ``None``."""
        empty_number_tags_ds = dcmread(empty_number_tags_name)
        assert empty_number_tags_ds.ExaminedBodyThickness is None
        assert empty_number_tags_ds.SimpleFrameList is None
        assert empty_number_tags_ds.ReferencePixelX0 is None
        assert empty_number_tags_ds.PhysicalUnitsXDirection is None
        assert empty_number_tags_ds.TagAngleSecondAxis is None
        assert empty_number_tags_ds.TagSpacingSecondDimension is None
        assert empty_number_tags_ds.VectorGridData is None

    def test_UTF8_filename(self):
        utf8_filename = os.path.join(tempfile.gettempdir(), "ДИКОМ.dcm")
        shutil.copyfile(rtdose_name, utf8_filename)
        ds = dcmread(utf8_filename)
        os.remove(utf8_filename)
        assert ds is not None

    def test_RTPlan(self):
        """Returns correct values for sample data elements in test
        RT Plan file.
        """
        plan = dcmread(rtplan_name)
        beam = plan.BeamSequence[0]
        # if not two controlpoints, then this would raise exception
        cp0, cp1 = beam.ControlPointSequence

        assert "unit001" == beam.TreatmentMachineName
        assert beam[0x300a, 0x00b2].value == beam.TreatmentMachineName

        got = cp1.ReferencedDoseReferenceSequence[
            0].CumulativeDoseReferenceCoefficient
        DS = pydicom.valuerep.DS
        expected = DS('0.9990268')
        assert expected == got
        got = cp0.BeamLimitingDevicePositionSequence[0].LeafJawPositions
        assert [DS('-100'), DS('100.0')] == got

    def test_RTDose(self):
        """Returns correct values for sample data elements in test
        RT Dose file"""
        dose = dcmread(rtdose_name)
        assert Tag((0x3004, 0x000c)) == dose.FrameIncrementPointer
        assert dose[0x28, 9].value == dose.FrameIncrementPointer

        # try a value that is nested the deepest
        # (so deep I break it into two steps!)
        fract = (
            dose.ReferencedRTPlanSequence[0].ReferencedFractionGroupSequence[0]
        )
        assert 1 == fract.ReferencedBeamSequence[0].ReferencedBeamNumber

    def test_CT(self):
        """Returns correct values for sample data elements in test CT file."""
        ct = dcmread(ct_name)
        assert '1.3.6.1.4.1.5962.2' == ct.file_meta.ImplementationClassUID
        value = ct.file_meta[0x2, 0x12].value
        assert value == ct.file_meta.ImplementationClassUID

        # (0020, 0032) Image Position (Patient)
        # [-158.13580300000001, -179.035797, -75.699996999999996]
        got = ct.ImagePositionPatient
        DS = pydicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        assert expected == got

        assert 128 == ct.Rows
        assert 128 == ct.Columns
        assert 16 == ct.BitsStored
        assert 128 * 128 * 2 == len(ct.PixelData)

        # Also test private elements name can be resolved:
        got = ct[(0x0043, 0x104e)].name
        assert "[Duration of X-ray on]" == got

    @pytest.mark.skipif(not have_numpy, reason="Numpy not installed")
    def test_CT_PixelData(self):
        """Check that we can read pixel data.
        Tests that we get last one in array.
        """
        ct = dcmread(ct_name)
        assert 909 == ct.pixel_array[-1][-1]

    def test_no_force(self):
        """Raises exception if missing DICOM header and force==False."""
        with pytest.raises(InvalidDicomError):
            dcmread(rtstruct_name)

    def test_RTStruct(self):
        """Returns correct values for sample elements in test RTSTRUCT file."""
        # RTSTRUCT test file has complex nested sequences
        # -- see rtstruct.dump file
        # Also has no DICOM header ... so tests 'force' argument of dcmread

        rtss = dcmread(rtstruct_name, force=True)
        frame_of_ref = rtss.ReferencedFrameOfReferenceSequence[0]
        study = frame_of_ref.RTReferencedStudySequence[0]
        uid = study.RTReferencedSeriesSequence[0].SeriesInstanceUID
        assert "1.2.826.0.1.3680043.8.498.2010020400001.2.1.1" == uid

        got = rtss.ROIContourSequence[0].ContourSequence[2].ContourNumber
        assert 3 == got

        obs_seq0 = rtss.RTROIObservationsSequence[0]
        got = obs_seq0.ROIPhysicalPropertiesSequence[0].ROIPhysicalProperty
        assert 'REL_ELEC_DENSITY' == got

    def test_dir(self):
        """Returns correct dir attributes for both Dataset and DICOM names
        (python >= 2.6).."""
        # Only python >= 2.6 calls __dir__ for dir() call
        rtss = dcmread(rtstruct_name, force=True)
        # sample some expected 'dir' values
        got_dir = dir(rtss)
        expect_in_dir = ['pixel_array', 'add_new', 'ROIContourSequence',
                         'StructureSetDate']
        for name in expect_in_dir:
            assert name in got_dir

        # Now check for some items in dir() of a nested item
        roi0 = rtss.ROIContourSequence[0]
        got_dir = dir(roi0)
        expect_in_dir = ['pixel_array', 'add_new', 'ReferencedROINumber',
                         'ROIDisplayColor']
        for name in expect_in_dir:
            assert name in got_dir

    def test_MR(self):
        """Returns correct values for sample data elements in test MR file."""
        mr = dcmread(mr_name)
        # (0010, 0010) Patient's Name           'CompressedSamples^MR1'
        mr.decode()
        assert 'CompressedSamples^MR1' == mr.PatientName
        assert mr[0x10, 0x10].value == mr.PatientName

        DS = pydicom.valuerep.DS
        assert [DS('0.3125'), DS('0.3125')] == mr.PixelSpacing

    def test_deflate(self):
        """Returns correct values for sample data elements in test compressed
         (zlib deflate) file
         """
        # Everything after group 2 is compressed.
        # If we can read anything else, the decompression must have been ok.
        ds = dcmread(deflate_name)
        assert "WSD" == ds.ConversionType

    def test_no_pixels_read(self):
        """Returns all data elements before pixels using
        stop_before_pixels=False.
        """
        # Just check the tags, and a couple of values
        ctpartial = dcmread(ct_name, stop_before_pixels=True)
        ctpartial_tags = sorted(ctpartial.keys())
        ctfull = dcmread(ct_name)
        ctfull_tags = sorted(ctfull.keys())
        missing = [Tag(0x7fe0, 0x10), Tag(0xfffc, 0xfffc)]
        assert ctfull_tags == ctpartial_tags + missing

    def test_specific_tags(self):
        """Returns only tags specified by user."""
        ctspecific = dcmread(ct_name, specific_tags=[
            Tag(0x0010, 0x0010), 'PatientID', 'ImageType', 'ViewName'])
        ctspecific_tags = sorted(ctspecific.keys())
        expected = [
            # SpecificCharacterSet is always added
            # ViewName does not exist in the data set
            Tag(0x0008, 0x0005), Tag(0x0008, 0x0008),
            Tag(0x0010, 0x0010), Tag(0x0010, 0x0020)
        ]
        assert expected == ctspecific_tags

    def test_specific_tags_with_unknown_length_SQ(self):
        """Returns only tags specified by user."""
        unknown_len_sq_tag = Tag(0x3f03, 0x1001)
        tags = dcmread(priv_SQ_name, specific_tags=[unknown_len_sq_tag])
        tags = sorted(tags.keys())
        assert [unknown_len_sq_tag] == tags

        tags = dcmread(priv_SQ_name, specific_tags=['PatientName'])
        tags = sorted(tags.keys())
        assert [] == tags

    def test_specific_tags_with_unknown_length_tag(self):
        """Returns only tags specified by user."""
        unknown_len_tag = Tag(0x7fe0, 0x0010)  # Pixel Data
        tags = dcmread(emri_jpeg_2k_lossless, specific_tags=[unknown_len_tag])
        tags = sorted(tags.keys())
        # SpecificCharacterSet is always added
        assert [Tag(0x08, 0x05), unknown_len_tag] == tags

        tags = dcmread(
            emri_jpeg_2k_lossless, specific_tags=['SpecificCharacterSet']
        )
        tags = sorted(tags.keys())
        assert [Tag(0x08, 0x05)] == tags

    def test_private_SQ(self):
        """Can read private undefined length SQ without error."""
        # From issues 91, 97, 98. Bug introduced by fast reading, due to
        #    VR=None in raw data elements, then an undefined length private
        #    item VR is looked up, and there is no such tag,
        #    generating an exception

        # Simply read the file, in 0.9.5 this generated an exception
        dcmread(priv_SQ_name)

    def test_nested_private_SQ(self):
        """Can successfully read a private SQ which contains additional SQs."""
        # From issue 113. When a private SQ of undefined length is used, the
        #   sequence is read in and the length of the SQ is determined upon
        #   identification of the SQ termination sequence. When using nested
        #   Sequences, the first termination sequence encountered actually
        #   belongs to the nested Sequence not the parent, therefore the
        #   remainder of the file is not read in properly
        ds = dcmread(nested_priv_SQ_name)

        # Make sure that the entire dataset was read in
        pixel_data_tag = TupleTag((0x7fe0, 0x10))
        assert pixel_data_tag in ds

        # Check that the DataElement is indeed a Sequence
        tag = TupleTag((0x01, 0x01))
        seq0 = ds[tag]
        assert 'SQ' == seq0.VR

        # Now verify the presence of the nested private SQ
        seq1 = seq0[0][tag]
        assert 'SQ' == seq1.VR

        # Now make sure the values that are parsed are correct
        assert b'Double Nested SQ' == seq1[0][tag].value
        assert b'Nested SQ' == seq0[0][0x01, 0x02].value

    def test_no_meta_group_length(self):
        """Read file with no group length in file meta."""
        # Issue 108 -- iView example file with no group length (0002,0002)
        # Originally crashed, now check no exception, but also check one item
        #     in file_meta, and second one in followinsg dataset
        ds = dcmread(no_meta_group_length)
        assert "20111130" == ds.InstanceCreationDate

    def test_no_transfer_syntax_in_meta(self):
        """Read file with file_meta, but has no TransferSyntaxUID in it."""
        # From issue 258: if file has file_meta but no TransferSyntaxUID in it,
        #   should assume default transfer syntax
        ds = dcmread(meta_missing_tsyntax_name)  # is default transfer syntax

        # Repeat one test from nested private sequence test to maker sure
        #    file was read correctly
        pixel_data_tag = TupleTag((0x7fe0, 0x10))
        assert pixel_data_tag in ds

    def test_explicit_VR_little_endian_no_meta(self):
        """Read file without file meta with Little Endian Explicit VR dataset.
        """
        # Example file from CMS XiO 5.0 and above
        # Still need to force read data since there is no 'DICM' marker present
        ds = dcmread(explicit_vr_le_no_meta, force=True)
        assert "20150529" == ds.InstanceCreationDate

    def test_explicit_VR_big_endian_no_meta(self):
        """Read file without file meta with Big Endian Explicit VR dataset."""
        # Example file from CMS XiO 5.0 and above
        # Still need to force read data since there is no 'DICM' marker present
        ds = dcmread(explicit_vr_be_no_meta, force=True)
        assert "20150529" == ds.InstanceCreationDate

    def test_planar_config(self):
        px_data_ds = dcmread(color_px_name)
        pl_data_ds = dcmread(color_pl_name)
        assert px_data_ds.PlanarConfiguration != pl_data_ds.PlanarConfiguration
        if have_numpy:
            px_data = px_data_ds.pixel_array
            pl_data = pl_data_ds.pixel_array
            assert numpy.all(px_data == pl_data)

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
        file_ds.save_as(fp, write_like_original=True)

        ds = dcmread(fp, force=True)
        assert 'US' == ds[0x00280108].VR
        assert 10 == ds.SmallestPixelValueInSeries

    def test_correct_ambiguous_explicit_vr(self):
        """Test correcting ambiguous VR elements read from file"""
        ds = Dataset()
        ds.PixelRepresentation = 0
        ds.add(DataElement(0x00280108, 'US', 10))
        ds.add(DataElement(0x00280109, 'US', 500))

        fp = BytesIO()
        file_ds = FileDataset(fp, ds)
        file_ds.is_implicit_VR = False
        file_ds.is_little_endian = True
        file_ds.save_as(fp, write_like_original=True)

        ds = dcmread(fp, force=True)
        assert 'US' == ds[0x00280108].VR
        assert 10 == ds.SmallestPixelValueInSeries

    def test_correct_ambiguous_vr_compressed(self):
        """Test correcting compressed Pixel Data read from file"""
        # Create an implicit VR compressed dataset
        ds = dcmread(jpeg_lossless_name)
        fp = BytesIO()
        file_ds = FileDataset(fp, ds)
        file_ds.is_implicit_VR = True
        file_ds.is_little_endian = True
        file_ds.save_as(fp, write_like_original=True)

        ds = dcmread(fp, force=True)
        assert 'OB' == ds[0x7fe00010].VR

    def test_long_specific_char_set(self):
        """Test that specific character set is read even if it is longer
         than defer_size"""
        ds = Dataset()

        long_specific_char_set_value = ['ISO 2022IR 100'] * 9
        ds.add(DataElement(0x00080005, 'CS', long_specific_char_set_value))

        msg = (
            r"Unknown encoding 'ISO 2022IR 100' - using default encoding "
            r"instead"
        )

        fp = BytesIO()
        file_ds = FileDataset(fp, ds)
        with pytest.warns(UserWarning, match=msg):
            file_ds.save_as(fp, write_like_original=True)

        with pytest.warns(UserWarning, match=msg):
            ds = dcmread(fp, defer_size=65, force=True)
            assert long_specific_char_set_value == ds[0x00080005].value

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
        ds = dcmread(fp, force=True)
        assert 'MediaStorageSOPClassUID' in ds.file_meta
        assert ImplicitVRLittleEndian == ds.file_meta.TransferSyntaxUID
        assert 'NORMAL' == ds.Polarity
        assert 1 == ds.ImageBoxPosition

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
        ds = dcmread(fp, force=True)
        assert 'MediaStorageSOPClassUID' in ds.file_meta
        assert ImplicitVRLittleEndian == ds.file_meta.TransferSyntaxUID
        assert 'NORMAL' == ds.Polarity
        assert 1 == ds.ImageBoxPosition
        assert 3 == ds.MessageID

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
        ds = dcmread(fp, force=True)
        value = ds.file_meta.FileMetaInformationGroupLength
        assert not len(bytestream) - 12 == value
        assert 10 == ds.file_meta.FileMetaInformationGroupLength
        assert 'MediaStorageSOPClassUID' in ds.file_meta
        assert ImplicitVRLittleEndian == ds.file_meta.TransferSyntaxUID
        assert 'NORMAL' == ds.Polarity
        assert 1 == ds.ImageBoxPosition

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
        ds = dcmread(fp, force=True)
        assert 'TransferSyntaxUID' in ds.file_meta
        assert 'MessageID' in ds

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
        ds = dcmread(fp, force=True)
        assert b'\x00' * 128 == ds.preamble
        assert 'TransferSyntaxUID' in ds.file_meta
        assert Dataset() == ds[:]

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
        ds = dcmread(fp, force=True)
        assert 'MessageID' in ds
        assert Dataset() == ds.file_meta

    def test_meta_no_dataset(self):
        """Test reading only meta elements"""
        bytestream = (b'\x02\x00\x00\x00\x55\x4C\x04\x00\x0A\x00\x00\x00'
                      b'\x02\x00\x02\x00\x55\x49\x16\x00\x31\x2e\x32\x2e'
                      b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e'
                      b'\x31\x2e\x31\x2e\x39\x00\x02\x00\x10\x00\x55\x49'
                      b'\x12\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
                      b'\x30\x30\x38\x2e\x31\x2e\x32\x00')
        fp = BytesIO(bytestream)
        ds = dcmread(fp, force=True)
        assert 'TransferSyntaxUID' in ds.file_meta
        assert Dataset() == ds[:]

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
        ds = dcmread(fp, force=True)
        assert 'MessageID' in ds
        assert ds.preamble is None
        assert Dataset() == ds.file_meta

    def test_file_meta_dataset_implicit_vr(self):
        """Test reading a file meta dataset that is implicit VR"""

        bytestream = (b'\x02\x00\x10\x00\x12\x00\x00\x00'
                      b'\x31\x2e\x32\x2e\x38\x34\x30\x2e'
                      b'\x31\x30\x30\x30\x38\x2e\x31\x2e'
                      b'\x32\x00')
        fp = BytesIO(bytestream)
        with pytest.warns(UserWarning):
            ds = dcmread(fp, force=True)
        assert 'TransferSyntaxUID' in ds.file_meta

    def test_no_dataset(self):
        """Test reading no elements or preamble produces empty Dataset"""
        bytestream = b''
        fp = BytesIO(bytestream)
        ds = dcmread(fp, force=True)
        assert ds.preamble is None
        assert Dataset() == ds.file_meta
        assert Dataset() == ds[:]

    def test_empty_file(self):
        """Test reading no elements from file produces empty Dataset"""
        with tempfile.NamedTemporaryFile() as f:
            ds = dcmread(f, force=True)
            assert ds.preamble is None
            assert Dataset() == ds.file_meta
            assert Dataset() == ds[:]

    def test_dcmread_does_not_raise(self):
        """Test that reading from DicomBytesIO does not raise on EOF.
        Regression test for #358."""
        ds = dcmread(mr_name)
        fp = DicomBytesIO()
        ds.save_as(fp, write_like_original=True)
        fp.seek(0)
        de_gen = data_element_generator(fp, False, True)
        try:
            while True:
                next(de_gen)
        except StopIteration:
            pass
        except EOFError:
            self.fail('Unexpected EOFError raised')

    def test_lut_descriptor(self):
        """Regression test for #942: incorrect first value"""
        prefixes = [
            b'\x28\x00\x01\x11',
            b'\x28\x00\x02\x11',
            b'\x28\x00\x03\x11',
            b'\x28\x00\x02\x30'
        ]
        suffix = b'\x53\x53\x06\x00\x00\xf5\x00\xf8\x10\x00'

        for raw_tag in prefixes:
            tag = unpack('<2H', raw_tag)
            bs = DicomBytesIO(raw_tag + suffix)
            bs.is_little_endian = True
            bs.is_implicit_VR = False

            ds = dcmread(bs, force=True)
            elem = ds[tag]
            assert elem.VR == 'SS'
            assert elem.value == [62720, -2048, 16]


class TestIncorrectVR(object):
    def setup(self):
        config.enforce_valid_values = False
        self.ds_explicit = BytesIO(
            b'\x08\x00\x05\x00CS\x0a\x00ISO_IR 100'  # SpecificCharacterSet
            b'\x08\x00\x20\x00DA\x08\x0020000101'  # StudyDate
        )
        self.ds_implicit = BytesIO(
            b'\x08\x00\x05\x00\x0a\x00\x00\x00ISO_IR 100'
            b'\x08\x00\x20\x00\x08\x00\x00\x0020000101'
        )

    def teardown(self):
        config.enforce_valid_values = False

    def test_implicit_vr_expected_explicit_used(self):
        msg = ('Expected implicit VR, but found explicit VR - '
               'using explicit VR for reading')

        with pytest.warns(UserWarning, match=msg):
            ds = read_dataset(
                self.ds_explicit, is_implicit_VR=True, is_little_endian=True
            )
        assert 'ISO_IR 100' == ds.SpecificCharacterSet
        assert '20000101' == ds.StudyDate

    def test_implicit_vr_expected_explicit_used_strict(self):
        config.enforce_valid_values = True
        msg = ('Expected implicit VR, but found explicit VR - '
               'using explicit VR for reading')

        with pytest.raises(InvalidDicomError, match=msg):
            read_dataset(
                self.ds_explicit, is_implicit_VR=True, is_little_endian=True
            )

    def test_explicit_vr_expected_implicit_used(self):
        msg = ('Expected explicit VR, but found implicit VR - '
               'using implicit VR for reading')

        with pytest.warns(UserWarning, match=msg):
            ds = read_dataset(
                self.ds_implicit, is_implicit_VR=False, is_little_endian=True
            )
        assert 'ISO_IR 100' == ds.SpecificCharacterSet
        assert '20000101' == ds.StudyDate

    def test_explicit_vr_expected_implicit_used_strict(self):
        config.enforce_valid_values = True
        msg = ('Expected explicit VR, but found implicit VR - '
               'using implicit VR for reading')
        with pytest.raises(InvalidDicomError, match=msg):
            read_dataset(
                self.ds_implicit, is_implicit_VR=False, is_little_endian=True
            )


class TestUnknownVR(object):
    @pytest.mark.parametrize(
        'vr_bytes, str_output',
        [
            # Test limits of char values
            (b'\x00\x41', '0x00 0x41'),  # 000/A
            (b'\x40\x41', '0x40 0x41'),  # 064/A
            (b'\x5B\x41', '0x5b 0x41'),  # 091/A
            (b'\x60\x41', '0x60 0x41'),  # 096/A
            (b'\x7B\x41', '0x7b 0x41'),  # 123/A
            (b'\xFF\x41', '0xff 0x41'),  # 255/A
            # Test good/bad
            (b'\x41\x00', '0x41 0x00'),  # A/-
            (b'\x5A\x00', '0x5a 0x00'),  # Z/-
            # Test not quite good/bad
            (b'\x61\x00', '0x61 0x00'),  # a/-
            (b'\x7A\x00', '0x7a 0x00'),  # z/-
            # Test bad/good
            (b'\x00\x41', '0x00 0x41'),  # -/A
            (b'\x00\x5A', '0x00 0x5a'),  # -/Z
            # Test bad/not quite good
            (b'\x00\x61', '0x00 0x61'),  # -/a
            (b'\x00\x7A', '0x00 0x7a'),  # -/z
            # Test good/good
            (b'\x41\x41', 'AA'),  # A/A
            (b'\x41\x5A', 'AZ'),  # A/Z
            (b'\x5A\x41', 'ZA'),  # Z/A
            (b'\x5A\x5A', 'ZZ'),  # Z/Z
            # Test not quite good
            (b'\x41\x61', 'Aa'),  # A/a
            (b'\x41\x7A', 'Az'),  # A/z
            (b'\x61\x41', 'aA'),  # a/A
            (b'\x61\x5A', 'aZ'),  # a/Z
            (b'\x61\x61', 'aa'),  # a/a
            (b'\x61\x7A', 'az'),  # a/z
            (b'\x5A\x61', 'Za'),  # Z/a
            (b'\x5A\x7A', 'Zz'),  # Z/z
            (b'\x7A\x41', 'zA'),  # z/A
            (b'\x7A\x5A', 'zZ'),  # z/Z
            (b'\x7A\x61', 'za'),  # z/a
            (b'\x7A\x7A', 'zz'),  # z/z
        ]
    )
    def test_fail_decode_msg(self, vr_bytes, str_output):
        """Regression test for #791."""
        # start the dataset with a valid tag (SpecificCharacterSet),
        # as the first tag is used to check the VR
        ds = read_dataset(
            BytesIO(
                b'\x08\x00\x05\x00CS\x0a\x00ISO_IR 100'
                b'\x08\x00\x06\x00' +
                vr_bytes +
                b'\x00\x00\x00\x08\x00\x49'
            ),
            False, True
        )
        msg = (
            r"Unknown Value Representation '{}' in tag \(0008, 0006\)"
            .format(str_output)
        )
        with pytest.raises(NotImplementedError, match=msg):
            print(ds)


class TestReadDataElement(object):
    def setup(self):
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
        file_ds.save_as(self.fp, write_like_original=True)

        self.fp_ex = BytesIO()  # Explicit little
        file_ds = FileDataset(self.fp_ex, ds)
        file_ds.is_implicit_VR = False
        file_ds.is_little_endian = True
        file_ds.save_as(self.fp_ex, write_like_original=True)

    def test_read_OD_implicit_little(self):
        """Check creation of OD DataElement from byte data works correctly."""
        ds = dcmread(self.fp, force=True)
        ref_elem = ds.get(0x7fe00009)
        elem = DataElement(0x7fe00009, 'OD',
                           b'\x00\x01\x02\x03\x04\x05\x06\x07'
                           b'\x01\x01\x02\x03\x04\x05\x06\x07')
        assert ref_elem == elem

    def test_read_OD_explicit_little(self):
        """Check creation of OD DataElement from byte data works correctly."""
        ds = dcmread(self.fp_ex, force=True)
        ref_elem = ds.get(0x7fe00009)
        elem = DataElement(0x7fe00009, 'OD',
                           b'\x00\x01\x02\x03\x04\x05\x06\x07'
                           b'\x01\x01\x02\x03\x04\x05\x06\x07')
        assert ref_elem == elem

    def test_read_OL_implicit_little(self):
        """Check creation of OL DataElement from byte data works correctly."""
        ds = dcmread(self.fp, force=True)
        ref_elem = ds.get(0x00720075)
        elem = DataElement(0x00720075, 'OL',
                           b'\x00\x01\x02\x03\x04\x05\x06\x07'
                           b'\x01\x01\x02\x03')
        assert ref_elem == elem

    def test_read_OL_explicit_little(self):
        """Check creation of OL DataElement from byte data works correctly."""
        ds = dcmread(self.fp_ex, force=True)
        ref_elem = ds.get(0x00720075)
        elem = DataElement(0x00720075, 'OL',
                           b'\x00\x01\x02\x03\x04\x05\x06\x07'
                           b'\x01\x01\x02\x03')
        assert ref_elem == elem

    def test_read_UC_implicit_little(self):
        """Check creation of DataElement from byte data works correctly."""
        ds = dcmread(self.fp, force=True)
        ref_elem = ds.get(0x00189908)
        elem = DataElement(0x00189908, 'UC', ['A', 'B', 'C'])
        assert ref_elem == elem

        ds = dcmread(self.fp, force=True)
        ref_elem = ds.get(0x00100212)
        elem = DataElement(0x00100212, 'UC', 'Test')
        assert ref_elem == elem

    def test_read_UC_explicit_little(self):
        """Check creation of DataElement from byte data works correctly."""
        ds = dcmread(self.fp_ex, force=True)
        ref_elem = ds.get(0x00189908)
        elem = DataElement(0x00189908, 'UC', ['A', 'B', 'C'])
        assert ref_elem == elem

        ds = dcmread(self.fp_ex, force=True)
        ref_elem = ds.get(0x00100212)
        elem = DataElement(0x00100212, 'UC', 'Test')
        assert ref_elem == elem

    def test_read_UR_implicit_little(self):
        """Check creation of DataElement from byte data works correctly."""
        ds = dcmread(self.fp, force=True)
        ref_elem = ds.get(0x00080120)  # URNCodeValue
        elem = DataElement(0x00080120, 'UR', 'http://test.com')
        assert ref_elem == elem

        # Test trailing spaces ignored
        ref_elem = ds.get(0x00081190)  # RetrieveURL
        elem = DataElement(0x00081190, 'UR', 'ftp://test.com')
        assert ref_elem == elem

    def test_read_UR_explicit_little(self):
        """Check creation of DataElement from byte data works correctly."""
        ds = dcmread(self.fp_ex, force=True)
        ref_elem = ds.get(0x00080120)  # URNCodeValue
        elem = DataElement(0x00080120, 'UR', 'http://test.com')
        assert ref_elem == elem

        # Test trailing spaces ignored
        ref_elem = ds.get(0x00081190)  # RetrieveURL
        elem = DataElement(0x00081190, 'UR', 'ftp://test.com')
        assert ref_elem == elem

    def test_read_AE(self):
        """Check creation of AE DataElement from byte data works correctly."""
        ds = dcmread(self.fp, force=True)
        assert 'TEST  12' == ds.DestinationAE


class TestDeferredRead(object):
    """Test that deferred data element reading (for large size)
    works as expected
    """
    # Copy one of test files and use temporarily, then later remove.
    def setup(self):
        self.testfile_name = ct_name + ".tmp"
        shutil.copyfile(ct_name, self.testfile_name)

    def teardown(self):
        if os.path.exists(self.testfile_name):
            os.remove(self.testfile_name)

    def test_time_check(self):
        """Deferred read warns if file has been modified"""
        ds = dcmread(self.testfile_name, defer_size='2 kB')
        from time import sleep
        sleep(0.1)
        with open(self.testfile_name, "r+") as f:
            f.write('\0')  # "touch" the file

        msg = r"Deferred read warning -- file modification time has changed"
        with pytest.warns(UserWarning, match=msg):
            ds.PixelData

    def test_file_exists(self):
        """Deferred read raises error if file no longer exists."""
        ds = dcmread(self.testfile_name, defer_size=2000)
        os.remove(self.testfile_name)
        with pytest.raises(IOError):
            ds.PixelData

    def test_values_identical(self):
        """Deferred values exactly matches normal read."""
        ds_norm = dcmread(self.testfile_name)
        ds_defer = dcmread(self.testfile_name, defer_size=2000)
        for data_elem in ds_norm:
            tag = data_elem.tag
            assert data_elem.value == ds_defer[tag].value

    def test_zipped_deferred(self):
        """Deferred values from a gzipped file works."""
        # Arose from issue 103 "Error for defer_size read of gzip file object"
        fobj = gzip.open(gzip_name)
        ds = dcmread(fobj, defer_size=1)
        fobj.close()
        # before the fix, this threw an error as file reading was not in
        # the right place, it was re-opened as a normal file, not a zip file
        ds.InstanceNumber

    def test_filelike_deferred(self):
        """Deferred values work with file-like objects."""
        with open(ct_name, 'rb') as fp:
            data = fp.read()
        filelike = io.BytesIO(data)
        dataset = pydicom.dcmread(filelike, defer_size=1024)
        assert 32768 == len(dataset.PixelData)


class TestReadTruncatedFile(object):
    def testReadFileWithMissingPixelData(self):
        mr = dcmread(truncated_mr_name)
        mr.decode()
        assert 'CompressedSamples^MR1' == mr.PatientName
        assert mr.PatientName == mr[0x10, 0x10].value
        DS = pydicom.valuerep.DS
        assert [DS('0.3125'), DS('0.3125')] == mr.PixelSpacing

    @pytest.mark.skipif(not have_numpy or have_gdcm_handler,
                        reason="Missing numpy or GDCM present")
    def testReadFileWithMissingPixelDataArray(self):
        mr = dcmread(truncated_mr_name)
        mr.decode()
        # Need to escape brackets
        msg = (
            r"The length of the pixel data in the dataset \(8130 bytes\) "
            r"doesn't match the expected length \(8192 bytes\). "
            r"The dataset may be corrupted or there may be an issue with "
            r"the pixel data handler."
        )
        with pytest.raises(ValueError, match=msg):
            mr.pixel_array


class TestFileLike(object):
    """Test that can read DICOM files with file-like object rather than
    filename
    """
    def test_read_file_given_file_object(self):
        """filereader: can read using already opened file............"""
        f = open(ct_name, 'rb')
        ct = dcmread(f)
        # Tests here simply repeat testCT -- perhaps should collapse
        # the code together?
        got = ct.ImagePositionPatient
        DS = pydicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        assert expected == got
        assert '1.3.6.1.4.1.5962.2' == ct.file_meta.ImplementationClassUID
        value = ct.file_meta[0x2, 0x12].value
        assert ct.file_meta.ImplementationClassUID == value

        # (0020, 0032) Image Position (Patient)
        # [-158.13580300000001, -179.035797, -75.699996999999996]
        got = ct.ImagePositionPatient
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        assert expected == got
        assert 128 == ct.Rows
        assert 128 == ct.Columns
        assert 16 == ct.BitsStored
        assert 128 * 128 * 2 == len(ct.PixelData)

        # Should also be able to close the file ourselves without
        # exception raised:
        f.close()

    def test_read_file_given_file_like_object(self):
        """filereader: can read using a file-like (BytesIO) file...."""
        with open(ct_name, 'rb') as f:
            file_like = BytesIO(f.read())
        ct = dcmread(file_like)
        # Tests here simply repeat some of testCT test
        got = ct.ImagePositionPatient
        DS = pydicom.valuerep.DS
        expected = [DS('-158.135803'), DS('-179.035797'), DS('-75.699997')]
        assert expected == got
        assert 128 * 128 * 2 == len(ct.PixelData)
        # Should also be able to close the file ourselves without
        # exception raised:
        file_like.close()


class TestDataElementGenerator(object):
    """Test filereader.data_element_generator"""
    def test_little_endian_explicit(self):
        """Test reading little endian explicit VR data"""
        # (0010, 0010) PatientName PN 6 ABCDEF
        bytestream = (b'\x10\x00\x10\x00'
                      b'PN'
                      b'\x06\x00'
                      b'ABCDEF')
        fp = BytesIO(bytestream)
        # fp, is_implicit_VR, is_little_endian,
        gen = data_element_generator(fp, False, True)
        elem = DataElement(0x00100010, 'PN', 'ABCDEF')
        assert elem == DataElement_from_raw(next(gen), 'ISO_IR 100')

    def test_little_endian_implicit(self):
        """Test reading little endian implicit VR data"""
        # (0010, 0010) PatientName PN 6 ABCDEF
        bytestream = b'\x10\x00\x10\x00' \
                     b'\x06\x00\x00\x00' \
                     b'ABCDEF'
        fp = BytesIO(bytestream)
        gen = data_element_generator(fp, is_implicit_VR=True,
                                     is_little_endian=True)
        elem = DataElement(0x00100010, 'PN', 'ABCDEF')
        assert elem == DataElement_from_raw(next(gen), 'ISO_IR 100')

    def test_big_endian_explicit(self):
        """Test reading big endian explicit VR data"""
        # (0010, 0010) PatientName PN 6 ABCDEF
        bytestream = b'\x00\x10\x00\x10' \
                     b'PN' \
                     b'\x00\x06' \
                     b'ABCDEF'
        fp = BytesIO(bytestream)
        # fp, is_implicit_VR, is_little_endian,
        gen = data_element_generator(fp, False, False)
        elem = DataElement(0x00100010, 'PN', 'ABCDEF')
        assert elem == DataElement_from_raw(next(gen), 'ISO_IR 100')
