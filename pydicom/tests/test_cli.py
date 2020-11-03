# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Tests for command-line interface"""

from argparse import ArgumentTypeError

import pytest

from pydicom.cli.main import filespec_parser

bad_elem_specs = (
    "extra:colon", 
    "no_callable()", 
    "no_equals = ",
    "BeamSequence[0]extra", # must match to end of string
    "BeamSequence[x]", # index must an int
)

missing_elements = (
    "NotThere",
    "BeamSequenceXX",
    "BeamDose" # valid keyword but not at top level
)

bad_indexes = (
    "BeamSequence[42]",
    "BeamSequence[-42]",
)

class TestFileSpec:
    @pytest.mark.parametrize('bad_spec', bad_elem_specs)
    def test_syntax(self, bad_spec):
        """Invalid syntax for for CLI file:element spec raises error"""
        with pytest.raises(ArgumentTypeError, match=r".* syntax .*"):
            filespec_parser(f"rtplan.dcm:{bad_spec}")
    
    @pytest.mark.parametrize('missing_element', missing_elements)
    def test_elem_not_exists(self, missing_element):
        """CLI filespec elements not in the dataset raise an error"""
        with pytest.raises(ArgumentTypeError, match=r".* is not in the dataset"):
            filespec_parser(f"rtplan.dcm:{missing_element}")
    
    @pytest.mark.parametrize('bad_index', bad_indexes)
    def test_bad_index(self, bad_index):
        """CLI filespec elements with an invalid index raise an error"""
        with pytest.raises(ArgumentTypeError, match=r".* index error"):
            filespec_parser(f"rtplan.dcm:{bad_index}")