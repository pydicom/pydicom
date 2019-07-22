import pytest
from pydicom.dataset import Dataset, FileMetaDataset


def test_group2_only():
    """FileMetaDataset class allows only group 2 tags"""
    meta = FileMetaDataset()

    # Group !=2 raises exception
    with pytest.raises(KeyError):
        meta.PatientName = "test"

    with pytest.raises(KeyError):
        meta.add_new(0x30001, "OB", "test")

    # But group 2 is allowed
    meta.ImplementationVersionName = "abc"
    meta.add_new(0x20016, "AE", "ae")


def test_file_meta_binding():
    """File_meta reference remains bound in parent Dataset"""
    # Test exists to show new FileMetaDataset still
    #   allows old-style, does not get re-bound to new FileMetaDataset
    # This ensures old code using file_meta = Dataset() will still work
    ds = Dataset()
    meta = Dataset()  # old style
    ds.file_meta = meta
    meta.ImplementationVersionName = "implem"
    assert ds.file_meta.ImplementationVersionName == "implem"


def test_access_file_meta_from_parent():
    """Accessing group2 tag in dataset gets from file_meta if exists"""
    # New in v1.4
    ds = Dataset()
    meta = Dataset()
    ds.file_meta = meta
    meta.ImplementationVersionName = "abc"

    # direct from ds, not through ds.file_meta
    assert ds.ImplementationVersionName == "abc"
    assert ds[0x00020013].value == "abc"


def test_assign_file_meta_existing_tags():
    """Dataset raises if assigning file_meta with tags already in dataset"""
    # New in v1.4
    meta = FileMetaDataset()
    ds = Dataset()

    # store element in main dataset, no file_meta for it
    ds.ImplementationVersionName = "already here"

    # Now also in meta
    meta.ImplementationVersionName = "new one"

    # conflict raises
    with pytest.raises(KeyError):
        ds.file_meta = meta


def test_assign_file_meta_moves_existing_group2():
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
    assert 'MediaStorageSOPClassUID' not in ds
    assert 'ImplementationVersionName' not in ds
