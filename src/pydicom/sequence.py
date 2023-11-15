# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Define the Sequence class, which contains a sequence DataElement's items.

Sequence is a list of pydicom Dataset objects.
"""
from copy import deepcopy
from typing import cast, overload, Any, TypeVar
from collections.abc import Iterable, Iterator, MutableSequence
import weakref
import warnings

from pydicom import config
from pydicom.dataset import Dataset
from pydicom.multival import ConstrainedList


# Python 3.11 adds typing.Self, until then...
Self = TypeVar("Self", bound="Sequence")


class Sequence(ConstrainedList[Dataset]):
    """Class to hold multiple :class:`~pydicom.dataset.Dataset` in a :class:`list`."""

    def __init__(self, iterable: Iterable[Dataset] | None = None) -> None:
        if isinstance(iterable, Dataset):
            raise TypeError("The Sequence constructor requires an iterable")

        # If True, SQ element uses an undefined length of 0xFFFFFFFF
        self.is_undefined_length: bool

        super().__init__(iterable)

        # The dataset that contains the SQ element this is the value of
        self._parent_dataset: weakref.ReferenceType[Dataset] | None = None

        for ds in self:
            ds.parent_seq = self  # type: ignore[assignment]

    def append(self, val: Dataset) -> None:
        """Append a :class:`~pydicom.dataset.Dataset` to the Sequence."""
        super().append(val)
        val.parent_seq = self  # type: ignore[assignment]

    def extend(self, val: Iterable[Dataset]) -> None:
        """Extend the :class:`~pydicom.sequence.Sequence` using an iterable
        of :class:`~pydicom.dataset.Dataset` instances.
        """
        if isinstance(val, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        super().extend(val)

        for ds in val:
            ds.parent_seq = self  # type: ignore[assignment]

    def __deepcopy__(self, memo: dict[int, Any] | None) -> "Sequence":
        """Create a deepcopy of the Sequence."""
        cls = self.__class__
        copied = cls.__new__(cls)
        if memo is not None:
            memo[id(self)] = copied
        copied.__dict__.update(deepcopy(self.__dict__, memo))
        for ds in copied:
            ds.parent_seq = copied  # type: ignore[assignment]
        return copied

    def __iadd__(self: Self, other: Iterable[Dataset]) -> Self:
        """Implement Sequence() += [Dataset()]."""
        if isinstance(other, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        result = super().__iadd__(other)
        for ds in other:
            ds.parent_seq = self  # type: ignore[assignment]

        return result

    def insert(self, position: int, val: Dataset) -> None:
        """Insert a :class:`~pydicom.dataset.Dataset` into the sequence."""
        super().insert(position, val)
        val.parent_seq = self  # type: ignore[assignment]

    @property
    def parent_dataset(self) -> "weakref.ReferenceType[Dataset] | None":
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

    def __setitem__(self, idx: slice | int, val: Iterable[Dataset] | Dataset) -> None:
        """Add item(s) to the Sequence at `idx`.

        Also sets the parent :class:`~pydicom.dataset.Dataset` to the new
        :class:`Sequence` item(s)
        """
        if isinstance(idx, slice):
            if isinstance(val, Dataset):
                raise TypeError("Can only assign an iterable of 'Dataset'")

            super().__setitem__(idx, val)
            for ds in val:
                ds.parent_seq = self  # type: ignore[assignment]
        else:
            val = cast(Dataset, val)
            super().__setitem__(idx, val)
            val.parent_seq = self  # type: ignore[assignment]

    def __str__(self) -> str:
        """String description of the Sequence."""
        return f"[{''.join([str(x) for x in self])}]"

    def __repr__(self) -> str:
        """String representation of the Sequence."""
        return f"<{self.__class__.__name__}, length {len(self)}>"

    def __getstate__(self) -> dict[str, Any]:
        if self.parent_dataset is not None:
            s = self.__dict__.copy()
            s["_parent_dataset"] = s["_parent_dataset"]()
            return s
        return self.__dict__

    # If recovering from a pickle, turn back into weak ref
    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)
        if self.__dict__["_parent_dataset"] is not None:
            self.__dict__["_parent_dataset"] = weakref.ref(
                self.__dict__["_parent_dataset"]
            )

    @staticmethod
    def _validate(item: Any) -> Dataset:
        """Check that `item` is a :class:`~pydicom.dataset.Dataset` instance."""
        if not isinstance(item, Dataset):
            raise TypeError("Sequence contents must be 'Dataset' instances.")

        return item
