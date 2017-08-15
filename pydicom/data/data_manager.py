"""pydicom data manager"""

# authors : Vanessa Sochat
#           Guillaume Lemaitre <g.lemaitre58@gmail.com>
# license : See LICENSE

from os import walk
from os.path import abspath, dirname, join, isdir
import fnmatch

DATA_ROOT = abspath(dirname(__file__))


def get_files(bases, pattern="*"):
    """Return all files from a set of sources.

    Parameters
    ----------
    bases : list of str or str
        This can be a list of files and/or folders conforming to some standard
        pattern.

    pattern : str, optional (default="*")
        A string pattern to filter the files. Default is "*" and it will return
        all files.

    Returns
    -------
    files : list of str
        The list of filenames matched.
    """

    # if the user forgot to add them
    pattern = "*" + pattern + "*"

    if not isinstance(bases, (list, tuple)):
        bases = [bases]

    files = []
    for contender in bases:
        if isdir(contender):

            for root, dirnames, filenames in walk(contender):
                for filename in filenames:
                    filename_filter = fnmatch.filter([join(root, filename)],
                                                     pattern)
                    if len(filename_filter):
                        files.append(filename_filter[0])
        else:
            files.append(contender)

    files = [filename for filename in files if not filename.endswith('.py')]

    return files


def get_testdata_files(pattern="*"):
    """Return test data files from pydicom data root.

    Parameters
    ----------
    pattern : str, optional (default="*")
        A string pattern to filter the files

    Returns
    -------
    files : list of str
        The list of filenames matched.

    """

    data_path = join(DATA_ROOT, 'test_files')
    return get_files(bases=data_path, pattern=pattern)


def get_charset_files(pattern="*"):
    """Return charset files from pydicom data root.

    Parameters
    ----------
    pattern : str, optional (default="*")
        A string pattern to filter the files

    Returns
    ----------
    files : list of str
        The list of filenames matched.

    """

    data_path = join(DATA_ROOT, 'charset_files')
    return get_files(bases=data_path, pattern=pattern)
