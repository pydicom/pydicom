# Copyright 2008-2020 pydicom authors. See LICENSE file for details.
"""Define the Sequence class, which contains a sequence DataElement's items.

Sequence is a list of pydicom Dataset objects.
"""
from typing import cast, overload
from collections.abc import Iterable, MutableSequence

from pydicom.dataset import Dataset
from pydicom.multival import MultiValue


def validate_dataset(elem: object) -> Dataset:
    """Check that `elem` is a :class:`~pydicom.dataset.Dataset` instance."""
    if not isinstance(elem, Dataset):
        raise TypeError("Sequence contents must be Dataset instances.")

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

    def __init__(self, iterable: Iterable[Dataset] | None = None) -> None:
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
            raise TypeError("The Sequence constructor requires an iterable")

        # validate_dataset is used as a pseudo type_constructor
        self._list: list[Dataset] = []
        # If no inputs are provided, we create an empty Sequence
        super().__init__(validate_dataset, iterable or [])
        self.is_undefined_length: bool

    def append(self, val: Dataset) -> None:  # type: ignore[override]
        """Append a :class:`~pydicom.dataset.Dataset` to the sequence."""
        super().append(val)

    def extend(self, val: Iterable[Dataset]) -> None:  # type: ignore[override]
        """Extend the :class:`~pydicom.sequence.Sequence` using an iterable
        of :class:`~pydicom.dataset.Dataset` instances.
        """
        if isinstance(val, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        super().extend(val)

    def __iadd__(  # type: ignore[override]
        self, other: Iterable[Dataset]
    ) -> MutableSequence[Dataset]:
        """Implement Sequence() += [Dataset()]."""
        if isinstance(other, Dataset):
            raise TypeError("An iterable of 'Dataset' is required")

        return super().__iadd__(other)

    def insert(self, position: int, val: Dataset) -> None:  # type: ignore[override]
        """Insert a :class:`~pydicom.dataset.Dataset` into the sequence."""
        super().insert(position, val)

    @overload  # type: ignore[override]
    def __setitem__(self, idx: int, val: Dataset) -> None:
        pass  # pragma: no cover

    @overload
    def __setitem__(self, idx: slice, val: Iterable[Dataset]) -> None:
        pass  # pragma: no cover

    def __setitem__(self, idx: slice | int, val: Iterable[Dataset] | Dataset) -> None:
        """Set the parent :class:`~pydicom.dataset.Dataset` to the new
        :class:`Sequence` item
        """
        if isinstance(idx, slice):
            if isinstance(val, Dataset):
                raise TypeError("Can only assign an iterable of 'Dataset'")

            super().__setitem__(idx, val)
        else:
            val = cast(Dataset, val)
            super().__setitem__(idx, val)

    def __str__(self) -> str:
        """String description of the Sequence."""
        return f"[{''.join([str(x) for x in self])}]"

    def __repr__(self) -> str:  # type: ignore[override]
        """String representation of the Sequence."""
        return f"<{self.__class__.__name__}, length {len(self)}>"
