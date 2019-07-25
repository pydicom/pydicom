# -*- coding: utf-8 -*-
# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
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
    ds.add_new(0x00091003, 'OW', b'\x0102\x3040\x5060')
    ds.add_new(0x00091004, 'OF', b'\x00\x01\x02\x03\x04\x05\x06\x07')
    ds.add_new(0x00091005, 'OD', b'\x00\x01\x02\x03\x04\x05\x06\x07'
                                 b'\x01\x01\x02\x03\x04\x05\x06\x07')
    ds.add_new(0x00091006, 'OL', b'\x00\x01\x02\x03\x04\x05\x06\x07'
                                 b'\x01\x01\x02\x03')
    ds.add_new(0x00091007, 'UI', '1.2.3.4.5.6')
    ds.add_new(0x00091008, 'DA', '20200101')
    ds.add_new(0x00091009, 'TM', '115500')
    ds.add_new(0x0009100a, 'DT', '20200101115500.000000')
    ds.add_new(0x0009100b, 'UL', 3000000000)
    ds.add_new(0x0009100c, 'SL', -2000000000)
    ds.add_new(0x0009100d, 'US', 40000)
    ds.add_new(0x0009100e, 'SS', -22222)
    ds.add_new(0x0009100f, 'FL', 3.14)
    ds.add_new(0x00091010, 'FD', 3.14159265)
    ds.add_new(0x00091011, 'CS', 'TEST MODE')
    ds.add_new(0x00091012, 'PN', 'CITIZEN^1')
    ds.add_new(0x00091013, 'PN', u'Yamada^Tarou=山田^太郎=やまだ^たろう')
    ds.add_new(0x00091014, 'IS', '42')
    ds.add_new(0x00091015, 'DS', '3.14159265')
    ds.add_new(0x00091016, 'AE', b'CONQUESTSRV1')
    ds.add_new(0x00091017, 'AS', '055Y')
    ds.add_new(0x00091018, 'LT', 50 * u'Калинка,')
    ds.add_new(0x00091019, 'UC', 'LONG CODE VALUE')
    ds.add_new(0x0009101a, 'UN', b'\x0102\x3040\x5060')
    ds.add_new(0x0009101b, 'UR', 'https://example.com')
    ds.add_new(0x0009101c, 'AT', b'\x10\x00\x20\x00\x10\x00\x30\x00\x10')
    ds.add_new(0x0009101d, 'ST', 100 * u'علي بابا')
    ds.add_new(0x0009101e, 'SH', u'Διονυσιος')
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
