"""DICOM structured reporting content item value types."""
from enum import Enum

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.sr.coding import Code, CodedConcept
from pydicom.valuerep import DA, TM, DT, PersonName


Concept = namedtuple('Concept', "value scheme_designator meaning ".split())


class ValueTypes(Enum):
    CODE = 'CODE'
    COMPOSITE = 'COMPOSITE'
    CONTAINER = 'CONTAINER'
    DATE = 'DATE'
    DATETIME = 'DATETIME'
    IMAGE = 'IMAGE'
    NUM = 'NUM'
    PNAME = 'PNAME'
    SCOORD = 'SCOORD'
    SCOORD3D = 'SCOORD3D'
    TCOORD = 'TCOORD'
    TEXT = 'TEXT'
    TIME = 'TIME'
    UIDREF = 'UIDREF'
    WAVEFORM = 'WAVEFORM'


class GraphicTypes(Enum):
    CIRCLE = 'CIRCLE'
    ELLIPSE = 'ELLIPSE'
    ELLIPSOID = 'ELLIPSOID'
    MULTIPOINT = 'MULTIPOINT'
    POINT = 'POINT'
    POLYLINE = 'POLYLINE'


class GraphicTypes3D(Enum):
    ELLIPSE = 'ELLIPSE'
    ELLIPSOID = 'ELLIPSOID'
    MULTIPOINT = 'MULTIPOINT'
    POINT = 'POINT'
    POLYLINE = 'POLYLINE'
    POLYGON = 'POLYGON'


class TemporalRangeTypes(Enum):
    BEGIN = 'BEGIN'
    END = 'END'
    MULTIPOINT = 'MULTIPOINT'
    MULTISEGMENT = 'MULTISEGMENT'
    POINT = 'POINT'
    SEGMENT = 'SEGMENT'


class RelationshipTypes(Enum):
    CONTAINS = 'CONTAINS'
    HAS_ACQ_CONTENT = 'HAS ACQ CONTENT'
    HAS_CONCEPT_MOD = 'HAS CONCEPT MOD'
    HAS_OBS_CONTEXT = 'HAS OBS CONTEXT'
    HAS_PROPERTIES = 'HAS PROPERTIES'
    INFERRED_FROM = 'INFERRED FROM'
    SELECTED_FROM = 'SELECTED FROM'


class PixelOriginInterpretations(Enum):
    FRAME = 'FRAME'
    VOLUME = 'VOLUME'


class ContentItem(Dataset):

    """Abstract base class for a collection of attributes contained in the
    DICOM SR Document Content Module."""

    def __init__(self, value_type, name, relationship_type):
        """
        Parameters
        ----------
        value_type: str
            type of value encoded in a content item
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            coded name or an enumerated item representing a coded name
        relationship_type: Union[str, None]
            type of relationship with parent content item

        """  #noqa
        super(ContentItem, self).__init__()
        value_type = ValueTypes(value_type)
        self.ValueType = value_type.value
        if not isinstance(name, (CodedConcept, Code, )):
            raise TypeError(
                'Argument "name" must have type CodedConcept or Code.'
            )
        if isinstance(name, Code):
            name = CodedConcept(*name)
        self.ConceptNameCodeSequence = [name]
        if relationship_type is not None:
            relationship_type = RelationshipTypes(relationship_type)
            self.RelationshipType = relationship_type.value

    def __setattr__(self, name, value):
        if name == 'ContentSequence':
            super(ContentItem, self).__setattr__(name, ContentSequence(value))
        else:
            super(ContentItem, self).__setattr__(name, value)

    @property
    def name(self):
        """CodedConcept: coded name of the content item"""
        return self.ConceptNameCodeSequence[0]

    @property
    def value_type(self):
        """str: type of the content item
        (see `pydicom.sr.value_types.ValueTypes`)

        """
        return self.ValueType

    @property
    def relationship_type(self):
        """str: type of relationship the content item has with its parent
        (see `pydicom.sr.value_types.RelationshipTypes`)

        """
        return getattr(self, 'RelationshipType', None)

    def get_content_items(self, name=None, value_type=None,
                          relationship_type=None):
        """Gets content items, i.e. items contained in the content sequence,
        optionally filtering them based on specified criteria.

        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code, None]
            coded name that items should have
        value_type: Union[pydicom.sr.value_types.ValueTypes, None]
            type of value that items should have
            (e.g. ``pydicom.sr.value_types.ValueTypes.CONTAINER``)
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, None]
            type of relationship that items should have with its parent
            (e.g. ``pydicom.sr.value_types.RelationshipTypes.CONTAINS``)

        Returns
        -------
        pydicom.sr.value_types.ContentSequence[pydicom.sr.value_types.ContentItem]
            matched child content items

        Raises
        ------
        AttributeError
            when content item has no `ContentSequence` attribute

        """  #noqa
        try:
            content_sequence = self.ContentSequence
        except AttributeError:
            raise AttributeError(
                'Content item "{}" does not contain any child items.'.format(
                    self.name.meaning
                )
            )
        return content_sequence.filter(
            name=name,
            value_type=value_type,
            relationship_type=relationship_type
        )


