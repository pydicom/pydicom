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


# Python 3.11 adds typing.Self, until then...
Self = TypeVar("Self", bound="Sequence")


class Sequence(MutableSequence[Dataset]):
    """Class to hold multiple :class:`~pydicom.dataset.Dataset` in a :class:`list`."""

    def __init__(self, iterable: Iterable[Dataset] | None = None) -> None:
        """Initialize a list of :class:`~pydicom.dataset.Dataset`.

        Parameters
        ----------
        iterable : Iterable[Dataset] | None
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
            raise TypeError("The Sequence constructor requires an iterable")

        # If True, SQ element uses an undefined length of 0xFFFFFFFF
        self.is_undefined_length: bool

        self._list: list[Dataset] = []
        if iterable is not None:
            self._list = [self._validate(item) for item in iterable]

        # The dataset that contains the SQ element this is the value of
        self._parent_dataset: weakref.ReferenceType[Dataset] | None = None

        for ds in self:
            ds.parent_seq = self  # type: ignore[assignment]

    def append(self, val: Dataset) -> None:
        """Append a :class:`~pydicom.dataset.Dataset` to the Sequence."""
        self._list.append(self._validate(val))
        val.parent_seq = self  # type: ignore[assignment]

    def __delitem__(self, index: slice | int) -> None:
        """Remove the item(s) at `index` from the Sequence."""
        del self._list[index]

    def extend(self, val: Iterable[Dataset]) -> None:
        """Extend the :class:`~pydicom.sequence.Sequence` using an iterable
        of :class:`~pydicom.dataset.Dataset` instances.
        """
        if isinstance(val, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        self._list.extend([self._validate(item) for item in val])

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

    def __eq__(self, other: Any) -> Any:
        """Return ``True`` if `other` is equal to the Sequence."""
        return self._list == other

    @overload
    def __getitem__(self, index: int) -> Dataset:
        ...

    @overload
    def __getitem__(self, index: slice) -> MutableSequence[Dataset]:
        ...

    def __getitem__(self, index: slice | int) -> MutableSequence[Dataset] | Dataset:
        """Return item(s) from the Sequence."""
        return self._list[index]

    def __iadd__(self: Self, other: Iterable[Dataset]) -> Self:
        """Implement Sequence() += [Dataset()]."""
        if isinstance(other, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        self._list += [self._validate(item) for item in other]
        for ds in other:
            ds.parent_seq = self  # type: ignore[assignment]

        return self

    def insert(self, position: int, val: Dataset) -> None:
        """Insert a :class:`~pydicom.dataset.Dataset` into the sequence."""
        self._list.insert(position, self._validate(val))
        val.parent_seq = self  # type: ignore[assignment]

    def __iter__(self) -> Iterator[Dataset]:
        """Yield items from the Sequence."""
        yield from self._list

    def __len__(self) -> int:
        """Return the number of items in the Sequence."""
        return len(self._list)

    def __ne__(self, other: Any) -> Any:
        """Return ``True`` if `other` is not equal to the Sequence."""
        return self._list != other

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

    @overload
    def __setitem__(self, idx: int, val: Dataset) -> None:
        ...

    @overload
    def __setitem__(self, idx: slice, val: Iterable[Dataset]) -> None:
        ...

    def __setitem__(self, idx: slice | int, val: Iterable[Dataset] | Dataset) -> None:
        """Add item(s) to the Sequence at `idx`.

        Also sets the parent :class:`~pydicom.dataset.Dataset` to the new
        :class:`Sequence` item(s)
        """
        if isinstance(idx, slice):
            if isinstance(val, Dataset):
                raise TypeError("Can only assign an iterable of 'Dataset'")

            self._list.__setitem__(idx, [self._validate(item) for item in val])
            for ds in val:
                ds.parent_seq = self  # type: ignore[assignment]
        else:
            val = cast(Dataset, val)
            self._list.__setitem__(idx, self._validate(val))
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
