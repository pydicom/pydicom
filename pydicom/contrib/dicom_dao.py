#!/usr/bin/python

""" dicom_dao

Data Access Objects for persisting PyDicom DataSet objects.

Currently we support couchdb through the DicomCouch class.

Limitations:
 - Private tags are discarded

TODO:
 - Unit tests with multiple objects open at a time
 - Unit tests with rtstruct objects
 - Support for mongodb (mongo has more direct support for binary data)

Dependencies:
 - PyDicom
 - python-couchdb

Tested with:
 - PyDicom 0.9.4-1
 - python-couchdb 0.6
 - couchdb 0.10.1

"""
#
# Copyright (c) 2010 Michael Wallace
# This file is released under the pydicom license.
#    See the file license.txt included with the pydicom distribution, also
#    available at http://pydicom.googlecode.com
#

import hashlib
import os
import string
import couchdb
import dicom


def uid2str(uid):
    """ Convert PyDicom uid to a string """
    return repr(uid).strip("'")

# When reading files a VR of 'US or SS' is left as binary, because we
# don't know how to interpret the values different numbers. We therefore
# treat it as binary and will continue to until either pydicom works it out
# for us, or we figure out a test.
BINARY_VR_VALUES = ['OW', 'OB', 'OW/OB', 'US or SS']


class DicomCouch(dict):
    """ A Data Access Object for persisting PyDicom objects into CouchDB

    We follow the same pattern as the python-couchdb library for getting and
    setting documents, for example storing dicom.dataset.Dataset object dcm:
        db = DicomCouch('http://localhost:5984/', 'dbname')
        db[dcm.SeriesInstanceUID] = dcm

    The only constraints on the key are that it must be json-serializable and
    unique within the database instance. In theory it should be possible to
    use any DICOM UID. Unfortunately I have written this code under the
    assumption that SeriesInstanceUID will always be used. This will be fixed.

    Retrieving object with key 'foo':
        dcm = db['foo']

    Deleting object with key 'foo':
        dcm = db['foo']
        db.delete(dcm)

    TODO:
     - It is possible to have couchdb assign a uid when adding objects. This
       should be supported.
    """

    def __init__(self, server, db):
        """ Create connection to couchdb server/db """
        super(DicomCouch, self).__init__()
        self._meta = {}
        server = couchdb.Server(server)
        try:
            self._db = server[db]
        except couchdb.client.ResourceNotFound:
            self._db = server.create(db)

    def __getitem__(self, key):
        """ Retrieve DICOM object with specified SeriesInstanceUID """
        doc = self._db[key]
        dcm = json2pydicom(doc)

        if dcm.SeriesInstanceUID not in self._meta:
            self._meta[dcm.SeriesInstanceUID] = {}
            self._meta[dcm.SeriesInstanceUID]['hashes'] = {}

        if '_attachments' in doc:
            self.__get_attachments(dcm, doc)
        _set_meta_info_dcm(dcm)
        # Keep a copy of the couch doc for use in DELETE operations
        self._meta[dcm.SeriesInstanceUID]['doc'] = doc
        return dcm

    def __setitem__(self, key, dcm):
        """ Write the supplied DICOM object to the database """
        try:
            dcm.PixelData = dcm.pixel_array.tostring()
        except AttributeError:
            pass  # Silently ignore errors due to pixel_array not existing
        except NotImplementedError:
            pass  # Silently ignore attempts to modify compressed pixel data
        except TypeError:
            pass  # Silently ignore errors due to PixelData not existing

        jsn, binary_elements, file_meta_binary_elements = pydicom2json(dcm)
        _strip_elements(jsn, binary_elements)
        _strip_elements(jsn['file_meta'], file_meta_binary_elements)
        if dcm.SeriesInstanceUID in self._meta:
            self.__set_meta_info_jsn(jsn, dcm)

        try:  # Actually write to the db
            self._db[key] = jsn
        except TypeError as type_error:
            if str(type_error) == 'string indices must be integers, not str':
                pass

        if dcm.SeriesInstanceUID not in self._meta:
            self._meta[dcm.SeriesInstanceUID] = {}
            self._meta[dcm.SeriesInstanceUID]['hashes'] = {}

        self.__put_attachments(dcm, binary_elements, jsn)
        # Get a local copy of the document
        # We get this from couch because we get the _id, _rev and _attachments
        # keys which will ensure we don't overwrite the attachments we just
        # uploaded.
        # I don't really like the extra HTTP GET and I think we can generate
        # what we need without doing it. Don't have time to work out how yet.
        self._meta[dcm.SeriesInstanceUID]['doc'] = \
            self._db[dcm.SeriesInstanceUID]

    def __str__(self):
        """ Return the string representation of the couchdb client """
        return str(self._db)

    def __repr__(self):
        """ Return the canonical string representation of the couchdb client """
        return repr(self._db)

    def __get_attachments(self, dcm, doc):
        """ Set binary tags by retrieving attachments from couchdb.

        Values are hashed so they are only updated if they have changed.

        """
        for id in doc['_attachments'].keys():
            tagstack = id.split(':')
            value = self._db.get_attachment(doc['_id'], id)
            _add_element(dcm, tagstack, value)
            self._meta[dcm.SeriesInstanceUID]['hashes'][id] = hashlib.md5(value)

    def __put_attachments(self, dcm, binary_elements, jsn):
        """ Upload all new and modified attachments """
        elements_to_update = \
            [(tagstack, item)
             for tagstack, item in binary_elements
             if self.__attachment_update_needed(dcm,
                                                _tagstack2id(tagstack + [item.tag]), item)
            ]  # nopep8
        for tagstack, element in elements_to_update:
            id = _tagstack2id(tagstack + [element.tag])
            self._db.put_attachment(jsn, element.value, id)
            self._meta[dcm.SeriesInstanceUID]['hashes'][id] = \
                hashlib.md5(element.value)

    def delete(self, dcm):
        """ Delete from database and remove meta info from the DAO """
        self._db.delete(self._meta[dcm.SeriesInstanceUID]['doc'])
        self._meta.pop(dcm.SeriesInstanceUID)

    def __set_meta_info_jsn(self, jsn, dcm):
        """ Set the couch-specific meta data for supplied dict """
        jsn['_rev'] = self._meta[dcm.SeriesInstanceUID]['doc']['_rev']
        if '_attachments' in self._meta[dcm.SeriesInstanceUID]['doc']:
            jsn['_attachments'] = \
                self._meta[dcm.SeriesInstanceUID]['doc']['_attachments']

    def __attachment_update_needed(self, dcm, id, binary_element):
        """ Compare hashes for binary element and return true if different """
        try:
            hashes = self._meta[dcm.SeriesInstanceUID]['hashes']
        except KeyError:
            return True  # If no hashes dict then attachments do not exist

        if id not in hashes or hashes[id].digest() != \
                hashlib.md5(binary_element.value).digest():
            return True
        else:
            return False


