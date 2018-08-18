# -*- coding: utf-8 -*-
# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""unittest cases for pydicom.charset module"""

import pytest

import pydicom.charset
from pydicom import dcmread
from pydicom.data import get_charset_files, get_testdata_files
from pydicom.dataelem import DataElement

PATIENT_NAMES = [
    # incorrectly decoded data sets are commented out
    ('chrArab', u'قباني^لنزار'),
    ('chrFren', u'Buc^Jérôme'),
    ('chrFrenMulti', u'Buc^Jérôme'),
    ('chrGerm', u'Äneas^Rüdiger'),
    ('chrGreek', u'Διονυσιος'),
    ('chrH31', u'Yamada^Tarou=山田^太郎=やまだ^たろう'),
    ('chrH32', u'ﾔﾏﾀﾞ^ﾀﾛｳ=山田^太郎=やまだ^たろう'),
    ('chrHbrw', u'שרון^דבורה'),
    # ('chrI2', u'Hong^Gildong=洪^C吉洞=홍^C길동'),
    # ('chrJapMulti', u'やまだ^たろう'),
    # ('chrJapMultiExplicitIR6', u'やまだ^たろう'),
    # ('chrKoreanMulti', u'김희중'),
    ('chrRuss', u'Люкceмбypг'),
    # ('chrX1', u'Wang^XiaoDong=王^小東'),
    # ('chrX2', u'Wang^XiaoDong=王^小东'),
]


class TestCharset(object):
    def test_encodings(self):
        test_string = u'Hello World'
        for x in pydicom.charset.python_encoding.items():
            test_string.encode(x[1])

    def test_nested_character_sets(self):
        """charset: can read and decode SQ with different encodings........."""
        ds = dcmread(get_charset_files("chrSQEncoding.dcm")[0])
        ds.decode()

        # These datasets inside of the SQ cannot be decoded with
        # default_encoding OR UTF-8 (the parent dataset's encoding).
        # Instead, we make sure that it is decoded using the
        # (0008,0005) tag of the dataset

        sequence = ds[0x32, 0x1064][0]
        assert ['shift_jis', 'iso2022_jp'] == sequence._character_set
        assert u'ﾔﾏﾀﾞ^ﾀﾛｳ=山田^太郎=やまだ^たろう' == sequence.PatientName

    def test_inherited_character_set_in_sequence(self):
        """charset: can read and decode SQ with parent encoding............."""
        ds = dcmread(get_charset_files('chrSQEncoding1.dcm')[0])
        ds.decode()

        # These datasets inside of the SQ shall be decoded with the parent
        # dataset's encoding
        sequence = ds[0x32, 0x1064][0]
        assert ['shift_jis', 'iso2022_jp'] == sequence._character_set
        assert u'ﾔﾏﾀﾞ^ﾀﾛｳ=山田^太郎=やまだ^たろう' == sequence.PatientName

    def test_standard_file(self):
        """charset: can read and decode standard file without special char.."""
        ds = dcmread(get_testdata_files("CT_small.dcm")[0])
        ds.decode()
        assert u'CompressedSamples^CT1' == ds.PatientName

    def test_encoding_with_specific_tags(self):
        """Encoding is correctly applied even if  Specific Character Set
        is not in specific tags..."""
        rus_file = get_charset_files("chrRuss.dcm")[0]
        ds = dcmread(rus_file, specific_tags=['PatientName'])
        ds.decode()
        assert 2 == len(ds)  # specific character set is always decoded
        assert u'Люкceмбypг' == ds.PatientName

    def test_bad_charset(self):
        """Test bad charset defaults to ISO IR 6"""
        # Python 3: elem.value is PersonName3, Python 2: elem.value is str
        elem = DataElement(0x00100010, 'PN', 'CITIZEN')
        pydicom.charset.decode(elem, ['ISO 2022 IR 126'])
        # After decode Python 2: elem.value is PersonNameUnicode
        assert 'iso_ir_126' in elem.value.encodings
        assert 'iso8859' not in elem.value.encodings
        # default encoding is iso8859
        pydicom.charset.decode(elem, [])
        assert 'iso8859' in elem.value.encodings

    def test_patched_charset(self):
        """Test some commonly misspelled charset values"""
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        pydicom.charset.decode(elem, ['ISO_IR 192'])
        # correct encoding
        assert u'Buc^Jérôme' == elem.value

        # patched encoding shall behave correctly, but a warning is issued
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        with pytest.warns(UserWarning,
                          match='Incorrect value for Specific Character Set '
                                "'ISO IR 192' - assuming 'ISO_IR 192'"):
            pydicom.charset.decode(elem, ['ISO IR 192'])
            assert u'Buc^Jérôme' == elem.value

        elem = DataElement(0x00100010, 'PN', b'Buc^J\xe9r\xf4me')
        with pytest.warns(UserWarning,
                          match='Incorrect value for Specific Character Set '
                                "'ISO-IR 144' - assuming 'ISO_IR 144'") as w:
            pydicom.charset.decode(elem, ['ISO_IR 100', 'ISO-IR 144'])
            # make sure no warning is issued for the correct value
            assert 1 == len(w)

        # not patched incorrect encoding raises
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        with pytest.raises(LookupError):
            pydicom.charset.decode(elem, ['ISOIR 192'])

        # Python encoding also can be used directly
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xc3\xa9r\xc3\xb4me')
        pydicom.charset.decode(elem, ['utf8'])
        assert u'Buc^Jérôme' == elem.value

    def test_multi_charset_default_value(self):
        """Test that the first value is used if no escape code is given"""
        # regression test for #707
        elem = DataElement(0x00100010, 'PN', b'Buc^J\xe9r\xf4me')
        pydicom.charset.decode(elem, ['ISO 2022 IR 100', 'ISO 2022 IR 144'])
        assert u'Buc^Jérôme' == elem.value

        elem = DataElement(0x00081039, 'LO', b'R\xf6ntgenaufnahme')
        pydicom.charset.decode(elem, ['ISO 2022 IR 100', 'ISO 2022 IR 144'])
        assert u'Röntgenaufnahme' == elem.value

    def test_single_byte_multi_charset_personname(self):
        elem = DataElement(0x00100010, 'PN',
                           b'Dionysios=\x1b\x2d\x46'
                           b'\xc4\xe9\xef\xed\xf5\xf3\xe9\xef\xf2')
        pydicom.charset.decode(elem, ['ISO 2022 IR 100', 'ISO 2022 IR 126'])
        assert u'Dionysios=Διονυσιος' == elem.value

    @pytest.mark.parametrize('filename,patient_name', PATIENT_NAMES)
    def test_charset_patient_names(self, filename, patient_name):
        """Test pixel_array for big endian matches little."""
        file_path = get_charset_files(filename + '.dcm')[0]
        ds = dcmread(file_path)
        ds.decode()
        assert patient_name == ds.PatientName
