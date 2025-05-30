# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Tests for command-line interface"""

from argparse import ArgumentTypeError

import pytest

from pydicom.cli.main import filespec_parser, eval_element, main, filespec_parts


bad_elem_specs = (
    "extra:colon",
    "no_callable()",
    "no_equals = ",
    "BeamSequence[0]extra",  # must match to end of string
    "(300a,00b0)[0]extra",  # as above
    "BeamSequence[x]",  # index must be an int
    "(0010,0010b)",  # bad tag format
    "(0010, 0010)",  # space in tag
    "(0010,  0010)",  # spaces in tag
    "BeamSequence[0].(10,10)",  # nested bad tag format
)

not_dicom_keywords = (
    "NotThere",
    "BeamSequenceXX",
)

not_in_parent = ("BeamDose",)  # valid keyword but not at top level

bad_indexes = (
    "BeamSequence[42]",
    "BeamSequence[-42]",
)


class TestFilespec:
    @pytest.mark.parametrize("bad_spec", bad_elem_specs)
    def test_syntax(self, bad_spec):
        """Invalid syntax for CLI file:element spec raises error"""
        match = r".* syntax .*"
        if ", " in bad_spec:
            match += "tag: no spaces allowed"
        with pytest.raises(ArgumentTypeError, match=match):
            filespec_parser(f"pydicom::rtplan.dcm::{bad_spec}")

    @pytest.mark.parametrize("missing_element", not_dicom_keywords)
    def test_elem_not_keyword(self, missing_element):
        """CLI filespec elements not in the dataset raise an error"""
        with pytest.raises(
            ArgumentTypeError,
            match=r".*not a known DICOM keyword, tag or allowed class property",
        ):
            filespec_parser(f"pydicom::rtplan.dcm::{missing_element}")

    @pytest.mark.parametrize("missing_element", not_in_parent)
    def test_elem_not_in_parent(self, missing_element):
        """CLI filespec elements not in the dataset raise an error"""
        with pytest.raises(ArgumentTypeError, match=r".*not in the parent object"):
            filespec_parser(f"pydicom::rtplan.dcm::{missing_element}")

    @pytest.mark.parametrize("bad_index", bad_indexes)
    def test_bad_index(self, bad_index):
        """CLI filespec elements with an invalid index raise an error"""
        with pytest.raises(ArgumentTypeError, match=r".*index error"):
            filespec_parser(f"pydicom::rtplan.dcm::{bad_index}")

    def test_offers_pydicom_testfile(self):
        """CLI message offers pydicom data file if file not found"""
        with pytest.raises(
            ArgumentTypeError, match=r".*pydicom::rtplan\.dcm.*is available.*"
        ):
            filespec_parser("rtplan.dcm")

    def test_colons(self):
        """CLI filespec with a colon in filename works correctly"""
        expected = ("", r"c:\test.dcm", "")
        assert expected == filespec_parts(r"c:\test.dcm")

        expected = ("pydicom", r"c:\test.dcm", "")
        assert expected == filespec_parts(r"pydicom::c:\test.dcm")

        filespec = r"pydicom::c:\test.dcm::StudyDate"
        expected = ("pydicom", r"c:\test.dcm", "StudyDate")
        assert expected == filespec_parts(filespec)

        filespec = r"c:\test.dcm::StudyDate"
        expected = ("", r"c:\test.dcm", "StudyDate")
        assert expected == filespec_parts(filespec)


class TestFilespecElementEval:
    # Load plan once
    plan, _ = filespec_parser("pydicom::rtplan.dcm")[0]

    # Test basic correct data elements
    @pytest.mark.parametrize(
        "elem_str, expected",
        (
            ("BeamSequence[0].ControlPointSequence[0].NominalBeamEnergy", 6.0),
            ("PatientID", "id00001"),
            ("(0010,0020)", "id00001"),
            ("file_meta.TransferSyntaxUID.name", "Implicit VR Little Endian"),
            ("PatientName.family_name", "Last"),
        ),
    )
    def test_correct_data_elements(self, elem_str, expected):
        """CLI produces correct evaluation of requested element"""
        assert eval_element(self.plan, elem_str) == expected

    # Test data elements in sequence items
    @pytest.mark.parametrize(
        "elem_str, expected",
        (
            ("BeamSequence[0].ControlPointSequence[0]", 6.0),
            ("(300A,00B0)[0].ControlPointSequence[0]", 6.0),
            ("(300a,00b0)[0].(300a,0111)[0]", 6.0),
        ),
    )
    def test_data_elem_from_sequence_item(self, elem_str, expected):
        elem_val = eval_element(self.plan, elem_str)
        assert elem_val.NominalBeamEnergy == expected

    def test_nested_sequence(self):
        elem_val = eval_element(self.plan, "BeamSequence[0].ControlPointSequence")
        assert 6.0 == elem_val[0].NominalBeamEnergy

    def test_file_meta_or_meta_element(self):
        elem_val = eval_element(self.plan, "file_meta")
        assert "RT Plan Storage" == elem_val.MediaStorageSOPClassUID.name

        elem_val = eval_element(self.plan, "file_meta.MediaStorageSOPClassUID")
        assert "RT Plan Storage" == elem_val.name


