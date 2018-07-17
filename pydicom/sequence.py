# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Define the Sequence class, which contains a sequence DataElement's items.

Sequence is a list of pydicom Dataset objects.
"""

from pydicom.dataset import Dataset
from pydicom.multival import MultiValue


def validate_dataset(elem):
    """Check that `elem` is a Dataset instance."""
    if not isinstance(elem, Dataset):
        raise TypeError('Sequence contents must be Dataset instances.')

    return elem


class Sequence(MultiValue):
    """Class to hold multiple Datasets in a list.

    This class is derived from MultiValue and as such
    enforces that all items added to the list are Dataset
    instances. In order to due this, a validator is
    substituted for type_constructor when constructing
    the MultiValue super class
    """

    def __init__(self, iterable=None):
        """Initialize a list of Datasets.

        Parameters
        ----------
        iterable : list-like of pydicom.dataset.Dataset, optional
            An iterable object (e.g. list, tuple) containing
            Datasets. If not used then an empty Sequence is generated.
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
        """String description of the Sequence."""
        lines = [str(x) for x in self]
        return "[" + "".join(lines) + "]"

    def __repr__(self):
        """String representation of the Sequence."""
        formatstr = "<%(classname)s, length %(count)d>"
        return formatstr % {
            'classname': self.__class__.__name__,
            'count': len(self)
        }
