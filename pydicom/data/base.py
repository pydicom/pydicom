"""pydicom data manager"""
#
# Copyright (c) 2008-2012 Darcy Mason
# Copyright (c) 2017 pydicom AUTHORS
# This file is part of pydicom, released under a modified MIT license.
#    See the file LICENSE included with this distribution, also
#    available at https://github.com/pydicom/pydicom
#

import fnmatch
import os

def get_datadir():
    '''get the data directory base
    '''
    return os.path.abspath(os.path.dirname(__file__))


def get_dataset(dataset=None, pattern=None, return_base=False):
    '''get_dataset will return data provided by pydicom
    based on a user-provided label.
    '''
    here = get_datadir()
    valid_datasets = {'charset': '%s/charset_files' % here,
                      'test': '%s/test_files' % here}

    if dataset is not None:

        dataset = os.path.splitext(dataset)[0].lower()
        if dataset in valid_datasets:
            if return_base is True:
                return valid_datasets[dataset]
            return get_files(bases=valid_datasets[dataset],
                             pattern=pattern)

    print("Valid datasets include: %s"
          % (', '.join(list(valid_datasets.keys()))))


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