class ContentSequence(Sequence):

    """Sequence of DICOM SR Content Items."""

    def __init__(self, iterable=None):
        if iterable is not None:
            if not all(isinstance(item, ContentItem) for item in iterable):
                raise TypeError(
                    'Items of "{}" must have type ContentItem.'.format(
                        self.__class__.__name__
                    )
                )
        super(ContentSequence, self).__init__(iterable)

    def __setitem__(self, position, item):
        self.insert(position, item)

    def __contains__(self, item):
        return any([item == contained_item for contained_item in self])

    def get_nodes(self):
        """Gets content items that represent nodes in the content tree, i.e.
        target items that have a `ContentSequence` attribute.

        Returns
        -------
        pydicom.sr.value_types.ContentSequence[pydicom.sr.value_types.ContentItem]
            matched content items

        """
        return self.__class__([
            item for item in self
            if hasattr(item, 'ContentSequence')
        ])

    def filter(self, name=None, value_type=None, relationship_type=None):
        """Filters content items.

        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code, None], optional
            coded name that items should have
        value_type: Union[pydicom.sr.value_types.ValueTypes, None], optional
            type of value that items should have
            (e.g. ``pydicom.sr.value_types.ValueTypes.CONTAINER``)
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, None], optional
            type of relationship that items should have with its parent
            (e.g. ``pydicom.sr.value_types.RelationshipTypes.CONTAINS``)

        Returns
        -------
        pydicom.sr.value_types.ContentSequence[pydicom.sr.value_types.ContentItem]
            matched content items

        """  #noqa
        def has_matching_name(item):
            if name is None:
                return True
            return item.name == name

        def has_matching_value_type(item):
            if value_type is None:
                return True
            return item.value_type == value_type.value

        def has_matching_relationship_type(item):
            if relationship_type is None:
                return True
            return item.relationship_type == relationship_type.value

        return self.__class__([
            item for item in self
            if has_matching_name(item)
            and has_matching_value_type(item)
            and has_matching_relationship_type(item)
        ])

    def append(self, item):
        """Appends a content item to the sequence.

        Parameters
        ----------
        item: pydicom.sr.value_types.ContentItem
            content item

        """
        if not isinstance(item, ContentItem):
            raise TypeError(
                'Items of "{}" must have type ContentItem.'.format(
                    self.__class__.__name__
                )
            )
        super(ContentSequence, self).append(item)

    def extend(self, items):
        """Extends multiple content items to the sequence.

        Parameters
        ----------
        items: pydicom.sr.value_types.ContentSequence[pydicom.sr.value_types.ContentItem]
            content items

        """
        if not isinstance(items, ContentSequence):
            raise TypeError('Items must have type ContentSequence.')
        for item in items:
            self.append(item)

    def insert(self, position, item):
        """Inserts a content item into the sequence at a given position.

        Parameters
        ----------
        position: int
            index position
        item: pydicom.sr.value_types.ContentItem
            content item

        """
        if not isinstance(item, ContentItem):
            raise TypeError(
                'Items of "{}" must have type ContentItem.'.format(
                    self.__class__.__name__
                )
            )
        super(ContentSequence, self).insert(position, item)


