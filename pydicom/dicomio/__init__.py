"""Input-output pydicom module"""

from .filereader import read_file
from .filewriter import write_file

__all__ = ['read_file',
           'write_file']
