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

# Get the directory test_dir where the test scripts are
from pkg_resources import Requirement, resource_filename
test_dir = resource_filename(Requirement.parse("pydicom"), "dicom/test")


class MyTestLoader(object):
    def loadTestsFromNames(self, *args):
        # Simplest to change to directory where test_xxx.py files are
        save_dir = os.getcwd()
        if test_dir:
            os.chdir(test_dir)
        filenames = os.listdir(".")
        module_names = [f[:-3] for f in filenames
                        if f.startswith("test") and f.endswith(".py")]

        # Load all the tests
        suite = unittest.TestSuite()
        for module_name in module_names:
            module_dotted_name = "dicom.test." + module_name
            test = unittest.defaultTestLoader.loadTestsFromName(
                module_dotted_name)
            suite.addTest(test)
        os.chdir(save_dir)
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
    save_dir = os.getcwd()
    testfiles_dir = resource_filename(Requirement.parse("pydicom"),
                                      "dicom/testfiles")
    os.chdir(testfiles_dir)
    runner.run(suite)
    os.chdir(save_dir)
