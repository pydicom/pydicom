# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Define the Sequence class, which contains a sequence DataElement's items.

Sequence is a list of pydicom Dataset objects.
"""
from typing import cast, Any, TypeVar
from collections.abc import Iterable

from pydicom.dataset import Dataset
from pydicom.multival import ConstrainedList


# Python 3.11 adds typing.Self, until then...
Self = TypeVar("Self", bound="Sequence")


class Sequence(ConstrainedList[Dataset]):
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

        super().__init__(iterable)

    def extend(self, val: Iterable[Dataset]) -> None:
        """Extend the :class:`~pydicom.sequence.Sequence` using an iterable
        of :class:`~pydicom.dataset.Dataset` instances.
        """
        if isinstance(val, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        super().extend(val)

    def __iadd__(self: Self, other: Iterable[Dataset]) -> Self:
        """Implement Sequence() += [Dataset()]."""
        if isinstance(other, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        return super().__iadd__(other)

    def __setitem__(self, index: slice | int, val: Iterable[Dataset] | Dataset) -> None:
        """Add item(s) to the Sequence at `index`."""
        if isinstance(index, slice):
            if isinstance(val, Dataset):
                raise TypeError("Can only assign an iterable of 'Dataset'")

            super().__setitem__(index, val)
        else:
            super().__setitem__(index, cast(Dataset, val))

    def __str__(self) -> str:
        """String description of the Sequence."""
        return f"[{''.join([str(x) for x in self])}]"

    def __repr__(self) -> str:
        """String representation of the Sequence."""
        return f"<{self.__class__.__name__}, length {len(self)}>"

    @staticmethod
    def _validate(item: Any) -> Dataset:
        """Check that `item` is a :class:`~pydicom.dataset.Dataset` instance."""
        if isinstance(item, Dataset):
            return item

        raise TypeError("Sequence contents must be 'Dataset' instances.")
