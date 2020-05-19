# -*- coding: utf-8 -*-
# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test suite for valuerep.py"""

import copy
from datetime import datetime, date, time, timedelta, timezone

from pydicom.tag import Tag
from pydicom.values import convert_value

import pydicom
import platform
from pydicom import config
from pydicom import valuerep
from pydicom.data import get_testdata_files
from pydicom.valuerep import DS, IS
import pytest

from pydicom.valuerep import PersonName


try:
    import cPickle as pickle
except ImportError:
    import pickle

badvr_name = get_testdata_files("badVR.dcm")[0]
default_encoding = "iso8859"


@pytest.mark.skipif(
    platform.python_implementation() == "PyPy",
    reason="PyPy has trouble with this pickle",
)
class TestTM:
    """Unit tests for pickling TM"""

    def test_pickling(self):
        # Check that a pickled TM is read back properly
        x = pydicom.valuerep.TM("212223")
        x.original_string = "hello"
        assert "hello" == x.original_string
        assert time(21, 22, 23) == x
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        assert x == x2
        assert x.original_string == x2.original_string
        assert str(x) == str(x2)


class TestDT:
    """Unit tests for pickling DT"""

    def test_pickling(self):
        # Check that a pickled DT is read back properly
        x = pydicom.valuerep.DT("19111213212123")
        x.original_string = "hello"
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        assert x == x2
        assert x.original_string == x2.original_string
        assert str(x) == str(x2)


class TestDA:
    """Unit tests for pickling DA"""

    def test_pickling(self):
        # Check that a pickled DA is read back properly
        x = pydicom.valuerep.DA("19111213")
        x.original_string = "hello"
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        assert x == x2
        assert x.original_string == x2.original_string
        assert str(x) == str(x2)


class TestDS:
    """Unit tests for DS values"""

    def test_empty_value(self):
        assert DS(None) is None
        assert "" == DS("")

    def test_float_values(self):
        val = DS(0.9)
        assert isinstance(val, pydicom.valuerep.DSfloat)
        assert 0.9 == val
        val = DS("0.9")
        assert isinstance(val, pydicom.valuerep.DSfloat)
        assert 0.9 == val


class TestDSfloat:
    """Unit tests for pickling DSfloat"""

    def test_pickling(self):
        # Check that a pickled DSFloat is read back properly
        x = pydicom.valuerep.DSfloat(9.0)
        x.original_string = "hello"
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        assert x.real == x2.real
        assert x.original_string == x2.original_string

    def test_str(self):
        """Test DSfloat.__str__()."""
        val = pydicom.valuerep.DSfloat(1.1)
        assert "1.1" == str(val)

        val = pydicom.valuerep.DSfloat("1.1")
        assert "1.1" == str(val)

    def test_repr(self):
        """Test DSfloat.__repr__()."""
        val = pydicom.valuerep.DSfloat(1.1)
        assert '"1.1"' == repr(val)

        val = pydicom.valuerep.DSfloat("1.1")
        assert '"1.1"' == repr(val)


class TestDSdecimal:
    """Unit tests for pickling DSdecimal"""

    def test_pickling(self):
        # Check that a pickled DSdecimal is read back properly
        # DSdecimal actually prefers original_string when
        # reading back
        x = pydicom.valuerep.DSdecimal(19)
        x.original_string = "19"
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        assert x.real == x2.real
        assert x.original_string == x2.original_string

    def test_float_value(self):
        config.allow_DS_float = False
        with pytest.raises(
            TypeError, match="cannot be instantiated with a float value"
        ):
            pydicom.valuerep.DSdecimal(9.0)
        config.allow_DS_float = True
        assert 9 == pydicom.valuerep.DSdecimal(9.0)


