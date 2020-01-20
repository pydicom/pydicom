====================
Structured Reporting
====================

.. versionadded:: 1.4

Starting in *pydicom* version 1.4, some support for DICOM Structured Reporting (SR) began to be added,
as alpha code; the API for this is subject to change in future *pydicom* versions. At this point the 
code is limited to code dictionaries and one class :class:`~pydicom.sr.coding.Code` 
as a foundational step for future work.

Most access is through a ``codes`` class instance provided in ``pydicom.sr.codedict``. This can be used 
with a ``dir()`` method on a particular scheme designator ('DCM' here) or CID (see further below)::

    >>> from pydicom.sr.codedict import codes
    >>> codes.DCM.dir("Modality")
    ['IncorrectModalityWorklistEntry', 'MixedModality3DCAMModel', 'Modality', 'ModalityToRead', 'OtherModality']

Once a name is known, the ``Code`` instance can be created using that name::

    >>> codes.DCM.ModalityToRead
    Code(value='128002', scheme_designator='DCM', meaning='Modality to Read', scheme_version=None)

Codes with keywords that start with a number are prefixed with an underscore::

    >>> codes.SCT._1SigmaLowerValueOfPopulation
    Code(value='371919006', scheme_designator='SCT', meaning='1 Sigma Lower Value of population', scheme_version=None)

Codes can also be accessed by CID::

    >>> codes.cid270.Person
    Code(value='121006', scheme_designator='DCM', meaning='Person', scheme_version=None)
    >>> codes.cid270.dir()
    ['Device', 'Person']

If the CID number is unknown, it is possible to find it through a CID name dictionary::

    >>> from pydicom.sr.codedict import cid_for_name
    >>> [name for name in cid_for_name if 'Observ' in name]
    ['ObservationSubjectClass', 'ObserverType', 'EchoFindingObservationTypes']
    >>> cid_for_name['ObserverType']
    270   


The following Scheme Designators are available in ``codes``:
SCT, DCM, LN, FMA, MDC, UMLS, BARI, NCIt,
NEU, UCUM, RADLEX, NDC, ITIS_TSN, PUBCHEM_CID, MSH

As noted, these steps do not yet directly provide SR capabilities in *pydicom*, but provide some access
to codes and CIDs in a similar way to DICOM keywords for the DICOM dictionary.
