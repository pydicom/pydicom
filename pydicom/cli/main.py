# Copyright 2020 pydicom authors. See LICENSE file for details.
"""Pydicom command line interface program

Each subcommand is a module within pydicom.cli, which
defines an add_subparser(subparsers) function to set argparse
attributes, and does a  set_defaults(func=callback_function)

"""

import argparse
import sys
import pkg_resources
import re

from pydicom import dcmread
from pydicom.data.data_manager import get_testdata_file

subparsers = None


re_kywd_or_item = (
    r"\w+"  # Keyword  
    r"(\[(-)?\d+\])?"  # Optional [index] or [-index]
)

re_file_spec_object = re.compile(
    re_kywd_or_item + r"(\." + re_kywd_or_item + r")*$"
)

filespec_help = (
    "filename[:subobject]\n"
    "DICOM file and optional data element within it.\n"
    "e.g. rtplan.dcm:BeamSequence[0].BeamNumber"
)


def filespec_parser(filespec: str):
    """Utility to return a dataset and an optional data element value within it

    Note: this is used as an argparse 'type' for adding parsing arguments.

    Parameters
    ----------
    filespec: str
        A filename and optional extra details, in format:
        <filename>[:<element>]
        Filename is mandatory.
        If an element is specified, it must be a path to a data element,
        sequence item (dataset), or a sequence.
        Examples:
            rtplan.dcm:PlanLabel
            rtplan.dcm:BeamSequence[0]
            rtplan.dcm:BeamSequence[0].BeamLimitingDeviceSequence

    Returns
    -------
    ds: Dataset
        The entire dataset read from the file.
    element: Union[Sequence, Dataset, Any]
        The specified data element's value: one of Sequence, Dataset
        (sequence item) or data element value like float, int, str

    Raises
    ------
    argparse.ArgumentTypeError
        If the filename does not exist in local path or in pydicom test files
        If the optional element is not a valid expression
        If the optional element is a valid expression but does not exist
        within the dataset
    """

    splitup = filespec.split(":", 1)
    filename = splitup[0]
    element = splitup[1] if len(splitup) == 2 else ""

    # Check element first to avoid unnecessary load of file
    if element and not re_file_spec_object.match(element):
        raise argparse.ArgumentTypeError(
            f"Component '{element}' is not valid syntax for a "
            "data element, sequence, or sequence item"
        )

    # Read DICOM file
    try:
        ds = dcmread(filename, force=True)
    except FileNotFoundError:
        # Try pydicom's test_files
        test_filepath = get_testdata_file(filename)
        not_found_msg = (
            f"Unable to read file '{filename}' locally "
            "or in pydicom test files"
        )
        if not test_filepath:
            raise argparse.ArgumentTypeError(not_found_msg)
        try:
            ds = dcmread(test_filepath, force=True)
        except Exception as e:
            raise argparse.ArgumentTypeError(
                f"Error reading '{filename}': {str(e)}"
            )

    if not element:
        return ds, None

    try:
        data_elem_val = eval("ds." + element, locals())
    except AttributeError:
        raise argparse.ArgumentTypeError(
            f"Data element '{element}' is not in the dataset"
        )
    except IndexError as e:
        raise argparse.ArgumentTypeError(
            f"'{element}' has an index error: {str(e)}"
        )

    return ds, data_elem_val


def help_command(args):
    subcommands = list(subparsers.choices.keys())
    if args.subcommand and args.subcommand in subcommands:
        subparsers.choices[args.subcommand].print_help()
    else:
        print("Use pydicom help [subcommand] to show help for a subcommand")
        subcommands.remove("help")
        print(f"Available subcommands: {', '.join(subcommands)}")


def get_subcommand_entry_points():
    subcommands = {}
    for entry_point in pkg_resources.iter_entry_points("pydicom_subcommands"):
        subcommands[entry_point.name] = entry_point.load()
    return subcommands


def main(args=None):
    """Entry point for 'pydicom' command line interface

    args: list
        Command-line arguments to parse.  If None, then sys.argv is used
    """
    global subparsers

    parser = argparse.ArgumentParser(
        prog="pydicom", description="pydicom command line utilities"
    )
    subparsers = parser.add_subparsers(help="subcommand help")

    help_parser = subparsers.add_parser(
        "help", help="display help for subcommands"
    )
    help_parser.add_argument(
        "subcommand", nargs="?", help="Subcommand to show help for"
    )
    help_parser.set_defaults(func=help_command)

    # Get subcommands to register themselves as a subparser
    subcommands = get_subcommand_entry_points()
    for subcommand in subcommands.values():
        subcommand(subparsers)

    args = parser.parse_args(args)
    if not len(args.__dict__):
        parser.print_help()
    else:
        args.func(args)
