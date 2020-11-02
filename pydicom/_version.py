"""Pure python package for DICOM medical file reading and writing."""
import re
from typing import Tuple


__version__: str = '2.1.0'
__version_info__: Tuple[str, str, str] = tuple(
    re.match(r'(\d+\.\d+\.\d+).*', __version__).group(1).split('.')
)


# DICOM Standard version used for:
#   _dicom_dict, _uid_dict and _storage_sopclass_uids
__dicom_version__: str = '2020d'
