# Copyright 2008-2021 pydicom authors. See LICENSE file for details.
"""Test suite for util functions"""
import copy
from contextlib import contextmanager

import pytest

from pydicom import config, dcmread
from pydicom import filereader
from pydicom._private_dict import private_dictionaries
from pydicom.data import get_testdata_file
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.tag import Tag
from pydicom.uid import (
    ImplicitVRLittleEndian, ExplicitVRBigEndian, ExplicitVRLittleEndian
)
from pydicom.util import fixer, hexutil, debug_pixel_data
from pydicom.util.codify import (
    camel_to_underscore,
    tag_repr,
    default_name_filter,
    code_imports,
    code_dataelem,
    main as codify_main,
)
from pydicom.util.dump import *
from pydicom.util.hexutil import hex2bytes, bytes2hex
from pydicom.util.leanread import dicomfile

have_numpy = True
try:
    import numpy
except ImportError:
    have_numpy = False

test_dir = os.path.dirname(__file__)
raw_hex_module = os.path.join(test_dir, '_write_stds.py')
raw_hex_code = open(raw_hex_module, "rb").read()


class TestCodify:
    """Test the utils.codify module"""
    def test_camel_to_underscore(self):
        """Test utils.codify.camel_to_underscore"""
        input_str = ['TheNameToConvert', 'Some12Variable_Name']
        output_str = ['the_name_to_convert', 'some12_variable__name']
        for in_str, out_str in zip(input_str, output_str):
            assert out_str == camel_to_underscore(in_str)

    def test_tag_repr(self):
        """Test utils.codify.tag_repr"""
        input_tag = [0x00000000, 0x00100010, 0x7fe00010, 0x11110001]
        output_str = ['(0x0000, 0x0000)', '(0x0010, 0x0010)',
                      '(0x7fe0, 0x0010)', '(0x1111, 0x0001)']
        for tag, out_str in zip(input_tag, output_str):
            assert out_str == tag_repr(Tag(tag))

    def test_default_name_filter(self):
        """Test utils.codify.default_name_filter"""
        input_keyword = ['ControlPointSet', 'ReferenceDataSet',
                         'FractionGroupThing']
        output_str = ['cp_set', 'ref_data_set', 'frxn_gp_thing']
        for in_str, out_str in zip(input_keyword, output_str):
            assert out_str == default_name_filter(in_str)

    def test_code_imports(self):
        """Test utils.codify.code_imports"""
        out = 'import pydicom\n'
        out += 'from pydicom.dataset import Dataset, FileMetaDataset\n'
        out += 'from pydicom.sequence import Sequence'
        assert out == code_imports()

    def test_code_dataelem_standard(self):
        """Test utils.codify.code_dataelem for standard element"""
        # Element keyword in data dictionary
        input_elem = [DataElement(0x00100010, 'PN', 'CITIZEN'),
                      DataElement(0x0008010c, 'UI', '1.1.2.3.4.5'),
                      DataElement(0x00080301, 'US', 1200)]
        out_str = ["ds.PatientName = 'CITIZEN'",
                   "ds.CodingSchemeUID = '1.1.2.3.4.5'",
                   "ds.PrivateGroupReference = 1200"]
        for elem, out in zip(input_elem, out_str):
            assert out == code_dataelem(elem)

    def test_code_dataelem_exclude_size(self):
        """Test utils.codify.code_dataelem exclude_size param"""
        input_elem = [DataElement(0x00100010, 'OB', 'CITIZEN'),
                      DataElement(0x0008010c, 'UI', '1.1'),
                      DataElement(0x00200011, 'IS', 3)]
        # Fails
        # DataElement(0x00080301, 'US', 1200)]
        out_str = ["ds.PatientName = # XXX Array of 7 bytes excluded",
                   "ds.CodingSchemeUID = '1.1'",
                   "ds.SeriesNumber = '3'"]
        # Fails
        # "ds.PrivateGroupReference = 1200"]
        for elem, out in zip(input_elem, out_str):
            assert out == code_dataelem(elem, exclude_size=4)

    def test_code_dataelem_private(self):
        """Test utils.codify.code_dataelem"""
        # Element keyword not in data dictionary
        input_elem = [DataElement(0x00111010, 'PN', 'CITIZEN'),
                      DataElement(0x0081010c, 'UI', '1.1.2.3.4.5'),
                      DataElement(0x11110301, 'US', 1200)]
        out_str = ["ds.add_new((0x0011, 0x1010), 'PN', 'CITIZEN')",
                   "ds.add_new((0x0081, 0x010c), 'UI', '1.1.2.3.4.5')",
                   "ds.add_new((0x1111, 0x0301), 'US', 1200)"]
        for elem, out in zip(input_elem, out_str):
            assert out == code_dataelem(elem)

    def test_code_dataelem_sequence(self):
        """Test utils.codify.code_dataelem"""
        # ControlPointSequence
        elem = DataElement(0x300A0111, 'SQ', [])
        out = "\n# Control Point Sequence\n"
        out += "cp_sequence = Sequence()\n"
        out += "ds.ControlPointSequence = cp_sequence"
        assert out == code_dataelem(elem)

    def test_code_sequence(self):
        """Test utils.codify.code_dataelem"""
        # ControlPointSequence
        elem = DataElement(0x300A0111, 'SQ', [])
        elem.value.append(Dataset())
        elem.value[0].PatientID = '1234'
        out = (
            "\n"
            "# Control Point Sequence\n"
            "cp_sequence = Sequence()\n"
            "ds.ControlPointSequence = cp_sequence\n"
            "\n"
            "# Control Point Sequence: Control Point 1\n"
            "cp1 = Dataset()\n"
            "cp1.PatientID = '1234'\n"
            "cp_sequence.append(cp1)"
        )

        assert out == code_dataelem(elem)

    def test_code_dataset(self):
        """Test utils.codify.code_dataset"""
        pass

    def test_code_file(self, capsys):
        """Test utils.codify.code_file"""
        filename = get_testdata_file("rtplan.dcm")
        args = ["--save-as", r"c:\temp\testout.dcm", filename]
        codify_main(100, args)
        out, err = capsys.readouterr()
        assert r"c:\temp\testout.dcm" in out


