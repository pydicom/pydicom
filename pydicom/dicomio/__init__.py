"""Input-output pydicom module"""

from .filereader import read_file
from .filereader import read_file_meta_info
from .filereader import read_partial
from .filereader import read_preamble
from .filereader import read_dataset

from .filewriter import write_file
from .filewriter import write_file_meta_info
from .filewriter import write_dataset

__all__ = ['read_file',
           'read_file_meta_info',
           'read_partial',
           'read_preamble',
           'read_dataset',
           'write_file',
           'write_file_meta_info',
           'write_dataset']
