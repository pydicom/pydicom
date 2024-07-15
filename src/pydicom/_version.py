"""Pure python package for DICOM medical file reading and writing."""

import re
from typing import cast
from re import Match
from importlib.metadata import version

__version__: str = version("pydicom")

result = cast(Match[str], re.match(r"(\d+\.\d+\.\d+).*", __version__))
__version_info__ = tuple(result.group(1).split("."))


# DICOM Standard version used for:
#   _dicom_dict.py, _uid_dict.py and uid.py
__dicom_version__: str = "2024c"


# DICOM Standard version used for:
#   sr/_cid_dict.py
#   sr/_concepts_dict.py
#   sr/_snomed_dict.py
__concepts_version__: str = "2024c"