def _add_element(dcm, tagstack, value):
    """ Add element with tag, vr and value to dcm at location tagstack """
    current_node = dcm
    for item in tagstack[:-1]:
        try:
            address = int(item)
        except ValueError:
            address = dicom.tag.Tag(__str2tag(item))
        current_node = current_node[address]
    tag = __str2tag(tagstack[-1])
    vr = dicom.datadict.dictionaryVR(tag)
    current_node[tag] = dicom.dataelem.DataElement(tag, vr, value)


def _tagstack2id(tagstack):
    """ Convert a list of tags to a unique (within document) attachment id """
    return string.join([str(tag) for tag in tagstack], ':')


def _strip_elements(jsn, elements):
    """ Remove supplied elements from the dict object

    We use this with a list of binary elements so that we don't store
    empty tags in couchdb when we are already storing the binary data as
    attachments.

    """
    for tagstack, element in elements:
        if len(tagstack) == 0:
            jsn.pop(element.tag)
        else:
            current_node = jsn
            for tag in tagstack:
                current_node = current_node[tag]
            current_node.pop(element.tag)


def _set_meta_info_dcm(dcm):
    """ Set the file metadata DataSet attributes

    This is done by PyDicom when we dicom.read_file(foo) but we need to do it
    ourselves when creating a DataSet from scratch, otherwise we cannot use
    foo.pixel_array or dicom.write_file(foo).

    This code is lifted from PyDicom.

    """
    TransferSyntax = dcm.file_meta.TransferSyntaxUID
    if TransferSyntax == dicom.UID.ExplicitVRLittleEndian:
        dcm.is_implicit_vr = False
        dcm.is_little_endian = True  # This line not in PyDicom
    elif TransferSyntax == dicom.UID.ImplicitVRLittleEndian:
        dcm.is_implicit_vr = True
        dcm.is_little_endian = True
    elif TransferSyntax == dicom.UID.ExplicitVRBigEndian:
        dcm.is_implicit_vr = False
        dcm.is_little_endian = False
    elif TransferSyntax == dicom.UID.DeflatedExplicitVRLittleEndian:
        dcm.is_implicit_vr = False   # Deleted lines above as it relates
        dcm.is_little_endian = True  # to reading compressed file data.
    else:
        # Any other syntax should be Explicit VR Little Endian,
        #   e.g. all Encapsulated (JPEG etc) are ExplVR-LE by
        #   Standard PS 3.5-2008 A.4 (p63)
        dcm.is_implicit_vr = False
        dcm.is_little_endian = True


