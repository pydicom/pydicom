# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for pydicom.util.fixes module."""

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

pickle_choices = [
    (pickle, pickle, proto) for proto in range(pickle.HIGHEST_PROTOCOL + 1)
]

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


@pytest.mark.skipif(not compat.in_py2, reason='Only test backport in Python 2')
class TestTimeZone(object):
    """Backport of datetime.timezone tests.

    Notes
    -----
    Backport of datetime.timezone for Python 2.7, from Python 3.6
    documentation (https://tinyurl.com/z4cegu9), copyright Python Software
    Foundation (https://docs.python.org/3/license.html)

    """
    def setup(self):
        self.ACDT = timezone(timedelta(hours=9.5), 'ACDT')
        self.EST = timezone(-timedelta(hours=5), 'EST')
        self.DT = datetime(2010, 1, 1)

    def test_str(self):
        for tz in [self.ACDT, self.EST, timezone.utc,
                   timezone.min, timezone.max]:
            assert tz.tzname(None) == str(tz)

    def test_repr(self):
        datetime = datetime_module
        pydicom = pydicom_module
        for tz in [self.ACDT, self.EST, timezone.utc,
                   timezone.min, timezone.max]:
            # test round-trip
            tzrep = repr(tz)
            assert tz == eval(tzrep)

    def test_class_members(self):
        limit = timedelta(hours=23, minutes=59)
        assert ZERO == timezone.utc.utcoffset(None)
        assert -limit == timezone.min.utcoffset(None)
        assert limit == timezone.max.utcoffset(None)

    def test_constructor(self):
        assert timezone.utc is timezone(timedelta(0))
        assert timezone.utc is not timezone(timedelta(0), 'UTC')
        assert timezone(timedelta(0), 'UTC') == timezone.utc
        # invalid offsets
        for invalid in [timedelta(microseconds=1), timedelta(1, 1),
                        timedelta(seconds=1), timedelta(1), -timedelta(1)]:
            with pytest.raises(ValueError):
                timezone(invalid)
            with pytest.raises(ValueError):
                timezone(-invalid)

        with pytest.raises(TypeError):
            timezone(None)
        with pytest.raises(TypeError):
            timezone(42)
        with pytest.raises(TypeError):
            timezone(ZERO, None)
        with pytest.raises(TypeError):
            timezone(ZERO, 42)
        with pytest.raises(TypeError):
            timezone(ZERO, 'ABC', 'extra')

    def test_inheritance(self):
        assert isinstance(timezone.utc, tzinfo)
        assert isinstance(self.EST, tzinfo)

    def test_utcoffset(self):
        dummy = self.DT
        for h in [0, 1.5, 12]:
            offset = h * HOUR.total_seconds()
            offset = timedelta(seconds=offset)
            assert offset == timezone(offset).utcoffset(dummy)
            assert -offset == timezone(-offset).utcoffset(dummy)

        with pytest.raises(TypeError):
            self.EST.utcoffset('')
        with pytest.raises(TypeError):
            self.EST.utcoffset(5)

    def test_dst(self):
        assert timezone.utc.dst(self.DT) is None

        with pytest.raises(TypeError):
            self.EST.dst('')
        with pytest.raises(TypeError):
            self.EST.dst(5)

    def test_tzname(self):
        assert 'UTC' in timezone.utc.tzname(None)
        assert 'UTC' in timezone(ZERO).tzname(None)
        assert 'UTC-05:00' == timezone(timedelta(hours=-5)).tzname(None)
        assert 'UTC+09:30' == timezone(timedelta(hours=9.5)).tzname(None)
        assert 'UTC-00:01' == timezone(timedelta(minutes=-1)).tzname(None)
        assert 'XYZ' == timezone(-5 * HOUR, 'XYZ').tzname(None)

        with pytest.raises(TypeError):
            self.EST.tzname('')
        with pytest.raises(TypeError):
            self.EST.tzname(5)

    def test_fromutc(self):
        with pytest.raises(ValueError):
            timezone.utc.fromutc(self.DT)
        with pytest.raises(TypeError):
            timezone.utc.fromutc('not datetime')
        for tz in [self.EST, self.ACDT, Eastern]:
            utctime = self.DT.replace(tzinfo=tz)
            local = tz.fromutc(utctime)
            assert local - utctime == tz.utcoffset(local)
            assert local == self.DT.replace(tzinfo=timezone.utc)

    def test_comparison(self):
        assert timezone(ZERO) != timezone(HOUR)
        assert timezone(HOUR) == timezone(HOUR)
        assert timezone(-5 * HOUR) == timezone(-5 * HOUR, 'EST')
        with pytest.raises(TypeError):
            timezone(ZERO) < timezone(ZERO)
        assert timezone(ZERO) in {timezone(ZERO)}
        assert timezone(ZERO) is not None
        assert not timezone(ZERO) is None
        assert 'random' != timezone(ZERO)

    def test_aware_datetime(self):
        # test that timezone instances can be used by datetime
        t = datetime(1, 1, 1)
        for tz in [timezone.min, timezone.max, timezone.utc]:
            print(tz.tzname(t))
            assert t.replace(tzinfo=tz).tzname() == tz.tzname(t)
            assert t.replace(tzinfo=tz).utcoffset() == tz.utcoffset(t)
            assert t.replace(tzinfo=tz).dst() == tz.dst(t)

    def test_pickle(self):
        for tz in self.ACDT, self.EST, timezone.min, timezone.max:
            for pickler, unpickler, proto in pickle_choices:
                tz_copy = unpickler.loads(pickler.dumps(tz, proto))
                assert tz == tz_copy
        tz = timezone.utc
        for pickler, unpickler, proto in pickle_choices:
            tz_copy = unpickler.loads(pickler.dumps(tz, proto))
            assert tz_copy is tz

    def test_copy(self):
        for tz in self.ACDT, self.EST, timezone.min, timezone.max:
            tz_copy = copy.copy(tz)
            assert tz == tz_copy
        tz = timezone.utc
        tz_copy = copy.copy(tz)
        assert tz_copy is tz

    def test_deepcopy(self):
        for tz in self.ACDT, self.EST, timezone.min, timezone.max:
            tz_copy = copy.deepcopy(tz)
            assert tz == tz_copy
        tz = timezone.utc
        tz_copy = copy.deepcopy(tz)
        assert tz_copy is tz
