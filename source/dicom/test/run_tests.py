# run_tests.py
"""Call all the unit test files - all files in test directory starting with 'test'"""
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, relased under an MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

import os
import os.path
import sys
import unittest

test_dir = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()   # save for later
if test_dir:
    os.chdir(test_dir)
filenames = os.listdir(".")
modulenames = [f[:-3] for f in filenames if f.startswith("test") and f.endswith(".py")]

# Load all the tests
suite = unittest.TestSuite()
for module in modulenames:
    print 'Loading ' + module
    # __import__(module)
    test = unittest.defaultTestLoader.loadTestsFromName(module)
    suite.addTest(test)

# Run the tests
verbosity = 1
if len(sys.argv) > 1 and (sys.argv[1]=="-v" or sys.argv[1]=="--verbose"):
    verbosity = 2
runner = unittest.TextTestRunner(verbosity=verbosity)
os.chdir("../testfiles")
runner.run(suite)
os.chdir(save_dir)
