"""Input-output pydicom module"""

from .filereader import dcmread
from .filereader import read_file
from .filereader import read_file_meta_info
from .filereader import read_dicomdir
from .filereader import read_partial
from .filereader import read_preamble
from .filereader import read_dataset

from .filewriter import write_file
from .filewriter import write_file_meta_info
from .filewriter import write_dataset

# create some aliases
dcmwrite = write_file

__all__ = ['dcmread',
           'dcmwrite',
           'read_file',
           'read_file_meta_info',
           'read_dicomdir',
           'read_partial',
           'read_preamble',
           'read_dataset',
           'write_file',
           'write_file_meta_info',
           'write_dataset']
