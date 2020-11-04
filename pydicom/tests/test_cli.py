# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Tests for command-line interface"""

from argparse import ArgumentTypeError

import pytest

from pydicom.cli.main import filespec_parser, eval_element

bad_elem_specs = (
    "extra:colon",
    "no_callable()",
    "no_equals = ",
    "BeamSequence[0]extra",  # must match to end of string
    "BeamSequence[x]",  # index must an int
)

missing_elements = (
    "NotThere",
    "BeamSequenceXX",
    "BeamDose",  # valid keyword but not at top level
)

bad_indexes = (
    "BeamSequence[42]",
    "BeamSequence[-42]",
)


class TestFileSpec:
    @pytest.mark.parametrize("bad_spec", bad_elem_specs)
    def test_syntax(self, bad_spec):
        """Invalid syntax for for CLI file:element spec raises error"""
        with pytest.raises(ArgumentTypeError, match=r".* syntax .*"):
            filespec_parser(f"rtplan.dcm:{bad_spec}")

    @pytest.mark.parametrize("missing_element", missing_elements)
    def test_elem_not_exists(self, missing_element):
        """CLI filespec elements not in the dataset raise an error"""
        with pytest.raises(
            ArgumentTypeError, match=r".* is not in the dataset"
        ):
            filespec_parser(f"rtplan.dcm:{missing_element}")

    @pytest.mark.parametrize("bad_index", bad_indexes)
    def test_bad_index(self, bad_index):
        """CLI filespec elements with an invalid index raise an error"""
        with pytest.raises(ArgumentTypeError, match=r".* index error"):
            filespec_parser(f"rtplan.dcm:{bad_index}")

class TestFilespecElementEval:
    # Load plan once
    plan, _ = filespec_parser("rtplan.dcm")

    def test_correct_values(self):
        """CLI produces correct evaluation of requested element"""
        # A nested data element 
        elem_str = "BeamSequence[0].ControlPointSequence[0].NominalBeamEnergy"
        elem_val = eval_element(self.plan, elem_str)
        assert 6.0 == elem_val

        # A nested Sequence item
        elem_str = "BeamSequence[0].ControlPointSequence[0]"
        elem_val = eval_element(self.plan, elem_str)
        assert 6.0 == elem_val.NominalBeamEnergy

        # A nested Sequence itself
        elem_str = "BeamSequence[0].ControlPointSequence"
        elem_val = eval_element(self.plan, elem_str)
        assert 6.0 == elem_val[0].NominalBeamEnergy


        # A non-nested data element
        elem_str = "PatientID"
        elem_val = eval_element(self.plan, elem_str)
        assert "id00001" == elem_val

        # The file_meta or file_meta data element
        elem_str = "file_meta"
        elem_val = eval_element(self.plan, elem_str)
        assert "RT Plan Storage" == elem_val.MediaStorageSOPClassUID.name

        elem_str = "file_meta.MediaStorageSOPClassUID"
        elem_val = eval_element(self.plan, elem_str)
        assert "RT Plan Storage" == elem_val.name
        