class TestDump:
    """Test the utils.dump module"""
    def test_print_character(self):
        """Test utils.dump.print_character"""
        assert print_character(0x30) == '0'
        assert print_character(0x31) == '1'
        assert print_character(0x39) == '9'
        assert print_character(0x41) == 'A'
        assert print_character(0x5A) == 'Z'
        assert print_character(0x61) == 'a'
        assert print_character(0x7A) == 'z'
        assert print_character(0x00) == '.'

    def test_filedump(self):
        """Test utils.dump.filedump"""
        p = get_testdata_file("CT_small.dcm")
        s = filedump(p, start_address=500, stop_address=1000)

        assert (
            "000  49 49 2A 00 54 18 08 00 00 00 00 00 00 00 00 00  "
            "II*.T..........."
        ) not in s
        assert (
            "1F4  2E 31 2E 31 2E 31 2E 31 2E 32 30 30 34 30 31 31  "
            ".1.1.1.1.2004011"
        ) in s

    def test_datadump(self):
        """Test utils.dump.datadump"""
        p = get_testdata_file("CT_small.dcm")
        with open(p, 'rb') as f:
            s = datadump(f.read(), 500, 1000)

        assert (
            "1F4  2E 31 2E 31 2E 31 2E 31 2E 32 30 30 34 30 31 31  "
            ".1.1.1.1.2004011"
        ) in s

    def test_hexdump(self):
        """Test utils.dump.hexdump"""
        # Default
        p = get_testdata_file("CT_small.dcm")
        with open(p, 'rb') as f:
            s = hexdump(f)

        assert (
            "0000  49 49 2A 00 54 18 08 00 00 00 00 00 00 00 00 00  "
            "II*.T..........."
        ) in s
        assert (
            "0170  41 4C 5C 50 52 49 4D 41 52 59 5C 41 58 49 41 4C  "
            "AL.PRIMARY.AXIAL"
        ) in s
        assert (
            "9920  08 00 00 00 00 00                                ......"
        ) in s

        # `stop_address` parameter
        with open(p, 'rb') as f:
            s = hexdump(f, stop_address=1000)

        assert (
            "000  49 49 2A 00 54 18 08 00 00 00 00 00 00 00 00 00  "
            "II*.T..........."
        ) in s
        assert (
            "170  41 4C 5C 50 52 49 4D 41 52 59 5C 41 58 49 41 4C  "
            "AL.PRIMARY.AXIAL"
        ) in s
        assert (
            "9920  08 00 00 00 00 00                                ......"
        ) not in s

        # `show_address` parameter
        with open(p, 'rb') as f:
            s = hexdump(f, show_address=False, stop_address=1000)

        assert (
            "49 49 2A 00 54 18 08 00 00 00 00 00 00 00 00 00  "
            "II*.T..........."
        ) in s
        assert (
            "000  49 49 2A 00 54 18 08 00 00 00 00 00 00 00 00 00  "
            "II*.T..........."
        ) not in s

        # `start_address` parameter
        with open(p, 'rb') as f:
            s = hexdump(f, start_address=500, stop_address=1000)

        assert (
            "000  49 49 2A 00 54 18 08 00 00 00 00 00 00 00 00 00  "
            "II*.T..........."
        ) not in s
        assert (
            "1F4  2E 31 2E 31 2E 31 2E 31 2E 32 30 30 34 30 31 31  "
            ".1.1.1.1.2004011"
        ) in s

    def test_pretty_print(self, capsys):
        """Test utils.dump.pretty_print"""
        ds = get_testdata_file("CT_small.dcm", read=True)
        pretty_print(ds)

        s = capsys.readouterr().out
        assert (
            "(0008, 0005) Specific Character Set              CS: 'ISO_IR 100'"
        ) in s
        assert (
            "(0010, 1002) Other Patient IDs Sequence -- 2 item(s)"
        ) in s
        assert (
            "  (0010, 0022) Type of Patient ID                  CS: 'TEXT'"
        ) in s
        assert (
            "(fffc, fffc) Data Set Trailing Padding           OB: Array of "
            "126 elements"
        ) in s


