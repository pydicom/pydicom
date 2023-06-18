# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Define the Sequence class, which contains a sequence DataElement's items.

Sequence is a list of pydicom Dataset objects.
"""
from copy import deepcopy
from typing import (
    Iterable, Optional, List, cast, Union, overload, MutableSequence,
    Dict, Any)
import weakref
import warnings

from pydicom import config
from pydicom.dataset import Dataset
from pydicom.multival import MultiValue


def validate_dataset(elem: object) -> Dataset:
    """Check that `elem` is a :class:`~pydicom.dataset.Dataset` instance."""
    if not isinstance(elem, Dataset):
        raise TypeError('Sequence contents must be Dataset instances.')

    return elem


class Sequence(MultiValue[Dataset]):
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
        self._parent_dataset: "Optional[weakref.ReferenceType[Dataset]]" = None

        # validate_dataset is used as a pseudo type_constructor
        self._list: List[Dataset] = []
        # If no inputs are provided, we create an empty Sequence
        super().__init__(validate_dataset, iterable or [])
        for ds in self:
            ds.parent_seq = self  # type: ignore
        self.is_undefined_length: bool

    def append(self, val: Dataset) -> None:  # type: ignore[override]
        """Append a :class:`~pydicom.dataset.Dataset` to the sequence."""
        super().append(val)
        val.parent_seq = self  # type: ignore

    def extend(self, val: Iterable[Dataset]) -> None:  # type: ignore[override]
        """Extend the :class:`~pydicom.sequence.Sequence` using an iterable
        of :class:`~pydicom.dataset.Dataset` instances.
        """
        if isinstance(val, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        super().extend(val)
        for ds in val:
            ds.parent_seq = self  # type: ignore

    def __deepcopy__(self, memo: Optional[Dict[int, Any]]) -> "Sequence":
        cls = self.__class__
        copied = cls.__new__(cls)
        if memo is not None:
            memo[id(self)] = copied
        copied.__dict__.update(deepcopy(self.__dict__, memo))
        for ds in copied:
            ds.parent_seq = copied  # type:ignore
        return copied

    def __iadd__(    # type: ignore[override]
        self, other: Iterable[Dataset]
    ) -> MutableSequence[Dataset]:
        """Implement Sequence() += [Dataset()]."""
        if isinstance(other, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        result = super().__iadd__(other)
        for ds in other:
            ds.parent_seq = self  # type: ignore

        return result

    def insert(    # type: ignore[override]
        self, position: int, val: Dataset
    ) -> None:
        """Insert a :class:`~pydicom.dataset.Dataset` into the sequence."""
        super().insert(position, val)
        val.parent_seq = self  # type: ignore

    @property
    def parent_dataset(self) -> "Optional[weakref.ReferenceType[Dataset]]":
        """Return a weak reference to the parent
        :class:`~pydicom.dataset.Dataset`.

        .. versionadded:: 2.4

            Returned value is a weak reference to the parent ``Dataset``.
        """
        return self._parent_dataset

    @parent_dataset.setter
    def parent_dataset(self, value: Dataset) -> None:
        """Set the parent :class:`~pydicom.dataset.Dataset`

        .. versionadded:: 2.4
        """
        if value != self._parent_dataset:
            self._parent_dataset = weakref.ref(value)

    @property
    def parent(self) -> "Optional[weakref.ReferenceType[Dataset]]":
        """Return a weak reference to the parent Dataset

        .. deprecated:: 2.4
        """
        if config._use_future:
            raise AttributeError("Future: Sequence.parent is removed in v3.x")
        else:
            warnings.warn(
                "Sequence.parent will be removed in pydicom 3.0",
                DeprecationWarning
            )
            return self.parent_dataset

    @parent.setter
    def parent(self, value: "Dataset") -> None:
        """Set the parent :class:`~pydicom.dataset.Dataset`

        .. deprecated:: 2.4
        """
        if config._use_future:
            raise AttributeError("Future: Sequence.parent is removed in v3.x")
        else:
            warnings.warn(
                "Sequence.parent will be removed in pydicom 3.0",
                DeprecationWarning
            )
            self.parent_dataset = value  # type:ignore

    @overload  # type: ignore[override]
    def __setitem__(self, idx: int, val: Dataset) -> None:
        pass  # pragma: no cover

    @overload
    def __setitem__(self, idx: slice, val: Iterable[Dataset]) -> None:
        pass  # pragma: no cover

    def __setitem__(
        self, idx: Union[slice, int], val: Union[Iterable[Dataset], Dataset]
    ) -> None:
        """Set the parent :class:`~pydicom.dataset.Dataset` to the new
        :class:`Sequence` item
        """
        if isinstance(idx, slice):
            if isinstance(val, Dataset):
                raise TypeError("Can only assign an iterable of 'Dataset'")

            super().__setitem__(idx, val)
            for ds in val:
                ds.parent_seq = self  # type: ignore
        else:
            val = cast(Dataset, val)
            super().__setitem__(idx, val)
            val.parent_seq = self  # type: ignore

    def __str__(self) -> str:
        """String description of the Sequence."""
        return f"[{''.join([str(x) for x in self])}]"

    def __repr__(self) -> str:  # type: ignore[override]
        """String representation of the Sequence."""
        return f"<{self.__class__.__name__}, length {len(self)}>"

    def __getstate__(self) -> Dict[str, Any]:
        if self.parent_dataset is not None:
            s = self.__dict__.copy()
            s['_parent_dataset'] = s['_parent_dataset']()
            return s
        return self.__dict__

    # If recovering from a pickle, turn back into weak ref
    def __setstate__(self, state: Dict[str, Any]) -> None:
        self.__dict__.update(state)
        if self.__dict__['_parent_dataset'] is not None:
            self.__dict__['_parent_dataset'] = weakref.ref(
                self.__dict__['_parent_dataset']
            )
