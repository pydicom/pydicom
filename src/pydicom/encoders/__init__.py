# TODO: remove module in v4.0
from typing import Any

from pydicom import config
from pydicom.misc import warn_and_log
from pydicom.pixels import get_encoder as _get_encoder
from pydicom.pixels.encoders import RLELosslessEncoder as _rle_encoder


_DEPRECATED = {
    "get_encoder": _get_encoder,
    "RLELosslessEncoder": _rle_encoder,
}


def __getattr__(name: str) -> Any:
    if name in _DEPRECATED and not config._use_future:
        msg = (
            f"The 'pydicom.encoders' module will be removed in v4.0, please use "
            f"'from pydicom.pixels import {name}' instead"
        )
        warn_and_log(msg, DeprecationWarning)
        return _DEPRECATED[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