class TestCLIcall:
    """Test calls to `pydicom` command-line interface"""

    def test_bare_command(self, capsys):
        """CLI `pydicom` with no arguments displays help"""
        main([])
        out, _ = capsys.readouterr()
        assert out.startswith("usage: pydicom [-h] {")

    def test_codify_command(self, capsys):
        """CLI `codify` command prints correct output"""

        # With private elements
        main("codify -p pydicom::nested_priv_SQ.dcm".split())
        out, _ = capsys.readouterr()
        assert "add_new((0x0001, 0x0001)" in out

        # Without private elements
        main("codify pydicom::nested_priv_SQ.dcm".split())
        out, _ = capsys.readouterr()
        assert "add_new((0x0001, 0x0001)" not in out

    def test_codify_data_element(self, capsys):
        """CLI `codify` command raises error if not a Dataset"""
        with pytest.raises(NotImplementedError):
            main("codify pydicom::rtplan.dcm::RTPlanLabel".split())

    def test_codify_UTF8(self, capsys):
        """CLI `codify` command creates code with utf-8 characters"""
        main("codify pydicom::chrFren.dcm".split())
        out, _ = capsys.readouterr()
        assert out.startswith("# -*- coding: utf-8 -*-")
        assert "Buc^Jérôme" in out

    def test_help(self, capsys):
        """CLI `help` command gives expected output"""
        # With subcommand
        main("help show".split())
        out, err = capsys.readouterr()
        assert out.startswith("usage: pydicom show [-h] [")
        assert err == ""

        # No subcommand following
        main(["help"])
        out, _ = capsys.readouterr()
        assert "Available subcommands:" in out

        # Non-existent subcommand following
        main("help DoesntExist".split())
        out, _ = capsys.readouterr()
        assert "Available subcommands:" in out

    def test_show_command(self, capsys):
        """CLI `show` command prints correct output"""
        main("show pydicom::MR_small_RLE.dcm".split())
        out, err = capsys.readouterr()

        assert "Instance Creation Date              DA: '20040826'" in out
        assert out.endswith("OB: Array of 126 elements\n")
        assert err == ""

        # Get a specific data element
        main("show pydicom::MR_small_RLE.dcm::LargestImagePixelValue".split())
        out, _ = capsys.readouterr()
        assert "4000" == out.strip()

    def test_show_options(self, capsys):
        """CLI `show` command with options prints correct output"""
        # Quiet option, image file
        main("show -q pydicom::MR_small_RLE.dcm".split())
        out, err = capsys.readouterr()

        assert out.startswith("SOPClassUID: MR Image Storage")
        assert out.endswith("Rows: 64\nColumns: 64\nSliceLocation: 0.0000\n")
        assert err == ""

        # 'Quiet' option, RTPLAN file
        main("show -q pydicom::rtplan.dcm".split())
        out, err = capsys.readouterr()
        assert out.endswith(
            "Beam 1 'Field 1' TREATMENT STATIC PHOTON energy 6.00000000000000 "
            "gantry 0.0, coll 0.0, couch 0.0 "
            "(0 wedges, 0 comps, 0 boli, 0 blocks)\n"
        )
        assert err == ""

        # Top-level-only option, also different file for more variety
        main("show -t pydicom::nested_priv_SQ.dcm".split())
        out, err = capsys.readouterr()
        assert "(0001,0001)  Private Creator" in out
        assert "UN: b'Nested SQ'" not in out
        assert err == ""

        # Exclude private option
        main("show -x pydicom::nested_priv_SQ.dcm".split())
        out, err = capsys.readouterr()
        assert "(0001,0001)  Private Creator" not in out
        assert err == ""
