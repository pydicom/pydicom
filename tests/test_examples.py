"""Tests for the examples module."""

from pathlib import Path

import pytest

import pydicom
from pydicom import examples, FileDataset
from pydicom.examples import ct


class TestExamples:
    def test_exception(self):
        """Test accessing missing module attribute raises."""
        msg = "module 'pydicom.examples' has no attribute 'foo'"
        with pytest.raises(AttributeError, match=msg):
            examples.foo

    def test_access(self):
        """Test dataset access works OK."""
        assert isinstance(examples.ct, FileDataset)
        assert isinstance(examples.dicomdir, FileDataset)
        assert isinstance(examples.jpeg2k, FileDataset)
        assert isinstance(examples.mr, FileDataset)
        assert isinstance(examples.no_meta, FileDataset)
        assert isinstance(examples.overlay, FileDataset)
        assert isinstance(examples.palette_color, FileDataset)
        assert isinstance(examples.rgb_color, FileDataset)
        assert isinstance(examples.rt_dose, FileDataset)
        assert isinstance(examples.rt_plan, FileDataset)
        assert isinstance(examples.rt_ss, FileDataset)
        assert isinstance(examples.waveform, FileDataset)

    def test_module_characteristics(self):
        """Test characteristics of the attributes."""
        assert pydicom.examples.ct == examples.ct
        assert pydicom.examples.ct == ct
        assert ct == examples.ct

        # New instance every time the attribute is accessed
        assert examples.ct is not examples.ct
        assert ct is ct  # noqa
        assert isinstance(ct, FileDataset)
        assert ct.PatientName == "CompressedSamples^CT1"

    def test_get_path(self):
        """Test get_path()"""
        path = examples.get_path("ct")
        assert isinstance(path, Path)
        assert path.name == "CT_small.dcm"

        msg = "No example dataset exists with the name 'foo'"
        with pytest.raises(ValueError, match=msg):
            examples.get_path("foo")
