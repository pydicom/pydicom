import pytest

from pydicom.sr._cid_dict import (
    cid_concepts as CID_CONCEPTS,
    name_for_cid,
)
from pydicom.sr._concepts_dict import concepts as CONCEPTS
from pydicom.sr.coding import Code
from pydicom.sr.codedict import (
    codes,
    Collection,
    Concepts,
)


@pytest.fixture()
def ambiguous_scheme():
    """Add a scheme to the CID concepts dict that contains a duplicate attr"""
    cid = 6129
    attr = CID_CONCEPTS[cid]["SCT"][0]
    assert "FOO" not in CID_CONCEPTS[cid]
    CID_CONCEPTS[cid]["FOO"] = [attr]
    yield attr, cid
    del CID_CONCEPTS[cid]["FOO"]


@pytest.fixture()
def add_nonunique():
    """Add a non-unique keyword to the concepts dict"""
    CONCEPTS["TEST"] = {
        "Foo": {"BAR": ("Test A", [99999999999]), "BAZ": ("Test B", [99999999999])}
    }
    yield
    del CONCEPTS["TEST"]


@pytest.fixture()
def add_nonunique_cid():
    """Add a non-unique keyword to the CIDs dict"""
    CONCEPTS["TEST"] = {
        "Foo": {"BAR": ("Test A", [99999999999]), "BAZ": ("Test B", [99999999999])}
    }
    CID_CONCEPTS[99999999999] = {"TEST": ["Foo", "Foo"]}
    name_for_cid[99999999999] = "Test"
    yield
    del CONCEPTS["TEST"]
    del CID_CONCEPTS[99999999999]
    del name_for_cid[99999999999]


@pytest.fixture()
def add_multiple_cid():
    """Add multiple codes for a keyword, but with different CIDs"""
    CONCEPTS["TEST"] = {
        "Foo": {
            "BAR": ("Test A", [99999999999]),
            "BAZ": ("Test B", [99999999998]),
        },
    }
    CID_CONCEPTS[99999999999] = {"TEST": ["Foo"]}
    name_for_cid[99999999999] = "Test"
    yield
    del CONCEPTS["TEST"]
    del CID_CONCEPTS[99999999999]
    del name_for_cid[99999999999]


