import pytest
from pydicom.dataset import Dataset, FileMetaDataset, validate_file_meta
from pydicom.uid import (
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,
    PYDICOM_IMPLEMENTATION_UID,
)


class TestFileMetaDataset1(object):
    """Test valid file meta behavior"""

    def setup(self):
        self.ds = Dataset()
        self.meta = FileMetaDataset()
        self.ds.file_meta = self.meta
        self.meta.ImplementationVersionName = "Implem"

    def test_group2_only(self):
        """FileMetaDataset class allows only group 2 tags"""
        # Group !=2 raises exception
        with pytest.raises(KeyError):
            self.meta.PatientName = "test"

        with pytest.raises(KeyError):
            self.meta.add_new(0x30001, "OB", "test")

        # But group 2 is allowed
        self.meta.ImplementationVersionName = "abc"
        self.meta.add_new(0x20016, "AE", "ae")

    def test_file_meta_binding(self):
        """File_meta reference remains bound in parent Dataset"""
        # Test exists to show new FileMetaDataset still
        #   allows old-style, does not get re-bound to new FileMetaDataset
        # This ensures old code using file_meta = Dataset() will still work
        assert self.ds.file_meta.ImplementationVersionName == "Implem"

    def test_access_file_meta_from_parent(self):
        """Accessing group2 tag in dataset gets from file_meta if exists"""
        # direct from ds, not through ds.file_meta
        assert self.ds.ImplementationVersionName == "Implem"
        assert self.ds[0x00020013].value == "Implem"

    def test_assign_file_meta_existing_tags(self):
        """Dataset raises if assigning file_meta with tags already in dataset"""
        # New in v1.4
        # Note: not using self.ds etc.
        meta = FileMetaDataset()
        ds = Dataset()

        # store element in main dataset, no file_meta for it
        ds.ImplementationVersionName = "already here"

        # Now also in meta
        meta.ImplementationVersionName = "new one"

        # conflict raises
        with pytest.raises(KeyError):
            ds.file_meta = meta

    def test_assign_file_meta_moves_existing_group2(self):
        """Setting file_meta in a dataset moves existing group 2 elements"""
        meta = FileMetaDataset()
        ds = Dataset()

        # Set ds up with some group 2
        ds.ImplementationVersionName = "main ds"
        ds.MediaStorageSOPClassUID = "4.5.6"

        # also have something in meta
        meta.TransferSyntaxUID = "1.2.3"

        ds.file_meta = meta
        assert meta.ImplementationVersionName == "main ds"
        assert meta.MediaStorageSOPClassUID == "4.5.6"
        # and existing one unharmed
        assert meta.TransferSyntaxUID == "1.2.3"

        # And elements are no longer in main dataset
        assert "MediaStorageSOPClassUID" not in ds._dict
        assert "ImplementationVersionName" not in ds._dict

    def test_assign_ds_already_in_meta_overwrites(self):
        self.ds.ImplementationVersionName = "last set"
        assert "last set" == self.ds.file_meta.ImplementationVersionName
        assert "last set" == self.ds.ImplementationVersionName

    def test_file_meta_contains(self):
        assert "ImplementationVersionName" in self.ds.file_meta
        assert "ImplementationVersionName" in self.ds

    def test_file_meta_del(self):
        del self.ds.file_meta.ImplementationVersionName
        assert "ImplementationVersionName" not in self.ds    
        assert "ImplementationVersionName" not in self.meta

        self.ds.file_meta.ImplementationVersionName = "Implem2"
        del self.ds.ImplementationVersionName
        assert "ImplementationVersionName" not in self.ds    
        assert "ImplementationVersionName" not in self.ds.file_meta

    def test_dir(self):
        assert "ImplementationVersionName" in self.ds.dir()
        assert "ImplementationVersionName" in self.ds.dir("version")

    def test_eq_with_file_meta(self):
        ds2 = Dataset()
        self.ds.PatientName = "Test"
        ds2.PatientName = "Test"

        # self.ds has file_meta, other does not
        assert not (self.ds == ds2)

        # test with same file meta
        ds2.file_meta = FileMetaDataset()
        ds2.file_meta.ImplementationVersionName = "Implem"
        assert self.ds == ds2

        # change same item in file meta
        ds2.file_meta.ImplementationVersionName = "other"
        assert not (self.ds == ds2)
    
    def test_file_meta_through_data_element(self):
        data_elem = self.ds.data_element("ImplementationVersionName")
        assert data_elem.value == "Implem"

    def test_meta_keys_values_items(self):
        meta2 = FileMetaDataset()
        meta2.ImplementationVersionName = "Implem"
        expected_values = [meta2.data_element("ImplementationVersionName")]
        expected_keys = [(0x0002, 0x0013)]
        expected_items = list(zip(expected_keys, expected_values))
        assert expected_values == list(self.ds.values())
        assert expected_keys == list(self.ds.keys())
        assert expected_items == list(self.ds.items())

        self.ds.PatientName = "test"
        self.ds.PatientID = "123"

        ds2 = Dataset()
        ds2.PatientName = "test"
        ds2.PatientID = "123"
        expected_values.append(ds2.data_element("PatientName"))
        expected_values.append(ds2.data_element("PatientID"))
        assert expected_values == list(self.ds.values())

        expected_keys.extend([0x00100010, 0x00100020])
        assert expected_keys == list(self.ds.keys())

        expected_items = list(zip(expected_keys, expected_values))
        assert expected_items == list(self.ds.items())


