import pytest
from pydicom.dataset import FileMetaDataset

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