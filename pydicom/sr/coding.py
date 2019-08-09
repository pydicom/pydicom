from collections import namedtuple

from pydicom.dataset import Dataset
from pydicom.sr._snomed_dict import mapping as snomed_mapping

from pydicom.sr._snomed_dict import mapping as snomed_mapping


Code = namedtuple(
    'Code',
    ('value', 'scheme_designator', 'meaning', 'scheme_version')
)
Code.__new__.__defaults__ = (None, )


class CodedConcept(Dataset):

    """Coded concept of a DICOM SR document content module attribute."""

    def __init__(self, value, scheme_designator, meaning, scheme_version=None):
        """
        Parameters
        ----------
        value: str
            code
        meaning: str
            meaning of the code
        scheme_designator: str
            designator of coding scheme
        scheme_version: str, optional
            version of coding scheme

        """
        super(CodedConcept, self).__init__()
        if len(value) > 16:
            if value.startswith('urn') or '://' in value:
                self.URNCodeValue = str(value)
            else:
                self.LongCodeValue = str(value)
        else:
            self.CodeValue = str(value)
        self.CodeMeaning = str(meaning)
        self.CodingSchemeDesignator = str(scheme_designator)
        if scheme_version is not None:
            self.CodingSchemeVersion = str(scheme_version)
        # TODO: Enhanced Code Sequence Macro Attributes

    def __eq__(self, other):
        """Compares `self` and `other` for equality.

        Parameters
        ----------
        other: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            code

        Returns
        -------
        bool
            whether `self` and `other` are considered equal

        """
        if not isinstance(other, (self.__class__, Code)):
            return False
        if self.scheme_designator == 'SRT':
            self_mapped = CodedConcept(
                value=snomed_mapping['SRT'][self.value],
                meaning='',
                scheme_designator='SCT',
                scheme_version=self.scheme_version
            )
        else:
            self_mapped = CodedConcept(
                value=self.value,
                meaning='',
                scheme_designator=self.scheme_designator,
                scheme_version=self.scheme_version
            )
        if other.scheme_designator == 'SRT':
            other_mapped = CodedConcept(
                value=snomed_mapping['SRT'][other.value],
                meaning='',
                scheme_designator='SCT',
                scheme_version=other.scheme_version
            )
        else:
            other_mapped = CodedConcept(
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

    def __ne__(self, other):
        """Compares `self` and `other` for inequality.

        Parameters
        ----------
        other: Union[CodedConcept, pydicom.sr.coding.Code]
            code

        Returns
        -------
        bool
            whether `self` and `other` are not considered equal

        """
        return not (self == other)

    @property
    def value(self):
        """str: value of either `CodeValue`, `LongCodeValue` or `URNCodeValue`
        attribute"""
        return getattr(
            self, 'CodeValue',
            getattr(
                self, 'LongCodeValue',
                getattr(
                    self, 'URNCodeValue',
                    None
                )
            )
        )

    @property
    def meaning(self):
        """str: meaning of the code"""
        return self.CodeMeaning

    @property
    def scheme_designator(self):
        """str: designator of the coding scheme (e.g. ``"DCM"``)"""

        return self.CodingSchemeDesignator

    @property
    def scheme_version(self):
        """Union[str, None]: version of the coding scheme (if specified)"""
        return getattr(self, 'CodingSchemeVersion', None)


class CodingSchemeResourceItem(Dataset):

    """Class for items of the Coding Scheme Resource Sequence."""

    def __init__(self, url, url_type):
        """
        Parameters
        ----------
        url: str
            unique resource locator
        url_type: str
            type of resource `url` points to (options: `{"DOC", "OWL", "CSV"}`)

        """
        self.CodingSchemeURL = str(url)
        self.CodingSchemeURLType = str(url_type)


class CodingSchemeIdentificationItem(Dataset):

    """Class for items of the Coding Scheme Identification Sequence."""

    def __init__(self, designator, name=None, version=None, registry=None,
                 uid=None, external_id=None, responsible_organization=None,
                 resources=None):
        """
        Parameters
        ----------
        designator: str
            value of the Coding Scheme Designator attribute of a `CodedConcept`
        name: str, optional
            name of the scheme
        version: str, optional
            version of the scheme
        registry: str, optional
            name of an external registry where scheme may be obtained from;
            required if scheme is registered
        uid: str, optional
            unique identifier of the scheme; required if the scheme is
            registered by an ISO 8824 object identifier compatible with the
            UI value representation (VR)
        external_id: str, optional
            external identifier of the scheme; required if the scheme is
            registered and `uid` is not available
        responsible_organization: str, optional
            name of the organization that is responsible for the scheme
        resources: Sequence[pydicom.sr.coding.CodingSchemeResource], optional
            one or more resources related to the scheme

        """
        self.CodingSchemeDesignator = str(designator)
        if name is not None:
            self.CodingSchemeName = str(name)
        if version is not None:
            self.CodingSchemeVersion = str(version)
        if responsible_organization is not None:
            self.CodingSchemeResponsibleOrganization = \
                str(responsible_organization)
        if registry is not None:
            self.CodingSchemeRegistry = str(registry)
            if uid is None and external_id is None:
                raise ValueError(
                    'UID or external ID is required if coding scheme is '
                    'registered.'
                )
            if uid is not None and external_id is not None:
                raise ValueError(
                    'Either UID or external ID should be specified for '
                    'registered coding scheme.'
                )
            if uid is not None:
                self.CodingSchemeUID = str(uid)
            elif external_id is not None:
                self.CodingSchemeExternalID = str(external_id)
        if resources is not None:
            if isinstance(resources, (List, Sequence, )):
                self.CodingSchemeResourcesSequence = resources
            elif isinstance(resrc, CodingSchemeRegistry):
                self.CodingSchemeResourcesSequence = [resources, ]
