"""pydicom data manager utils"""
#
# Copyright (c) 2008-2012 Darcy Mason
# Copyright (c) 2017 pydicom AUTHORS
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom
#

import os
import fnmatch


def get_files(bases, pattern=None):
    """Return all files from a set of sources.

    Parameters
    ----------
    bases : list or file-like
            This can be a list of files and/or folders conforming
            to some standard pattern.
    pattern : string for fnmatch
            A string pattern to filter the files

    Returns
    ----------
    files : list of files recursively found
            from the bases
    """

    if pattern is None:
        pattern = "*"

    if not isinstance(bases, list):
        bases = [bases]

    files = []
    for contender in bases:
        if os.path.isdir(contender):

            for root, dirnames, filenames in os.walk(contender):
                for filename in fnmatch.filter(filenames, pattern):
                    files.append(os.path.join(root, filename))

            files.extend(data_files)
        else:
            files.append(contender)

    return files
