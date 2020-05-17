import pytest

from pydicom.sr.coding import Code
from pydicom.uid import UID


class TestCode:
    def setup(self):
        self._value = "373098007"
        self._meaning = "Mean Value of population"
        self._scheme_designator = "SCT"

    def test_construction_kwargs(self):
        c = Code(
            value=self._value,
            scheme_designator=self._scheme_designator,
            meaning=self._meaning,
        )
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version is None

    def test_construction_kwargs_optional(self):
        version = "v1.0"
        c = Code(
            value=self._value,
            scheme_designator=self._scheme_designator,
            meaning=self._meaning,
            scheme_version=version,
        )
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version == version

    def test_construction_args(self):
        c = Code(self._value, self._scheme_designator, self._meaning)
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version is None

    def test_construction_args_optional(self):
        version = "v1.0"
        c = Code(self._value, self._scheme_designator, self._meaning, version)
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version == version

    def test_equal(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code(self._value, self._scheme_designator, self._meaning)
        assert c1 == c2

    def test_not_equal(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code("373099004", "SCT", "Median Value of population")
        assert c1 != c2

    def test_equal_ignore_meaning(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code(self._value, self._scheme_designator, "bla bla bla")
        assert c1 == c2

    def test_equal_equivalent_coding(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code("R-00317", "SRT", self._meaning)
        assert c1 == c2
