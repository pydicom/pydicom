# attribute.py
"""Deprecated -- to be removed in pydicom 1.0. Use dataelem module instead
"""

# Deprecated, but load old names into this namespace so older code will still work
import warnings
warnings.warn("dicom.attribute is deprecated and will be removed in pydicom 1.0. Use dicom.dataelem instead.", DeprecationWarning)

from dicom.dataelem import *