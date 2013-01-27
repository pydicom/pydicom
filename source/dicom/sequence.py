# sequence.py
"""Hold the Sequence class, which stores a dicom sequence (list of Datasets)"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from dicom.dataset import Dataset
from dicom.multival import MultiValue


def validate_dataset(elem):
    """Ensures that the value is a Dataset instance"""
    if not isinstance(elem, Dataset):
        raise TypeError('Sequence contents must be a Dataset instance')

    return elem


class Sequence(MultiValue):
    """Class to hold multiple Datasets in a list

    This class is derived from MultiValue and as such enforces that all items
    added to the list are Dataset instances. In order to due this, a validator
    is substituted for type_constructor when constructing the MultiValue super
    class
    """
    def __init__(self, iterable=None):
        """Initialize a list of Datasets

        :param iterable: an iterable (e.g. list, tuple) of Datasets. If no
                        value is provided, an empty Sequence is generated
        """
        # We add this extra check to throw a relevant error. Without it, the
        # error will be simply that a Sequence must contain Datasets (since a
        # Dataset IS iterable). This error, however, doesn't inform the user
        # that the actual issue is that their Dataset needs to be INSIDE an
        # iterable object
        if isinstance(iterable, Dataset):
            raise TypeError('The Sequence constructor requires an iterable')

        # If no inputs are provided, we create an empty Sequence
        if not iterable:
            iterable = list()

        # validate_dataset is used as a pseudo type_constructor
        super(Sequence, self).__init__(validate_dataset, iterable)

    def __str__(self):
        lines = [str(x) for x in self]
        return "[" + "".join(lines) + "]"

    def __repr__(self):
        """Sequence-specific string representation"""
        formatstr = "<%(classname)s, length %(count)d, at %(id)X>"
        return formatstr % {'classname': self.__class__.__name__,
                            'id': id(self), 'count': len(self)}
