# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Compatibility fixes for older version of python."""

import sys

from datetime import datetime, tzinfo, timedelta

if sys.version_info[0] < 3:
    class timezone(tzinfo):
        """Backport of datetime.timezone.

        Notes
        -----
        Backport of datetime.timezone for Python 2.7, from Python 3.6
        documentation (https://tinyurl.com/z4cegu9), copyright Python Software
        Foundation (https://docs.python.org/3/license.html)

        """
        __slots__ = '_offset', '_name'

        # Sentinel value to disallow None
        _Omitted = object()

        def __new__(cls, offset, name=_Omitted):
            if not isinstance(offset, timedelta):
                raise TypeError("offset must be a timedelta")
            if name is cls._Omitted:
                if not offset:
                    return cls.utc
                name = None
            elif not isinstance(name, str):
                raise TypeError("name must be a string")
            if not cls._minoffset <= offset <= cls._maxoffset:
                raise ValueError("offset must be a timedelta "
                                 "strictly between -timedelta(hours=24) and "
                                 "timedelta(hours=24).")
            if (offset.microseconds != 0 or offset.seconds % 60 != 0):
                raise ValueError("offset must be a timedelta "
                                 "representing a whole number of minutes")
            return cls._create(offset, name)

        @classmethod
        def _create(cls, offset, name=None):
            self = tzinfo.__new__(cls)
            self._offset = offset
            self._name = name
            return self

        def __getinitargs__(self):
            """pickle support"""
            if self._name is None:
                return (self._offset,)
            return (self._offset, self._name)

        def __eq__(self, other):
            if type(other) != timezone:
                return False
            return self._offset == other._offset

        def __lt__(self, other):
            raise TypeError("'<' not supported between instances of"
                            " 'datetime.timezone' and 'datetime.timezone'")

        def __hash__(self):
            return hash(self._offset)

        def __repr__(self):
            if self is self.utc:
                return '%s.%s.utc' % (self.__class__.__module__,
                                      self.__class__.__name__)
            if self._name is None:
                return "%s.%s(%r)" % (self.__class__.__module__,
                                      self.__class__.__name__,
                                      self._offset)
            return "%s.%s(%r, %r)" % (self.__class__.__module__,
                                      self.__class__.__name__,
                                      self._offset, self._name)

        def __str__(self):
            return self.tzname(None)

        def utcoffset(self, dt):
            if isinstance(dt, datetime) or dt is None:
                return self._offset
            raise TypeError("utcoffset() argument must be a datetime instance"
                            " or None")

        def tzname(self, dt):
            if isinstance(dt, datetime) or dt is None:
                if self._name is None:
                    return self._name_from_offset(self._offset)
                return self._name
            raise TypeError("tzname() argument must be a datetime instance"
                            " or None")

        def dst(self, dt):
            if isinstance(dt, datetime) or dt is None:
                return None
            raise TypeError("dst() argument must be a datetime instance"
                            " or None")

        def fromutc(self, dt):
            if isinstance(dt, datetime):
                if dt.tzinfo is not self:
                    raise ValueError("fromutc: dt.tzinfo "
                                     "is not self")
                return dt + self._offset
            raise TypeError("fromutc() argument must be a datetime instance"
                            " or None")

        _maxoffset = timedelta(hours=23, minutes=59)
        _minoffset = -_maxoffset

        @staticmethod
        def _name_from_offset(delta):
            if not delta:
                return 'UTC'
            if delta < timedelta(0):
                sign = '-'
                delta = -delta
            else:
                sign = '+'
            hours, rest = divmod(delta.total_seconds(), 3600)
            hours = int(hours)
            minutes = rest // timedelta(minutes=1).total_seconds()
            minutes = int(minutes)
            return 'UTC{}{:02d}:{:02d}'.format(sign, hours, minutes)

    timezone.utc = timezone._create(timedelta(0))
    timezone.min = timezone._create(timezone._minoffset)
    timezone.max = timezone._create(timezone._maxoffset)
    _EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

else:
    from datetime import timezone