class TestIS:
    """Unit tests for IS"""

    def test_empty_value(self):
        assert IS(None) is None
        assert "" == IS("")

    def test_valid_value(self):
        assert 42 == IS(42)
        assert 42 == IS("42")
        assert 42 == IS(42.0)

    def test_invalid_value(self):
        with pytest.raises(TypeError, match="Could not convert value"):
            IS(0.9)
        with pytest.raises(ValueError, match="invalid literal for int()"):
            IS("0.9")

    def test_pickling(self):
        # Check that a pickled IS is read back properly
        x = pydicom.valuerep.IS(921)
        x.original_string = "hello"
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        assert x.real == x2.real
        assert x.original_string == x2.original_string

    def test_longint(self):
        # Check that a long int is read properly
        # Will not work with enforce_valid_values
        x = pydicom.valuerep.IS(3103050000)
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        assert x.real == x2.real

    def test_overflow(self):
        original_flag = config.enforce_valid_values
        config.enforce_valid_values = True
        with pytest.raises(OverflowError, match="Value exceeds DICOM limits*"):
            pydicom.valuerep.IS(3103050000)
        config.enforce_valid_values = original_flag

    def test_str(self):
        """Test IS.__str__()."""
        val = pydicom.valuerep.IS(1)
        assert "1" == str(val)

        val = pydicom.valuerep.IS("1")
        assert "1" == str(val)

    def test_repr(self):
        """Test IS.__repr__()."""
        val = pydicom.valuerep.IS(1)
        assert '"1"' == repr(val)

        val = pydicom.valuerep.IS("1")
        assert '"1"' == repr(val)


class TestBadValueRead:
    """Unit tests for handling a bad value for a VR
       (a string in a number VR here)"""

    def setup(self):
        class TagLike:
            pass

        self.tag = TagLike()
        self.tag.value = b"1A"
        self.tag.is_little_endian = True
        self.tag.is_implicit_VR = False
        self.tag.tag = Tag(0x0010, 0x0020)
        self.tag.length = 2
        self.default_retry_order = pydicom.values.convert_retry_VR_order

    def teardown(self):
        pydicom.values.convert_retry_VR_order = self.default_retry_order

    def test_read_bad_value_in_VR_default(self):
        # found a conversion
        assert "1A" == convert_value("SH", self.tag)
        # converted with fallback vr "SH"
        assert "1A" == convert_value("IS", self.tag)

        pydicom.values.convert_retry_VR_order = ["FL", "UL"]
        # no fallback VR succeeded, returned original value untranslated
        assert b"1A" == convert_value("IS", self.tag)

    def test_read_bad_value_in_VR_enforce_valid_value(self):
        pydicom.config.enforce_valid_values = True
        # found a conversion
        assert "1A" == convert_value("SH", self.tag)
        # invalid literal for base 10
        with pytest.raises(ValueError):
            convert_value("IS", self.tag)


class TestDecimalString:
    """Unit tests unique to the use of DS class
       derived from python Decimal"""

    def setup(self):
        config.DS_decimal(True)
        config.enforce_valid_values = True

    def teardown(self):
        config.DS_decimal(False)
        config.enforce_valid_values = False

    def test_DS_decimal_set(self):
        config.use_DS_decimal = False
        config.DS_decimal(True)
        assert config.use_DS_decimal is True

    def test_valid_decimal_strings(self):
        # Ensures that decimal.Decimal doesn't cause a valid string to become
        # invalid
        valid_str = "-9.81338674e-006"
        ds = valuerep.DS(valid_str)
        assert len(str(ds)) <= 16

        # Now the input string is too long but decimal.Decimal can convert it
        # to a valid 16-character string
        long_str = "-0.000000981338674"
        ds = valuerep.DS(long_str)
        assert len(str(ds)) <= 16

    def test_invalid_decimal_strings(self):
        # Now the input string truly is invalid
        invalid_string = "-9.813386743e-006"
        with pytest.raises(OverflowError):
            valuerep.DS(invalid_string)