class TestFixer:
    """Test the utils.fixer module"""
    def test_fix_separator_callback(self):
        """Test utils.fixer.fix_separator_callback"""
        pass

    def test_fix_separator(self):
        """Test utils.fixer.fix_separator"""
        pass

    def test_mismatch_callback(self):
        """Test utils.fixer.mismatch_callback"""
        pass

    def test_fix_mismatch(self):
        """Test utils.fixer.fix_mismatch"""
        pass


class TestHexUtil:
    """Test the utils.hexutil module"""
    def test_hex_to_bytes(self):
        """Test utils.hexutil.hex2bytes"""
        hexstring = "00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F"
        bytestring = (
            b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09'
            b'\x0A\x0B\x0C\x0D\x0E\x0F'
        )
        assert hex2bytes(hexstring) == bytestring

        hexstring = "00 10 20 30 40 50 60 70 80 90 A0 B0 C0 D0 E0 F0"
        bytestring = (
            b'\x00\x10\x20\x30\x40\x50\x60\x70\x80\x90'
            b'\xA0\xB0\xC0\xD0\xE0\xF0'
        )
        assert hex2bytes(hexstring) == bytestring

        hexstring = b"00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F"
        bytestring = (
            b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09'
            b'\x0A\x0B\x0C\x0D\x0E\x0F'
        )
        assert hex2bytes(hexstring) == bytestring

        with pytest.raises(TypeError):
            hex2bytes(0x1234)

    def test_bytes_to_hex(self):
        """Test utils.hexutil.hex2bytes"""
        hexstring = "00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f"
        bytestring = (
            b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09'
            b'\x0A\x0B\x0C\x0D\x0E\x0F'
        )
        assert bytes2hex(bytestring) == hexstring

        hexstring = "00 10 20 30 40 50 60 70 80 90 a0 b0 c0 d0 e0 f0"
        bytestring = (
            b'\x00\x10\x20\x30\x40\x50\x60\x70\x80\x90'
            b'\xA0\xB0\xC0\xD0\xE0\xF0'
        )
        assert bytes2hex(bytestring) == hexstring