class CodeContentItem(ContentItem):

    """DICOM SR document content item for value type CODE."""

    def __init__(self, name, value, relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        value: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            coded value or an enumerated item representing a coded value
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None]
            type of relationship with parent content item

        """  # noqa
        super(CodeContentItem, self).__init__(
            ValueTypes.CODE, name, relationship_type
        )
        if not isinstance(value, (CodedConcept, Code, )):
            raise TypeError(
                'Argument "value" must have type CodedConcept or Code.'
            )
        if isinstance(value, Code):
            value = CodedConcept(*value)
        self.ConceptCodeSequence = [value]


class PnameContentItem(ContentItem):

    """DICOM SR document content item for value type PNAME."""

    def __init__(self, name, value, relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        value: str
            name of the person
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None]
            type of relationship with parent content item

        """  # noqa
        super(PnameContentItem, self).__init__(
            ValueTypes.PNAME, name, relationship_type
        )
        self.PersonName = PersonName(value)


class TextContentItem(ContentItem):

    """DICOM SR document content item for value type TEXT."""

    def __init__(self, name, value, relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        value: str
            description of the concept in free text
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str]
            type of relationship with parent content item

        """
        super(TextContentItem, self).__init__(
            ValueTypes.TEXT, name, relationship_type
        )
        self.TextValue = str(value)


class TimeContentItem(ContentItem):

    """DICOM SR document content item for value type TIME."""

    def __init__(self, name, value, relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        value: pydicom.valuerep.TM
            time
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None]
            type of relationship with parent content item

        """  # noqa
        super(TimeContentItem, self).__init__(
            ValueTypes.TIME, name, relationship_type
        )
        self.Time = TM(value)


class DateContentItem(ContentItem):

    """DICOM SR document content item for value type DATE."""

    def __init__(self, name, value, relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        value: Union[pydicom.valuerep.DA, str]
            date
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None]
            type of relationship with parent content item

        """  # noqa
        super(DateContentItem, self).__init__(
            ValueTypes.DATE, name, relationship_type
        )
        self.Date = DA(value)


class DateTimeContentItem(ContentItem):

    """DICOM SR document content item for value type DATETIME."""

    def __init__(self, name, value, relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        value: Union[pydicom.valuerep.DT, str]
            datetime
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None]
            type of relationship with parent content item

        """  # noqa
        super(DateTimeContentItem, self).__init__(
            ValueTypes.DATETIME, name, relationship_type
        )
        self.DateTime = DT(value)


class UIDRefContentItem(ContentItem):

    """DICOM SR document content item for value type UIDREF."""

    def __init__(self, name, value, relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        value: Union[pydicom.uid.UID, str]
            unique identifier
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None]
            type of relationship with parent content item

        """  # noqa
        super(UIDRefContentItem, self).__init__(
            ValueTypes.UIDREF, name, relationship_type
        )
        self.UID = str(value)


class NumContentItem(ContentItem):

    """DICOM SR document content item for value type NUM."""

    def __init__(self, name, value=None, unit=None, qualifier=None,
                 relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        value: Union[int, float], optional
            numeric value
        unit: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code, None], optional
            coded units of measurement (see CID 7181 "Abstract Multi-dimensional
            Image Model Component Units")
        qualifier: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code, None], optional
            qualification of numeric value or as an alternative to
            numeric value, e.g., reason for absence of numeric value
            (see CID 42 "Numeric Value Qualifier" for options)
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None], optional
            type of relationship with parent content item

        Note
        ----
        Either `value` and `unit` or `qualifier` must be specified.

        """ # noqa
        super(NumContentItem, self).__init__(
            ValueTypes.NUM, name, relationship_type
        )
        if value is not None:
            self.MeasuredValueSequence = []
            measured_value_sequence_item = Dataset()
            if not isinstance(value, (int, float, )):
                raise TypeError(
                    'Argument "value" must have type "int" or "float".'
                )
            measured_value_sequence_item.NumericValue = value
            if isinstance(value, float):
                measured_value_sequence_item.FloatingPointValue = value
            if not isinstance(unit, (CodedConcept, Code, )):
                raise TypeError(
                    'Argument "unit" must have type CodedConcept or Code.'
                )
            if isinstance(unit, Code):
                unit = CodedConcept(*unit)
            measured_value_sequence_item.MeasurementUnitsCodeSequence = [unit]
            self.MeasuredValueSequence.append(measured_value_sequence_item)
        elif qualifier is not None:
            if not isinstance(qualifier, (CodedConcept, Code, )):
                raise TypeError(
                    'Argument "qualifier" must have type "CodedConcept" or '
                    '"Code".'
                )
            if isinstance(qualifier, Code):
                qualifier = CodedConcept(*qualifier)
            self.NumericValueQualifierCodeSequence = [qualifier]
        else:
            raise ValueError(
                'Either argument "value" or "qualifier" must be specified '
                'upon creation of NumContentItem.'
            )


