# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Compatibility functions for previous Python 2 support"""

# These are largely modeled on Armin Ronacher's porting advice
# at http://lucumr.pocoo.org/2013/5/21/porting-to-python-3-redux/

import sys

in_PyPy = 'PyPy' in sys.version

# Text types
# In py3+, the native text type ('str') is unicode
text_type = str
string_types = (str, )
char_types = (str, bytes)
number_types = (int, )
int_type = int
