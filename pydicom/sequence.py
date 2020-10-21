# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Define the Sequence class, which contains a sequence DataElement's items.

Sequence is a list of pydicom Dataset objects.
"""
from typing import Iterable, Optional, List, cast, Union, overload
from typing import Sequence as SeqType
import weakref

from pydicom.dataset import Dataset
from pydicom.multival import MultiValue


def validate_dataset(elem: object) -> object:
    """Check that `elem` is a :class:`~pydicom.dataset.Dataset` instance."""
    if not isinstance(elem, Dataset):
        raise TypeError('Sequence contents must be Dataset instances.')

    return elem


class Sequence(MultiValue):
    """Class to hold multiple :class:`~pydicom.dataset.Dataset` in a
    :class:`list`.

    This class is derived from :class:`~pydicom.multival.MultiValue`
    and as such enforces that all items added to the list are
    :class:`~pydicom.dataset.Dataset` instances. In order to do this,
    a validator is substituted for `type_constructor` when constructing the
    :class:`~pydicom.multival.MultiValue` super class.
    """

    def __init__(self, iterable: Optional[Iterable[Dataset]] = None) -> None:
        """Initialize a list of :class:`~pydicom.dataset.Dataset`.

        Parameters
        ----------
        iterable : list-like of dataset.Dataset, optional
            An iterable object (e.g. :class:`list`, :class:`tuple`) containing
            :class:`~pydicom.dataset.Dataset`. If not used then an empty
            :class:`Sequence` is generated.
        """
        # We add this extra check to throw a relevant error. Without it, the
        # error will be simply that a Sequence must contain Datasets (since a
        # Dataset IS iterable). This error, however, doesn't inform the user
        # that the actual issue is that their Dataset needs to be INSIDE an
        # iterable object
        if isinstance(iterable, Dataset):
            raise TypeError('The Sequence constructor requires an iterable')

        # the parent dataset
        self._parent: "Optional[weakref.ReferenceType[Dataset]]" = None

        # validate_dataset is used as a pseudo type_constructor
        self._list: List[Dataset] = []
        # If no inputs are provided, we create an empty Sequence
        super().__init__(validate_dataset, iterable or [])

    def append(self, val: Dataset) -> None:
        """Append a :class:`~pydicom.dataset.Dataset` to the sequence."""
        super().append(val)
        val.parent = self._parent

    def insert(self, position: int, val: Dataset) -> None:
        """Insert a :class:`~pydicom.dataset.Dataset` into the sequence."""
        super().insert(position, val)
        val.parent = self._parent

    @property
    def parent(self) -> "Optional[weakref.ReferenceType[Dataset]]":
        """Return a weak reference to the parent
        :class:`~pydicom.dataset.Dataset`.

        .. versionadded:: 1.3

        .. versionchanged:: 1.4

            Returned value is a weak reference to the parent ``Dataset``.
        """
        return self._parent

    @parent.setter
    def parent(self, value: Dataset) -> None:
        """Set the parent :class:`~pydicom.dataset.Dataset` and pass it to all
        :class:`Sequence` items.

        .. versionadded:: 1.3
        """
        if value != self._parent:
            self._parent = weakref.ref(value)
            for item in self._list:
                item.parent = self._parent

    @overload
    def __setitem__(self, i: int, val: Dataset) -> None: pass

    @overload
    def __setitem__(self, i: slice, val: SeqType[Dataset]) -> None: pass

    def __setitem__(
        self, i: Union[slice, int], val: Union[SeqType[Dataset], Dataset]
    ) -> None:
        """Set the parent :class:`~pydicom.dataset.Dataset` to the new
        :class:`Sequence` item
        """
        super().__setitem__(i, val)
        if isinstance(i, slice):
            for ds in val:
                ds.parent = self._parent
        else:
            val.parent = self._parent

    def __str__(self) -> str:
        """String description of the Sequence."""
        return f"[{''.join([str(x) for x in self])}]"

    def __repr__(self) -> str:
        """String representation of the Sequence."""
        return f"<{self.__class__.__name__}, length {len(self)}>"
