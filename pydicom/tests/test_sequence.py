# test_sequence.py
"""unittest cases for Sequence class"""
# Copyright (c) 2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at https://github.com/darcymason/pydicom

import unittest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence


class SequenceTests(unittest.TestCase):
    def testDefaultInitialization(self):
        """Sequence: Ensure a valid Sequence is created"""
        empty = Sequence()
        self.assertTrue(len(empty) == 0, "Non-empty Sequence created")

    def testValidInitialization(self):
        """Sequence: Ensure valid creation of Sequences using Dataset inputs"""
        inputs = {'PatientPosition': 'HFS',
                  'PatientSetupNumber': '1',
                  'SetupTechniqueDescription': ''}
        patientSetups = Dataset()
        patientSetups.update(inputs)

        # Construct the sequence
        seq = Sequence((patientSetups,))
        self.assertTrue(isinstance(seq[0], Dataset),
                        "Dataset modified during Sequence creation")

    def testInvalidInitialization(self):
        """Sequence: Raise error if inputs are not iterables or Datasets"""
        # Error on construction with single Dataset
        self.assertRaises(TypeError, Sequence, Dataset())
        # Test for non-iterable
        self.assertRaises(TypeError, Sequence, 1)
        # Test for invalid iterable contents
        self.assertRaises(TypeError, Sequence, [1, 2])

    def testInvalidAssignment(self):
        """Sequence: validate exception for invalid assignment"""
        seq = Sequence([Dataset(), ])
        # Attempt to assign an integer to the first element
        self.assertRaises(TypeError, seq.__setitem__, 0, 1)

    def testValidAssignment(self):
        """Sequence: ensure ability to assign a Dataset to a Sequence item"""
        ds = Dataset()
        ds.add_new((1, 1), 'IS', 1)

        # Create a single element Sequence first
        seq = Sequence([Dataset(), ])
        seq[0] = ds

        self.assertEqual(seq[0], ds, "Dataset modified during assignment")


if __name__ == "__main__":
    unittest.main()