class TestDataElementCallbackTests:
    def setup(self):
        # Set up a dataset with commas in one item instead of backslash
        namespace = {}
        exec(raw_hex_code, {}, namespace)
        ds_bytes = hexutil.hex2bytes(namespace['impl_LE_deflen_std_hex'])
        # Change "2\4\8\16" to "2,4,8,16"
        ds_bytes = ds_bytes.replace(b"\x32\x5c\x34\x5c\x38\x5c\x31\x36",
                                    b"\x32\x2c\x34\x2c\x38\x2c\x31\x36")

        self.bytesio = BytesIO(ds_bytes)

    def testBadSeparator(self, enforce_valid_values):
        """Ensure that unchanged bad separator does raise an error..."""
        ds = filereader.read_dataset(self.bytesio, is_little_endian=True,
                                     is_implicit_VR=True)
        contour = ds.ROIContourSequence[0].ContourSequence[0]
        with pytest.raises(ValueError):
            getattr(contour, "ContourData")

    def testImplVRcomma(self):
        """util.fix_separator:
           Able to replace comma in Implicit VR dataset.."""
        fixer.fix_separator(b",", for_VRs=["DS", "IS"],
                            process_unknown_VRs=False)
        ds = filereader.read_dataset(self.bytesio, is_little_endian=True,
                                     is_implicit_VR=True)
        got = ds.ROIContourSequence[0].ContourSequence[0].ContourData
        config.reset_data_element_callback()

        expected = [2., 4., 8., 16.]
        if have_numpy and config.use_DS_numpy:
            assert numpy.allclose(expected, got)
        else:
            assert expected == got


class TestLeanRead:
    def test_explicit_little(self):
        p = get_testdata_file("CT_small.dcm")
        ds = dcmread(p)
        assert ds.file_meta.TransferSyntaxUID == ExplicitVRLittleEndian
        with dicomfile(p) as ds:
            assert ds.preamble is not None
            for elem in ds:
                if elem[0] == (0x7fe0, 0x0010):
                    assert elem[2] == 32768

    def test_implicit_little(self):
        p = get_testdata_file("MR_small_implicit.dcm")
        ds = dcmread(p)
        assert ds.file_meta.TransferSyntaxUID == ImplicitVRLittleEndian
        with dicomfile(p) as ds:
            assert ds.preamble is not None
            for elem in ds:
                if elem[0] == (0x7fe0, 0x0010):
                    assert elem[2] == 8192

    def test_explicit_big(self):
        p = get_testdata_file("MR_small_bigendian.dcm")
        ds = dcmread(p)
        assert ds.file_meta.TransferSyntaxUID == ExplicitVRBigEndian
        with dicomfile(p) as ds:
            assert ds.preamble is not None
            for elem in ds:
                if elem[0] == (0x7fe0, 0x0010):
                    assert elem[2] == 8192

    def test_no_tsyntax(self):
        p = get_testdata_file("meta_missing_tsyntax.dcm")
        ds = dcmread(p)
        assert "TransferSyntaxUID" not in ds.file_meta
        msg = "No transfer syntax in file meta info"
        with dicomfile(p) as ds:
            assert ds.preamble is not None
            with pytest.raises(NotImplementedError, match=msg):
                for elem in ds:
                    pass

    def test_no_meta(self):
        p = get_testdata_file("no_meta.dcm")
        msg = "No transfer syntax in file meta info"
        with dicomfile(p) as ds:
            assert ds.preamble is None
            with pytest.raises(NotImplementedError, match=msg):
                for elem in ds:
                    pass

    def test_UN_sequence(self):
        p = get_testdata_file("UN_sequence.dcm")
        msg = "This reader does not handle undefined length except for SQ"
        with dicomfile(p) as ds:
            with pytest.raises(NotImplementedError, match=msg):
                for elem in ds:
                    pass


