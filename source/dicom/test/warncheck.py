# warncheck.py
# 
import warnings
import unittest
from sys import version_info

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
    if version_info < (2, 6):
        all_warnings = []
        def new_warn_explicit(*warn_args):
            all_warnings.append(warn_args[0]) # save only the message here

        saved_warn_explicit = warnings.warn_explicit
        try:
            warnings.warn_explicit = new_warn_explicit
            result = function(*func_args, **func_kwargs)
        finally:
            warnings.warn_explicit = saved_warn_explicit

    else: # python > 2.5
        # Need to import this separately since syntax (using "with" statement) gives errors in python < 2.6
        from dicom.test.version_dep import capture_warnings
        result, all_warnings = capture_warnings(function, *func_args, **func_kwargs)
        
    self.assert_(len(all_warnings)==1, "Expected one warning; got %d" % len(all_warnings))
    self.assert_(warn_msg in all_warnings[0], 
        "Expected warning message '%s...'; got '%s'" % (warn_msg, all_warnings[0]))
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
    