# attribute.py
"""Deprecated -- to be removed in pydicom 1.0. Use dataelem module instead
"""
#
# Copyright (c) 2008 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com
#

# Deprecated, but load old names into this namespace so older code will still work
import warnings
warnings.warn("dicom.attribute is deprecated and will be removed in pydicom 1.0. Use dicom.dataelem instead.", DeprecationWarning)

from dicom.dataelem import *