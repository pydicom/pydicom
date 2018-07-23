# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test fixes modules"""

import unittest
import copy
import pickle

import datetime as datetime_module
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo

import pytest

import pydicom as pydicom_module
from pydicom import compat
from pydicom.util.fixes import timezone

pickle_choices = [(pickle, pickle, proto)
                  for proto in range(pickle.HIGHEST_PROTOCOL + 1)]

ZERO = timedelta(0)
HOUR = timedelta(hours=1)
# In the US, DST starts at 2am (standard time) on the first Sunday in April.
DSTSTART = datetime(1, 4, 1, 2)
# and ends at 2am (DST time; 1am standard time) on the last Sunday of Oct,
# which is the first Sunday on or after Oct 25.  Because we view 1:MM as
# being standard time on that day, there is no spelling in local time of
# the last hour of DST (that's 1:MM DST, but 1:MM is taken as standard time).
DSTEND = datetime(1, 10, 25, 1)


def first_sunday_on_or_after(dt):
    days_to_go = 6 - dt.weekday()
    if days_to_go:
        dt += timedelta(days_to_go)
    return dt


class USTimeZone(tzinfo):

    def __init__(self, hours, reprname, stdname, dstname):
        self.stdoffset = timedelta(hours=hours)
        self.reprname = reprname
        self.stdname = stdname
        self.dstname = dstname

    def __repr__(self):
        return self.reprname

    def tzname(self, dt):
        if self.dst(dt):
            return self.dstname
        else:
            return self.stdname

    def utcoffset(self, dt):
        return self.stdoffset + self.dst(dt)

    def dst(self, dt):
        if dt is None or dt.tzinfo is None:
            # An exception instead may be sensible here, in one or more of
            # the cases.
            return ZERO
        assert dt.tzinfo is self

        # Find first Sunday in April.
        start = first_sunday_on_or_after(DSTSTART.replace(year=dt.year))
        assert start.weekday() == 6 and start.month == 4 and start.day <= 7

        # Find last Sunday in October.
        end = first_sunday_on_or_after(DSTEND.replace(year=dt.year))
        assert end.weekday() == 6 and end.month == 10 and end.day >= 25

        # Can't compare naive to aware objects, so strip the timezone from
        # dt first.
        if start <= dt.replace(tzinfo=None) < end:
            return HOUR
        else:
            return ZERO


Eastern = USTimeZone(-5, "Eastern",  "EST", "EDT")


@pytest.mark.skipif(not compat.in_py2,
                    reason='only test the backport to Python 2')
