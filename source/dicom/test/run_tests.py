# run_tests.py
# Call all the unit test files - all files in test directory
#    starting with 'test'

import os
import os.path
import sys
import unittest

test_dir = os.path.dirname(sys.argv[0])
save_dir = os.getcwd()   # save for later
if test_dir:
    os.chdir(test_dir)
filenames = os.listdir(test_dir)
modulenames = [f[:-3] for f in filenames if f[:4].lower()=="test" and f[-3:]==".py"]

# Load all the tests
suite = unittest.TestSuite()
for module in modulenames:
    print 'Loading ' + module
    __import__(module)
    test = unittest.defaultTestLoader.loadTestsFromName(module)
    suite.addTest(test)

# Run the testsrunner = unittest.TextTestRunner(verbosity=2)runner.run(suite)

os.chdir(save_dir)