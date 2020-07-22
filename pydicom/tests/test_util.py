# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test suite for util functions"""

from io import BytesIO
import os

import pytest

from pydicom import config
from pydicom import filereader
from pydicom import valuerep
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom.util import fixer
from pydicom.util import hexutil
from pydicom.util.codify import (camel_to_underscore, tag_repr,
                                 default_name_filter, code_imports,
                                 code_dataelem, main as codify_main)
from pydicom.util.dump import *
from pydicom.util.hexutil import hex2bytes, bytes2hex
from pydicom.data import get_testdata_files

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
                   'ds.SeriesNumber = "3"']
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
        elem[0].PatientID = '1234'
        out = "\n"
        out += "# Control Point Sequence\n"
        out += "cp_sequence = Sequence()\n"
        out += "ds.ControlPointSequence = cp_sequence\n"
        out += "\n"
        out += "# Control Point Sequence: Control Point 1\n"
        out += "cp1 = Dataset()\n"
        out += "cp1.PatientID = '1234'\n"
        out += "cp_sequence.append(cp1)"

        assert out == code_dataelem(elem)

    def test_code_dataset(self):
        """Test utils.codify.code_dataset"""
        pass

    def test_code_file(self, capsys):
        """Test utils.codify.code_file"""
        filename = get_testdata_files("rtplan.dcm")[0]
        args = ["--save-as", r"c:\temp\testout.dcm", filename]
        codify_main(100, args)
        out, err = capsys.readouterr()
        assert r"c:\temp\testout.dcm" in out


class TestDump:
    """Test the utils.dump module"""
    def test_print_character(self):
        """Test utils.dump.print_character"""
        # assert print_character(0x30) == '0'  # Missing!
        assert '1' == print_character(0x31)
        assert '9' == print_character(0x39)
        assert 'A' == print_character(0x41)
        assert 'Z' == print_character(0x5A)
        assert 'a' == print_character(0x61)
        assert 'z' == print_character(0x7A)
        assert '.' == print_character(0x00)

    def test_filedump(self):
        """Test utils.dump.filedump"""
        pass

    def test_datadump(self):
        """Test utils.dump.datadump"""
        pass

    def test_hexdump(self):
        """Test utils.dump.hexdump"""
        pass

    def test_pretty_print(self):
        """Test utils.dump.pretty_print"""
        pass


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
        bytestring = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09' \
                     b'\x0A\x0B\x0C\x0D\x0E\x0F'
        assert bytestring == hex2bytes(hexstring)

        hexstring = b"00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F"
        bytestring = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09' \
                     b'\x0A\x0B\x0C\x0D\x0E\x0F'
        assert bytestring == hex2bytes(hexstring)

        hexstring = "00 10 20 30 40 50 60 70 80 90 A0 B0 C0 D0 E0 F0"
        bytestring = b'\x00\x10\x20\x30\x40\x50\x60\x70\x80\x90' \
                     b'\xA0\xB0\xC0\xD0\xE0\xF0'
        assert bytestring == hex2bytes(hexstring)

        with pytest.raises(TypeError):
            hex2bytes(0x1234)

    def test_bytes_to_hex(self):
        """Test utils.hexutil.hex2bytes"""
        hexstring = "00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f"
        bytestring = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09' \
                     b'\x0A\x0B\x0C\x0D\x0E\x0F'
        assert hexstring == bytes2hex(bytestring)

        hexstring = "00 10 20 30 40 50 60 70 80 90 a0 b0 c0 d0 e0 f0"
        bytestring = b'\x00\x10\x20\x30\x40\x50\x60\x70\x80\x90' \
                     b'\xA0\xB0\xC0\xD0\xE0\xF0'
        assert hexstring == bytes2hex(bytestring)


class TestDataElementCallbackTests:
    def setup(self):
        # Set up a dataset with commas in one item instead of backslash
        config.enforce_valid_values = True
        namespace = {}
        exec(raw_hex_code, {}, namespace)
        ds_bytes = hexutil.hex2bytes(namespace['impl_LE_deflen_std_hex'])
        # Change "2\4\8\16" to "2,4,8,16"
        ds_bytes = ds_bytes.replace(b"\x32\x5c\x34\x5c\x38\x5c\x31\x36",
                                    b"\x32\x2c\x34\x2c\x38\x2c\x31\x36")

        self.bytesio = BytesIO(ds_bytes)

    def teardown(self):
        config.enforce_valid_values = False

    def testBadSeparator(self):
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