class TestFileMetaDataset2(object):
    """Test valid file meta behavior"""

    def setup(self):
        self.ds = Dataset()
        self.sub_ds1 = Dataset()
        self.sub_ds2 = Dataset()

    def test_ensure_file_meta(self):
        assert not hasattr(self.ds, "file_meta")
        self.ds.ensure_file_meta()
        assert hasattr(self.ds, "file_meta")
        assert not self.ds.file_meta

    def test_fix_meta_info(self):
        self.ds.is_little_endian = True
        self.ds.is_implicit_VR = True
        self.ds.fix_meta_info(enforce_standard=False)
        assert ImplicitVRLittleEndian == self.ds.file_meta.TransferSyntaxUID

        self.ds.is_implicit_VR = False
        self.ds.fix_meta_info(enforce_standard=False)
        # transfer syntax does not change because of ambiguity
        assert ImplicitVRLittleEndian == self.ds.file_meta.TransferSyntaxUID

        self.ds.is_little_endian = False
        self.ds.is_implicit_VR = True
        with pytest.raises(NotImplementedError):
            self.ds.fix_meta_info()

        self.ds.is_implicit_VR = False
        self.ds.fix_meta_info(enforce_standard=False)
        assert ExplicitVRBigEndian == self.ds.file_meta.TransferSyntaxUID

        assert "MediaStorageSOPClassUID" not in self.ds.file_meta
        assert "MediaStorageSOPInstanceUID " not in self.ds.file_meta
        with pytest.raises(ValueError, match="Missing required File Meta .*"):
            self.ds.fix_meta_info(enforce_standard=True)

        self.ds.SOPClassUID = "1.2.3"
        self.ds.SOPInstanceUID = "4.5.6"
        self.ds.fix_meta_info(enforce_standard=False)
        assert "1.2.3" == self.ds.file_meta.MediaStorageSOPClassUID
        assert "4.5.6" == self.ds.file_meta.MediaStorageSOPInstanceUID
        self.ds.fix_meta_info(enforce_standard=True)

    def test_validate_and_correct_file_meta(self):
        file_meta = FileMetaDataset()
        validate_file_meta(file_meta, enforce_standard=False)
        with pytest.raises(ValueError):
            validate_file_meta(file_meta, enforce_standard=True)

        file_meta = FileMetaDataset()
        file_meta.MediaStorageSOPClassUID = "1.2.3"
        file_meta.MediaStorageSOPInstanceUID = "1.2.4"
        # still missing TransferSyntaxUID
        with pytest.raises(ValueError):
            validate_file_meta(file_meta, enforce_standard=True)

        file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        validate_file_meta(file_meta, enforce_standard=True)

        # check the default created values
        assert b"\x00\x01" == file_meta.FileMetaInformationVersion
        assert PYDICOM_IMPLEMENTATION_UID == file_meta.ImplementationClassUID
        assert file_meta.ImplementationVersionName.startswith("PYDICOM ")

        file_meta.ImplementationClassUID = "1.2.3.4"
        file_meta.ImplementationVersionName = "ACME LTD"
        validate_file_meta(file_meta, enforce_standard=True)
        # check that existing values are left alone
        assert "1.2.3.4" == file_meta.ImplementationClassUID
        assert "ACME LTD" == file_meta.ImplementationVersionName
