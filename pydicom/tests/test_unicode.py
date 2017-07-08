# test_unicode.py
# -*- coding: utf-8 -*-

import sys
import unittest
from pydicom import dicomio


class UnicodeFilenames(unittest.TestCase):
    def testRead(self):
        """Unicode: Can read a file with unicode characters in name................"""
        uni_name = u'test°'

        # verify first that we could encode file name in this environment
        try:
            _ = uni_name.encode(sys.getfilesystemencoding())
        except UnicodeEncodeError:
            print("SKIP: Environment doesn't support unicode filenames")
            return

        try:
            dicomio.read_file(uni_name)
        except UnicodeEncodeError:
            self.fail("UnicodeEncodeError generated for unicode name")
        # ignore file doesn't exist error
        except IOError:
            pass


if __name__ == "__main__":
    unittest.main()
