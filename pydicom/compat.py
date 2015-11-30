# compat.py
"""Compatibility functions for python 2 vs later versions"""
# Copyright (c) 2014 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://github.com/darcymason/pydicom

# These are largely modeled on Armin Ronacher's porting advice
# at http://lucumr.pocoo.org/2013/5/21/porting-to-python-3-redux/

import sys

in_py2 = sys.version_info[0] == 2
in_PyPy = 'PyPy' in sys.version

# Text types
# In py3+, the native text type ('str') is unicode
# In py2, str can be either bytes or text.
if in_py2:
    text_type = unicode
    string_types = (str, unicode)
else:
    text_type = str
    string_types = (str,)

if in_py2:
    # Have to run through exec as the code is a syntax error in py 3
    exec('def reraise(tp, value, tb):\n raise tp, value, tb')
else:
    def reraise(tp, value, tb):
        raise value.with_traceback(tb)
