"""Pure python package for DICOM medical file reading and writing."""
import re


__version__ = '2.0.0'
__version_info__ = tuple(
    re.match(r'(\d+\.\d+\.\d+).*', __version__).group(1).split('.'))
