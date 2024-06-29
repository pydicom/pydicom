# Copyright 2008-2024 pydicom authors. See LICENSE file for details.
"""Access code dictionary information"""

from itertools import chain
import inspect
from typing import cast, Any
from collections.abc import KeysView, Iterable

from pydicom.sr.coding import Code
from pydicom.sr._concepts_dict import concepts as CONCEPTS
from pydicom.sr._cid_dict import name_for_cid, cid_concepts as CID_CONCEPTS


# Reverse lookup for cid names
cid_for_name = {v: k for k, v in name_for_cid.items()}


def _filtered(source: Iterable[str], filters: Iterable[str]) -> list[str]:
    """Return a sorted list of filtered str.

    Parameters
    ----------
    source : Iterable[str]
        The iterable of str to be filtered.
    filters : Iterable[str]
        An iterable containing patterns for which values are to be included
        in the results.

    Returns
    -------
    List[str]
        A sorted list of unique values from `source`, filtered by including
        case-insensitive partial or full matches against the values
        in `filters`.
    """
    if not filters:
        return sorted(set(source))

    filters = [f.lower() for f in filters]

    return sorted(
        set(val for val in source if any((f in val.lower()) for f in filters))
    )


CIDValueType = dict[str, tuple[str, list[int]]]
ConceptsType = dict[str, CIDValueType]
SnomedMappingType = dict[str, dict[str, str]]


