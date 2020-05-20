# -*- coding: utf-8 -*-
# Copyright 2008-2019 pydicom authors. See LICENSE file for details.
import json

import pytest

from pydicom import dcmread
from pydicom.data import get_testdata_file
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom.tag import Tag, BaseTag
from pydicom.valuerep import PersonName


class TestPersonName:
    def test_json_pn_from_file(self):
        with open(get_testdata_file("test_PN.json")) as s:
            ds = Dataset.from_json(s.read())
        assert isinstance(ds[0x00080090].value, PersonName)
        assert isinstance(ds[0x00100010].value, PersonName)
        inner_seq = ds[0x04000561].value[0][0x04000550]
        dataelem = inner_seq[0][0x00100010]
        assert isinstance(dataelem.value, PersonName)

    def test_pn_components_to_json(self):
        def check_name(tag, components):
            # we cannot directly compare the dictionaries, as they are not
            # guaranteed insertion-ordered in Python < 3.7
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
        ds_json = ds.to_json_dict()
        check_name('00100010', ['Yamada^Tarou', u'山田^太郎', u'やまだ^たろう'])
        check_name('00091001', ['Yamada^Tarou'])
        check_name('00091002', ['Yamada^Tarou'])
        check_name('00091003', ['', u'山田^太郎', u'やまだ^たろう'])
        check_name('00091004', ['Yamada^Tarou', '', u'やまだ^たろう'])
        check_name('00091005', ['', '', u'やまだ^たろう'])
        check_name('00091006', ['', u'山田^太郎'])
        check_name('00091007', ['Yamada^Tarou', u'山田^太郎'])

    def test_pn_components_from_json(self):
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
        ds_json = ds.to_json_dict()
        assert '00100010' in ds_json
        assert 'Value' not in ds_json['00100010']

    def test_multi_value_to_json(self):
        ds = Dataset()
        patient_names = [u'Buc^Jérôme', u'Διονυσιος', u'Люкceмбypг']
        ds.add_new(0x00091001, 'PN', patient_names)
        ds_json = ds.to_json_dict()
        assert [{'Alphabetic': u'Buc^Jérôme'},
                {'Alphabetic': u'Διονυσιος'},
                {'Alphabetic': u'Люкceмбypг'}] == ds_json['00091001']['Value']

    def test_dataelem_from_json(self):
        tag = 0x0080090
        vr = "PN"
        value = [{"Alphabetic": ""}]
        dataelem = DataElement.from_json(Dataset, tag, vr, value, "Value")
        assert isinstance(dataelem.value, PersonName)


class TestAT:
    def test_to_json(self):
        ds = Dataset()
        ds.add_new(0x00091001, 'AT', [0x00100010, 0x00100020])
        ds.add_new(0x00091002, 'AT', Tag(0x28, 0x02))
        ds.add_new(0x00091003, 'AT', BaseTag(0x00280002))
        ds.add_new(0x00091004, 'AT', [0x00280002, Tag('PatientName')])
        ds_json = ds.to_json_dict()

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

    def test_invalid_value_in_json(self):
        ds_json = ('{"00091001": {"vr": "AT", "Value": ["000910AG"]}, '
                   '"00091002": {"vr": "AT", "Value": ["00100010"]}}')
        with pytest.warns(UserWarning, match='Invalid value "000910AG" for '
                                             'AT element - ignoring it'):
            ds = Dataset.from_json(ds_json)
            assert ds[0x00091001].value is None
            assert 0x00100010 == ds[0x00091002].value

    def test_invalid_tag_in_json(self):
        ds_json = ('{"000910AG": {"vr": "AT", "Value": ["00091000"]}, '
                   '"00091002": {"vr": "AT", "Value": ["00100010"]}}')
        with pytest.raises(ValueError, match='Data element "000910AG" could '
                                             'not be loaded from JSON:'):
            ds = Dataset.from_json(ds_json)
            assert ds[0x00091001].value is None
            assert 0x00100010 == ds[0x00091002].value


