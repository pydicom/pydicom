import pytest
from pydicom.data import get_testdata_files
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom import compat

from pydicom.valuerep import PersonNameUnicode, PersonName3


def test_json_PN():
    s = open(get_testdata_files("test_PN.json")[0], "r").read()
    ds = Dataset.from_json(s)
    assert isinstance(ds[0x00080090].value,
                      (PersonNameUnicode, PersonName3))
    assert isinstance(ds[0x00100010].value,
                      (PersonNameUnicode, PersonName3))
    inner_seq = ds[0x04000561].value[0][0x04000550]
    dataelem = inner_seq[0][0x00100010]
    assert isinstance(dataelem.value, (PersonNameUnicode, PersonName3))


@pytest.mark.skipif(compat.in_py2,
                    reason='JSON conversion not yet working in Python 2')
def test_dataelem_from_json():
    tag = 0x0080090
    vr = "PN"
    value = [{"Alphabetic": ""}]
    dataelem = DataElement.from_json(Dataset, tag, vr, value, "Value")
    assert isinstance(dataelem.value, (PersonNameUnicode, PersonName3))


def test_json_roundtrip():
    ds = Dataset()
    ds.add_new(0x00080005, 'CS', 'ISO_IR 100')
    ds.add_new(0x00090010, 'LO', 'Creator 1.0')
    ds.add_new(0x00091001, 'SH', 'Version1')
    ds.add_new(0x00091002, 'OB', b'BinaryContent')
    ds.add_new(0x00091002, 'OW', b'\x0102\x3040\x5060')
    ds.add_new(0x00090011, 'LO', 'Creator 2.0')
    ds.add_new(0x00091101, 'SH', 'Version2')
    ds.add_new(0x00091102, 'US', 2)

    jsonmodel = ds.to_json(bulk_data_threshold=100)
    ds2 = Dataset.from_json(jsonmodel)

    assert ds2.SpecificCharacterSet == ['ISO_IR 100']


def test_json_private_DS_VM():
    test1_json = get_testdata_files("test1.json")[0]
    jsonmodel = open(test1_json, 'r').read()
    ds = Dataset.from_json(jsonmodel)
    import json
    jsonmodel2 = ds.to_json(dump_handler=lambda d: json.dumps(d, indent=2))
    ds2 = Dataset.from_json(jsonmodel2)

    assert ds.PatientIdentityRemoved == 'YES'
    assert ds2.PatientIdentityRemoved == 'YES'
