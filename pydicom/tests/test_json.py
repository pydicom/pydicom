# -*- coding: utf-8 -*-
# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
import json

import pytest

from pydicom import dcmread, compat
from pydicom.data import get_testdata_files
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom.tag import Tag, BaseTag
from pydicom.valuerep import PersonNameUnicode, PersonName3


class TestPersonName(object):
    def test_json_PN_from_file(self):
        with open(get_testdata_files("test_PN.json")[0]) as s:
            ds = Dataset.from_json(s.read())
        assert isinstance(ds[0x00080090].value,
                          (PersonNameUnicode, PersonName3))
        assert isinstance(ds[0x00100010].value,
                          (PersonNameUnicode, PersonName3))
        inner_seq = ds[0x04000561].value[0][0x04000550]
        dataelem = inner_seq[0][0x00100010]
        assert isinstance(dataelem.value, (PersonNameUnicode, PersonName3))

    def test_PN_components_to_json(self):
        def check_name(tag, components):
            # we cannot directly compare the dictionaries, as they are not
            # ordered in Python 2
            value = ds_json[tag]['Value']
            assert 1 == len(value)
            value = value[0]
            if len(components) == 3:
                assert components[2] == value['Phonetic']
            else:
                assert 'Phonetic' not in value
            if len(components) >= 2:
                assert components[1] == value['Ideographic']
            else:
                assert 'Ideographic' not in value
            assert components[0] == value['Alphabetic']

        ds = Dataset()
        ds.add_new(0x00100010, 'PN', u'Yamada^Tarou=山田^太郎=やまだ^たろう')
        ds.add_new(0x00091001, 'PN', u'Yamada^Tarou')
        ds.add_new(0x00091002, 'PN', u'Yamada^Tarou==')
        ds.add_new(0x00091003, 'PN', u'=山田^太郎=やまだ^たろう')
        ds.add_new(0x00091004, 'PN', u'Yamada^Tarou==やまだ^たろう')
        ds.add_new(0x00091005, 'PN', u'==やまだ^たろう')
        ds.add_new(0x00091006, 'PN', u'=山田^太郎')
        ds.add_new(0x00091007, 'PN', u'Yamada^Tarou=山田^太郎')
        ds_json = json.loads(ds.to_json())
        check_name('00100010', ['Yamada^Tarou', u'山田^太郎', u'やまだ^たろう'])
        check_name('00091001', ['Yamada^Tarou'])
        check_name('00091002', ['Yamada^Tarou'])
        check_name('00091003', ['', u'山田^太郎', u'やまだ^たろう'])
        check_name('00091004', ['Yamada^Tarou', '', u'やまだ^たろう'])
        check_name('00091005', ['', '', u'やまだ^たろう'])
        check_name('00091006', ['', u'山田^太郎'])
        check_name('00091007', ['Yamada^Tarou', u'山田^太郎'])

    def test_PN_components_from_json(self):
        # this is the encoded dataset from the previous test, with some
        # empty components omitted
        ds_json = (u'{"00100010": {"vr": "PN", "Value": [{"Alphabetic": '
                   u'"Yamada^Tarou", "Ideographic": "山田^太郎", '
                   u'"Phonetic": "やまだ^たろう"}]}, '
                   u'"00091001": {"vr": "PN", "Value": '
                   u'[{"Alphabetic": "Yamada^Tarou"}]}, '
                   u'"00091002": {"vr": "PN", "Value": '
                   u'[{"Alphabetic": "Yamada^Tarou", "Ideographic": "", '
                   u'"Phonetic": ""}]}, '
                   u'"00091003": {"vr": "PN", "Value": [{'
                   u'"Ideographic": "山田^太郎", '
                   u'"Phonetic": "やまだ^たろう"}]}, '
                   u'"00091004": {"vr": "PN", "Value": '
                   u'[{"Alphabetic": "Yamada^Tarou", '
                   u'"Phonetic": "やまだ^たろう"}]}, '
                   u'"00091005": {"vr": "PN", "Value": '
                   u'[{"Phonetic": "やまだ^たろう"}]}, '
                   u'"00091006": {"vr": "PN", "Value":'
                   u' [{"Ideographic": "山田^太郎"}]}, '
                   u'"00091007": {"vr": "PN", "Value": '
                   u'[{"Alphabetic": "Yamada^Tarou", '
                   u'"Ideographic": "山田^太郎"}]}}')
        if compat.in_py2:
            ds_json = ds_json.encode('UTF8')

        ds = Dataset.from_json(ds_json)
        assert u'Yamada^Tarou=山田^太郎=やまだ^たろう' == ds.PatientName
        assert u'Yamada^Tarou' == ds[0x00091001].value
        assert u'Yamada^Tarou' == ds[0x00091002].value
        assert u'=山田^太郎=やまだ^たろう' == ds[0x00091003].value
        assert u'Yamada^Tarou==やまだ^たろう' == ds[0x00091004].value
        assert u'==やまだ^たろう' == ds[0x00091005].value
        assert u'=山田^太郎' == ds[0x00091006].value
        assert u'Yamada^Tarou=山田^太郎' == ds[0x00091007].value

    def test_empty_value(self):
        ds = Dataset()
        ds.add_new(0x00100010, 'PN', '')
        ds_json = json.loads(ds.to_json())
        assert '00100010' in ds_json
        assert 'Value' not in ds_json['00100010']

    def test_multi_value_to_json(self):
        ds = Dataset()
        patient_names = [u'Buc^Jérôme', u'Διονυσιος', u'Люкceмбypг']
        ds.add_new(0x00091001, 'PN', patient_names)
        ds_json = json.loads(ds.to_json())
        assert [{'Alphabetic': u'Buc^Jérôme'},
                {'Alphabetic': u'Διονυσιος'},
                {'Alphabetic': u'Люкceмбypг'}] == ds_json['00091001']['Value']

    def test_dataelem_from_json(self):
        tag = 0x0080090
        vr = "PN"
        value = [{"Alphabetic": ""}]
        dataelem = DataElement.from_json(Dataset, tag, vr, value, "Value")
        assert isinstance(dataelem.value, (PersonNameUnicode, PersonName3))


