from collections import namedtuple

from pydicom.dataset import Dataset
from pydicom._snomed_dict import mapping as snomed_mapping


def _eq(self, other):
    if self.scheme_designator == 'SRT':
        self_mapped = Code(
            value=snomed_mapping['SRT'][self.value],
            meaning='',
            scheme_designator='SCT',
            scheme_version=self.scheme_version
        )
    else:
        self_mapped = Code(
            value=self.value,
            meaning='',
            scheme_designator=self.scheme_designator,
            scheme_version=self.scheme_version
        )
    if other.scheme_designator == 'SRT':
        other_mapped = Code(
            value=snomed_mapping['SRT'][other.value],
            meaning='',
            scheme_designator='SCT',
            scheme_version=other.scheme_version
        )
    else:
        other_mapped = Code(
            value=other.value,
            meaning='',
            scheme_designator=other.scheme_designator,
            scheme_version=other.scheme_version
        )
    return (
        self_mapped.value == other_mapped.value and
        self_mapped.scheme_designator == other_mapped.scheme_designator and
        self_mapped.scheme_version == other_mapped.scheme_version
    )


def _ne(self, other):
    return not(self == other)


Code = namedtuple(
    'Code',
    ('value', 'scheme_designator', 'meaning', 'scheme_version')
)
Code.__new__.__defaults__ = (None, )
Code.__eq__ = _eq
Code.__ne__ = _ne
