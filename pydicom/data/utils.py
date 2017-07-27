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


def recursive_find(base, pattern=None):
    '''recursively find files based on a pattern
    '''
    if pattern is None:
        pattern = "*"
    files = []
    for root, dirnames, filenames in os.walk(base):
        for filename in fnmatch.filter(filenames, pattern):
            files.append(os.path.join(root, filename))

    return files


def get_files(bases, pattern=None):
    '''return all files for a valid dataset, which may
    be a list of files and/or folders conforming to some
    pattern.
    '''
    if not isinstance(bases, list):
        bases = [bases]

    files = []
    for contender in bases:
        if os.path.isdir(contender):
            data_files = recursive_find(contender,
                                        pattern=pattern)
            files.extend(data_files)
        else:
            files.append(contender)

    return files
