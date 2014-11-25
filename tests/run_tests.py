# run_tests.py
"""Call all the unit test files in the test directory starting with 'test'"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import os
import os.path
import sys
import unittest
import glob

# Get the directory test_dir where the test scripts are
test_dir = os.path.dirname(__file__)


class MyTestLoader(object):
    def loadTestsFromNames(self, *args):
        # Simplest to change to directory where test_xxx.py files are
        filenames = glob.glob(os.path.join(test_dir, 'test*.py'))
        filenames = [os.path.basename(fname) for fname in filenames]
        module_names = [os.path.splitext(fname)[0] for fname in filenames]

        # Load all the tests
        suite = unittest.TestSuite()
        for module_name in module_names:
            module_dotted_name = "tests." + module_name
            test = unittest.defaultTestLoader.loadTestsFromName(
                module_dotted_name)
            suite.addTest(test)
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
    runner.run(suite)