class TestDataSetToJson:
    def test_json_from_dicom_file(self):
        ds1 = Dataset(dcmread(get_testdata_file("CT_small.dcm")))
        ds_json = ds1.to_json()
        ds2 = Dataset.from_json(ds_json)
        assert ds1 == ds2

        ds_json = ds1.to_json_dict()
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

        json_string = ds.to_json()
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
        ds2 = Dataset.from_json(json_model)
        assert ds == ds2

        json_model2 = ds.to_json_dict()

        assert json_model == json_model2

    def test_dataset_dumphandler(self):
        ds = Dataset()
        ds.add_new(0x00100010, 'PN', 'Jane^Doe')
        # as the order of the keys is not defined, we have to check both
        assert ds.to_json() in ('{"00100010": {"vr": "PN", "Value": [{'
                                '"Alphabetic": "Jane^Doe"}]}}',
                                '{"00100010": {"Value": [{'
                                '"Alphabetic": "Jane^Doe"}], "vr": "PN"}}')

        assert {
                   "00100010": {
                       "vr": "PN", "Value": [{"Alphabetic": "Jane^Doe"}]}
               } == ds.to_json(dump_handler=lambda d: d)

    def test_dataelement_dumphandler(self):
        element = DataElement(0x00100010, 'PN', 'Jane^Doe')
        # as the order of the keys is not defined, we have to check both
        assert element.to_json() in ('{"vr": "PN", "Value": [{'
                                     '"Alphabetic": "Jane^Doe"}]}',
                                     '{"Value": [{'
                                     '"Alphabetic": "Jane^Doe"}], "vr": "PN"}')

        assert {
                   "vr": "PN", "Value": [{"Alphabetic": "Jane^Doe"}]
               } == element.to_json(dump_handler=lambda d: d)

    def test_sort_order(self):
        """Test that tags are serialized in ascending order."""
        ds = Dataset()
        ds.add_new(0x00100040, 'CS', 'F')
        ds.add_new(0x00100030, 'DA', '20000101')
        ds.add_new(0x00100020, 'LO', '0017')
        ds.add_new(0x00100010, 'PN', 'Jane^Doe')

        ds_json = ds.to_json()
        assert ds_json.index('"00100010"') < ds_json.index('"00100020"')
        assert ds_json.index('"00100020"') < ds_json.index('"00100030"')
        assert ds_json.index('"00100030"') < ds_json.index('"00100040"')


class TestSequence:
    def test_nested_sequences(self):
        test1_json = get_testdata_file("test1.json")
        with open(test1_json) as f:
            with pytest.warns(UserWarning,
                              match='no bulk data URI handler provided '):
                ds = Dataset.from_json(f.read())
            del ds.PixelData
        ds2 = Dataset.from_json(ds.to_json())
        assert ds == ds2


class TestBinary:
    def test_inline_binary(self):
        ds = Dataset()
        ds.add_new(0x00091002, 'OB', b'BinaryContent')
        ds_json = ds.to_json_dict()
        assert "00091002" in ds_json
        assert "QmluYXJ5Q29udGVudA==" == ds_json["00091002"]["InlineBinary"]
        ds1 = Dataset.from_json(ds_json)
        assert ds == ds1
        # also test if the binary is enclosed in a list
        ds_json["00091002"]["InlineBinary"] = ["QmluYXJ5Q29udGVudA=="]
        ds1 = Dataset.from_json(ds_json)
        assert ds == ds1

    def test_invalid_inline_binary(self):
        msg = ('"InlineBinary" of data element "00091002" '
               'must be a bytes-like object.')
        ds_json = '{"00091002": {"vr": "OB", "InlineBinary": 42}}'
        with pytest.raises(TypeError, match=msg):
            Dataset.from_json(ds_json)

        ds_json = '{"00091002": {"vr": "OB", "InlineBinary": [42]}}'
        with pytest.raises(TypeError, match=msg):
            Dataset.from_json(ds_json)

    def test_valid_bulkdata_uri(self):
        ds_json = ('{"00091002": {"vr": "OB", "BulkDataURI": '
                   '"http://example.com/bulkdatahandler"}}')
        msg = r"no bulk data URI handler provided"
        with pytest.warns(UserWarning, match=msg):
            ds = Dataset.from_json(ds_json)
        assert 0x00091002 in ds

        ds_json = ('{"00091002": {"vr": "OB", "BulkDataURI": '
                   '["http://example.com/bulkdatahandler"]}}')
        with pytest.warns(UserWarning, match=msg):
            ds = Dataset.from_json(ds_json)
        assert 0x00091002 in ds

    def test_invalid_bulkdata_uri(self):
        msg = ('"BulkDataURI" of data element "00091002" '
               'must be a string.')
        ds_json = '{"00091002": {"vr": "OB", "BulkDataURI": 42}}'
        with pytest.raises(TypeError, match=msg):
            Dataset.from_json(ds_json)

        ds_json = '{"00091002": {"vr": "OB", "BulkDataURI": [42]}}'
        with pytest.raises(TypeError, match=msg):
            Dataset.from_json(ds_json)

    def test_bulk_data_reader_is_called(self):
        def bulk_data_reader(_):
            return b'xyzzy'

        json_data = {
            "00091002": {"vr": "OB", "BulkDataURI": "https://a.dummy.url"}
        }
        ds = Dataset().from_json(json.dumps(json_data), bulk_data_reader)

        assert b'xyzzy' == ds[0x00091002].value
