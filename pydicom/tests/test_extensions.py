# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Test for encaps.py"""

import pytest

from pydicom.tag import Tag
from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement
from pydicom.extensions import handle_dataset_tags


@handle_dataset_tags(["ImagePositionPatient", "PatientName"])
class MyHandler:
    def __init__(self, dataset):
        self.ds = dataset

    def get_item(self, tag):
        """Return the data element instance"""
        if tag.keyword == "ImagePositionPatient":
            x, y, z = self.ds.ImagePositionPatient
            # This one updates underlying dataset
            self.ds.ImagePositionPatient = [x + 1, y + 1, z + 1]
            return self.ds["ImagePositionPatient"]
        elif tag.keyword == "PatientName":
            # This one leaves underlying dataset alone
            return DataElement(tag, "PN", "anonymous")
        else:
            NotImplementedError("handled tag without code to deal with it")


class TestDatasetExtension(object):
    """Test handlers which extend Dataset"""
    def setup(self):
        self.ds = Dataset()
        self.ds.PatientName = "Patient^Joe"
        self.ds.ImagePositionPatient = [0.0, 0.0, 0.0]
        self.ds.PatientID = "123"

    def test_get_item(self):
        """Test handler handles specified tags when retrieved by tag."""
        assert [1.0, 1.0, 1.0] == self.ds["ImagePositionPatient"].value
        assert "anonymous" == self.ds["PatientName"].value
        # Check that one we haven't changed is okay
        assert "123" == self.ds["PatientID"].value
