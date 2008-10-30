# run_tests.py
"""Call all the unit test files - all files in test directory starting with 'test'"""
# Copyright 2008, Darcy Mason
# This file is part of pydicom.
#
# pydicom is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pydicom is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (license.txt) for more details

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
runner = unittest.TextTestRunner(verbosity=2)
os.chdir("../testfiles")
runner.run(suite)
os.chdir(save_dir)
