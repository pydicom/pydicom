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

if in_py2:
    text_type = unicode
    string_types = (str, unicode)
else:
    text_type = str
    string_types = (str,)