def pydicom2json(dcm):
    """ Convert the supplied PyDicom object into a json-serializable dict

    Binary elements cannot be represented in json so we return these as
    as separate list of the tuple (tagstack, element), where:
     - element  = dicom.dataelem.DataElement
     - tagstack = list of tags/sequence IDs that address the element

    The tagstack variable means we know the absolute address of each binary
    element. We then use this as the attachment id in couchdb - when we
    retrieve the attachment we can then insert it at the appropriate point in
    the tree.

    """
    dcm.remove_private_tags()  # No support for now
    dcm.decode()               # Convert to unicode
    binary_elements = []
    tagstack = []
    jsn = dict((key, __jsonify(dcm[key], binary_elements, tagstack))
               for key in dcm.keys())
    file_meta_binary_elements = []
    jsn['file_meta'] = dict((key, __jsonify(dcm.file_meta[key],
                            file_meta_binary_elements, tagstack))
                            for key in dcm.file_meta.keys())
    return jsn, binary_elements, file_meta_binary_elements


def __jsonify(element, binary_elements, tagstack):
    """ Convert key, value to json-serializable types

    Recursive, so if value is key/value pairs then all children will get
    converted

    """
    value = element.value
    if element.VR in BINARY_VR_VALUES:
        binary_elements.append((tagstack[:], element))
        return ''
    elif type(value) == list:
        new_list = [__typemap(listvalue) for listvalue in value]
        return new_list
    elif type(value) == dicom.sequence.Sequence:
        tagstack.append(element.tag)
        nested_data = []
        for i in range(0, len(value)):
            tagstack.append(i)
            nested_data.append(dict(
                (subkey, __jsonify(value[i][subkey], binary_elements, tagstack))
                for subkey in value[i].keys()))
            tagstack.pop()
        tagstack.pop()
        return nested_data
    else:
        return __typemap(value)


def __typemap(value):
    """ Map PyDicom types that won't serialise to JSON types """
    if type(value) == dicom.UID.UID:
        return uid2str(value)
    elif isinstance(value, dicom.tag.BaseTag):
        return long(value)
    else:
        return value


def json2pydicom(jsn):
    """ Convert the supplied json dict into a PyDicom object """
    dataset = dicom.dataset.Dataset()
    # Don't try to convert couch specific tags
    dicom_keys = [key for key in jsn.keys()
                  if key not in ['_rev', '_id', '_attachments', 'file_meta']]
    for key in dicom_keys:
        dataset.add(__dicomify(key, jsn[key]))
    file_meta = dicom.dataset.Dataset()
    for key in jsn['file_meta']:
        file_meta.add(__dicomify(key, jsn['file_meta'][key]))
    dataset.file_meta = file_meta
    return dataset


def __dicomify(key, value):
    """ Convert a json key, value to a PyDicom DataElement """
    tag = __str2tag(key)
    if tag.element == 0:  # 0 tag implies group length (filreader.py pydicom)
        vr = 'UL'
    else:
        vr = dicom.datadict.dictionaryVR(tag)

    if vr == 'OW/OB':  # Always write pixel data as bytes
        vr = 'OB'      # rather than words

    if vr == 'US or SS':    # US or SS is up to us as the data is already
        if value < 0:       # decoded. We therefore choose US, unless we
            vr = 'SS'       # need a signed value.
        else:
            vr = 'US'

    if vr == 'SQ':  # We have a sequence of datasets, so we recurse
        seq_list = [__make_dataset([__dicomify(subkey, listvalue[subkey])
                                    for subkey in listvalue.keys()])
                    for listvalue in value
                    ]
        seq = dicom.sequence.Sequence(seq_list)
        return dicom.dataelem.DataElement(tag, vr, seq)
    else:
        return dicom.dataelem.DataElement(tag, vr, value)


def __make_dataset(data_elements):
    """ Create a Dataset from a list of DataElement objects """
    dataset = dicom.dataset.Dataset()
    for element in data_elements:
        dataset.add(element)
    return dataset


def __str2tag(key):
    """ Convert string representation of a tag into a Tag """
    return dicom.tag.Tag((int(key[1:5], 16), int(key[7:-1], 16)))


if __name__ == '__main__':
    TESTDB = 'dicom_test'
    SERVER = 'http://127.0.0.1:5984'
    # Delete test database if it already exists
    couch = couchdb.Server(SERVER)
    try:
        couch.delete(TESTDB)
    except couchdb.client.ResourceNotFound:
        pass  # Don't worry if it didn't exist

    db = DicomCouch(SERVER, TESTDB)

    testfiles_dir = '../testfiles'
    testfiles = os.listdir('../testfiles')
    testfiles = filter(lambda x: x.endswith('dcm'), testfiles)
    testfiles = map(lambda x: os.path.join('../testfiles', x), testfiles)

    for dcmfile in testfiles:
        dcm = dicom.read_file(dcmfile)
        db[dcm.SeriesInstanceUID] = dcm
