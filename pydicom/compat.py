# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Compatibility functions for python 2 vs later versions"""

import sys

in_py2 = sys.version_info[0] == 2
in_PyPy = 'PyPy' in sys.version

# Text types
# In py3+, the native text type ('str') is unicode
# In py2, str can be either bytes or text.
if in_py2:
    text_type = unicode
    string_types = (str, unicode)
    number_types = (int, long)
    int_type = long
else:
    text_type = str
    string_types = (str, )
    number_types = (int, )
    int_type = int

if in_py2:
    # Have to run through exec as the code is a syntax error in py 3
    exec('def reraise(tp, value, tb):\n raise tp, value, tb')
else:

    def reraise(tp, value, tb):
        raise value.with_traceback(tb)