class ContainerContentItem(ContentItem):

    """DICOM SR document content item for value type CONTAINER."""

    def __init__(self, name, relationship_type=None,
                 is_content_continuous=True, template_id=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        relationship_type: Union[str, None], optional
            type of relationship with parent content item
        is_content_continous: bool, optional
            whether contained content items are logically linked in a
            continuous manner or separate items (default: ``True``)
        template_id: Union[str, None], optional
            SR template identifier

        """
        super(ContainerContentItem, self).__init__(
            ValueTypes.CONTAINER, name, relationship_type
        )
        if is_content_continuous:
            self.ContinuityOfContent = 'CONTINUOUS'
        else:
            self.ContinuityOfContent = 'SEPARATE'
        if template_id is not None:
            item = Dataset()
            item.MappingResource = 'DCMR'
            item.TemplateIdentifier = str(template_id)
            self.ContentTemplateSequence = [item]


class CompositeContentItem(ContentItem):

    """DICOM SR document content item for value type COMPOSITE."""

    def __init__(self, name,
                 referenced_sop_class_uid, referenced_sop_instance_uid,
                 relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str]
            type of relationship with parent content item
        referenced_sop_class_uid: Union[pydicom.uid.UID, str]
            SOP Class UID of the referenced object
        referenced_sop_instance_uid: Union[pydicom.uid.UID, str]
            SOP Instance UID of the referenced object
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None], optional
            type of relationship with parent content item

        """  # noqa
        super(CompositeContentItem, self).__init__(
            ValueTypes.COMPOSITE, name, relationship_type
        )
        item = Dataset()
        item.ReferencedSOPClassUID = str(referenced_sop_class_uid)
        item.ReferencedSOPInstanceUID = str(referenced_sop_instance_uid)
        self.ReferencedSOPSequence = [item]


class ImageContentItem(ContentItem):

    """DICOM SR document content item for value type IMAGE."""

    def __init__(self, name,
                 referenced_sop_class_uid, referenced_sop_instance_uid,
                 referenced_frame_numbers=None, referenced_segment_numbers=None,
                 relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        referenced_sop_class_uid: Union[pydicom.uid.UID, str]
            SOP Class UID of the referenced image object
        referenced_sop_instance_uid: Union[pydicom.uid.UID, str]
            SOP Instance UID of the referenced image object
        referenced_frame_numbers: Union[int, List[int], None], optional
            number of frame(s) to which the reference applies in case of a
            multi-frame image
        referenced_segment_numbers: Union[int, List[int], None], optional
            number of segment(s) to which the refernce applies in case of a
            segmentation image
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None], optional
            type of relationship with parent content item

        """  # noqa
        super(ImageContentItem, self).__init__(
            ValueTypes.IMAGE, name, relationship_type
        )
        item = Dataset()
        item.ReferencedSOPClassUID = str(referenced_sop_class_uid)
        item.ReferencedSOPInstanceUID = str(referenced_sop_instance_uid)
        if referenced_frame_numbers is not None:
            item.ReferencedFrameNumber = referenced_frame_numbers
        if referenced_segment_numbers is not None:
            item.ReferencedSegmentNumber = referenced_segment_numbers
        self.ReferencedSOPSequence = [item]


class ScoordContentItem(ContentItem):

    """DICOM SR document content item for value type SCOORD.

    Note
    ----
    Spatial coordinates are defined in image space and have pixel units.

    """

    def __init__(self, name, graphic_type, graphic_data,
                 pixel_origin_interpretation, fiducial_uid=None,
                 relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        graphic_type: Union[pydicom.sr.value_types.GraphicTypes, str]
            name of the graphic type
        graphic_data: Union[List[List[Union[int, float]]], List[Union[int, float]]]
            ordered (column, row) coordinate pairs
        pixel_origin_interpretation: Union[pydicom.sr.value_types.PixelOriginInterpretations, str]
            whether pixel coordinates specified by `graphic_data` are defined
            relative to the total pixel matrix
            (``pydicom.sr.value_types.PixelOriginInterpretations.VOLUME``) or
            relative to an individual frame
            (``pydicom.sr.value_types.PixelOriginInterpretations.FRAME``)
        fiducial_uid: Union[pydicom.uid.UID, str, None], optional
            unique identifier for the content item
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None], optional
            type of relationship with parent content item

        """  # noqa
        super(ScoordContentItem, self).__init__(
            ValueTypes.SCOORD, name, relationship_type
        )
        graphic_type = GraphicTypes(graphic_type)
        pixel_origin_interpretation = PixelOriginInterpretations(
            pixel_origin_interpretation
        )
        self.GraphicType = graphic_type.value

        def is_point(coordinate):
            try:
                return all([
                    isinstance(coordinate, (list, tuple, )),
                    len(coordinate) == 2,
                    all([isinstance(c, (int, float, )) for c in coordinate]),
                ])
            except IndexError:
                return False

        if graphic_type == GraphicTypes.POINT:
            if not is_point(graphic_data):
                raise ValueError(
                    'Graphic data of a scoord of graphic type "POINT" '
                    'must be a single (column row) pair in two-dimensional '
                    'image coordinate space.'
                )
            # Flatten list of coordinate pairs
            self.GraphicData = [
                float(coordinate) for coordinate in graphic_data
            ]
        else:
            # TODO: This may be expensive for large lists.
            are_all_points = all([
                is_point(coordinates) for coordinates in graphic_data
            ])
            if graphic_type == GraphicTypes.CIRCLE:
                if len(graphic_data) != 2 or not(are_all_points):
                    raise ValueError(
                        'Graphic data of a scoord of graphic type "CIRCLE" '
                        'must be two (column, row) pairs in two-dimensional '
                        'image coordinate space.'
                    )
            elif graphic_type == GraphicTypes.ELLIPSE:
                if len(graphic_data) != 4 or not(are_all_points):
                    raise ValueError(
                        'Graphic data of a scoord of graphic type "ELLIPSE" '
                        'must be four (column, row) pairs in two-dimensional '
                        'image coordinate space.'
                    )
            elif graphic_type == GraphicTypes.ELLIPSOID:
                if len(graphic_data) != 6 or not(are_all_points):
                    raise ValueError(
                        'Graphic data of a scoord of graphic type "ELLIPSOID" '
                        'must be six (column, row) pairs in two-dimensional '
                        'image coordinate space.'
                    )
            else:
                if not len(graphic_data) > 1 or not(are_all_points):
                    raise ValueError(
                        'Graphic data of a scoord must be multiple '
                        '(column, row) pairs in two-dimensional image '
                        'coordinate space.'
                    )
            # Flatten list of coordinate pairs
            self.GraphicData = [
                float(coordinate) for pair in graphic_data
                for coordinate in pair
            ]
        self.PixelOriginInterpretation = pixel_origin_interpretation.value
        if fiducial_uid is not None:
            self.FiducialUID = fiducial_uid


class Scoord3DContentItem(ContentItem):

    """DICOM SR document content item for value type SCOORD3D.

    Note
    ----
    Spatial coordinates are defined in the patient or specimen-based coordinate
    system and have milimeter unit.

    """

    def __init__(self, name, graphic_type, graphic_data,
                 frame_of_reference_uid, fiducial_uid=None,
                 relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        graphic_type: Union[pydicom.sr.value_types.GraphicTypes, str]
            name of the graphic type
        graphic_data: List[List[int, float]]
            ordered set of (x, y, z) coordinate triplets
        frame_of_reference_uid: Union[pydicom.uid.UID, str]
            unique identifier of the frame of reference within which the
            coordinates are defined
        fiducial_uid: Union[str, None], optional
            unique identifier for the content item
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None], optional
            type of relationship with parent content item

        """  # noqa
        super(Scoord3DContentItem, self).__init__(
            ValueTypes.SCOORD3D, name, relationship_type
        )
        graphic_type = GraphicTypes3D(graphic_type)
        self.GraphicType = graphic_type.value

        def is_point(coordinate):
            try:
                return all([
                    isinstance(coordinate, (list, tuple, )),
                    len(coordinate) == 3,
                    all([isinstance(c, (int, float, )) for c in coordinate]),
                ])
            except IndexError:
                return False

        if graphic_type == GraphicTypes3D.POINT:
            if not is_point(graphic_data):
                raise ValueError(
                    'Graphic data of a scoord 3D of graphic type "POINT" '
                    'must be a single point in three-dimensional patient or '
                    'slide coordinate space in form of a (x, y, z) triplet.'
                )
            self.GraphicData = [
                float(coordinate) for coordiante in graphic_data
            ]
        else:
            are_all_points = all([
                is_point(coordinates) for coordinates in graphic_data
            ])
            if graphic_type == GraphicTypes3D.ELLIPSE:
                if len(graphic_data) != 4 or not(are_all_points):
                    raise ValueError(
                        'Graphic data of a 3D scoord of graphic type "ELLIPSE" '
                        'must be four (x, y, z) triplets in three-dimensional '
                        'patient or slide coordinate space.'
                    )
            elif graphic_type == GraphicTypes3D.ELLIPSOID:
                if len(graphic_data) != 6 or not(are_all_points):
                    raise ValueError(
                        'Graphic data of a 3D scoord of graphic type '
                        '"ELLIPSOID" must be six (x, y, z) triplets in '
                        'three-dimensional patient or slide coordinate space.'
                    )
            else:
                if not len(graphic_data) > 1 or not(are_all_points):
                    raise ValueError(
                        'Graphic data of a 3D scoord must be multiple '
                        '(x, y, z) triplets in three-dimensional patient or '
                        'slide coordinate space.'
                    )
            # Flatten list of coordinate triplets
            self.GraphicData = [
                float(coordinate) for triplet in graphic_data
                for coordinate in triplet
            ]
        self.ReferencedFrameOfReferenceUID = frame_of_reference_uid
        if fiducial_uid is not None:
            self.FiducialUID = fiducial_uid


class TcoordContentItem(ContentItem):

    """DICOM SR document content item for value type TCOORD."""

    def __init__(self, name, referenced_sample_positions,
                 referenced_time_offsets, referenced_date_time=None,
                 relationship_type=None):
        """
        Parameters
        ----------
        name: Union[pydicom.sr.coding.CodedConcept, pydicom.sr.coding.Code]
            concept name
        temporal_range_type: Union[pydicom.sr.value_types.TemporalRangeTypes, str]
            name of the temporal range type
        referenced_sample_positions: Union[List[int], None], optional
            one-based relative sample position of acquired time points
            within the time series
        referenced_time_offsets: Union[List[float], None], optional
            seconds after start of the acquisition of the time series
        referenced_date_time: Union[List[datetime.datetime], None], optional
            absolute time points
        relationship_type: Union[pydicom.sr.value_types.RelationshipTypes, str, None], optional
            type of relationship with parent content item

        """  # noqa
        super(TcoordContentItem, self).__init__(
            ValueTypes.TSCOORD, name, relationship_type
        )
        temporal_range_type = TemporalRangeTypes(temporal_range_type)
        self.TemporalRangeType = temporal_range_type.value
        if referenced_sample_positions is not None:
            self.ReferencedSamplePositions = [
                int(v) for v in referenced_sample_positions
            ]
        elif referenced_time_offsets is not None:
            self.ReferencedTimeOffsets = [
                float(v) for v in referenced_time_offsets
            ]
        elif referenced_date_time is not None:
            self.ReferencedDateTime = [
                DT(v) for v in referenced_date_time
            ]
        else:
            raise ValueError(
                'One of the following arguments is required: "{}"'.format(
                    '", "'.join([
                        'referenced_sample_positions',
                        'referenced_time_offsets',
                        'referenced_date_time'
                    ])
                )
            )