class TestPersonName:
    def test_last_first(self):
        """PN: Simple Family-name^Given-name works..."""
        pn = PersonName("Family^Given")
        assert "Family" == pn.family_name
        assert "Given" == pn.given_name
        assert "" == pn.name_suffix
        assert "" == pn.phonetic

    def test_copy(self):
        """PN: Copy and deepcopy works..."""
        pn = PersonName(
            "Hong^Gildong="
            "\033$)C\373\363^\033$)C\321\316\324\327="
            "\033$)C\310\253^\033$)C\261\346\265\277",
            [default_encoding, "euc_kr"],
        )
        pn_copy = copy.copy(pn)
        assert pn == pn_copy
        assert pn.components == pn_copy.components
        # the copied object references the original components
        assert pn_copy.components is pn.components
        assert pn.encodings == pn_copy.encodings

        pn_copy = copy.deepcopy(pn)
        assert pn == pn_copy
        assert pn.components == pn_copy.components
        # deepcopy() returns the same immutable objects (tuples)
        assert pn_copy.components is pn.components
        assert pn.encodings is pn_copy.encodings

    def test_three_component(self):
        """PN: 3component (single-byte, ideographic,
        phonetic characters) works..."""
        # Example name from PS3.5-2008 section I.2 p. 108
        pn = PersonName(
            "Hong^Gildong="
            "\033$)C\373\363^\033$)C\321\316\324\327="
            "\033$)C\310\253^\033$)C\261\346\265\277"
        )
        assert ("Hong", "Gildong") == (pn.family_name, pn.given_name)

    def test_formatting(self):
        """PN: Formatting works..."""
        pn = PersonName("Family^Given")
        assert "Family, Given" == pn.family_comma_given()

    def test_unicode_kr(self):
        """PN: 3component in unicode works (Korean)..."""
        # Example name from PS3.5-2008 section I.2 p. 101
        pn = PersonName(
            b"Hong^Gildong="
            b"\033$)C\373\363^\033$)C\321\316\324\327="
            b"\033$)C\310\253^\033$)C\261\346\265\277",
            [default_encoding, "euc_kr"],
        )

        # PersonName does not decode the components automatically
        pn = pn.decode()
        assert (u"Hong", u"Gildong") == (pn.family_name, pn.given_name)
        assert u"洪^吉洞" == pn.ideographic
        assert u"홍^길동" == pn.phonetic

    def test_unicode_jp_from_bytes(self):
        """PN: 3component in unicode works (Japanese)..."""
        # Example name from PS3.5-2008 section H  p. 98
        pn = PersonName(
            b"Yamada^Tarou="
            b"\033$B;3ED\033(B^\033$BB@O:\033(B="
            b"\033$B$d$^$@\033(B^\033$B$?$m$&\033(B",
            [default_encoding, "iso2022_jp"],
        )
        pn = pn.decode()
        assert (u"Yamada", u"Tarou") == (pn.family_name, pn.given_name)
        assert u"山田^太郎" == pn.ideographic
        assert u"やまだ^たろう" == pn.phonetic

    def test_unicode_jp_from_bytes_comp_delimiter(self):
        """The example encoding without the escape sequence before '='"""
        pn = PersonName(
            b"Yamada^Tarou="
            b"\033$B;3ED\033(B^\033$BB@O:="
            b"\033$B$d$^$@\033(B^\033$B$?$m$&\033(B",
            [default_encoding, "iso2022_jp"],
        )
        pn = pn.decode()
        assert (u"Yamada", u"Tarou") == (pn.family_name, pn.given_name)
        assert u"山田^太郎" == pn.ideographic
        assert u"やまだ^たろう" == pn.phonetic

    def test_unicode_jp_from_bytes_caret_delimiter(self):
        """PN: 3component in unicode works (Japanese)..."""
        # Example name from PS3.5-2008 section H  p. 98
        pn = PersonName(
            b"Yamada^Tarou="
            b"\033$B;3ED\033(B^\033$BB@O:\033(B="
            b"\033$B$d$^$@\033(B^\033$B$?$m$&\033(B",
            [default_encoding, "iso2022_jp"],
        )
        pn = pn.decode()
        assert (u"Yamada", u"Tarou") == (pn.family_name, pn.given_name)
        assert u"山田^太郎" == pn.ideographic
        assert u"やまだ^たろう" == pn.phonetic

    def test_unicode_jp_from_unicode(self):
        """A person name initialized from unicode is already decoded"""
        pn = PersonName(
            u"Yamada^Tarou=山田^太郎=やまだ^たろう", [default_encoding, "iso2022_jp"]
        )
        assert (u"Yamada", u"Tarou") == (pn.family_name, pn.given_name)
        assert u"山田^太郎" == pn.ideographic
        assert u"やまだ^たろう" == pn.phonetic

    def test_not_equal(self):
        """PN3: Not equal works correctly (issue 121)..."""
        # Meant to only be used in python 3 but doing simple check here
        from pydicom.valuerep import PersonName

        pn = PersonName("John^Doe")
        assert not pn != "John^Doe"

    def test_encoding_carried(self):
        """Test encoding is carried over to a new PN3 object"""
        # Issue 466
        from pydicom.valuerep import PersonName

        pn = PersonName("John^Doe", encodings="iso_ir_126")
        assert pn.encodings == ("iso_ir_126",)
        pn2 = PersonName(pn)
        assert pn2.encodings == ("iso_ir_126",)

    def test_hash(self):
        """Test that the same name creates the same hash."""
        # Regression test for #785
        pn1 = PersonName("John^Doe^^Dr", encodings=default_encoding)
        pn2 = PersonName("John^Doe^^Dr", encodings=default_encoding)
        assert hash(pn1) == hash(pn2)
        pn3 = PersonName("John^Doe", encodings=default_encoding)
        assert hash(pn1) != hash(pn3)

        pn1 = PersonName(
            u"Yamada^Tarou=山田^太郎=やまだ^たろう", [default_encoding, "iso2022_jp"]
        )
        pn2 = PersonName(
            u"Yamada^Tarou=山田^太郎=やまだ^たろう", [default_encoding, "iso2022_jp"]
        )
        assert hash(pn1) == hash(pn2)