class TestCode:
    def setup_method(self):
        self._value = "373098007"
        self._meaning = "Mean Value of population"
        self._scheme_designator = "SCT"

    def test_construction_kwargs(self):
        c = Code(
            value=self._value,
            scheme_designator=self._scheme_designator,
            meaning=self._meaning,
        )
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version is None

    def test_use_as_dictionary_key(self):
        c = Code(
            value=self._value,
            scheme_designator=self._scheme_designator,
            meaning=self._meaning,
        )
        d = {c: 1}
        assert c in d.keys()

    def test_construction_kwargs_optional(self):
        version = "v1.0"
        c = Code(
            value=self._value,
            scheme_designator=self._scheme_designator,
            meaning=self._meaning,
            scheme_version=version,
        )
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version == version

    def test_construction_args(self):
        c = Code(self._value, self._scheme_designator, self._meaning)
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version is None

    def test_construction_args_optional(self):
        version = "v1.0"
        c = Code(self._value, self._scheme_designator, self._meaning, version)
        assert c.value == self._value
        assert c.scheme_designator == self._scheme_designator
        assert c.meaning == self._meaning
        assert c.scheme_version == version

    def test_equal(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code(self._value, self._scheme_designator, self._meaning)
        assert c1 == c2

    def test_not_equal(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code("373099004", "SCT", "Median Value of population")
        assert c1 != c2

    def test_equal_ignore_meaning(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code(self._value, self._scheme_designator, "bla bla bla")
        assert c1 == c2

    def test_equal_equivalent_coding(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code("R-00317", "SRT", self._meaning)
        assert c1 == c2
        assert c2 == c1

    def test_equal_not_in_snomed_mapping(self):
        c1 = Code(self._value, self._scheme_designator, self._meaning)
        c2 = Code("bla bal bla", "SRT", self._meaning)
        assert c1 != c2
        assert c2 != c1


class TestCollection:
    """Tests for Collection"""

    def test_init(self):
        """Test creation of new collections"""
        coll = Collection("SCT")
        assert coll.name == "SCT"
        assert coll.scheme_designator == "SCT"
        assert coll.is_cid is False

        coll = Collection("CID2")
        assert coll.name == "CID2"
        assert coll.scheme_designator == "CID2"
        assert coll.is_cid is True

    def test_concepts(self):
        """Test Collection.concepts"""
        coll = Collection("UCUM")
        assert coll._concepts == {}
        concepts = coll.concepts
        assert coll._concepts != {}
        assert concepts["Second"] == Code(
            "s", scheme_designator="UCUM", meaning="second"
        )

        coll = Collection("CID2")
        assert coll.concepts["Transverse"] == Code(
            "62824007", scheme_designator="SCT", meaning="Transverse"
        )

    def test_contains(self):
        """Test the in operator"""
        coll = Collection("UCUM")
        assert "Second" in coll
        assert "Foo" not in coll

        coll = Collection("CID2")
        assert "Transverse" in coll
        assert "Foo" not in coll

        c = Code("24028007", "SCT", "Right")
        assert c in codes.CID244
        assert c in codes.SCT

    def test_dir(self):
        """Test dir()"""
        coll = Collection("UCUM")
        assert "Second" in dir(coll)
        assert "Foo" not in dir(coll)

        coll = Collection("CID2")
        assert "Transverse" in dir(coll)
        assert "Foo" not in dir(coll)

        coll = Collection("CID4")
        matches = coll.dir("Thoracic")
        assert "CervicoThoracicSpine" in matches
        assert "IntraThoracic" in matches
        assert "StructureOfDescendingThoracicAorta" in matches
        assert "ThoracicSpine" in matches

        # Check None_
        coll = Collection("CID606")
        assert "None_" in coll
        assert "None_" in dir(coll)

        # Check _125Iodine
        coll = Collection("CID18")
        assert "_125Iodine" in coll
        assert "_125Iodine" in dir(coll)

    def test_getattr(self):
        """Test Collection.Foo"""
        coll = Collection("UCUM")
        assert coll.Second == Code("s", scheme_designator="UCUM", meaning="second")
        msg = "No matching code for keyword 'Foo' in scheme 'UCUM'"
        with pytest.raises(AttributeError, match=msg):
            coll.Foo

        coll = Collection("CID2")
        assert coll.Transverse == Code(
            "62824007", scheme_designator="SCT", meaning="Transverse"
        )

        msg = "No matching code for keyword 'Foo' in CID2"
        with pytest.raises(AttributeError, match=msg):
            coll.Foo

        coll.foo = None
        assert coll.foo is None

    def test_getattr_multiple_cid(self, add_multiple_cid):
        """Test Collection.Foo for a CID"""
        coll = Collection("CID99999999999")
        assert coll.Foo == Code("BAR", scheme_designator="TEST", meaning="Test A")

    def test_getattr_multiple_raises(self, add_nonunique):
        """Test non-unique results for the keyword"""
        coll = Collection("TEST")
        msg = "Multiple codes found for keyword 'Foo' in scheme 'TEST': BAR, BAZ"
        with pytest.raises(RuntimeError, match=msg):
            coll.Foo

    def test_getattr_multiple_raises_cid(self, add_nonunique_cid):
        """Test non-unique results for the keyword"""
        coll = Collection("CID99999999999")
        msg = "Multiple codes found for keyword 'Foo' in CID99999999999: BAR, BAZ"
        with pytest.raises(RuntimeError, match=msg):
            coll.Foo

        coll._cid_data["TEST2"] = ["Foo"]
        msg = (
            "Multiple schemes found to contain the keyword 'Foo' in CID99999999999: "
            "TEST, TEST2"
        )
        with pytest.raises(RuntimeError, match=msg):
            coll.Foo

    def test_repr(self):
        """Test repr()"""
        coll = Collection("UCUM")
        assert (
            "Second = Code(value='s', scheme_designator='UCUM', meaning='second', "
            "scheme_version=None)"
        ) in repr(coll)

        coll = Collection("CID2")
        assert (
            "Transverse = Code(value='62824007', scheme_designator='SCT', "
            "meaning='Transverse', scheme_version=None)"
        ) in repr(coll)

    def test_str(self):
        """Test str()"""
        coll = Collection("UCUM")
        assert (
            "Second                                                  s          "
            "                  second\n"
        ) in str(coll)

        coll = Collection("CID2")
        assert "Transverse       62824007    SCT      Transverse\n" in str(coll)

    def test_trait_names(self):
        """Test trait_names()"""
        traits = Collection("UCUM").trait_names()
        assert "Second" in traits
        assert "Foo" not in traits

        traits = Collection("CID2").trait_names()
        assert "Transverse" in traits
        assert "Foo" not in traits


class TestConcepts:
    """Tests for Concepts"""

    def test_init(self):
        """Test creating a new instance"""
        colls = Concepts([Collection("SCT"), Collection("CID2")])

        assert list(colls.collections) == ["SCT", "CID2"]
        assert colls.schemes() == ["SCT"]
        assert colls.CIDs() == ["CID2"]

    def test_getattr(self):
        """Test Concepts.Foo"""
        colls = Concepts([Collection("SCT"), Collection("CID2")])

        assert isinstance(colls.SCT, Collection)
        assert isinstance(colls.CID2, Collection)

        colls.foo = None
        assert colls.foo is None

        msg = "'Concepts' object has no attribute 'Foo'"
        with pytest.raises(AttributeError, match=msg):
            colls.Foo