class Collection:
    """Interface for a collection of concepts, such as SNOMED-CT, or a DICOM CID.

    .. versionadded:: 3.0
    """

    repr_format = "{} = {}"

    def __init__(self, name: str) -> None:
        """Create a new collection.

        Parameters
        ----------
        name : str
            The name of the collection, should either be a key in the
            ``sr._concepts_dict.concepts`` :class:`dict` or a CID name for
            a CID in ``sr._cid_dict.cid_concepts`` such as ``"CID1234"``.
        """
        if not name.upper().startswith("CID"):
            self._name = name
            # dict[str, dict[str, tuple(str, list[int])]]
            # {'ACEInhibitor': {'41549009': ('ACE inhibitor', [3760])},
            self._scheme_data = CONCEPTS[name]
        else:
            self._name = f"CID{name[3:]}"
            # dict[str, list[str]]
            # {'SCT': ['Pericardium', 'Pleura', 'LeftPleura', 'RightPleura']}
            self._cid_data = CID_CONCEPTS[int(name[3:])]

        self._concepts: dict[str, Code] = {}

    @property
    def concepts(self) -> dict[str, Code]:
        """Return a :class:`dict` of {SR identifiers: codes}"""
        if not self._concepts:
            self._concepts = {name: getattr(self, name) for name in self.dir()}

        return self._concepts

    def __contains__(self, item: str | Code) -> bool:
        """Checks whether a given code is a member of the collection.

        Parameters
        ----------
        item : pydicom.sr.coding.Code | str
            The code to check for as either the code or the corresponding
            keyword.

        Returns
        -------
        bool
            Whether the collection contains the `code`
        """
        if isinstance(item, str):
            try:
                code = getattr(self, item)
            except AttributeError:
                return False
        else:
            code = item

        return code in self.concepts.values()

    def __dir__(self) -> list[str]:
        """Return a list of available concept keywords.

        List of attributes is used, for example, in auto-completion in editors
        or command-line environments.
        """
        meths = {v[0] for v in inspect.getmembers(type(self), inspect.isroutine)}
        props = {v[0] for v in inspect.getmembers(type(self), inspect.isdatadescriptor)}
        sr_names = set(self.dir())

        return sorted(props | meths | sr_names)

    def dir(self, *filters: str) -> list[str]:
        """Return an sorted list of concept keywords based on a partial match.

        Parameters
        ----------
        filters : str
            Zero or more string arguments to the function. Used for
            case-insensitive match to any part of the SR keyword.

        Returns
        -------
        list of str
            The matching keywords. If no `filters` are used then all
            keywords are returned.
        """
        # CID_CONCEPTS: Dict[int, Dict[str, List[str]]]
        if self.is_cid:
            return _filtered(chain.from_iterable(self._cid_data.values()), filters)

        return _filtered(self._scheme_data, filters)

    def __getattr__(self, name: str) -> Code:
        """Return the :class:`~pydicom.sr.Code` corresponding to `name`.

        Parameters
        ----------
        name : str
            A camel case version of the concept's code meaning, such as
            ``"FontanelOfSkull" in the SCT coding scheme.

        Returns
        -------
        pydicom.sr.Code
            The :class:`~pydicom.sr.Code` corresponding to `name`.
        """
        if self.name.startswith("CID"):
            # Try DICOM's CID collections
            matches = [
                scheme
                for scheme, keywords in self._cid_data.items()
                if name in keywords
            ]
            if not matches:
                raise AttributeError(
                    f"No matching code for keyword '{name}' in {self.name}"
                )

            if len(matches) > 1:
                # Shouldn't happen, but just in case
                raise RuntimeError(
                    f"Multiple schemes found to contain the keyword '{name}' in "
                    f"{self.name}: {', '.join(matches)}"
                )

            scheme = matches[0]
            identifiers = cast(CIDValueType, CONCEPTS[scheme][name])

            if len(identifiers) == 1:
                code, val = list(identifiers.items())[0]
            else:
                cid = int(self.name[3:])
                _matches = [
                    (code, val) for code, val in identifiers.items() if cid in val[1]
                ]
                if len(_matches) > 1:
                    # Shouldn't happen, but just in case
                    codes = ", ".join(v[0] for v in _matches)
                    raise RuntimeError(
                        f"Multiple codes found for keyword '{name}' in {self.name}: "
                        f"{codes}"
                    )

                code, val = _matches[0]

            return Code(value=code, meaning=val[0], scheme_designator=scheme)

        # Try concept collections such as SCT, DCM, etc
        try:
            entries = cast(CIDValueType, self._scheme_data[name])
        except KeyError:
            raise AttributeError(
                f"No matching code for keyword '{name}' in scheme '{self.name}'"
            )

        if len(entries) > 1:
            # val is {"code": ("meaning", [cid1, cid2, ...], "code": ...}
            code_values = ", ".join(entries.keys())
            raise RuntimeError(
                f"Multiple codes found for keyword '{name}' in scheme '{self.name}': "
                f"{code_values}"
            )

        code = list(entries.keys())[0]  # get first and only
        meaning, cids = entries[code]

        return Code(value=code, meaning=meaning, scheme_designator=self.name)

    @property
    def is_cid(self) -> bool:
        """Return ``True`` if the collection is one of the DICOM CIDs"""
        return self.name.startswith("CID")

    @property
    def name(self) -> str:
        """Return the name of the collection."""
        return self._name

    def __repr__(self) -> str:
        """Return a representation of the collection."""
        concepts = [
            self.repr_format.format(name, concept)
            for name, concept in self.concepts.items()
        ]

        return f"{self.name}\n" + "\n".join(concepts)

    @property
    def scheme_designator(self) -> str:
        """Return the scheme designator for the collection."""
        return self.name

    def __str__(self) -> str:
        """Return a string representation of the collection."""
        len_names = max(len(n) for n in self.concepts.keys()) + 2
        len_codes = max(len(c[0]) for c in self.concepts.values()) + 2
        len_schemes = max(len(c[1]) for c in self.concepts.values()) + 2

        # Ensure each column is at least X characters wide
        len_names = max(len_names, 11)
        len_codes = max(len_codes, 6)
        len_schemes = max(len_schemes, 8)

        if self.is_cid:
            fmt = f"{{:{len_names}}} {{:{len_codes}}} {{:{len_schemes}}} {{}}"

            s = [self.name]
            s.append(fmt.format("Attribute", "Code", "Scheme", "Meaning"))
            s.append(fmt.format("---------", "----", "------", "-------"))
            s.append(
                "\n".join(
                    fmt.format(name, *concept)
                    for name, concept in self.concepts.items()
                )
            )
        else:
            fmt = f"{{:{len_names}}} {{:{len_codes}}} {{}}"

            s = [f"Scheme: {self.name}"]
            s.append(fmt.format("Attribute", "Code", "Meaning"))
            s.append(fmt.format("---------", "----", "-------"))

            s.append(
                "\n".join(
                    fmt.format(name, concept[0], concept[2])
                    for name, concept in self.concepts.items()
                )
            )

        return "\n".join(s)

    def trait_names(self) -> list[str]:
        """Return a list of valid names for auto-completion code.

        Used in IPython, so that data element names can be found and offered
        for autocompletion on the IPython command line.
        """
        return dir(self)


class Concepts:
    """Management class for the available concept collections.

    .. versionadded:: 3.0
    """

    def __init__(self, collections: list[Collection]) -> None:
        """Create a new concepts management class instance.

        Parameters
        ----------
        collections : list[Collection]
            A list of the available concept collections.
        """
        self._collections = {c.name: c for c in collections}

    @property
    def collections(self) -> KeysView[str]:
        """Return the names of the available concept collections."""
        return self._collections.keys()

    def __getattr__(self, name: str) -> Any:
        """Return the concept collection corresponding to `name`.

        Parameters
        ----------
        name : str
            The scheme designator or CID name for the collection to be returned.
        """
        if name.upper().startswith("CID"):
            name = f"CID{name[3:]}"

        if name in self._collections:
            return self._collections[name]

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def schemes(self) -> list[str]:
        """Return a list of available scheme designations."""
        return [c for c in self._collections.keys() if not c.startswith("CID")]

    def CIDs(self) -> list[str]:
        """Return a list of available CID names."""
        return [c for c in self._collections.keys() if c.startswith("CID")]


# Named concept collections like SNOMED-CT, etc
_collections = [Collection(designator) for designator in CONCEPTS]
# DICOM CIDs
_collections.extend(Collection(f"CID{cid}") for cid in name_for_cid)

codes = Concepts(_collections)
