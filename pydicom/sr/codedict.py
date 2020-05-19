# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
# -*- coding: utf-8 -*-
"""Access code dictionary information"""

from itertools import chain
import inspect

from pydicom.sr.coding import Code
from pydicom.sr._concepts_dict import concepts
from pydicom.sr._cid_dict import name_for_cid, cid_concepts


# Reverse lookup for cid names
cid_for_name = {v: k for k, v in name_for_cid.items()}


def _filtered(allnames, filters):
    """Helper function for dir() methods"""
    matches = {}
    for filter_ in filters:
        filter_ = filter_.lower()
        match = [x for x in allnames if x.lower().find(filter_) != -1]
        matches.update(dict([(x, 1) for x in match]))
    if filters:
        names = sorted(matches.keys())
        return names
    else:
        return sorted(allnames)


class _CID_Dict:
    repr_format = "{} = {}"
    str_format = "{:20} {:12} {:8} {}\n"

    def __init__(self, cid):
        self.cid = cid
        self._concepts = None

    def __dir__(self):
        """Gives a list of available SR identifiers.

        List of attributes is used, for example, in auto-completion in editors
        or command-line environments.
        """
        # Force zip object into a list in case of python3. Also backwards
        # compatible
        meths = set(
            list(zip(*inspect.getmembers(self.__class__, inspect.isroutine)))[
                0
            ]
        )
        props = set(
            list(
                zip(
                    *inspect.getmembers(
                        self.__class__, inspect.isdatadescriptor
                    )
                )
            )[0]
        )
        sr_names = set(self.dir())
        alldir = sorted(props | meths | sr_names)
        return alldir

    def __getattr__(self, name):
        matches = [
            scheme
            for scheme, keywords in cid_concepts[self.cid].items()
            if name in keywords
        ]
        if not matches:
            msg = "Identifier '{}' not found for cid{}".format(name, self.cid)
            raise AttributeError(msg)
        elif len(matches) > 1:
            # Should never happen, but just in case
            msg = "Multiple schemes found for '{}' in cid{}".format(name, cid)
            raise AssertionError(msg)
        else:
            scheme = matches[0]
            concept = concepts[scheme][name]
            # Almost always only one code per concepts name
            if len(concept) == 1:
                code, val = list(concept.items())[0]
            else:
                matches = [
                    (code, val)
                    for code, val in concept.items()
                    if self.cid in val[1]
                ]
                if len(matches) > 1:
                    # Should never happen, but check in case
                    msg = "{} had multiple code matches for cid{}".format(
                        name, cid
                    )
                    raise AssertionError(msg)
                code, val = matches[0]
            return Code(value=code, meaning=val[0], scheme_designator=scheme)

    @property
    def concepts(self):
        if not self._concepts:
            self._concepts = {name: getattr(self, name) for name in self.dir()}
        return self._concepts

    def __repr__(self):
        heading = "CID{}\n".format(self.cid)
        concepts = [
            self.repr_format.format(name, concept)
            for name, concept in self.concepts.items()
        ]
        return heading + "\n".join(concepts)

    def __str__(self):
        heading = "CID{}\n".format(self.cid)
        fmt = self.str_format
        line2 = self.str_format.format(
            "Business name", "value", "scheme", "meaning"
        )
        lines = "".join(
            fmt.format(name, *concept)
            for name, concept in self.concepts.items()
        )
        return heading + line2 + lines

    def dir(self, *filters):
        """Return an alphabetical list of SR identifiers based on a partial
        match.

        Intended mainly for use in interactive Python sessions.

        Parameters
        ----------
        filters : str
            Zero or more string arguments to the function. Used for
            case-insensitive match to any part of the SR keyword.

        Returns
        -------
        list of str
            The matching SR keywords. If no filters are
            used then all keywords are returned.
        """
        allnames = set(chain(*cid_concepts[self.cid].values()))
        return _filtered(allnames, filters)

    def __contains__(self, code):
        """Checks whether a given code is a member of the context group.

        Parameters
        ----------
        code: Union[pydicom.sr.coding.Code, pydicom.sr.coding.CodedConcept]
            coded concept

        Returns
        -------
        bool
            whether CID contains `code`

        """
        return any([concept == code for concept in self.concepts.values()])

    def trait_names(self):
        """Returns a list of valid names for auto-completion code.

        Used in IPython, so that data element names can be found and offered
        for autocompletion on the IPython command line.

        """
        return dir(self)


class _CodesDict:
    def __init__(self, scheme=None):
        self.scheme = scheme
        if scheme:
            self._dict = {scheme: concepts[scheme]}
        else:
            self._dict = concepts

    def __dir__(self):
        """Gives a list of available SR identifiers.

        List of attributes is used, for example, in auto-completion in editors
        or command-line environments.
        """
        # Force zip object into a list in case of python3. Also backwards
        # compatible
        meths = set(
            list(zip(*inspect.getmembers(self.__class__, inspect.isroutine)))[
                0
            ]
        )
        props = set(
            list(
                zip(
                    *inspect.getmembers(
                        self.__class__, inspect.isdatadescriptor
                    )
                )
            )[0]
        )
        sr_names = set(self.dir())
        alldir = sorted(props | meths | sr_names)
        return alldir

    def __getattr__(self, name):
        # for codes.X, X must be a CID or a scheme designator
        if name.startswith("cid"):
            if not self.scheme:
                return _CID_Dict(int(name[3:]))
            raise AttributeError("Cannot call cid selector on scheme dict")
        if name in self._dict.keys():
            # Return concepts limited only the specified scheme designator
            return _CodesDict(scheme=name)

        # If not already narrowed to a particular scheme, is an error
        if not self.scheme:
            msg = "'{}' not recognized as a CID or scheme designator"
            raise AttributeError(msg.format(name))

        # else try to find in this scheme
        scheme = self.scheme
        try:
            val = self._dict[scheme][name]
        except KeyError:
            msg = "Unknown code name '{}' for scheme '{}'"
            raise AttributeError(msg.format(name, scheme))
        # val is like {code1: (meaning, cid_list}, code2: ...}
        if len(val) > 1:  # more than one code for this name
            raise NotImplementedError("Need cid to disambiguate")
        else:
            code = list(val.keys())[0]  # get first and only
            meaning, cids = val[code]
            return Code(value=code, meaning=meaning, scheme_designator=scheme)

    def dir(self, *filters):
        """Returns an alphabetical list of SR identifiers based on a partial
        match.

        Intended mainly for use in interactive Python sessions.

        Parameters
        ----------
        filters : str
            Zero or more string arguments to the function. Used for
            case-insensitive match to any part of the SR keyword.

        Returns
        -------
        list of str
            The matching SR keywords. If no filters are
            used then all keywords are returned.

        """
        allnames = set(chain(*(x.keys() for x in self._dict.values())))
        return _filtered(allnames, filters)

    def schemes(self):
        return self._dict.keys()

    def trait_names(self):
        """Returns a list of valid names for auto-completion code.

        Used in IPython, so that data element names can be found and offered
        for autocompletion on the IPython command line.

        """
        return dir(self)


codes = _CodesDict()
