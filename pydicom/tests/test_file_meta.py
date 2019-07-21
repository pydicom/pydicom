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
    ds = Dataset()
    meta = Dataset()
    ds.file_meta = meta
    meta.ImplementationVersionName = "abc"
    
    # direct from ds, not through ds.file_meta
    assert ds.ImplementationVersionName == "abc"
    assert ds[0x00020013].value == "abc"