class TestTimeZone(unittest.TestCase):
    """Backport of datetime.timezone tests.

    Notes
    -----
    Backport of datetime.timezone for Python 2.7, from Python 3.6
    documentation (https://tinyurl.com/z4cegu9), copyright Python Software
    Foundation (https://docs.python.org/3/license.html)

    """

    def setUp(self):
        self.ACDT = timezone(timedelta(hours=9.5), 'ACDT')
        self.EST = timezone(-timedelta(hours=5), 'EST')
        self.DT = datetime(2010, 1, 1)

    def test_str(self):
        for tz in [self.ACDT, self.EST, timezone.utc,
                   timezone.min, timezone.max]:
            self.assertEqual(str(tz), tz.tzname(None))

    def test_repr(self):
        datetime = datetime_module
        pydicom = pydicom_module
        for tz in [self.ACDT, self.EST, timezone.utc,
                   timezone.min, timezone.max]:
            # test round-trip
            tzrep = repr(tz)
            self.assertEqual(tz, eval(tzrep))

    def test_class_members(self):
        limit = timedelta(hours=23, minutes=59)
        self.assertEqual(timezone.utc.utcoffset(None), ZERO)
        self.assertEqual(timezone.min.utcoffset(None), -limit)
        self.assertEqual(timezone.max.utcoffset(None), limit)

    def test_constructor(self):
        self.assertIs(timezone.utc, timezone(timedelta(0)))
        self.assertIsNot(timezone.utc, timezone(timedelta(0), 'UTC'))
        self.assertEqual(timezone.utc, timezone(timedelta(0), 'UTC'))
        # invalid offsets
        for invalid in [timedelta(microseconds=1), timedelta(1, 1),
                        timedelta(seconds=1), timedelta(1), -timedelta(1)]:
            self.assertRaises(ValueError, timezone, invalid)
            self.assertRaises(ValueError, timezone, -invalid)

        with self.assertRaises(TypeError):
            timezone(None)
        with self.assertRaises(TypeError):
            timezone(42)
        with self.assertRaises(TypeError):
            timezone(ZERO, None)
        with self.assertRaises(TypeError):
            timezone(ZERO, 42)
        with self.assertRaises(TypeError):
            timezone(ZERO, 'ABC', 'extra')

    def test_inheritance(self):
        self.assertIsInstance(timezone.utc, tzinfo)
        self.assertIsInstance(self.EST, tzinfo)

    def test_utcoffset(self):
        dummy = self.DT
        for h in [0, 1.5, 12]:
            offset = h * HOUR.total_seconds()
            offset = timedelta(seconds=offset)
            self.assertEqual(offset, timezone(offset).utcoffset(dummy))
            self.assertEqual(-offset, timezone(-offset).utcoffset(dummy))

        with self.assertRaises(TypeError):
            self.EST.utcoffset('')
        with self.assertRaises(TypeError):
            self.EST.utcoffset(5)

    def test_dst(self):
        self.assertIsNone(timezone.utc.dst(self.DT))

        with self.assertRaises(TypeError):
            self.EST.dst('')
        with self.assertRaises(TypeError):
            self.EST.dst(5)

    def test_tzname(self):
        self.assertTrue('UTC' in timezone.utc.tzname(None))
        self.assertTrue('UTC' in timezone(ZERO).tzname(None))
        self.assertEqual('UTC-05:00', timezone(timedelta(
            hours=-5)).tzname(None))
        self.assertEqual('UTC+09:30', timezone(timedelta(
            hours=9.5)).tzname(None))
        self.assertEqual('UTC-00:01',
                         timezone(timedelta(minutes=-1)).tzname(None))
        self.assertEqual('XYZ', timezone(-5 * HOUR, 'XYZ').tzname(None))

        with self.assertRaises(TypeError):
            self.EST.tzname('')
        with self.assertRaises(TypeError):
            self.EST.tzname(5)

    def test_fromutc(self):
        with self.assertRaises(ValueError):
            timezone.utc.fromutc(self.DT)
        with self.assertRaises(TypeError):
            timezone.utc.fromutc('not datetime')
        for tz in [self.EST, self.ACDT, Eastern]:
            utctime = self.DT.replace(tzinfo=tz)
            local = tz.fromutc(utctime)
            self.assertEqual(local - utctime, tz.utcoffset(local))
            self.assertEqual(local,
                             self.DT.replace(tzinfo=timezone.utc))

    def test_comparison(self):
        self.assertNotEqual(timezone(ZERO), timezone(HOUR))
        self.assertEqual(timezone(HOUR), timezone(HOUR))
        self.assertEqual(timezone(-5 * HOUR), timezone(-5 * HOUR, 'EST'))
        with self.assertRaises(TypeError):
            timezone(ZERO) < timezone(ZERO)
        self.assertIn(timezone(ZERO), {timezone(ZERO)})
        self.assertTrue(timezone(ZERO) is not None)
        self.assertFalse(timezone(ZERO) is None)
        self.assertNotEqual(timezone(ZERO), 'random')

    def test_aware_datetime(self):
        # test that timezone instances can be used by datetime
        t = datetime(1, 1, 1)
        for tz in [timezone.min, timezone.max, timezone.utc]:
            print(tz.tzname(t))
            self.assertEqual(tz.tzname(t),
                             t.replace(tzinfo=tz).tzname())
            self.assertEqual(tz.utcoffset(t),
                             t.replace(tzinfo=tz).utcoffset())
            self.assertEqual(tz.dst(t),
                             t.replace(tzinfo=tz).dst())

    def test_pickle(self):
        for tz in self.ACDT, self.EST, timezone.min, timezone.max:
            for pickler, unpickler, proto in pickle_choices:
                tz_copy = unpickler.loads(pickler.dumps(tz, proto))
                self.assertEqual(tz_copy, tz)
        tz = timezone.utc
        for pickler, unpickler, proto in pickle_choices:
            tz_copy = unpickler.loads(pickler.dumps(tz, proto))
            self.assertIs(tz_copy, tz)

    def test_copy(self):
        for tz in self.ACDT, self.EST, timezone.min, timezone.max:
            tz_copy = copy.copy(tz)
            self.assertEqual(tz_copy, tz)
        tz = timezone.utc
        tz_copy = copy.copy(tz)
        self.assertIs(tz_copy, tz)

    def test_deepcopy(self):
        for tz in self.ACDT, self.EST, timezone.min, timezone.max:
            tz_copy = copy.deepcopy(tz)
            self.assertEqual(tz_copy, tz)
        tz = timezone.utc
        tz_copy = copy.deepcopy(tz)
        self.assertIs(tz_copy, tz)