class TestDateTime:
    """Unit tests for DA, DT, TM conversion to datetime objects"""

    def setup(self):
        config.datetime_conversion = True

    def teardown(self):
        config.datetime_conversion = False

    def test_date(self):
        """DA conversion to datetime.date ..."""
        dicom_date = "19610804"
        da = valuerep.DA(dicom_date)
        # Assert `da` equals to correct `date`
        assert date(1961, 8, 4) == da
        # Assert `da.__repr__` holds original string
        assert '"{0}"'.format(dicom_date) == repr(da)

        dicom_date = "1961.08.04"  # ACR-NEMA Standard 300
        da = valuerep.DA(dicom_date)
        # Assert `da` equals to correct `date`
        assert date(1961, 8, 4) == da
        # Assert `da.__repr__` holds original string
        assert '"{0}"'.format(dicom_date) == repr(da)

        dicom_date = ""
        da = valuerep.DA(dicom_date)
        # Assert `da` equals to no date
        assert da is None

    def test_date_time(self):
        """DT conversion to datetime.datetime ..."""
        dicom_datetime = "1961"
        dt = valuerep.DT(dicom_datetime)
        # Assert `dt` equals to correct `datetime`
        assert datetime(1961, 1, 1) == dt
        # Assert `dt.__repr__` holds original string
        assert '"{0}"'.format(dicom_datetime) == repr(dt)

        dicom_datetime = "19610804"
        dt = valuerep.DT(dicom_datetime)
        # Assert `dt` equals to correct `datetime`
        assert datetime(1961, 8, 4) == dt
        # Assert `dt.__repr__` holds original string
        assert '"{0}"'.format(dicom_datetime) == repr(dt)

        dicom_datetime = "19610804192430.123"
        dt = valuerep.DT(dicom_datetime)
        # Assert `dt` equals to correct `datetime`
        assert datetime(1961, 8, 4, 19, 24, 30, 123000) == dt
        # Assert `dt.__repr__` holds original string
        assert '"{0}"'.format(dicom_datetime) == repr(dt)

        dicom_datetime = "196108041924-1000"
        dt = valuerep.DT(dicom_datetime)
        # Assert `dt` equals to correct `datetime`
        datetime_datetime = datetime(
            1961, 8, 4, 19, 24, 0, 0, timezone(timedelta(seconds=-10 * 3600))
        )
        assert datetime_datetime == dt
        assert timedelta(0, 0, 0, 0, 0, -10) == dt.utcoffset()

        # Assert `dt.__repr__` holds original string
        assert '"{0}"'.format(dicom_datetime) == repr(dt)

    def test_time(self):
        """TM conversion to datetime.time..."""
        dicom_time = "2359"
        tm = valuerep.TM(dicom_time)
        # Assert `tm` equals to correct `time`
        assert time(23, 59) == tm
        # Assert `tm.__repr__` holds original string
        assert '"{0}"'.format(dicom_time) == repr(tm)

        dicom_time = "235900.123"
        tm = valuerep.TM(dicom_time)
        # Assert `tm` equals to correct `time`
        assert time(23, 59, 00, 123000) == tm
        # Assert `tm.__repr__` holds original string
        assert '"{0}"'.format(dicom_time) == repr(tm)

        # Assert `tm` equals to no `time`
        tm = valuerep.TM("")
        assert tm is None
