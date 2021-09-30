"""Pure python package for DICOM medical file reading and writing."""
import re
from typing import cast, Match


__version__: str = '2.2.2'

result = cast(Match[str], re.match(r'(\d+\.\d+\.\d+).*', __version__))
__version_info__ = tuple(result.group(1).split('.'))


# DICOM Standard version used for:
#   _dicom_dict, _uid_dict and _storage_sopclass_uids
__dicom_version__: str = '2021d'
