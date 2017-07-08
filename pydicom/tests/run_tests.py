# run_tests.py
"""Call all the unit test files in the test directory starting with 'test'"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import os
import os.path
import sys
import unittest
import glob

# Get the directory test_dir where the test scripts are
test_dir = os.path.dirname(__file__)


class MyTestLoader(object):
    def loadTestsFromNames(self, *args):
        suite = unittest.TestSuite()
        try:
            suite.addTests(unittest.defaultTestLoader.discover(test_dir))
        except AttributeError:
            try:
                import unittest2
            except ImportError:
                print("Unittest2 is needed for test discovery with python 2.6")
                raise
            else:
                suite.addTests(unittest2.defaultTestLoader.discover(test_dir))

        return suite

if __name__ == "__main__":
    # Get the tests -- in format used by Distribute library
    #        to run under 'python setup.py test'
    suite = MyTestLoader().loadTestsFromNames()

    # Run the tests
    verbosity = 1
    args = sys.argv
    if len(args) > 1 and (args[1] == "-v" or args[1] == "--verbose"):
        verbosity = 2
    runner = unittest.TextTestRunner(verbosity=verbosity)

    # Switch directories to test DICOM files, used by many of the tests
    testfiles_dir = os.path.join(test_dir, 'test_files')
    result = runner.run(suite)

    # Return an exit code corresponding to the number of issues found
    sys.exit(len(result.failures) + len(result.errors))
