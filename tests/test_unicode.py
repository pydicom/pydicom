# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for unicode."""

import sys


from pydicom import dcmread


class TestUnicodeFilenames:
    def test_read(self):
        """Unicode: Can read a file with unicode characters in name..."""
        uni_name = "test°"

        # verify first that we could encode file name in this environment
        try:
            _ = uni_name.encode(sys.getfilesystemencoding())
        except UnicodeEncodeError:
            print("SKIP: Environment doesn't support unicode filenames")
            return

        try:
            dcmread(uni_name)
        except UnicodeEncodeError:
            self.fail("UnicodeEncodeError generated for unicode name")
        # ignore file doesn't exist error
        except OSError:
            pass
