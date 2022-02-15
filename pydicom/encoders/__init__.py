import sys
from typing import Any
import warnings

from pydicom.pixels import (
    get_encoder as _get_encoder,
    RLELosslessEncoder as _RLELosslessEncoder,
)


_deprecations = {
    "get_encoder": _get_encoder,
    "RLELosslessEncoder": _RLELosslessEncoder,
}

def __getattr__(name: str) -> Any:
    if name in _deprecations:
        warnings.warn(
            f"Importing '{name}' from 'pydicom.encoders' is "
            f"deprecated, import from 'pydicom.pixels' instead",
            DeprecationWarning,
        )

        return _deprecations[name]

    raise AttributeError(f"module {__name__} has no attribute {name}")


if sys.version_info[:2] < (3, 7):
    get_encoder = _get_encoder
    RLELosslessEncoder = _RLELosslessEncoder
