from collections import namedtuple

from pydicom.dataset import Dataset
from pydicom.sr._snomed_dict import mapping as snomed_mapping

_CodeBase = namedtuple(
    "Code", ("value", "scheme_designator", "meaning", "scheme_version")
)
_CodeBase.__new__.__defaults__ = (None,)


class Code(_CodeBase):
    """Namedtuple for representation of a coded concept consisting of the
    actual code *value*, the coding *scheme designator*, the code *meaning*
    (and optionally the coding *scheme version*).

    ..versionadded: 1.4
    """

    def __eq__(self, other):
        if self.scheme_designator == "SRT":
            self_mapped = Code(
                value=snomed_mapping["SRT"][self.value],
                meaning="",
                scheme_designator="SCT",
                scheme_version=self.scheme_version,
            )
        else:
            self_mapped = Code(
                value=self.value,
                meaning="",
                scheme_designator=self.scheme_designator,
                scheme_version=self.scheme_version,
            )
        if other.scheme_designator == "SRT":
            other_mapped = Code(
                value=snomed_mapping["SRT"][other.value],
                meaning="",
                scheme_designator="SCT",
                scheme_version=other.scheme_version,
            )
        else:
            other_mapped = Code(
                value=other.value,
                meaning="",
                scheme_designator=other.scheme_designator,
                scheme_version=other.scheme_version,
            )
        return (
            self_mapped.value == other_mapped.value
            and self_mapped.scheme_designator == other_mapped.scheme_designator
            and self_mapped.scheme_version == other_mapped.scheme_version
        )

    def __ne__(self, other):
        return not (self == other)
