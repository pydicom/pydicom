# test_valuerep.py
"""Test suite for valuerep.py"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom
import copy
from datetime import (
    datetime,
    date,
    time,
    timedelta
)

from pydicom.tag import Tag
from pydicom.values import convert_value

import pydicom
import platform
from pydicom.compat import in_py2
from pydicom import config
from pydicom import valuerep
from pydicom.util.fixes import timezone
from pydicom.data import get_testdata_files
import unittest
import pytest

try:
    unittest.skipIf
except AttributeError:
    try:
        import unittest2 as unittest
    except ImportError:
        print("unittest2 is required for testing in python2.6")

if not in_py2:
    from pydicom.valuerep import PersonName3 as PersonNameUnicode
    PersonName = PersonNameUnicode
else:
    from pydicom.valuerep import (
        PersonName,
        PersonNameUnicode
    )

try:
    import cPickle as pickle
except ImportError:
    import pickle

badvr_name = get_testdata_files("badVR.dcm")[0]
default_encoding = 'iso8859'


@unittest.skipIf(platform.python_implementation() == 'PyPy',
                 "PyPy has trouble with this pickle")
class TMPickleTest(unittest.TestCase):
    """Unit tests for pickling TM"""
    def testPickling(self):
        # Check that a pickled TM is read back properly
        x = pydicom.valuerep.TM("212223")
        x.original_string = 'hello'
        self.assertEqual(x.original_string, 'hello')
        self.assertEqual(x, time(21, 22, 23))
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        self.assertEqual(x, x2)
        self.assertEqual(x.original_string,
                         x2.original_string)
        self.assertEqual(str(x), str(x2))


class DTPickleTest(unittest.TestCase):
    """Unit tests for pickling DT"""
    def testPickling(self):
        # Check that a pickled DT is read back properly
        x = pydicom.valuerep.DT("19111213212123")
        x.original_string = 'hello'
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        self.assertEqual(x, x2)
        self.assertEqual(x.original_string,
                         x2.original_string)
        self.assertEqual(str(x), str(x2))


class DAPickleTest(unittest.TestCase):
    """Unit tests for pickling DA"""
    def testPickling(self):
        # Check that a pickled DA is read back properly
        x = pydicom.valuerep.DA("19111213")
        x.original_string = 'hello'
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        self.assertEqual(x, x2)
        self.assertEqual(x.original_string,
                         x2.original_string)
        self.assertEqual(str(x), str(x2))


class DSfloatPickleTest(unittest.TestCase):
    """Unit tests for pickling DSfloat"""

    def testPickling(self):
        # Check that a pickled DSFloat is read back properly
        x = pydicom.valuerep.DSfloat(9.0)
        x.original_string = 'hello'
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        self.assertEqual(x.real, x2.real)
        self.assertEqual(x.original_string,
                         x2.original_string)


class DSdecimalPickleTest(unittest.TestCase):
    """Unit tests for pickling DSdecimal"""

    def testPickling(self):
        # Check that a pickled DSdecimal is read back properly
        # DSdecimal actually prefers original_string when
        # reading back
        x = pydicom.valuerep.DSdecimal(19)
        x.original_string = '19'
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        self.assertEqual(x.real, x2.real)
        self.assertEqual(x.original_string,
                         x2.original_string)


class ISPickleTest(unittest.TestCase):
    """Unit tests for pickling IS"""

    def testPickling(self):
        # Check that a pickled IS is read back properly
        x = pydicom.valuerep.IS(921)
        x.original_string = 'hello'
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        self.assertEqual(x.real, x2.real)
        self.assertEqual(x.original_string,
                         x2.original_string)

    def testLongInt(self):
        # Check that a long int is read properly
        # Will not work with enforce_valid_values
        x = pydicom.valuerep.IS(3103050000)
        data1_string = pickle.dumps(x)
        x2 = pickle.loads(data1_string)
        self.assertEqual(x.real, x2.real)

    def testOverflow(self):
        original_flag = config.enforce_valid_values
        config.enforce_valid_values = True
        with pytest.raises(OverflowError, match="Value exceeds DICOM limits*"):
            pydicom.valuerep.IS(3103050000)
        config.enforce_valid_values = original_flag


class BadValueReadtests(unittest.TestCase):
    """Unit tests for handling a bad value for a VR
       (a string in a number VR here)"""

    def setUp(self):
        class TagLike(object):
            pass

        self.tag = TagLike()
        self.tag.value = b'1A'
        self.tag.is_little_endian = True
        self.tag.is_implicit_VR = False
        self.tag.tag = Tag(0x0010, 0x0020)

    def testReadBadValueInVRDefault(self):
        # found a conversion
        self.assertEqual('1A', convert_value('SH', self.tag))
        # converted with fallback vr "SH"
        self.assertEqual('1A', convert_value('IS', self.tag))

        pydicom.values.convert_retry_VR_order = ['FL', 'UL']
        # no fallback VR succeeded, returned original value untranslated
        self.assertEqual(b'1A', convert_value('IS', self.tag))

    def testReadBadValueInVREnforceValidValue(self):
        pydicom.config.enforce_valid_values = True
        # found a conversion
        self.assertEqual('1A', convert_value('SH', self.tag))
        # invalid literal for base 10
        self.assertRaises(ValueError, convert_value, 'IS', self.tag)


class DecimalStringtests(unittest.TestCase):
    """Unit tests unique to the use of DS class
       derived from python Decimal"""

    def setUp(self):
        config.DS_decimal(True)
        config.enforce_valid_values = True

    def tearDown(self):
        config.DS_decimal(False)
        config.enforce_valid_values = False

    def testValidDecimalStrings(self):
        # Ensures that decimal.Decimal doesn't cause a valid string to become
        # invalid
        valid_str = '-9.81338674e-006'
        ds = valuerep.DS(valid_str)
        L = len(str(ds))
        self.assertTrue(L <= 16, "DS: expected a string of length 16 but got %d" % (L,))  # noqa

        # Now the input string is too long but decimal.Decimal can convert it
        # to a valid 16-character string
        long_str = '-0.000000981338674'
        ds = valuerep.DS(long_str)
        L = len(str(ds))
        self.assertTrue(L <= 16, "DS: expected a string of length 16 but got %d" % (L,))  # noqa

    def testInvalidDecimalStrings(self):
        # Now the input string truly is invalid
        invalid_string = '-9.813386743e-006'
        self.assertRaises(OverflowError,
                          valuerep.DS,
                          invalid_string)


class PersonNametests(unittest.TestCase):
    def testLastFirst(self):
        """PN: Simple Family-name^Given-name works..."""
        pn = PersonName("Family^Given")
        expected = "Family"
        got = pn.family_name
        self.assertEqual(got, expected,
                         "PN: expected '%s', got '%s' for family name"
                         % (expected, got))

        expected = 'Given'
        got = pn.given_name
        self.assertEqual(got, expected,
                         "PN: expected '%s', got '%s' for given name"
                         % (expected, got))

        expected = ''
        got = pn.name_suffix
        self.assertEqual(got, expected,
                         "PN: expected '%s', got '%s' for name_suffix"
                         % (expected, got))

        expected = ''
        got = pn.phonetic
        self.assertEqual(got, expected,
                         "PN: expected '%s', got '%s' for phonetic component"
                         % (expected, got))

    def testCopy(self):
        """PN: Copy and deepcopy works..."""
        pn = PersonNameUnicode(
            'Hong^Gildong='
            '\033$)C\373\363^\033$)C\321\316\324\327='
            '\033$)C\310\253^\033$)C\261\346\265\277',
            [default_encoding, 'euc_kr'])
        pn_copy = copy.copy(pn)
        self.assertEqual(pn_copy, pn)
        self.assertEqual(pn_copy.components, pn.components)
        # the copied object references the original components
        self.assertTrue(pn_copy.components is pn.components)
        self.assertEqual(pn_copy.encodings, pn.encodings)

        pn_copy = copy.deepcopy(pn)
        self.assertEqual(pn_copy, pn)
        self.assertEqual(pn_copy.components, pn.components)
        # deepcopy() shall have made a copy of components
        self.assertFalse(pn_copy.components is pn.components)
        self.assertEqual(pn_copy.encodings, pn.encodings)

    def testThreeComponent(self):
        """PN: 3component (single-byte, ideographic,
        phonetic characters) works..."""
        # Example name from PS3.5-2008 section I.2 p. 108
        pn = PersonName('Hong^Gildong='
                        '\033$)C\373\363^\033$)C\321\316\324\327='
                        '\033$)C\310\253^\033$)C\261\346\265\277')
        expected = ("Hong", "Gildong")
        got = (pn.family_name, pn.given_name)
        msg = "PN: Expected single_byte name '%s', got '%s'" % (expected, got)
        self.assertEqual(got, expected, msg)

    def testFormatting(self):
        """PN: Formatting works..."""
        pn = PersonName("Family^Given")
        expected = "Family, Given"
        got = pn.family_comma_given()
        msg = ("PN: expected '%s', got '%s' for formatted Family, Given"
               % (expected, got))
        self.assertEqual(got, expected, msg)

    def testUnicodeKr(self):
        """PN: 3component in unicode works (Korean)..."""
        # Example name from PS3.5-2008 section I.2 p. 101
        pn = PersonNameUnicode('Hong^Gildong='
                               '\033$)C\373\363^\033$)C\321\316\324\327='
                               '\033$)C\310\253^\033$)C\261\346\265\277',
                               [default_encoding, 'euc_kr'])
        expected = ("Hong", "Gildong")
        got = (pn.family_name, pn.given_name)
        msg = "PN: Expected single_byte name '{0!s}', got '{1!s}'".format(expected, got)  # noqa
        self.assertEqual(got, expected, msg)

    def testUnicodeJp(self):
        """PN: 3component in unicode works (Japanese)..."""
        # Example name from PS3.5-2008 section H  p. 98
        pn = PersonNameUnicode('Yamada^Tarou='
                               '\033$B;3ED\033(B^\033$BB@O:\033(B='
                               '\033$B$d$^$@\033(B^\033$B$?$m$&\033(B',
                               [default_encoding, 'iso2022_jp'])
        expected = ("Yamada", "Tarou")
        got = (pn.family_name, pn.given_name)
        msg = ("PN: Expected single_byte name '{0!s}', got '{1!s}'"
               .format(expected, got))
        self.assertEqual(got, expected, msg)

    def testNotEqual(self):
        """PN3: Not equal works correctly (issue 121)..."""
        # Meant to only be used in python 3 but doing simple check here
        from pydicom.valuerep import PersonName3
        pn = PersonName3("John^Doe")
        msg = "PersonName3 not equal comparison did not work correctly"
        self.assertFalse(pn != "John^Doe", msg)

    def test_encoding_carried(self):
        """Test encoding is carried over to a new PN3 object"""
        # Issue 466
        from pydicom.valuerep import PersonName3
        pn = PersonName3("John^Doe", encodings='iso_ir_126')
        assert pn.encodings == ['iso_ir_126', 'iso_ir_126', 'iso_ir_126']
        pn2 = PersonName3(pn)
        assert pn2.encodings == ['iso_ir_126', 'iso_ir_126', 'iso_ir_126']


class DateTimeTests(unittest.TestCase):
    """Unit tests for DA, DT, TM conversion to datetime objects"""

    def setUp(self):
        config.datetime_conversion = True

    def tearDown(self):
        config.datetime_conversion = False

    def testDate(self):
        """DA conversion to datetime.date ..."""
        dicom_date = "19610804"
        da = valuerep.DA(dicom_date)
        datetime_date = date(1961, 8, 4)
        self.assertEqual(da, datetime_date,
                         ("DA {0} not equal to date {1}"
                          .format(dicom_date, datetime_date)))

        dicom_date = "1961.08.04"  # ACR-NEMA Standard 300
        da = valuerep.DA(dicom_date)
        datetime_date = date(1961, 8, 4)
        self.assertEqual(da, datetime_date,
                         ("DA {0} not equal to date {1}"
                          .format(dicom_date, datetime_date)))

        dicom_date = ""
        da = valuerep.DA(dicom_date)
        self.assertEqual(da, None,
                         "DA {0} not None".format(dicom_date))

    def testDateTime(self):
        """DT conversion to datetime.datetime ..."""
        dicom_datetime = "1961"
        dt = valuerep.DT(dicom_datetime)
        datetime_datetime = datetime(1961, 1, 1)
        self.assertEqual(dt, datetime_datetime,
                         ("DT {0} not equal to datetime {1}"
                          .format(dicom_datetime,
                                  datetime_datetime)))

        dicom_datetime = "19610804"
        dt = valuerep.DT(dicom_datetime)
        datetime_datetime = datetime(1961, 8, 4)
        self.assertEqual(dt, datetime_datetime,
                         ("DT {0} not equal to datetime {1}"
                          .format(dicom_datetime,
                                  datetime_datetime)))

        dicom_datetime = "19610804192430.123"
        dt = valuerep.DT(dicom_datetime)
        datetime_datetime = datetime(1961, 8, 4, 19, 24, 30, 123000)
        self.assertEqual(dt, datetime_datetime,
                         ("DT {0} not equal to datetime {1}"
                          .format(dicom_datetime,
                                  datetime_datetime)))

        dicom_datetime = "196108041924-1000"
        dt = valuerep.DT(dicom_datetime)
        datetime_datetime = datetime(1961, 8, 4, 19, 24, 0, 0,
                                     timezone(timedelta(seconds=-10 * 3600)))
        self.assertEqual(dt, datetime_datetime,
                         ("DT {0} not equal to datetime {1}"
                          .format(dicom_datetime,
                                  datetime_datetime)))
        self.assertEqual(dt.utcoffset(),
                         timedelta(0, 0, 0, 0, 0, -10),
                         "DT offset did not compare correctly to timedelta")

    def testTime(self):
        """TM conversion to datetime.time..."""
        dicom_time = "2359"
        tm = valuerep.TM(dicom_time)
        datetime_time = time(23, 59)
        self.assertEqual(tm, datetime_time,
                         ("TM {0} not equal to time {1}"
                          .format(dicom_time, datetime_time)))

        dicom_time = "235900.123"
        tm = valuerep.TM(dicom_time)
        datetime_time = time(23, 59, 00, 123000)
        self.assertEqual(tm, datetime_time,
                         ("TM {0} not equal to time {1}"
                          .format(dicom_time, datetime_time)))

        dicom_time = ""
        tm = valuerep.TM(dicom_time)
        self.assertEqual(tm, None,
                         "TM {0} not None".format(dicom_time))


if __name__ == "__main__":
    unittest.main()
