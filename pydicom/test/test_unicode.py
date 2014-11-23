# test_unicode.py
# -*- coding: utf-8 -*-

import dicom
import unittest


class UnicodeFilenames(unittest.TestCase):
    def testRead(self):
        """Unicode: Can read a file with unicode characters in name................"""
        uni_name = u'test°'
        try:
            dicom.read_file(uni_name)
        except UnicodeEncodeError:
            self.fail("UnicodeEncodeError generated for unicode name")
        # ignore file doesn't exist error
        except IOError:
            pass


if __name__ == "__main__":
    unittest.main()
