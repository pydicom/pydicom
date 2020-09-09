
import sys

import pydicom.overlays.numpy_handler as _np_handler

globals()['numpy_handler'] = _np_handler
# Add to cache - needed for pytest
sys.modules['pydicom.overlay_data_handlers.numpy_handler'] = _np_handler