class TestAT(object):
    def test_to_json(self):
        ds = Dataset()
        ds.add_new(0x00091001, 'AT', [0x00100010, 0x00100020])
        ds.add_new(0x00091002, 'AT', Tag(0x28, 0x02))
        ds.add_new(0x00091003, 'AT', BaseTag(0x00280002))
        ds.add_new(0x00091004, 'AT', [0x00280002, Tag('PatientName')])
        ds_json = json.loads(ds.to_json())

        assert ['00100010', '00100020'] == ds_json['00091001']['Value']
        assert ['00280002'] == ds_json['00091002']['Value']
        assert ['00280002'] == ds_json['00091003']['Value']
        assert ['00280002', '00100010'] == ds_json['00091004']['Value']

    def test_from_json(self):
        ds_json = ('{"00091001": {"vr": "AT", "Value": ["000910AF"]}, '
                   '"00091002": {"vr": "AT", "Value": ["00100010", '
                   '"00100020", "00100030"]}}')
        ds = Dataset.from_json(ds_json)
        assert 0x000910AF == ds[0x00091001].value
        assert [0x00100010, 0x00100020, 0x00100030] == ds[0x00091002].value

    def test_invalid_json(self):
        ds_json = ('{"00091001": {"vr": "AT", "Value": ["000910AG"]}, '
                   '"00091002": {"vr": "AT", "Value": ["00100010"]}}')
        with pytest.warns(UserWarning, match='Invalid value "000910AG" for '
                                             'AT element - ignoring it'):
            ds = Dataset.from_json(ds_json)
            assert ds[0x00091001].value is None
            assert 0x00100010 == ds[0x00091002].value


class TestDataSetToJson(object):
    def test_json_from_dicom_file(self):
        ds1 = Dataset(dcmread(get_testdata_files("CT_small.dcm")[0]))
        ds_json = ds1.to_json(bulk_data_threshold=100000)
        ds2 = Dataset.from_json(ds_json)
        assert ds1 == ds2

    def test_roundtrip(self):
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
        ds.add_new(0x0009101c, 'AT', [0x00100010, 0x00100020])
        ds.add_new(0x0009101d, 'ST', 100 * u'علي بابا')
        ds.add_new(0x0009101e, 'SH', u'Διονυσιος')
        ds.add_new(0x00090011, 'LO', 'Creator 2.0')
        ds.add_new(0x00091101, 'SH', 'Version2')
        ds.add_new(0x00091102, 'US', 2)

        json_string = ds.to_json(bulk_data_threshold=100)
        json_model = json.loads(json_string)
        assert json_model['00080005']['Value'] == ['ISO_IR 100']
        assert json_model['00091007']['Value'] == ['1.2.3.4.5.6']
        assert json_model['0009100A']['Value'] == ['20200101115500.000000']
        assert json_model['0009100B']['Value'] == [3000000000]
        assert json_model['0009100C']['Value'] == [-2000000000]
        assert json_model['0009100D']['Value'] == [40000]
        assert json_model['0009100F']['Value'] == [3.14]
        assert json_model['00091010']['Value'] == [3.14159265]
        assert json_model['00091018']['Value'] == [50 * u'Калинка,']

        ds2 = Dataset.from_json(json_string)
        assert ds == ds2

    def test_json_private_DS_VM(self):
        test1_json = get_testdata_files("test1.json")[0]
        jsonmodel = open(test1_json, 'r').read()
        ds = Dataset.from_json(jsonmodel)
        jsonmodel2 = ds.to_json(dump_handler=lambda d: json.dumps(d, indent=2))
        ds2 = Dataset.from_json(jsonmodel2)

        assert ds.PatientIdentityRemoved == 'YES'
        assert ds2.PatientIdentityRemoved == 'YES'