class TestDebugPixelData:
    """Tests for pydicom.util.debug.debug_pixel_data"""
    def test_bad_dataset_raises(self):
        """Test bad ds type raises"""
        msg = r"'ds' should be pydicom.dataset.Dataset, not 'int'"
        with pytest.raises(TypeError, match=msg):
            debug_pixel_data(1234)

    def test_meta(self, capsys):
        """Test file meta information"""
        ds = Dataset()
        debug_pixel_data(ds)
        out = capsys.readouterr().out
        assert "File Meta Information: absent" in out
        assert "Transfer Syntax UID: (none available)" in out
        assert "Dataset" in out
        assert "No pixel data elements found" in out

        ds.file_meta = FileMetaDataset()
        debug_pixel_data(ds)
        out = capsys.readouterr().out
        assert "File Meta Information: present" in out
        assert "Transfer Syntax UID: (none available)" in out
        assert "Dataset" in out
        assert "No pixel data elements found" in out

    def test_tsyntax(self, capsys):
        """Test transfer syntax UID"""
        ds = Dataset()
        ds.file_meta = FileMetaDataset()

        # Public
        ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
        debug_pixel_data(ds)
        out = capsys.readouterr().out
        assert "File Meta Information: present" in out
        assert (
            "Transfer Syntax UID: 1.2.840.10008.1.2.1 (Explicit VR "
            "Little Endian)"
        ) in out
        assert "Dataset" in out
        assert "No pixel data elements found" in out

        # Private
        ds.file_meta.TransferSyntaxUID = "9.10.11.12"
        debug_pixel_data(ds)
        out = capsys.readouterr().out
        assert "File Meta Information: present" in out
        assert "Transfer Syntax UID: 9.10.11.12" in out
        assert "Dataset" in out
        assert "No pixel data elements found" in out

    def test_image_pixel(self, capsys):
        """Test image pixel module"""
        ds = get_testdata_file("CT_small.dcm", read=True)
        debug_pixel_data(ds)
        out = capsys.readouterr().out
        assert "File Meta Information: present" in out
        assert "Transfer Syntax UID: 1.2.840.10008.1.2.1" in out
        assert "Dataset" in out
        assert (
            "(0028, 0010) Rows                                US: 128"
        ) in out
        assert (
            "(0028, 0011) Columns                             US: 128"
        ) in out
        assert (
            "(0028, 0030) Pixel Spacing                       DS: "
            "[0.661468, 0.661468]"
        ) in out
        assert (
            "(0028, 0100) Bits Allocated                      US: 16"
        ) in out
        assert (
            "(0028, 0101) Bits Stored                         US: 16"
        ) in out
        assert (
            "(0028, 0102) High Bit                            US: 15"
        ) in out
        assert (
            "(0028, 0103) Pixel Representation                US: 1"
        ) in out
        assert (
            "(0028, 0120) Pixel Padding Value                 SS: -2000"
        ) in out
        assert (
            "(0028, 1052) Rescale Intercept                   DS: '-1024.0'"
        ) in out
        assert (
            "(0028, 1053) Rescale Slope                       DS: '1.0'"
        ) in out
        assert (
            "(7fe0, 0010) Pixel Data                          OW: "
            "Array of 32768 elements"
        ) in out

    def test_pixel_keywords(self, capsys):
        """Test multiple pixel data elements"""
        ds = Dataset()
        ds.PixelData = None
        ds.FloatPixelData = None

        debug_pixel_data(ds)
        out = capsys.readouterr().out
        assert (
            "Multiple pixel data elements found: PixelData, FloatPixelData"
        ) in out

    def test_jpeg(self, capsys):
        """Test jpeg info"""
        ds = get_testdata_file("SC_jpeg_no_color_transform_2.dcm", read=True)
        debug_pixel_data(ds)
        out = capsys.readouterr().out
        assert "File Meta Information: present" in out
        assert (
            "Transfer Syntax UID: 1.2.840.10008.1.2.4.50 "
            "(JPEG Baseline (Process 1))"
        ) in out
        assert "Dataset" in out
        assert "(0028, 0002) Samples per Pixel                   US: 3" in out
        assert (
            "(0028, 0004) Photometric Interpretation          CS: 'RGB'"
        ) in out
        assert "(0028, 0006) Planar Configuration                US: 0" in out
        assert (
            "(0028, 0010) Rows                                US: 256"
        ) in out
        assert (
            "(0028, 0011) Columns                             US: 256"
        ) in out
        assert "(0028, 0100) Bits Allocated                      US: 8" in out
        assert "(0028, 0101) Bits Stored                         US: 8" in out
        assert "(0028, 0102) High Bit                            US: 7" in out
        assert "(0028, 0103) Pixel Representation                US: 0" in out
        assert (
            "(7fe0, 0010) Pixel Data                          OB: "
            "Array of 3422 elements"
        ) in out

        assert "JPEG codestream info for frame 0" in out
        assert "SOI (FF D8) marker found" in out
        assert "APP segment(s) found" in out
        assert "APP14: 41 64 6F 62 65 00 65 00 00 00 00 00" in out
        assert "SOF (FF C0) segment found" in out
        assert "Precision: 8" in out
        assert "Rows: 256" in out
        assert "Columns: 256" in out
        assert "Components:" in out
        assert "ID: 0x00, subsampling h1 v1" in out
        assert "ID: 0x01, subsampling h1 v1" in out
        assert "ID: 0x02, subsampling h1 v1" in out

    def test_jpeg2k(self, capsys):
        """Test jpeg2k info"""
        ds = get_testdata_file("JPEG2000.dcm", read=True)
        debug_pixel_data(ds)
        out = capsys.readouterr().out

        assert "File Meta Information: present" in out
        assert (
            "Transfer Syntax UID: 1.2.840.10008.1.2.4.91 "
            "(JPEG 2000 Image Compression)"
        ) in out

        assert "JPEG 2000 codestream info for frame 0" in out
        assert "SOI (FF 4F) marker found @ offset 0" in out
        assert "SIZ (FF 51) segment found @ offset 2" in out
        assert "Rows: 1024" in out
        assert "Columns: 256" in out
        assert "Components:" in out
        assert "0: signed, precision 16" in out
        assert "COD (FF 52) segment found @ offset 45" in out
        assert "Multiple component transform: none" in out
        assert "Wavelet transform: 9-7 irreversible" in out

    def test_index(self, capsys):
        """Test using the index parameter"""
        # 10 frames
        ds = get_testdata_file("emri_small_jpeg_2k_lossless.dcm", read=True)
        with pytest.raises(StopIteration):
            debug_pixel_data(ds, idx=10)

        debug_pixel_data(ds, idx=9)
        out = capsys.readouterr().out
        assert "JPEG 2000 codestream info for frame 9" in out
        assert "SOI (FF 4F) marker found @ offset 0" in out
        assert "SIZ (FF 51) segment found @ offset 2" in out
        assert "Rows: 64" in out
        assert "Columns: 64" in out
        assert "Components:" in out
        assert "0: unsigned, precision 16" in out
        assert "COD (FF 52) segment found @ offset 45" in out
        assert "Multiple component transform: none" in out
        assert "Wavelet transform: 5-3 reversible" in out


@contextmanager
def save_private_dict():
    saved_private_dict = copy.deepcopy(private_dictionaries)
    try:
        yield
    finally:
        private_dictionaries.clear()
        private_dictionaries.update(saved_private_dict)
