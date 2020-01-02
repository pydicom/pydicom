# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
"""Unit tests for the pydicom.config module."""

import logging
import sys

import pytest

from pydicom import dcmread
from pydicom.config import debug
from pydicom.data import get_testdata_files


DS_PATH = get_testdata_files("CT_small.dcm")[0]
PYTEST = [int(x) for x in pytest.__version__.split('.')]


@pytest.mark.skipif(PYTEST[:2] < [3, 4], reason='no caplog')
class TestDebug(object):
    """Tests for config.debug()."""
    def setup(self):
        self.logger = logging.getLogger('pydicom')

    def teardown(self):
        # Reset to just NullHandler
        self.logger.handlers = [self.logger.handlers[0]]

    def test_default(self, caplog):
        """Test that the default logging handler is a NullHandler."""
        assert 1 == len(self.logger.handlers)
        assert isinstance(self.logger.handlers[0], logging.NullHandler)

        with caplog.at_level(logging.DEBUG, logger='pydicom'):
            ds = dcmread(DS_PATH)

            assert "Call to dcmread()" not in caplog.text
            assert "Reading File Meta Information preamble..." in caplog.text
            assert "Reading File Meta Information prefix..." in caplog.text
            assert "00000080: 'DICM' prefix found" in caplog.text

    def test_debug_on_handler_null(self, caplog):
        """Test debug(True, False)."""
        debug(True, False)
        assert 1 == len(self.logger.handlers)
        assert isinstance(self.logger.handlers[0], logging.NullHandler)

        with caplog.at_level(logging.DEBUG, logger='pydicom'):
            ds = dcmread(DS_PATH)

            assert "Call to dcmread()" in caplog.text
            assert "Reading File Meta Information preamble..." in caplog.text
            assert "Reading File Meta Information prefix..." in caplog.text
            assert "00000080: 'DICM' prefix found" in caplog.text
            msg = (
                "0000989c: fc ff fc ff 4f 42 00 00 7e 00 00 00    "
                "(fffc, fffc) OB Length: 126"
            )
            assert msg in caplog.text

    def test_debug_off_handler_null(self, caplog):
        """Test debug(False, False)."""
        debug(False, False)
        assert 1 == len(self.logger.handlers)
        assert isinstance(self.logger.handlers[0], logging.NullHandler)

        with caplog.at_level(logging.DEBUG, logger='pydicom'):
            ds = dcmread(DS_PATH)

            assert "Call to dcmread()" not in caplog.text
            assert "Reading File Meta Information preamble..." in caplog.text
            assert "Reading File Meta Information prefix..." in caplog.text
            assert "00000080: 'DICM' prefix found" in caplog.text

    def test_debug_on_handler_stream(self, caplog):
        """Test debug(True, True)."""
        debug(True, True)
        assert 2 == len(self.logger.handlers)
        assert isinstance(self.logger.handlers[0], logging.NullHandler)
        assert isinstance(self.logger.handlers[1], logging.StreamHandler)

        with caplog.at_level(logging.DEBUG, logger='pydicom'):
            ds = dcmread(DS_PATH)

            assert "Call to dcmread()" in caplog.text
            assert "Reading File Meta Information preamble..." in caplog.text
            assert "Reading File Meta Information prefix..." in caplog.text
            assert "00000080: 'DICM' prefix found" in caplog.text
            msg = (
                "0000989c: fc ff fc ff 4f 42 00 00 7e 00 00 00    "
                "(fffc, fffc) OB Length: 126"
            )
            assert msg in caplog.text

    def test_debug_off_handler_stream(self, caplog):
        """Test debug(False, True)."""
        debug(False, True)
        assert 2 == len(self.logger.handlers)
        assert isinstance(self.logger.handlers[0], logging.NullHandler)
        assert isinstance(self.logger.handlers[1], logging.StreamHandler)

        with caplog.at_level(logging.DEBUG, logger='pydicom'):
            ds = dcmread(DS_PATH)

            assert "Call to dcmread()" not in caplog.text
            assert "Reading File Meta Information preamble..." in caplog.text
            assert "Reading File Meta Information prefix..." in caplog.text
            assert "00000080: 'DICM' prefix found" in caplog.text
