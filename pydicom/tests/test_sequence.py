# Copyright 2008-2018 pydicom authors. See LICENSE file for details.
"""Unit tests for the pydicom.sequence module."""

import pytest

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence


class TestSequence(object):
    def testDefaultInitialization(self):
        """Sequence: Ensure a valid Sequence is created"""
        empty = Sequence()
        assert len(empty) == 0

    def testValidInitialization(self):
        """Sequence: Ensure valid creation of Sequences using Dataset inputs"""
        inputs = {'PatientPosition': 'HFS',
                  'PatientSetupNumber': '1',
                  'SetupTechniqueDescription': ''}
        patientSetups = Dataset()
        patientSetups.update(inputs)

        # Construct the sequence
        seq = Sequence((patientSetups,))
        assert isinstance(seq[0], Dataset)

    def testInvalidInitialization(self):
        """Sequence: Raise error if inputs are not iterables or Datasets"""
        # Error on construction with single Dataset
        with pytest.raises(TypeError):
            Sequence(Dataset())
        # Test for non-iterable
        with pytest.raises(TypeError):
            Sequence(1)
        # Test for invalid iterable contents
        with pytest.raises(TypeError):
            Sequence([1, 2])

    def testInvalidAssignment(self):
        """Sequence: validate exception for invalid assignment"""
        seq = Sequence([Dataset(), ])
        # Attempt to assign an integer to the first element
        with pytest.raises(TypeError):
            seq.__setitem__(0, 1)

    def testValidAssignment(self):
        """Sequence: ensure ability to assign a Dataset to a Sequence item"""
        ds = Dataset()
        ds.add_new((1, 1), 'IS', 1)

        # Create a single element Sequence first
        seq = Sequence([Dataset(), ])
        seq[0] = ds

        assert seq[0] == ds

    def test_str(self):
        """Test string output of the sequence"""
        ds = Dataset()
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].PatientName = 'TEST'
        ds.BeamSequence[0].PatientID = '12345'

        out = str(ds.BeamSequence)
        assert "[(0010, 0010) Patient's Name" in out
        assert "PN: 'TEST'" in out
        assert "(0010, 0020) Patient ID" in out
        assert "LO: '12345']" in out
