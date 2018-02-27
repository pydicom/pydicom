"""
A rudimentary shim module to import all items from pydicom space under the
space of a dicom module.

Note that this shim will be removed completely in 1.2 release of pydicom.
"""

import pydicom as _pydicom
import warnings as _warn
_warn.warn("'dicom' module is just a thin compatibility layer.  "
           "Import/use 'pydicom' instead.  This module will be completely "
           "removed in pydicom 1.2", DeprecationWarning)

locals().update(_pydicom.__dict__)
