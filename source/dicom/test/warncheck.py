# warncheck.py
# 
import warnings
import unittest
#PZ this clone ignores everything below 2.5
# Need to import this separately since syntax (using "with" statement) gives errors in python < 2.6
from dicom.test.version_dep import capture_warnings
#from sys import version_info
import sys
if sys.hexversion >= 0x02060000 and sys.hexversion < 0x03000000: 
    inPy26 = True
    inPy3 = False
elif sys.hexversion >= 0x03000000: 
    inPy26 = False
    inPy3 = True
#    basestring = str
#PZ PEP0237        
#    _MAXLONG_ = 0xFFFFFFFF
#    from io import BytesIO # tried cStringIO but wouldn't let me derive class from it.    
else: 
#PZ unsupported python version why we are here, should fail earlier
    pass
    
def assertWarns(self, warn_msg, function, *func_args, **func_kwargs):
    """
    Check that the function generates the expected warning
    with the arguments given.
    
    warn_msg -- part of the warning string, any thrown warnings should contain this
    function -- the function to call (expected to issue a warning)
    func_args -- positional arguments to the function
    func_kwargs -- keyword arguments to the function
    
    Return the function return value.
    """
    result, all_warnings = capture_warnings(function, *func_args, **func_kwargs)
    
    self.assertTrue(len(all_warnings)==1, "Expected one warning; got {}".format( len(all_warnings)))
    self.assertTrue(warn_msg in all_warnings[0], 
        "Expected warning message '{}...'; got '{}'".format(warn_msg, all_warnings[0]))
    return result
    
def test_warning(the_warning):
    if the_warning:
        warnings.warn(the_warning)

class WarnTests(unittest.TestCase):
    def testWarn(self):
        """Test that assertWarns works as expected"""
        assertWarns(self, "Look", test_warning, "Look out")

if __name__ == "__main__":
    unittest.main()
    